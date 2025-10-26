import re
from urllib.parse import urlparse

def normalize_giphy_url(url: str, prefer_webp: bool = True) -> str:
    """
    Normalize Giphy URLs to direct assets.
    prefer_webp=True will return .webp (faster, smaller).
    prefer_webp=False will return .gif.
    """
    parsed = urlparse(url)

    # Extract ID from path
    match = re.search(r"/media/([^/]+)/", parsed.path)
    if not match:
        match = re.search(r"/([A-Za-z0-9]+)$", parsed.path)

    if match:
        gif_id = match.group(1)
        if prefer_webp:
            return f"https://i.giphy.com/{gif_id}.gif"
        else:
            return f"https://media.giphy.com/media/{gif_id}/giphy.gif"

    return url