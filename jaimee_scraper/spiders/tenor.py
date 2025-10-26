import scrapy
from jaimee_scraper.settings import TENOR_API_KEY


class TenorSpider(scrapy.Spider):
    name = "tenor"
    start_urls = [
        f"https://tenor.googleapis.com/v2/featured?key={TENOR_API_KEY}&media_filter=gif"
    ]

    def parse(self, response):
        json_response = response.json()
        for item in json_response["results"]:
            try: 
                image_url = item["media_formats"]["gif"]["url"]
                yield {
                    "id": item["id"],
                    "name": item["content_description"],
                    "slug": item["itemurl"].split("/")[-1],
                    "image_urls": [image_url]
                }
            except KeyError:
                self.logger.warning(f"Skipping item due to missing gif format: {item}")
                continue
        
        next_page_pos = json_response.get("next", None)
        if not next_page_pos:
            return
        next_page = f"https://tenor.googleapis.com/v2/featured?key={{TENOR_API_KEY}}&media_filter=gif&pos={next_page_pos}"
        yield response.follow(next_page, callback=self.parse)

