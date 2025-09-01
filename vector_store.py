import asyncio
import json
import logging
from dotenv import load_dotenv
from langchain_postgres import PGVector
from langchain_aws import BedrockEmbeddings
from jaimee_scraper.settings import DATABASE_URL
from utils import get_embedding
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()
logger = logging.getLogger(__name__)

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
    pool_size=20,           # max open connections
    max_overflow=10,        # extra connections if pool is full
    pool_timeout=30,        # wait time before failing
    pool_recycle=1800,      # recycle connections every 30 min
    pool_pre_ping=True,     # checks stale connections
)

class InvalidCollectionError(Exception):

  def __init__(self, collection):
    self.message = f"Invalid collection: {collection}"
    super().__init__(self.message)


class VectorStore:
  "A class for managing vector store operations and database interaction"

  def __init__(self, collection):
    self.embedding = BedrockEmbeddings(model_id="amazon.titan-embed-image-v1", region_name="us-east-1")
    self.vec_client = PGVector(collection_name=collection,
                               connection=engine,
                               embeddings=self.embedding,
                               embedding_length=1024,
                               use_jsonb=True,
                               pre_delete_collection=False,
                               distance_strategy="cosine",
                               async_mode=True)

  async def search_highly_accurate(self,
                                   query,
                                   k: int = 10,
                                   similarity_threshold=0.75,
                                   metadata_filter=None,
                                   use_mmr=False,
                                   lambda_mult: float = 0.5):
    """
    Highly accurate similarity search with multiple optimization strategies
    """
    try:
      if use_mmr:
        # Use MMR for diverse results
        documents = await self.vec_client.amax_marginal_relevance_search(
            query=query,
            k=k,
            fetch_k=k * 3,  # Fetch more for better selection
            lambda_mult=lambda_mult,
            filter=metadata_filter)
        # Convert to scored results (MMR doesn't return scores)
        return [(doc, 1.0) for doc in documents]
      else:
        # Standard similarity search with scores
        results = await self.vec_client.asimilarity_search_with_score(
            query=query,
            k=k * 2,  # Fetch more to apply threshold filtering
            filter=metadata_filter)

        # Convert distance to similarity and apply threshold
        scored_results = []
        for doc, distance in results:
          # For cosine distance, similarity = 1 - distance
          similarity = max(0.0, 1.0 - distance)
          if similarity >= similarity_threshold:
            scored_results.append((doc, similarity))

        # Sort by similarity (highest first) and limit
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return results

    except Exception as e:
      logger.error(f"Error in similarity search: {e}")
      return []

  async def search(self, query, k=5):
    results = await self.search_highly_accurate(query, k, use_mmr=True)
    return results

  async def delete_collection(self):
    result = await self.vec_client.adelete_collection()
    return result
  
  async def search_with_vector(self, query):
    body = json.dumps({
            "inputText": query,
            "embeddingConfig": {"outputEmbeddingLength": 1024}
        })
    embedding = get_embedding(body)
    result = await self.vec_client.asimilarity_search_by_vector(embedding, k=5)
    return result
  
  async def add_embeddings(self, texts, ids, embeddings, metadatas):
    result = await self.vec_client.aadd_embeddings(
        texts=texts,
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas)
    return result
      
if __name__ == "__main__":
    async def main():
        vector_store = VectorStore("gif_frames")
        # results = await vector_store.search("NBA", 5)
        # print(f"Found {len(results)} results")
        # print(results)
        # context = "\n\n---\n\n".join([doc[0].page_content for doc in results])
        # print(context)
        results = await vector_store.delete_collection()
        # print(f"Deleted collection, result: {results}")
        # result = await vector_store.upsert()
        # print(result)

    asyncio.run(main())