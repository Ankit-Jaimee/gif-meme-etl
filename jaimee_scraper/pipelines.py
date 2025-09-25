# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import io
import os
from dotenv import load_dotenv
from scrapy import Request
from scrapy.pipelines.files import FilesPipeline, S3FilesStore
from sqlalchemy.orm import sessionmaker
from db.models import db_connect, CrawledItem, Job, create_items_table
from jaimee_scraper.settings import FILES_STORE
from tasks import embed_and_store
from utils import  get_file_name
import logging
logger = logging.getLogger(__name__)


load_dotenv()  # Loads variables from .env into environment


class JaimeeScraperPipeline:
    def process_item(self, item, spider):
        return item


class CustomS3FilesStore(S3FilesStore):

    def persist_file(self, path, buf, info, meta = None, headers = None):
        key_name = f"{self.prefix}{path}"
        buf.seek(0)
        extra = self._headers_to_botocore_kwargs(self.HEADERS)
        if headers:
            extra.update(self._headers_to_botocore_kwargs(headers))
        return self.s3_client.put_object(  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=key_name,
            Body=buf,
            Metadata={k: str(v) for k, v in (meta or {}).items()},
            ACL=self.POLICY,
            **extra)
class GifPipeline(FilesPipeline):
    STORE_SCHEMES = {
        "": FilesPipeline.STORE_SCHEMES[""],
        "file": FilesPipeline.STORE_SCHEMES["file"],
        "s3": CustomS3FilesStore,
        "gs": FilesPipeline.STORE_SCHEMES["gs"],
        "ftp": FilesPipeline.STORE_SCHEMES["ftp"],
    }
    def __init__(self, store_uri, download_func=None, settings=None):
        super().__init__(store_uri, download_func, settings)

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
        file_name = get_file_name(request)
        return file_name
    
    def file_downloaded(self, response, request, info, *, item=None):
        path = super().file_downloaded(response, request, info, item=item)
        return path
        
    def item_completed(self, results, item, info):
        item = super().item_completed(results, item, info)
        file_name = results[0][1].get("path")
        meta_info = {
            "slug": item.get("slug", "default"),
            "title": item.get("name", "default"),
        }
        for ok, file_info in results:
            logger.info(f"Processing result - ok: {ok}, file_info: {file_info}")
            if ok:
                status = file_info.get('status')
                logger.info(f"File status: {status}")
                path = file_info['path']
                if status == 'downloaded':
                    logger.info(f"✅ NEW file uploaded to S3: {path}")
                    file_path = os.path.join(FILES_STORE, file_name)
                    embed_and_store.delay(file_path, item.get("image_urls", [None])[0], meta_info)
                elif status == 'uptodate':
                    logger.info(f"🔁 Reused existing file: {path}")
        return item


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
        self.stats.set_value("pipeline/database/processed_items", 0)
        self.stats.set_value("pipeline/database/saved_items", 0)

    def process_item(self, item, spider):
        """
        Process the item and store to database.
        """

        db = self.Session()

        instance = db.query(CrawledItem).filter(CrawledItem.id == item["id"]).first()

        filtered_item = {
            "id": item["id"],
            "name": item["name"],
            "slug": item["slug"],
            "image_urls": item["image_urls"],
            "file_path": os.path.join(FILES_STORE, f"{item['slug']}.gif"),
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
        db = self.Session()
        db.close()
