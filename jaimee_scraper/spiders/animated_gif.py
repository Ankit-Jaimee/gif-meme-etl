import scrapy
import os
import re
import hashlib
import base64

def short_hash(url):
    digest = hashlib.sha256(url.encode()).digest()
    # urlsafe_b64encode avoids '/' and '+' characters
    return base64.urlsafe_b64encode(digest).decode()[:18]

class AnimatedGifSpider(scrapy.Spider):
    name = "animated_gif"
    allowed_domains = ["animatedgif.net"]
    start_urls = [
        "https://www.animatedgif.net/naughty/naughty1.shtml",
        "http://www.animatedgif.net/beavisbutthead/beavisbutthead.shtml"

    ]

    def parse(self, response):
        # Target only the main gif table
        for idx, link in enumerate(
            response.css("table[border='3'][cellpadding='8'][cellspacing='8'] a:has(img)"),
            start=1
        ):
            img_src = link.css("img::attr(src)").get()
            if not img_src:
                continue

            image_url = response.urljoin(img_src)

            filename = os.path.basename(img_src)
            name, _ = os.path.splitext(filename)
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

            yield {
                "id": f"{response.url}-{idx}",
                "name": name,
                "slug": slug,
                "image_urls": [image_url],
            }

        # ---- Pagination ----
        current_page_match = re.search(r"naughty(\d+)\.shtml", response.url)
        if not current_page_match:
            return
        current_page = int(current_page_match.group(1))

        next_href = None
        for a in response.css("font[size='+2'] a"):
            if a.css("::text").get().strip().upper() == "NEXT":
                next_href = a.attrib.get("href")
                break

        if next_href:
            next_url = response.urljoin(next_href)

            next_page_match = re.search(r"naughty(\d+)\.shtml", next_href)
            if next_page_match:
                next_page = int(next_page_match.group(1))
                if next_page > current_page:
                    yield scrapy.Request(next_url, callback=self.parse)
