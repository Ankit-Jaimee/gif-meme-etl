from pydantic import BaseModel
from typing import List

class GifResponse(BaseModel):
    id: str
    name: str
    slug: str
    image_urls: list[str]
    is_safe: bool
    file_path: str
    disabled: bool

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
        orm_mode = True

class GifListResponse(BaseModel):
    results: int
    data: list[GifResponse]

class PaginatedGifListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    List[GifResponse]

class GifSearchSchema(BaseModel):
    status: str
    query: str
    results: list[GifResponse]

