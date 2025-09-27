
import scrapy
import base64
import hashlib
from jaimee_scraper.settings import GIPHY_API_KEY
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def short_hash(url):
    digest = hashlib.sha256(url.encode()).digest()
    # urlsafe_b64encode avoids '/' and '+' characters
    return base64.urlsafe_b64encode(digest).decode()[:18]

def slug_from_img_src(img_src):
    # Parse the URL and split the path
    path = urlparse(img_src).path  # e.g., '/animations/alphabets/colored-glass/a_.gif'
    parts = path.strip("/").split("/")  # ['animations', 'alphabets', 'colored-glass', 'a_.gif']
    # Remove the file extension from the last part
    if parts:
        parts[-1] = parts[-1].rsplit(".", 1)[0]
    # Join with hyphens, skip the first part if you want (e.g., 'animations')
    slug = "-".join(parts[1:])  # skip 'animations', or use all: "-".join(parts)
    return slug

class GIFGIFSSpider(scrapy.Spider):
    name = "gifgifs"
    allowed_domains = ["gifgifs.com"]
    categories = ["anime", "science-body", "animals", "clothing", "computers-technology",
                  "creatures-cartoons", "food-drinks", "geography-history", "hobbies-entertainment",
                  "holidays", "jobs-people", "names", "nature", "jobs-people", "names", "nature",
                  "other-animations", "religious", "sports", "transportation", "webdesign-elements", "words"]
    start_urls = [
        f"https://gifgifs.com/{category}/" for category in categories
    ]

    def parse(self, response):
        for gif in response.css("div.item-card"):
            name = gif.css("img.item-image::attr(alt)").get()
            img_src = response.urljoin(gif.css("img::attr(src)").get())
            items = {
                "id": short_hash(img_src),
                "name": name,
                "slug": slug_from_img_src(img_src),
                "image_urls": [img_src]
            }
            yield items

        for next_link in response.css("a.page-link"):
            if next_link.attrib.get("aria-label") == "Next":
                next_page = next_link.attrib.get("href")
                if next_page:
                    yield response.follow(next_page, callback=self.parse)
                break