import logging
import schemas
from collections.abc import Sequence
from fastapi import APIRouter, HTTPException, Depends
from db.models import CrawledItem, get_db
from starlette import status
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gifs", tags=["gifs"])

@router.get("",
    response_model=schemas.CrawledItemsListSchema, 
    status_code = status.HTTP_200_OK, 
    summary="Get all gifs"
)
def list_():
    crawled_items = CrawledItem.get_all()

    if not crawled_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found")
    return {"status": "200", "results": len(crawled_items), "data": crawled_items}

