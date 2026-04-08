"""Web fetching tool with anti-detection capabilities."""

import asyncio
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from backend.tools.base import Tool


class WebFetchTool(Tool):
    """Tool for fetching web content with anti-detection support."""

    name = "web_fetch"
    description = """Fetch and extract content from web pages.

This tool can handle various websites including those with:
- JavaScript-rendered content (SPA, React, Vue apps)
- Anti-bot protection (Cloudflare, etc.)
- Dynamic content loading

Use this when you need to:
- Read documentation from websites
- Extract article content
- Get data from web pages
- Follow redirects and resolve URLs"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch. Must be a valid HTTP/HTTPS URL."
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method to use",
                    "enum": ["GET", "POST"],
                    "default": "GET"
                },
                "headers": {
                    "type": "object",
                    "description": "Optional custom headers to include in the request",
                    "default": {}
                },
                "render_js": {
                    "type": "boolean",
                    "description": "Whether to render JavaScript. Default: true (uses browser mode for better compatibility with dynamic sites). Set to false for faster static site fetching.",
                    "default": True
                },
                "extract_content": {
                    "type": "string",
                    "description": "Content extraction mode",
                    "enum": ["full", "article", "text"],
                    "default": "article"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds (10-300)",
                    "minimum": 10,
                    "maximum": 300,
                    "default": 30
                },
                "follow_redirects": {
                    "type": "boolean",
                    "description": "Whether to follow HTTP redirects",
                    "default": True
                },
                "max_retries": {
                    "type": "integer",
                    "description": "Maximum number of retries on failure (0-3)",
                    "minimum": 0,
                    "maximum": 3,
                    "default": 2
                }
            },
            "required": ["url"]
        }

    def __init__(self):
        self._session = None
        self._playwright = None

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict = None,
        render_js: bool = True,
        extract_content: str = "article",
        timeout: int = 30,
        follow_redirects: bool = True,
        max_retries: int = 2
    ) -> str:
        """Execute web fetch with anti-detection measures."""

        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme in ('http', 'https'):
            return f"Error: Invalid URL scheme. Must be http or https, got: {parsed.scheme}"

        headers = headers or {}

        try:
            if render_js:
                return await self._fetch_with_browser(
                    url, method, headers, extract_content, timeout, max_retries
                )
            else:
                return await self._fetch_with_http(
                    url, method, headers, extract_content, timeout,
                    follow_redirects, max_retries
                )
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"

    async def _fetch_with_http(
        self, url: str, method: str, headers: dict,
        extract_content: str, timeout: int,
        follow_redirects: bool, max_retries: int
    ) -> str:
        """Fetch using HTTP client with anti-detection headers."""
        try:
            import httpx
        except ImportError:
            return "Error: HTTP client requires httpx. Install with: pip install httpx"

        # Default anti-detection headers
        # Note: Don't set Accept-Encoding, let httpx handle it automatically
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Merge with custom headers (custom takes precedence)
        final_headers = {**default_headers, **headers}

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    follow_redirects=follow_redirects,
                    timeout=timeout
                ) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=final_headers
                    )
                    response.raise_for_status()

                    # Extract content based on mode
                    return self._extract_content(
                        response.text,
                        response.headers.get('content-type', ''),
                        extract_content,
                        url
                    )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (403, 429, 503) and attempt < max_retries:
                    # Might be blocked, wait and retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # If HTTP fails with 403, fallback to browser
        if last_error and isinstance(last_error, httpx.HTTPStatusError) and last_error.response.status_code == 403:
            return await self._fetch_with_browser(
                url, method, headers, extract_content, timeout, 0
            )

        raise last_error

    async def _fetch_with_browser(
        self, url: str, method: str, headers: dict,
        extract_content: str, timeout: int, max_retries: int
    ) -> str:
        """Fetch using Playwright for JavaScript-rendered content."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return "Error: JavaScript rendering requires playwright. Install with: pip install playwright && playwright install chromium"

        async with async_playwright() as p:
            # Launch browser with anti-detection
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Inject anti-detection script
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            try:
                response = await page.goto(
                    url,
                    wait_until='networkidle',
                    timeout=timeout * 1000
                )

                if not response:
                    return "Error: Failed to load page"

                # Wait for content to stabilize
                await page.wait_for_load_state('domcontentloaded')
                await asyncio.sleep(1)  # Extra wait for dynamic content

                # Get page content
                content = await page.content()

                await browser.close()

                return self._extract_content(
                    content,
                    response.headers.get('content-type', ''),
                    extract_content,
                    url
                )

            except Exception as e:
                await browser.close()
                raise

    def _extract_content(
        self, html: str, content_type: str,
        mode: str, base_url: str
    ) -> str:
        """Extract content from HTML based on mode."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback to simple regex extraction if bs4 not available
            return self._simple_extract(html, mode)

        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        if mode == 'full':
            # Return full body content
            body = soup.find('body')
            return body.get_text(separator='\n', strip=True) if body else soup.get_text(separator='\n', strip=True)

        elif mode == 'article':
            # Try to find main article content
            # Common article containers
            article_selectors = [
                'article', '[role="main"]', 'main',
                '.article-content', '.post-content', '.entry-content',
                '#article-content', '#main-content', '.content',
                '.markdown-body', '.readme', '.wiki-content'
            ]

            for selector in article_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(separator='\n', strip=True)
                    if len(text) > 200:  # Ensure we got substantial content
                        return self._format_text(text)

            # Fallback to largest text block
            paragraphs = soup.find_all('p')
            if paragraphs:
                texts = [p.get_text(strip=True) for p in paragraphs]
                return self._format_text('\n\n'.join(texts))

            # Last resort
            return self._format_text(soup.get_text(separator='\n', strip=True))

        else:  # text mode
            # Just plain text, minimal formatting
            return soup.get_text(separator=' ', strip=True)

    def _simple_extract(self, html: str, mode: str) -> str:
        """Simple extraction without BeautifulSoup."""
        # Remove script and style tags with content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode common HTML entities
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&amp;', '&').replace('&quot;', '"')
        text = text.replace('&apos;', "'").replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return self._format_text(text)

    def _format_text(self, text: str) -> str:
        """Clean up and format extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        # Limit length
        max_length = 100000
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n... [Content truncated, total length: {len(text)} characters]"

        return text.strip()
