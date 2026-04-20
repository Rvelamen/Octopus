"""
Browser Tool Module for Octopus

Provides browser automation tools for the agent.
Supports navigation, interaction, and screenshot capabilities.

Tools:
- browser_navigate: Navigate to a URL
- browser_snapshot: Get page snapshot (accessibility tree)
- browser_click: Click an element
- browser_type: Type text into an element
- browser_get_text: Get text content of an element
- browser_execute_js: Execute JavaScript
- browser_screenshot: Take a screenshot
- browser_close: Close browser session

Usage:
    from backend.tools.browser import BrowserTool
    
    browser_tool = BrowserTool(workspace=workspace_path)
    browser_tool.register_tools()  # Register to ToolRegistry
"""

import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path

from loguru import logger

from .local_playwright import LocalPlaywrightBackend


class BrowserSessionManager:
    """Manages browser sessions with auto-cleanup."""
    
    def __init__(self, max_sessions: int = 10, session_timeout: int = 300):
        """
        Args:
            max_sessions: Maximum number of concurrent sessions
            session_timeout: Session timeout in seconds (5 min default)
        """
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session."""
        if len(self._sessions) >= self.max_sessions:
            # Cleanup expired sessions first
            self._cleanup_expired()
            
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError(f"Maximum sessions reached: {self.max_sessions}")
        
        session_data = {
            "session_id": session_id,
            "created_at": time.time(),
            "last_activity": time.time(),
            "status": "active",
        }
        
        self._sessions[session_id] = session_data
        logger.info(f"Created browser session: {session_id}")
        return session_data
    
    def update_activity(self, session_id: str) -> None:
        """Update session last activity time."""
        if session_id in self._sessions:
            self._sessions[session_id]["last_activity"] = time.time()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        return self._sessions.get(session_id)
    
    def close_session(self, session_id: str) -> bool:
        """Close a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Closed browser session: {session_id}")
            return True
        return False
    
    def cleanup_all(self) -> None:
        """Close all sessions."""
        self._sessions.clear()
        logger.info("All browser sessions cleaned up")
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, data in self._sessions.items()
            if (now - data["last_activity"]) > self.session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]
            logger.info(f"Cleaned up expired session: {sid}")


class BrowserTool:
    """Browser automation tool for Octopus agent.
    
    Provides browser automation capabilities via Playwright.
    """
    
    def __init__(self, workspace: Optional[Path] = None, headless: bool = True):
        """
        Args:
            workspace: Workspace path (for screenshot storage)
            headless: Run browser in headless mode
        """
        self.workspace = workspace
        self.headless = headless
        self._backend: Optional[LocalPlaywrightBackend] = None
        self._session_manager = BrowserSessionManager()
        self._initialized = False
    
    async def _ensure_initialized(self) -> None:
        """Ensure browser backend is initialized."""
        if not self._initialized:
            self._backend = LocalPlaywrightBackend(headless=self.headless)
            await self._backend.initialize()
            self._initialized = True
    
    async def browser_navigate(self, url: str, session_id: str = "") -> str:
        """Navigate to a URL in the browser.
        
        Args:
            url: URL to navigate to
            session_id: Session ID (auto-generated if empty or invalid)
            
        Returns:
            JSON result string including session_id
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            # Create session if needed (including when session_id is empty or not found)
            if not session_id:
                session_id = f"browser_{int(time.time())}"
            if not self._session_manager.get_session(session_id):
                self._session_manager.create_session(session_id)
                await self._backend.create_session(session_id)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.navigate(session_id, url)
            # Include session_id in the result so LLM can use it for subsequent operations
            result["session_id"] = session_id
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_navigate failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Navigation failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_snapshot(self, session_id: str) -> str:
        """Get page snapshot (accessibility tree).
        
        Args:
            session_id: Active session ID
            
        Returns:
            JSON result string with snapshot
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.get_snapshot(session_id)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_snapshot failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Snapshot failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_click(self, element_ref: str, session_id: str) -> str:
        """Click an element on the page.
        
        Args:
            element_ref: Element reference (@e5 or CSS selector)
            session_id: Active session ID
            
        Returns:
            JSON result string
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.click(session_id, element_ref)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_click failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Click failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_type(self, element_ref: str, text: str, session_id: str) -> str:
        """Type text into an element.
        
        Args:
            element_ref: Element reference (@e5 or CSS selector)
            text: Text to type
            session_id: Active session ID
            
        Returns:
            JSON result string
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.type_text(session_id, element_ref, text)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_type failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Type text failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_get_text(self, element_ref: str, session_id: str) -> str:
        """Get text content of an element.
        
        Args:
            element_ref: Element reference (@e5 or CSS selector)
            session_id: Active session ID
            
        Returns:
            JSON result string with text content
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.get_text(session_id, element_ref)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_get_text failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Get text failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_execute_js(self, script: str, session_id: str) -> str:
        """Execute JavaScript on the page.
        
        Args:
            script: JavaScript code to execute
            session_id: Active session ID
            
        Returns:
            JSON result string
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.execute_js(session_id, script)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_execute_js failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "JavaScript execution failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_screenshot(self, session_id: str, full_page: bool = False) -> str:
        """Take a screenshot of the page.
        
        Args:
            session_id: Active session ID
            full_page: Whether to capture full page
            
        Returns:
            JSON result string with screenshot (base64)
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            if not self._session_manager.get_session(session_id):
                return json.dumps({
                    "success": False,
                    "error": "Session not found",
                    "message": f"Session {session_id} does not exist",
                }, ensure_ascii=False, indent=2)
            
            self._session_manager.update_activity(session_id)
            
            result = await self._backend.screenshot(session_id, full_page)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_screenshot failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Screenshot failed",
            }, ensure_ascii=False, indent=2)
    
    async def browser_close(self, session_id: str) -> str:
        """Close a browser session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            JSON result string
        """
        import json
        
        try:
            await self._ensure_initialized()
            
            # Close backend session
            if self._backend:
                await self._backend.close_session(session_id)
            
            # Close session manager
            self._session_manager.close_session(session_id)
            
            return json.dumps({
                "success": True,
                "message": f"Session {session_id} closed",
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"browser_close failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Close session failed",
            }, ensure_ascii=False, indent=2)
    
    async def cleanup_all(self) -> None:
        """Cleanup all browser sessions."""
        try:
            if self._backend:
                await self._backend.close_all()
            self._session_manager.cleanup_all()
            logger.info("All browser sessions cleaned up")
        except Exception as e:
            logger.error(f"cleanup_all failed: {e}")
    
    def get_tool_definitions(self) -> list:
        """Get tool definitions for LLM function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_navigate",
                    "description": "Navigate to a URL in the browser. Creates a new session if session_id is not provided or invalid. Returns a session_id that MUST be used for all subsequent browser operations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to navigate to"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session ID (optional, auto-generated if empty or invalid). Use the session_id returned by this tool for all subsequent browser operations."
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_snapshot",
                    "description": "Get page snapshot (accessibility tree). Returns text-based representation of the page with interactive elements. Must use the session_id returned by browser_navigate.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "Click an element on the page. Use element reference (@e5) or CSS selector.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "element_ref": {
                                "type": "string",
                                "description": "Element reference (@e5 or CSS selector)"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["element_ref", "session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_type",
                    "description": "Type text into an element on the page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "element_ref": {
                                "type": "string",
                                "description": "Element reference (@e5 or CSS selector)"
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to type"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["element_ref", "text", "session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_get_text",
                    "description": "Get text content of an element.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "element_ref": {
                                "type": "string",
                                "description": "Element reference (@e5 or CSS selector)"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["element_ref", "session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_execute_js",
                    "description": "Execute JavaScript on the page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "script": {
                                "type": "string",
                                "description": "JavaScript code to execute"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["script", "session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_screenshot",
                    "description": "Take a screenshot of the page. Returns base64-encoded image.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Active session ID (use the value returned by browser_navigate)"
                            },
                            "full_page": {
                                "type": "boolean",
                                "description": "Whether to capture full page (default: false)"
                            }
                        },
                        "required": ["session_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_close",
                    "description": "Close a browser session and cleanup resources.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Session ID to close (use the value returned by browser_navigate)"
                            }
                        },
                        "required": ["session_id"]
                    }
                }
            },
        ]
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Execute a browser tool by name.
        
        Args:
            tool_name: Tool name to execute
            params: Tool parameters
            
        Returns:
            JSON result string
        """
        tool_map = {
            "browser_navigate": lambda: self.browser_navigate(**params),
            "browser_snapshot": lambda: self.browser_snapshot(**params),
            "browser_click": lambda: self.browser_click(**params),
            "browser_type": lambda: self.browser_type(**params),
            "browser_get_text": lambda: self.browser_get_text(**params),
            "browser_execute_js": lambda: self.browser_execute_js(**params),
            "browser_screenshot": lambda: self.browser_screenshot(**params),
            "browser_close": lambda: self.browser_close(**params),
        }
        
        if tool_name not in tool_map:
            import json
            return json.dumps({
                "success": False,
                "error": f"Unknown browser tool: {tool_name}",
            }, ensure_ascii=False, indent=2)
        
        try:
            return await tool_map[tool_name]()
        except Exception as e:
            import json
            logger.error(f"execute_tool {tool_name} failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
            }, ensure_ascii=False, indent=2)
