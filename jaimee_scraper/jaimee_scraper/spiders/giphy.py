import scrapy
from jaimee_scraper.settings import GIPHY_API_KEY
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


class GiphySpider(scrapy.Spider):
    name = "giphy"
    start_urls = [
        f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=50&offset=450&rating=pg-13&bundle=clips_grid_picker",
        f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=50&offset=450&rating=pg-13&bundle=messaging_non_clips_grid_picker",
        f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=50&offset=450&rating=pg-13&bundle=sticker_layering",
        f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=50&offset=450&rating=pg-13&bundle=low_bandwidth",

    ]

    def parse(self, response):
        json_response = response.json()
        for item in json_response["data"]:
            image_url = f"https://i.giphy.com/{item['id']}.gif"
            yield {
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

