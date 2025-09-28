import logging
from sqlalchemy.orm import sessionmaker
from scrapy import signals
from scrapy.exceptions import NotConfigured

from db.models import (
    Job,
    db_connect,
)

logger = logging.getLogger(__name__)


class SaveCrawlStats:
    @classmethod
    def from_crawler(cls, crawler):
        # first check if the extension should be enabled and raise
        # NotConfigured otherwise
        if not crawler.settings.getbool("CRAWLERSAVESTATS_ENABLED"):
            raise NotConfigured

        ext = cls()
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)

        return ext

    def spider_closed(self, spider):
        engine = db_connect()
        self.Session = sessionmaker(bind=engine)
        db = self.Session()

        # get the crawl stats
        stats = spider.crawler.stats.get_stats()

        name = spider.name
        processed_items = stats.get("pipeline/database/processed_items", 0)
        saved_items = stats.get("pipeline/files/saved_items", 0)

        start_time = stats.get("start_time")
        finish_time = stats.get("finish_time")
        finish_reason = stats.get("finish_reason")
        elapsed_time_seconds = stats.get("elapsed_time_seconds")

        # remove from dict
        del stats["start_time"]
        del stats["finish_time"]
        del stats["finish_reason"]
        del stats["elapsed_time_seconds"]

        job = Job(
            name=name,
            start_time=start_time,
            finish_time=finish_time,
            finish_reason=finish_reason,
            elapsed_time_seconds=elapsed_time_seconds,
            processed_items=processed_items,
            saved_items=saved_items,
            stats=stats,
        )

        db.add(job)

        try:
            db.commit()

        except Exception as error:
            logger.error(error)
            db.rollback()
            raise

        finally:
            db.close()
            self.Session().close()
