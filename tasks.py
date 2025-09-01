import logging
import io, base64, json
from jaimee_scraper.settings import CELERY_BROKER_URL
from utils import extract_frames, get_embedding, sync
from vector_store import VectorStore

logger = logging.getLogger(__name__)

from celery import Celery
celery_app = Celery("gif_worker", broker=CELERY_BROKER_URL)

@celery_app.task
@sync
async def embed_and_store(file_path, source_url, meta_info):
    slug = meta_info.get("slug")
    vec_client  = VectorStore("gif_frames")
    logger.info(f"Embedding and storing frames for slug: {slug}")
    with open(file_path, "rb") as f:
        gif_bytes = f.read()
    frames = extract_frames(gif_bytes, max_frames=5)
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
            "file_path": file_path
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
