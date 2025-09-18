import boto3
import logging
import io, base64, json
from jaimee_scraper.settings import CELERY_BROKER_URL
from utils import extract_frames, get_embedding, sync, check_frames_safety, get_s3_obj, update_s3_metadata
from vector_store import VectorStore
from db.models import get_db, CrawledItem
import subprocess

logger = logging.getLogger(__name__)

from celery import Celery
celery_app = Celery("gif_worker", broker=CELERY_BROKER_URL)

@celery_app.task(autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, max_retries=5)
@sync
async def embed_and_store(file_path, source_url, meta_info):
    slug = meta_info.get("slug")
    vec_client  = VectorStore("gif_frames")
    logger.info(f"Embedding and storing frames for slug: {slug}")
    # with open(file_path, "rb") as f:
    #     gif_bytes = f.read()
    try:
        obj = get_s3_obj(file_path)
    except Exception as e:
        logger.error(f"Failed to get S3 object for {file_path}: {e}")
        raise Exception(f"Failed to get S3 object for {file_path}: {e}")

    gif_bytes = obj["Body"].read()
    s3_metadata = {"is_safe": "true"}
    frames = extract_frames(gif_bytes, max_frames=5)
    is_safe, labels, frame_index = check_frames_safety(frames)
    if not is_safe:
        logger.warning(f"GIF {slug} contains unsafe content: {labels}")
        db = next(get_db())
        try:
            s3_metadata["is_safe"] = "false"
            item = db.query(CrawledItem).filter(CrawledItem.slug == slug).first()
            if item:
                item.is_safe = is_safe
                item_labels = item.labels or []
                item.labels = list(set(item_labels + labels))
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update safety status for {slug}: {e}")
            db.rollback()
        finally:
            db.close()
        logger.info(f"GIF {slug} contains unsafe content: {labels} at frame {frame_index}")
    update_s3_metadata(file_path, s3_metadata)
    frame_texts, frame_ids, vectors, metadatas = [], [], [], []
    for i, frame in enumerate(frames):
        frame_id = f"{slug}_f{i}"
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        frame_bytes = buf.getvalue()
        input_image = base64.b64encode(frame_bytes).decode("utf8")

        body = json.dumps(
            {
                "inputImage": input_image,
                "embeddingConfig": {"outputEmbeddingLength": 1024},
            }
        )
        vector = get_embedding(body)

        metadata = {
            "gif_id": slug,
            "title": meta_info.get("title"),
            "slug": slug,
            "frame_index": i,
            "source_url": source_url,
            "file_path": file_path,
        }
        frame_texts.append(meta_info.get("title") + f" ;frame : {i}")
        frame_ids.append(frame_id)
        vectors.append(vector)
        metadatas.append(metadata)
    result = await vec_client.add_embeddings(
        texts=frame_texts,
        ids=frame_ids,
        embeddings=vectors,
        metadatas=metadatas,
    )

    return f"Stored {len(frames)} frames for slug: {slug}"

@celery_app.task
def run_giphy_spider():
    # Adjust the path to your Scrapy project as needed
    result = subprocess.run(
        ["scrapy", "crawl", "giphy"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("Scrapy spider failed:", result.stderr)
    else:
        print("Scrapy spider output:", result.stdout)