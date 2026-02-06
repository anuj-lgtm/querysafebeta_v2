"""
URL content extraction module for QuerySafe chatbot training.
Uses httpx + lxml (both already in requirements.txt).
No new dependencies needed.
"""
import logging
import time

import httpx
from lxml import html as lxml_html
from lxml import etree

logger = logging.getLogger(__name__)

# Tags to remove (navigation, scripts, ads, footers)
REMOVE_TAGS = {
    'script', 'style', 'nav', 'footer', 'header', 'aside',
    'iframe', 'noscript', 'svg', 'form', 'button',
}

HEADERS = {
    'User-Agent': 'QuerySafe-Bot/1.0 (+https://querysafe.in)',
    'Accept': 'text/html,application/xhtml+xml',
}

TIMEOUT = 15  # seconds per request


def fetch_url_text(url: str) -> tuple:
    """Fetch a single URL and extract clean text content.
    Returns (extracted_text, error_message_or_None).
    """
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True, verify=True) as client:
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return '', f'Not HTML content: {content_type}'

        tree = lxml_html.fromstring(response.text)

        # Remove unwanted elements
        for tag in REMOVE_TAGS:
            for element in tree.xpath(f'//{tag}'):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

        # Extract text from body (or full tree if no body)
        body = tree.xpath('//body')
        target = body[0] if body else tree
        text = target.text_content()

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = '\n'.join(lines)

        if len(clean_text) < 50:
            return '', f'Too little content extracted ({len(clean_text)} chars)'

        return clean_text, None

    except httpx.TimeoutException:
        return '', f'Timeout after {TIMEOUT}s'
    except httpx.HTTPStatusError as e:
        return '', f'HTTP {e.response.status_code}'
    except Exception as e:
        return '', str(e)[:200]


def parse_sitemap(sitemap_url: str) -> tuple:
    """Parse an XML sitemap and return list of page URLs.
    Handles sitemap index files (nested sitemaps) one level deep.
    Returns (url_list, error_message_or_None).
    """
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(sitemap_url, headers=HEADERS)
            response.raise_for_status()

        root = etree.fromstring(response.content)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Check if this is a sitemap index
        sitemaps = root.findall('.//sm:sitemap/sm:loc', ns)
        if sitemaps:
            # Sitemap index — fetch each child sitemap (limit 10)
            all_urls = []
            for sm_loc in sitemaps[:10]:
                child_urls, err = parse_sitemap(sm_loc.text.strip())
                if not err:
                    all_urls.extend(child_urls)
            return all_urls, None

        # Regular sitemap — extract <loc> URLs
        urls = []
        for loc in root.findall('.//sm:url/sm:loc', ns):
            if loc.text:
                urls.append(loc.text.strip())

        # Also try without namespace (some sitemaps don't use it)
        if not urls:
            for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                if loc.text:
                    urls.append(loc.text.strip())

        # Fallback: try plain <loc> tags without namespace
        if not urls:
            for loc in root.iter('loc'):
                if loc.text:
                    urls.append(loc.text.strip())

        if not urls:
            return [], 'No URLs found in sitemap'

        return urls, None

    except Exception as e:
        return [], f'Sitemap parse error: {str(e)[:200]}'


def crawl_urls(urls: list, max_pages: int = 50, delay: float = 1.0) -> list:
    """Crawl a list of URLs and return extracted content.
    Returns list of {"url": str, "content": str, "error": str|None}.
    Respects a delay between requests and caps at max_pages.
    """
    results = []
    for i, url in enumerate(urls[:max_pages]):
        text, error = fetch_url_text(url)
        results.append({
            'url': url,
            'content': text,
            'error': error,
        })
        if i < len(urls) - 1:
            time.sleep(delay)  # polite crawl delay
    return results
