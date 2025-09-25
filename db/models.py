from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
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
    is_safe = Column(Boolean, default=True)
    disabled = Column(Boolean, default=False)
    labels = Column(ARRAY(String), default=[])
    file_path = Column(String)
    created_dt = Column(DateTime, default=func.now())

    @classmethod
    def get_all(cls, db, **filters):
        query = select(cls)
        if "is_safe" in filters:
            query = query.where(cls.is_safe == filters["is_safe"])
        gifs = db.execute(query)
        return gifs.scalars().all()
    
    @classmethod
    def get_all_by_slugs(cls, db, slugs):
        order = case(
            {slug: index for index, slug in enumerate(slugs)},
            value=cls.slug,
            else_=len(slugs)
        )
        gifs = db.execute(
            select(cls).where(cls.slug.in_(slugs)).order_by(order)
        )
        return gifs.scalars().all()

    @classmethod
    def get_by_slug(cls, db, slug):
        gif = db.execute(select(cls).where(cls.slug == slug)).scalar()
        return gif

    @classmethod
    def filter_by_labels(cls, db, labels):
        gifs = db.execute(select(cls).where(cls.labels.contains(labels)))
        return gifs.scalars().all()

    def save(self, db):
        db.add(self)
        db.commit()
        db.refresh(self)
        return self