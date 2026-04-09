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
- Follow redirects and resolve URLs

The output can be in plain text or Markdown format."""

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
                "raw": {
                    "type": "string",
                    "description": "Output format: 'markdown' (default) for converted Markdown, 'html' for raw HTML content",
                    "enum": ["html", "markdown"],
                    "default": "markdown"
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
        max_retries: int = 2,
        raw: str = "markdown"
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
                    url, method, headers, extract_content, timeout, max_retries, raw
                )
            else:
                return await self._fetch_with_http(
                    url, method, headers, extract_content, timeout,
                    follow_redirects, max_retries, raw
                )
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"

    async def _fetch_with_http(
        self, url: str, method: str, headers: dict,
        extract_content: str, timeout: int,
        follow_redirects: bool, max_retries: int, raw: str
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
                        url,
                        raw,
                        None  # HTTP mode doesn't have inner_text
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
                url, method, headers, extract_content, timeout, 0, raw
            )

        raise last_error

    async def _fetch_with_browser(
        self, url: str, method: str, headers: dict,
        extract_content: str, timeout: int, max_retries: int, raw: str
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

                # Get page content and inner text
                content = await page.content()
                inner_text = await page.inner_text('body')

                await browser.close()

                return self._extract_content(
                    content,
                    response.headers.get('content-type', ''),
                    extract_content,
                    url,
                    raw,
                    inner_text
                )

            except Exception as e:
                await browser.close()
                raise

    def _extract_content(
        self, html: str, content_type: str,
        mode: str, base_url: str, raw: str = "markdown",
        inner_text: str = None
    ) -> str:
        """Extract content from HTML based on mode."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback to simple regex extraction if bs4 not available
            return self._simple_extract(html, mode)

        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements (including those with special attributes)
        for element in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Remove link tags (CSS files) and meta tags
        for element in soup(['link', 'meta']):
            element.decompose()
        
        # Remove textarea elements (often contain inline CSS/JS in encoded form)
        for element in soup(['textarea']):
            element.decompose()

        # If raw='html', return cleaned HTML
        if raw == "html":
            return str(soup)

        # If we have inner_text from browser, use it for text extraction
        if inner_text:
            # Convert plain text to simple markdown-like format
            lines = inner_text.strip().split('\n')
            result_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    result_lines.append(line)
            result = '\n'.join(result_lines)
            
            # Limit length
            max_length = 100000
            if len(result) > max_length:
                result = result[:max_length] + f"\n\n... [Content truncated]"
            return result

        if mode == 'full':
            # Return full body content
            body = soup.find('body')
            content = body if body else soup
            return self.html_to_markdown(str(content), base_url)

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
                        return self.html_to_markdown(str(element), base_url)

            # Fallback to largest text block or full content
            paragraphs = soup.find_all('p')
            if paragraphs:
                texts = [p.get_text(strip=True) for p in paragraphs]
                if texts:
                    return self.html_to_markdown('\n\n'.join(texts), base_url)

            # Last resort: use full page content
            body = soup.find('body')
            content = body if body else soup
            return self.html_to_markdown(str(content), base_url)

        else:  # text mode
            # Just plain text, minimal formatting
            return self.html_to_markdown(str(soup), base_url)

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

    def html_to_markdown(self, html: str, base_url: str) -> str:
        """Convert HTML to Markdown format."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return self._simple_extract(html, 'text')

        soup = BeautifulSoup(html, 'html.parser')
        
        # 如果没有找到标准元素，使用降级方案
        standard_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 
                                          'ul', 'ol', 'li', 'blockquote', 'pre', 
                                          'table', 'br', 'hr'])
        
        if not standard_elements:
            # 没有标准元素，返回清理后的纯文本
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 100000:
                text = text[:100000] + f"\n\n... [Content truncated]"
            return text

        markdown_parts = []

        def get_text(element):
            return element.get_text(separator=' ', strip=True)

        def get_attrs(element):
            return {k: v for k, v in element.attrs.items() if k in ('href', 'src', 'alt', 'title')}

        # Process each element
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'img',
                                     'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
                                     'table', 'thead', 'tbody', 'tr', 'th', 'td', 'br', 'hr',
                                     'strong', 'b', 'em', 'i', 'div', 'span']):
            tag_name = element.name

            if tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag_name[1])
                text = get_text(element)
                if text:
                    markdown_parts.append(f"\n{'#' * level} {text}\n")

            elif tag_name == 'p':
                text = get_text(element)
                if text:
                    # Check for links in this paragraph
                    links = element.find_all('a')
                    if links:
                        for link in links:
                            link_text = link.get_text(strip=True)
                            href = link.get('href', '')
                            if href:
                                href = urljoin(base_url, href)
                            if link_text and href:
                                text = text.replace(link_text, f'[{link_text}]({href})', 1)
                    markdown_parts.append(text + "\n")

            elif tag_name == 'a':
                # Handled in p
                pass

            elif tag_name == 'img':
                src = element.get('src', '')
                alt = element.get('alt', get_text(element))
                if src:
                    src = urljoin(base_url, src)
                    markdown_parts.append(f'![{alt}]({src})')

            elif tag_name == 'ul':
                for li in element.find_all('li', recursive=False):
                    text = get_text(li)
                    markdown_parts.append(f"- {text}\n")

            elif tag_name == 'ol':
                for idx, li in enumerate(element.find_all('li', recursive=False), 1):
                    text = get_text(li)
                    markdown_parts.append(f"{idx}. {text}\n")

            elif tag_name == 'blockquote':
                text = get_text(element)
                if text:
                    for line in text.split('\n'):
                        markdown_parts.append(f"> {line}\n")

            elif tag_name == 'pre':
                code = element.get_text()
                if code:
                    markdown_parts.append(f"\n```\n{code}\n```\n")

            elif tag_name == 'code' and element.parent.name != 'pre':
                code = element.get_text(strip=True)
                if code:
                    markdown_parts.append(f'`{code}`')

            elif tag_name == 'table':
                rows = element.find_all('tr')
                if rows:
                    markdown_parts.append("\n")
                    for row_idx, row in enumerate(rows):
                        cells = row.find_all(['th', 'td'])
                        cell_texts = []
                        for cell in cells:
                            cell_texts.append(get_text(cell))
                        markdown_parts.append('| ' + ' | '.join(cell_texts) + ' |\n')
                        if row_idx == 0:
                            markdown_parts.append('| ' + ' | '.join(['---'] * len(cells)) + ' |\n')

            elif tag_name == 'br':
                markdown_parts.append("\n")

            elif tag_name == 'hr':
                markdown_parts.append("\n---\n")

            elif tag_name in ('strong', 'b'):
                text = get_text(element)
                if text:
                    markdown_parts.append(f"**{text}**")

            elif tag_name in ('em', 'i'):
                text = get_text(element)
                if text:
                    markdown_parts.append(f"*{text}*")
            
            elif tag_name in ('div', 'span'):
                # 处理 div/span 中的文本，但避免重复
                text = get_text(element)
                if text and len(text) > 10:
                    # 检查是否已经有这个文本（避免重复）
                    if text not in ''.join(markdown_parts):
                        markdown_parts.append(text + "\n")

        result = ''.join(markdown_parts)

        # Clean up
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = result.strip()

        # 如果结果为空，返回纯文本
        if not result.strip():
            result = soup.get_text(separator=' ', strip=True)
            result = re.sub(r'\s+', ' ', result)

        # Limit length
        max_length = 100000
        if len(result) > max_length:
            result = result[:max_length] + f"\n\n... [Content truncated, total length: {len(result)} characters]"

        return result
