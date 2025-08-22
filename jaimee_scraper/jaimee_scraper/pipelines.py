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
