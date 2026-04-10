"""
Browser backend base interface.

Defines the abstract interface for browser backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BrowserBackend(ABC):
    """Abstract interface for browser backends.
    
    Implementations can include:
    - LocalPlaywrightBackend: Local browser control via Playwright
    - CloudBrowserBackend: Cloud browser services (Browserbase, etc.)
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the browser backend.
        
        Should be called once before creating sessions.
        """
    
    @abstractmethod
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new browser session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session metadata dict with at least:
            {
                "session_id": str,
                "created_at": float,
                "status": "active"
            }
        """
    
    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session.
        
        Args:
            session_id: Session to close
            
        Returns:
            True if successfully closed
        """
    
    @abstractmethod
    async def navigate(self, session_id: str, url: str) -> Dict[str, Any]:
        """Navigate to a URL.
        
        Args:
            session_id: Active session ID
            url: URL to navigate to
            
        Returns:
            Result dict with status and page info
        """
    
    @abstractmethod
    async def get_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Get page snapshot (accessibility tree).
        
        Returns a text-based representation of the page using
        accessibility tree, suitable for LLM consumption.
        
        Args:
            session_id: Active session ID
            
        Returns:
            Snapshot dict with:
            {
                "url": str,
                "title": str,
                "snapshot": str,  # Text representation
                "elements": list  # Interactive elements
            }
        """
    
    @abstractmethod
    async def click(self, session_id: str, element_ref: str) -> Dict[str, Any]:
        """Click an element by reference.
        
        Args:
            session_id: Active session ID
            element_ref: Element reference (e.g., "@e5" or selector)
            
        Returns:
            Result dict with status
        """
    
    @abstractmethod
    async def type_text(self, session_id: str, element_ref: str, text: str) -> Dict[str, Any]:
        """Type text into an element.
        
        Args:
            session_id: Active session ID
            element_ref: Element reference
            text: Text to type
            
        Returns:
            Result dict with status
        """
    
    @abstractmethod
    async def get_text(self, session_id: str, element_ref: str) -> Dict[str, Any]:
        """Get text content of an element.
        
        Args:
            session_id: Active session ID
            element_ref: Element reference
            
        Returns:
            Result dict with text content
        """
    
    @abstractmethod
    async def execute_js(self, session_id: str, script: str) -> Dict[str, Any]:
        """Execute JavaScript on the page.
        
        Args:
            session_id: Active session ID
            script: JavaScript code to execute
            
        Returns:
            Result dict with execution result
        """
    
    @abstractmethod
    async def screenshot(self, session_id: str, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot of the page.
        
        Args:
            session_id: Active session ID
            full_page: Whether to capture full page or viewport
            
        Returns:
            Result dict with screenshot data (base64 or file path)
        """
    
    @abstractmethod
    async def close_all(self) -> None:
        """Close all browser sessions and cleanup.
        
        Called during shutdown.
        """
