from datetime import datetime, timezone
import httpx

from webrag.models import RawPage

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}


def fetch_url(url: str, timeout: float = 15.0, headers: dict[str, str] | None = None) -> RawPage:
    """Fetch a web page using plain HTTP and return a RawPage object."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)

    with httpx.Client(follow_redirects=True, timeout=timeout, headers=req_headers) as client:
        response = client.get(url)
        content_type = response.headers.get("content-type", "text/html")
        return RawPage(
            url=url,
            final_url=str(response.url),
            status=response.status_code,
            content_type=content_type,
            body=response.content,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
