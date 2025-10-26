import scrapy

from jaimee_scraper.settings import GIPHY_API_KEY
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

class SearchGiphySpider(scrapy.Spider):
    name = "search_giphy"
    
    def __init__(self, query="funny", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.start_urls = [
            f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={self.query}&limit=500&offset=0&rating=r&lang=en&bundle=messaging_non_clips"
        ]

    def parse(self, response, **kwargs):
        json_response = response.json()
        for item in json_response["data"]:
            image_url = f"https://i.giphy.com/{item['id']}.gif"
            yield {
                "id": item["id"],
                "name": item["title"],
                "slug": item["slug"],
                "image_urls": [image_url]
            }
        current_offset = json_response.get("pagination", {}).get("offset", 0)
        count = json_response.get("pagination", {}).get("count", 0)
        if current_offset >= json_response.get("pagination", {}).get("total_count", 0):
            return
        next_offset = current_offset + count
        url_parts = list(urlparse(response.url))
        query = parse_qs(url_parts[4])
        query['offset'] = [str(next_offset)]
        url_parts[4] = urlencode(query, doseq=True)
        next_page = urlunparse(url_parts)
        yield response.follow(next_page, callback=self.parse)
