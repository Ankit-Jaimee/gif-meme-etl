import logging

from fastapi.params import Depends
import schemas
from fastapi import APIRouter, HTTPException
from db.models import CrawledItem, get_db
from starlette import status
from sqlalchemy.orm import Session
from vector_store import VectorStore
from fastapi import Query, BackgroundTasks
from api.schemas.gifs import GifListResponse 
from utils import get_s3_obj, update_s3_metadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gifs", tags=["gifs"])

@router.get("",
    response_model=GifListResponse,
    status_code = status.HTTP_200_OK, 
    summary="Get all gifs"
)
def get_all_gifs(
    safe_only: bool = Query(None, description="Filter to only safe gifs"), 
    db: Session = Depends(get_db)
):
    """Get all gifs from the database.
    Returns:
        dict: A dictionary containing the list of all gifs.
    """
    filters = {}
    if safe_only is not None:
        filters["is_safe"] = safe_only
    gifs = CrawledItem.get_all(db, **filters)
    if len(gifs) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found")
    if not gifs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No gifs found")
    return {"results": len(gifs), "data": gifs}

@router.get("/by_labels",
    response_model=schemas.CrawledItemsListSchema, 
    status_code = status.HTTP_200_OK, 
    summary="Get gifs by labels"
)
def list_by_labels(
    labels: str = Query(..., description="Comma separated list of labels"),
    db: Session = Depends(get_db)
):
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
async def search(
    query: str = Query(..., description="Search query string"),
    db: Session = Depends(get_db)
    ):
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
    crawled_items = CrawledItem.get_all_by_slugs(db, slugs)
    return {
        "status": "success",
        "query": query,
        "results": crawled_items,
    }


@router.post(
    "/crawl",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a Scrapy crawl with a search query"
)
def trigger_crawl(
    query: str = Query(..., description="Search term for Giphy"),
    background_tasks: BackgroundTasks = None
):
    """
    Trigger a Scrapy crawl for the given search term.
    """
    import subprocess

    def run_spider(search_term):
        subprocess.run(
            ["scrapy", "crawl", "search_giphy", "-a", f"query={search_term}"]
        )

    if background_tasks is not None:
        background_tasks.add_task(run_spider, query)
    else:
        run_spider(query)

    return {"status": "started", "search": query}


@router.patch(
    "/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable a GIF and its embeddings by id, slug, or filename"
)
async def disable_gif(
    id: int = Query(None, description="GIF ID"),
    slug: str = Query(None, description="GIF slug"),
    db: Session = Depends(get_db)
):
    """Disable a gif by setting its is_safe flag to False.
    Args:
        slug (str): The slug of the gif to disable.
        db (Session): The database session.
    """
    if id is not None:
        gif = CrawledItem.get_by_id(id)
    elif slug is not None:
        gif = CrawledItem.get_by_slug(db, slug)
    else:
        raise HTTPException(status_code=400, detail="Provide id or slug.")

    if not gif:
        raise HTTPException(status_code=404, detail="GIF not found.")
    
    gif.disabled = True
    gif.save(db)  # Make sure your model has a save() method or use your ORM's session commit
    
    # Update all related embeddings
    vector_store = VectorStore("gif_frames")
    # Assuming your embeddings have metadata with 'slug' or 'gif_id'
    filter_metadata = {"slug": gif.slug}  # or {"gif_id": gif.id} if that's how you store it
    embeddings = await vector_store.get_embeddings_by_metadata(filter_metadata)
    updated = 0
    for embedding in embeddings:
        metadata = embedding.cmetadata or {}
        metadata["disabled"] = True
        await vector_store.update_metadata(embedding.id, metadata)
        updated += 1
    try:
        s3_obj = get_s3_obj(gif.file_path)
        print(s3_obj["Metadata"])
        s3_metadata = s3_obj["Metadata"]
        s3_metadata["disabled"] = "true"
        update_s3_metadata(gif.file_path, s3_metadata)
    except Exception as e:
        logger.error(f"Failed to update S3 metadata for {gif.file_path}: {e}")
    return {"status": "success", "message": f"Disabled GIF and updated {updated} embeddings."}