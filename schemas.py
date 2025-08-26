from pydantic import BaseModel
from db.models import CrawledItem

class CrawledItemSchema(BaseModel):
    id: str
    name: str
    slug: str
    image_urls: list[str]

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True

class CrawledItemsListSchema(BaseModel):
    status: str
    results: int
    data: list[CrawledItemSchema]