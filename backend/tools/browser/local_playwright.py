"""
Local Playwright browser backend.

Uses Playwright to control a local Chromium browser instance.
Provides session isolation via separate browser contexts.
"""

import asyncio
import time
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger

from .base import BrowserBackend

# Try to import playwright
try:
    from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(
        "Playwright not available. Install with: pip install playwright && playwright install chromium"
    )


class LocalPlaywrightBackend(BrowserBackend):
    """Local browser backend using Playwright for Chromium control.
    
    Features:
    - Session isolation via browser contexts
    - Headless mode by default
    - Accessibility tree snapshots
    - Auto-cleanup on shutdown
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for operations (ms)
        """
        self.headless = headless
        self.timeout = timeout
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> {context, page, ...}
    
    async def initialize(self) -> None:
        """Initialize Playwright browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        
        if self._browser:
            return
        
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            logger.info("Local Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new browser session with isolated context."""
        if not self._browser:
            await self.initialize()
        
        if session_id in self._sessions:
            logger.warning(f"Session {session_id} already exists, closing first")
            await self.close_session(session_id)
        
        try:
            # Create isolated browser context
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            
            # Create new page
            page = await context.new_page()
            page.set_default_timeout(self.timeout)
            
            session_data = {
                "session_id": session_id,
                "context": context,
                "page": page,
                "created_at": time.time(),
                "status": "active",
                "last_activity": time.time(),
            }
            
            self._sessions[session_id] = session_data
            logger.info(f"Created browser session: {session_id}")
            
            return {
                "session_id": session_id,
                "created_at": session_data["created_at"],
                "status": "active",
            }
            
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            raise
    
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session."""
        if session_id not in self._sessions:
            logger.warning(f"Session {session_id} not found")
            return False
        
        try:
            session_data = self._sessions[session_id]
            context = session_data.get("context")
            
            if context:
                await context.close()
            
            del self._sessions[session_id]
            logger.info(f"Closed browser session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            return False
    
    async def navigate(self, session_id: str, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None,
                "message": f"Navigated to {url}",
            }
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to navigate to {url}",
            }
    
    async def get_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Get page snapshot as accessibility tree."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            # Get accessibility tree snapshot
            snapshot = await page.accessibility.snapshot(interesting_only=True)
            
            # Get page info
            url = page.url
            title = await page.title()
            
            # Extract interactive elements
            elements = await self._extract_elements(page)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "snapshot": self._format_snapshot(snapshot),
                "elements": elements,
                "element_count": len(elements),
            }
        except Exception as e:
            logger.error(f"Snapshot failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get page snapshot",
            }
    
    async def click(self, session_id: str, element_ref: str) -> Dict[str, Any]:
        """Click an element by reference or selector."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            selector = self._resolve_element_ref(element_ref)
            await page.click(selector, timeout=self.timeout)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "message": f"Clicked element: {element_ref}",
                "selector": selector,
            }
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to click element: {element_ref}",
            }
    
    async def type_text(self, session_id: str, element_ref: str, text: str) -> Dict[str, Any]:
        """Type text into an element."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            selector = self._resolve_element_ref(element_ref)
            await page.fill(selector, text, timeout=self.timeout)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "message": f"Typed text into element: {element_ref}",
                "selector": selector,
            }
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to type text into element: {element_ref}",
            }
    
    async def get_text(self, session_id: str, element_ref: str) -> Dict[str, Any]:
        """Get text content of an element."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            selector = self._resolve_element_ref(element_ref)
            element = page.locator(selector)
            text = await element.inner_text(timeout=self.timeout)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "text": text,
                "selector": selector,
            }
        except Exception as e:
            logger.error(f"Get text failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to get text from element: {element_ref}",
            }
    
    async def execute_js(self, session_id: str, script: str) -> Dict[str, Any]:
        """Execute JavaScript on the page."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            result = await page.evaluate(script)
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "result": result,
                "message": "JavaScript executed successfully",
            }
        except Exception as e:
            logger.error(f"JavaScript execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to execute JavaScript",
            }
    
    async def screenshot(self, session_id: str, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot of the page."""
        session_data = self._get_session(session_id)
        page = session_data["page"]
        
        try:
            # Create temp file for screenshot
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                screenshot_path = f.name
            
            # Take screenshot
            await page.screenshot(
                path=screenshot_path,
                full_page=full_page,
                timeout=self.timeout,
            )
            
            # Read and encode as base64
            with open(screenshot_path, "rb") as f:
                screenshot_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Clean up temp file
            Path(screenshot_path).unlink()
            
            session_data["last_activity"] = time.time()
            
            return {
                "success": True,
                "screenshot_base64": screenshot_data,
                "full_page": full_page,
                "message": "Screenshot taken successfully",
            }
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to take screenshot",
            }
    
    async def close_all(self) -> None:
        """Close all browser sessions and cleanup."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        
        if self._browser:
            await self._browser.close()
        
        if self._playwright:
            await self._playwright.stop()
        
        logger.info("All browser sessions closed")
    
    # --- Private helpers ---
    
    def _get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session data or raise error."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        return self._sessions[session_id]
    
    def _format_snapshot(self, snapshot: dict, indent: int = 0) -> str:
        """Format accessibility tree snapshot as text."""
        if not snapshot:
            return ""
        
        lines = []
        prefix = "  " * indent
        
        # Add element info
        role = snapshot.get("role", "")
        name = snapshot.get("name", "")
        if name:
            lines.append(f"{prefix}[{role}] {name}")
        else:
            lines.append(f"{prefix}[{role}]")
        
        # Add children
        for child in snapshot.get("children", []):
            lines.append(self._format_snapshot(child, indent + 1))
        
        return "\n".join(lines)
    
    async def _extract_elements(self, page: Page) -> list:
        """Extract interactive elements from page."""
        try:
            elements = await page.evaluate("""
                () => {
                    const selectors = ['a', 'button', 'input', 'select', 'textarea', '[role="button"]', '[role="link"]'];
                    const elements = [];
                    
                    document.querySelectorAll(selectors.join(', ')).forEach((el, idx) => {
                        const ref = `@e${idx}`;
                        const rect = el.getBoundingClientRect();
                        
                        elements.push({
                            ref: ref,
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim()?.substring(0, 100) || '',
                            type: el.type || '',
                            href: el.href || '',
                            visible: rect.width > 0 && rect.height > 0,
                        });
                    });
                    
                    return elements;
                }
            """)
            return elements
        except Exception as e:
            logger.error(f"Failed to extract elements: {e}")
            return []
    
    def _resolve_element_ref(self, element_ref: str) -> str:
        """Resolve element reference to CSS selector.
        
        Supports:
        - @e5 format: element index reference
        - Direct CSS selectors
        - XPath (starting with //)
        """
        # If it's a direct selector or xpath, use as-is
        if element_ref.startswith("//") or element_ref.startswith("#") or element_ref.startswith("."):
            return element_ref
        
        # If it's @eN format, convert to nth-of-type selector
        match = __import__('re').match(r'@e(\d+)', element_ref)
        if match:
            idx = int(match.group(1))
            # This is a simplified version - in practice you'd map @eN to actual elements
            return f":nth-match(:is(a, button, input, select, textarea), {idx + 1})"
        
        # Default: treat as CSS selector
        return element_ref
