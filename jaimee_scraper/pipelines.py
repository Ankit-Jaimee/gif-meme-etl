# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
from itemadapter import ItemAdapter
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.images import ImagesPipeline
from scrapy import Request
from db.models import db_connect, CrawledItem, create_items_table
from sqlalchemy.orm import sessionmaker

class JaimeeScraperPipeline:
    def process_item(self, item, spider):
        return item

class GifPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        for url in item.get('image_urls', []):
            yield Request(url, 
                            headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/139.0.0.0 Safari/537.36"
                            ),
                            "Referer": "https://giphy.com/",},
                          meta={'slug': item.get('slug')}
                        )

    def file_path(self, request, response=None, info=None, *, item=None):
        slug = request.meta.get('slug', 'default')
        ext = os.path.splitext(request.url)[-1]
        return f"{slug}{ext}"

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

        self.stats.set_value("pipeline/database/processed_items", 0) #3
        self.stats.set_value("pipeline/database/saved_items", 0) #4

    def process_item(self, item, spider):
        """
        Process the item and store to database.
        """

        db = self.Session()

        instance = (
            db.query(CrawledItem).filter(CrawledItem.id == item["id"]).first()
        )

        # modify/update the item as needed
        filtered_item = {
            "id": item["id"],
            "name": item["name"],
            "slug": item["slug"],
            "image_urls": item["image_urls"]
        }
        if not instance:
            instance = CrawledItem(**filtered_item)
            db.add(instance)
        else:
            for key, value in filtered_item.items():
                setattr(instance, key, value)

        try:
            db.commit()
            self.stats.inc_value("pipeline/database/saved_items") #5
            return item
        except Exception as error:
            print(error)
            db.rollback()
            raise
        finally:
            self.stats.inc_value("pipeline/database/processed_items") #6
            db.close()


    def close_spider(self, spider):
        self.Session().close()