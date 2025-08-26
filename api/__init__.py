from fastapi import FastAPI
from api import gifs

app = FastAPI(
    title="GIF & Meme ETL API",
    description="A FastAPI server for scraping GIF & Meme data",
)

@app.get("/")
async def index():
    return {"message": "GIF & Meme ETL API is running!"}

app.include_router(gifs.router)
