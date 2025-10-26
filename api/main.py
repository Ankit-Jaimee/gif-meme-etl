from fastapi import FastAPI
from api.endpoint import gif

app = FastAPI(
    title="GIF & Meme ETL API",
    description="A FastAPI server for scraping GIF & Meme data",
)

@app.get("/")
async def index():
    return {"message": "GIF & Meme ETL API is running!"}

app.include_router(gif.router)
