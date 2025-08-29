from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, case
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from jaimee_scraper.settings import DATABASE_URL

DeclarativeBase = declarative_base()
SQLALCHEMY_DATABASE_URL = DATABASE_URL

def db_connect():
    return create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_connect())

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_items_table(engine):
    DeclarativeBase.metadata.create_all(engine)

class Job(DeclarativeBase):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_dt = Column(DateTime, default=func.now())
    start_time = Column(DateTime)
    finish_time = Column(DateTime)
    finish_reason = Column(String)
    elapsed_time_seconds = Column(Float)
    processed_items = Column(Integer)
    saved_items = Column(Integer)
    stats = Column(JSONB)

class CrawledItem(DeclarativeBase):
    __tablename__ = "crawled_items"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    slug = Column(String)
    image_urls = Column(JSONB)
    created_dt = Column(DateTime, default=func.now())

    def get_all():
        db = next(get_db())
        gifs = db.execute(select(CrawledItem))
        return gifs.scalars().all()
    
    def get_all_by_slugs(slugs):
        db = next(get_db())
        # Create a CASE statement to preserve the order of slugs
        order = case(
            {slug: index for index, slug in enumerate(slugs)},
            value=CrawledItem.slug,
            else_=len(slugs)
        )
        gifs = db.execute(
            select(CrawledItem).where(CrawledItem.slug.in_(slugs)).order_by(order)
        )
        return gifs.scalars().all()

