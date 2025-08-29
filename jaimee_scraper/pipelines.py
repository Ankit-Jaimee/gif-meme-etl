# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import base64
import io
import json
import os
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings
from langchain_postgres import PGVector
from scrapy import Request
from scrapy.pipelines.files import FilesPipeline
from sqlalchemy.orm import sessionmaker
from jaimee_scraper.settings import DATABASE_URL
from db.models import db_connect, CrawledItem, create_items_table
from utils import extract_frames, get_embedding


load_dotenv()  # Loads variables from .env into environment


class JaimeeScraperPipeline:
    def process_item(self, item, spider):
        return item


class GifPipeline(FilesPipeline):
    def __init__(self, store_uri, download_func=None, settings=None):
        super().__init__(store_uri, download_func, settings)
        connection_string = DATABASE_URL
        self.embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-image-v1", region_name="us-east-1"
        )
        self.vectorstore = PGVector(
            connection=connection_string,
            embeddings=self.embeddings,
            collection_name="gif_frames",
            use_jsonb=True,
        )

    def get_media_requests(self, item, info):
        for url in item.get("image_urls", []):
            yield Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/139.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://giphy.com/",
                },
                meta={"slug": item.get("slug")},
            )

    def file_path(self, request, response=None, info=None, *, item=None):
        slug = request.meta.get("slug", "default")
        ext = os.path.splitext(request.url)[-1]
        return f"{slug}{ext}"

    def file_downloaded(self, response, request, info, *, item=None):
        """After download, run embeddings step"""
        path = super().file_downloaded(response, request, info, item=item)
        gif_bytes = response.body
        frames = extract_frames(gif_bytes, max_frames=5)
        for i, frame in enumerate(frames):
            frame_id = f"{request.meta['slug']}_f{i}"
            buf = io.BytesIO()
            frame.save(buf, format="PNG")
            frame_bytes = buf.getvalue()
            input_image = base64.b64encode(frame_bytes).decode("utf8")
            # Construct the JSON body
            body = json.dumps(
                {
                    "inputImage": input_image,
                    "embeddingConfig": {"outputEmbeddingLength": 1024},
                }
            )
            vector = get_embedding(body)
            metadata = {
                "gif_id": request.meta["slug"],
                "slug": request.meta["slug"],
                "frame_index": i,
                "source_url": response.url,
            }
            self.vectorstore.add_embeddings(
                texts=[frame_id],
                ids=[frame_id],
                embeddings=[vector],
                metadatas=[metadata],
            )
        return path


class DatabasePipeline:
    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        return cls(stats=crawler.stats)

    def open_spider(self, spider):
        """
        Initializes database connection and sessionmaker.
        Creates items table.
        """
        engine = db_connect()
        create_items_table(engine)
        self.Session = sessionmaker(bind=engine)

        self.stats.set_value("pipeline/database/processed_items", 0)  # 3
        self.stats.set_value("pipeline/database/saved_items", 0)  # 4

    def process_item(self, item, spider):
        """
        Process the item and store to database.
        """

        db = self.Session()

        instance = db.query(CrawledItem).filter(CrawledItem.id == item["id"]).first()

        # modify/update the item as needed
        filtered_item = {
            "id": item["id"],
            "name": item["name"],
            "slug": item["slug"],
            "image_urls": item["image_urls"],
        }
        if not instance:
            instance = CrawledItem(**filtered_item)
            db.add(instance)
        else:
            for key, value in filtered_item.items():
                setattr(instance, key, value)

        try:
            db.commit()
            self.stats.inc_value("pipeline/database/saved_items")  # 5
            return item
        except Exception as error:
            print(error)
            db.rollback()
            raise
        finally:
            self.stats.inc_value("pipeline/database/processed_items")  # 6
            db.close()

    def close_spider(self, spider):
        self.Session().close()
