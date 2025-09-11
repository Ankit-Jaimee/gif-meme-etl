# celeryconfig.py or in your main celery app setup
from celery import Celery
from jaimee_scraper.settings import CELERY_BROKER_URL
from celery.schedules import crontab

celery_app = Celery('tasks', broker=CELERY_BROKER_URL)
celery_app.conf.beat_schedule = {
    "run-giphy-spider-every-10-minutes": {
        "task": "tasks.run_giphy_spider",
        "schedule": crontab(minute=0, hour=1),
    },
}