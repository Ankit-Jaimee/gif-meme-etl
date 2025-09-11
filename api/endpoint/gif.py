import logging
import schemas
from fastapi import APIRouter, HTTPException
from db.models import CrawledItem
from starlette import status
from sqlalchemy.orm import Session
from vector_store import VectorStore


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gifs", tags=["gifs"])

@router.get("",
    response_model=schemas.CrawledItemsListSchema,
    status_code = status.HTTP_200_OK, 
    summary="Get all gifs"
)
def list_():
    """Get all gifs from the database.
    Returns:
        dict: A dictionary containing the list of all gifs.
    """
    crawled_items = CrawledItem.get_all()

    if not crawled_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found")
    return {"status": "200", "results": len(crawled_items), "data": crawled_items}

@router.get("/by_labels",
    response_model=schemas.CrawledItemsListSchema, 
    status_code = status.HTTP_200_OK, 
    summary="Get gifs by labels"
)
def list_by_labels(labels: str):
    """Get gifs by labels from the database.
    Args:
        labels (Sequence[str]): List of labels to filter gifs.
    Returns:
        dict: A dictionary containing the list of gifs matching the labels.
    """
    labels = list(labels.split(","))
    print(labels)
    crawled_items = CrawledItem.filter_by_labels(labels)

    if not crawled_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found for the given labels")
    return {"status": "200", "results": len(crawled_items), "data": crawled_items}


@router.get("/search",
    response_model=schemas.GifSearchSchema,
    status_code = status.HTTP_200_OK,
    summary="Search gifs by text query"
)
async def search(query: str):
    """Search gifs by text query using vector store.
    Args:
        query (str): The search query.
    Returns:
        dict: A dictionary containing the search results.
    """
    vector_store = VectorStore("gif_frames")
    results = await vector_store.search(query)
    
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found for the query")
    slugs = [doc[0].metadata['slug'] for doc in results]
    slugs = list(dict.fromkeys(slugs))
    crawled_items = CrawledItem.get_all_by_slugs(slugs)
    return {
        "status": "success",
        "query": query,
        "results": crawled_items,
    }