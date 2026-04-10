"""
Browser Automation Tools for Octopus

Provides browser automation capabilities using Playwright.
Supports local browser control with session management.

Features:
- Navigate to URLs
- Take snapshots (accessibility tree)
- Interact with page elements (click, type, select)
- Execute JavaScript
- Take screenshots
- Session management with auto-cleanup

Usage:
    from backend.tools.browser import BrowserTool
    
    browser = BrowserTool()
    session = browser.create_session(task_id="task_123")
    result = browser.navigate("https://example.com", session_id=session["session_id"])
    snapshot = browser.get_snapshot(session_id=session["session_id"])
"""

from .tool import BrowserTool

__all__ = ["BrowserTool"]
