from urllib.parse import urljoin, urlparse
import scrapy
import os
import re
import hashlib
import base64

import logging

logger = logging.getLogger(__name__)

def short_hash(url):
    digest = hashlib.sha256(url.encode()).digest()
    # urlsafe_b64encode avoids '/' and '+' characters
    return base64.urlsafe_b64encode(digest).decode()[:18]

class AnimatedGifSpider(scrapy.Spider):
    name = "animated_gif"
    allowed_domains = ["animatedgif.net"]
    start_urls = [
        "https://animatedgif.net"
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

    def parse(self, response):
        logger.info(f"Processing home page for categories")

        category_options = response.css("select[name='category'] option")
        for option in category_options:
            category_url = option.css("::attr(value)").get()
            category_name = option.css("::text").get().strip()
            if not category_url or not category_name:
                continue

            category_name = category_name.strip()

            # skip categories with no URL
            if category_url == "#" or not category_name:
                continue

            if not category_url.startswith(('http://', 'https://')):
                if category_url.startswith('/'):
                    category_url = urljoin('https://animatedgif.net', category_url)
                else:
                    category_url = urljoin('https://animatedgif.net/', category_url)

            yield scrapy.Request(
                url=category_url,
                callback=self.parse_category,
                meta={
                    'category_name': category_name,
                    'category_url': category_url
                },
                errback=self.handle_error
            )

    def parse_category(self, response):
        category_name = response.meta['category_name']
        category_url = response.meta['category_url']
        logger.info(f"Processing category: {category_name} - {category_url}")

        subcategory_links = self.extract_subcategory_links(response)

        if subcategory_links and len(subcategory_links) > 0:
            self.logger.info(f"Found {len(subcategory_links)} subcategories in {category_name}")
            
            # Update category item with subcategory info
            category_item = CategoryItem()
            category_item['category_name'] = category_name
            category_item['category_url'] = category_url
            category_item['has_subcategories'] = True
            category_item['subcategory_count'] = len(subcategory_links)
            
            yield category_item
            
            # Process each subcategory
            for link in subcategory_links:
                subcategory_url = link['url']
                subcategory_name = link['name']
                gif_count_estimate = link.get('count', '')
                
                # Create subcategory item
                subcategory_item = SubcategoryItem()
                subcategory_item['parent_category'] = category_name
                subcategory_item['subcategory_name'] = subcategory_name
                subcategory_item['subcategory_url'] = subcategory_url
                subcategory_item['gif_count_estimate'] = gif_count_estimate
                
                yield subcategory_item
                
                # Follow subcategory URL to extract GIFs
                yield scrapy.Request(
                    url=subcategory_url,
                    callback=self.parse_gif_page,
                    meta={
                        'category_name': category_name,
                        'subcategory_name': subcategory_name,
                        'page_number': 1
                    },
                    errback=self.handle_error
                )
        else:
            # This is Type B: Direct GIF category
            yield from self.parse_gif_page(response)

    def extract_subcategory_links(self, response):
        subcategory_links = []
        links = response.css("a[href]")

        for link in links:
            href = link.css('::attr(href)').get()
            text = link.css('::text').get()
            
            if not href or not text:
                continue
                
            # Skip navigation links, back links, etc.
            if any(keyword in text.lower() for keyword in ['back', 'home', 'main', 'return']):
                continue
                
            # Check if this looks like a subcategory link
            # Common pattern: contains subdirectory and .shtml
            if '/' in href and '.shtml' in href:
                # Extract count if available (e.g., " / 228k")
                count_match = re.search(r'/\s*(\d+[kKmM]?)', text)
                count = count_match.group(1) if count_match else ""
                
                # Clean subcategory name
                subcategory_name = re.sub(r'\s*/\s*\d+[kKmM]?.*$', '', text).strip()
                
                # Construct absolute URL
                if not href.startswith(('http://', 'https://')):
                    if href.startswith('/'):
                        href = urljoin('https://animatedgif.net', href)
                    else:
                        # Handle relative paths (e.g., "bears/bears.shtml")
                        # Extract the directory from the current URL
                        current_path = urlparse(response.url).path
                        current_dir = '/'.join(current_path.split('/')[:-1]) + '/'
                        href = urljoin(response.url, href)
                
                subcategory_links.append({
                    'url': href,
                    'name': subcategory_name,
                    'count': count
                })
        
        return subcategory_links
    
    def parse_gif_page(self, response):
        """Extract GIFs from a page and handle pagination"""
        category_name = response.meta.get('category_name', 'Unknown')
        subcategory_name = response.meta.get('subcategory_name', None)
        page_number = response.meta.get('page_number', 1)
        
        self.logger.info(f"Parsing GIF page {page_number} for {category_name}" + 
                        (f" > {subcategory_name}" if subcategory_name else ""))
        
        # Mark this page as processed
        page_key = f"{response.url}_{page_number}"
        self.processed_pages.add(page_key)
        
        # Extract GIFs from tables
        gif_tables = response.css('table[border="3"]')
        
        position = 0
        for table in gif_tables:
            gif_cells = table.css('td[align="center"]')
            
            for cell in gif_cells:
                gif_link = cell.css('a[href$=".gif"]')
                if not gif_link:
                    continue
                    
                href = gif_link.css('::attr(href)').get()
                img_src = gif_link.css('img::attr(src)').get()
                text_content = gif_link.css('::text').getall()
                
                if not href or not img_src:
                    continue
                
                # Extract filename and size from text content
                # Pattern: "filename.gif / filesize"
                text = ' '.join(text_content).strip()
                filename = ""
                file_size = ""
                
                if '/' in text:
                    parts = text.split('/')
                    filename = parts[0].strip()
                    if len(parts) > 1:
                        file_size = parts[1].strip()
                else:
                    filename = text
                
                # Use href for filename if not found in text
                if not filename:
                    filename = href.split('/')[-1]
                
                # Construct absolute GIF URL
                gif_url = href
                if not gif_url.startswith(('http://', 'https://')):
                    gif_url = urljoin(response.url, gif_url)
                
                # Create GIF item
        
        # Handle pagination
        next_pages = self.extract_pagination_links(response, page_number)
        
        for next_page in next_pages:
            next_url = next_page['url']
            next_page_num = next_page['page_number']
            
            # Avoid infinite loops by checking if we've processed this page
            next_page_key = f"{next_url}_{next_page_num}"
            if next_page_key in self.processed_pages:
                continue
            
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_gif_page,
                meta={
                    'category_name': category_name,
                    'subcategory_name': subcategory_name,
                    'page_number': next_page_num
                },
                errback=self.handle_error
            )
    
    def extract_pagination_links(self, response, current_page):
        """Extract pagination links using both patterns"""
        pagination_links = []
        
        # Pattern A: Simple Next/Previous
        # <a href="bears2.shtml">GO TO BEARS PAGE 2</a>
        next_links = response.css('a[href]:contains("GO TO"), a[href]:contains("NEXT"), a[href]:contains("next")')
        
        for link in next_links:
            href = link.css('::attr(href)').get()
            text = link.css('::text').get()
            
            if not href or not text:
                continue
            
            # Extract page number from text
            page_match = re.search(r'page\s+(\d+)', text, re.IGNORECASE)
            if page_match:
                page_num = int(page_match.group(1))
            else:
                # Try to extract from URL
                page_match = re.search(r'[^\d](\d+)\.shtml', href)
                if page_match:
                    page_num = int(page_match.group(1))
                else:
                    # Skip if we can't determine page number
                    continue
            
            # Construct absolute URL
            if not href.startswith(('http://', 'https://')):
                href = urljoin(response.url, href)
            
            pagination_links.append({
                'url': href,
                'page_number': page_num
            })
        
        # Pattern B: Numbered Pagination
        # <a href="bodyparts2.shtml"> 2</a>
        numbered_links = response.css('a[href]')
        
        for link in numbered_links:
            href = link.css('::attr(href)').get()
            text = link.css('::text').get()
            
            if not href or not text:
                continue
            
            # Check if text is a number
            text_clean = text.strip()
            if text_clean.isdigit():
                page_num = int(text_clean)
                
                # Skip current page
                if page_num == current_page:
                    continue
                
                # Construct absolute URL
                if not href.startswith(('http://', 'https://')):
                    href = urljoin(response.url, href)
                
                pagination_links.append({
                    'url': href,
                    'page_number': page_num
                })
        
        # Remove duplicates
        seen_urls = set()
        unique_pagination_links = []
        for link in pagination_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_pagination_links.append(link)
        
        return unique_pagination_links