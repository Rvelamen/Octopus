"""
Test suite for Browser Automation Tools.

Tests the browser automation module including:
- Browser session management
- Navigation
- Snapshots
- Element interaction (click, type, get_text)
- JavaScript execution
- Screenshots
- Cleanup

Run with:
    pytest tests/test_browser_tool.py -v
    pytest tests/test_browser_tool.py::test_browser_navigate -v
"""

import asyncio
import json
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.tools.browser.tool import BrowserTool
from backend.tools.browser.local_playwright import LocalPlaywrightBackend


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def browser_tool():
    """Create browser tool instance for testing."""
    tool = BrowserTool(headless=True)
    yield tool
    # Cleanup
    await tool.cleanup_all()


class TestBrowserToolRegistration:
    """Test browser tool registration."""
    
    def test_get_tool_definitions(self, event_loop):
        """Test that tool definitions are generated correctly."""
        async def run_test():
            tool = BrowserTool()
            definitions = tool.get_tool_definitions()
            
            assert len(definitions) == 8, "Should have 8 browser tools"
            
            # Check expected tools exist
            tool_names = [d["function"]["name"] for d in definitions]
            expected_tools = [
                "browser_navigate",
                "browser_snapshot",
                "browser_click",
                "browser_type",
                "browser_get_text",
                "browser_execute_js",
                "browser_screenshot",
                "browser_close",
            ]
            
            for expected in expected_tools:
                assert expected in tool_names, f"Missing tool: {expected}"
            
            # Check schema structure
            for tool_def in definitions:
                assert "function" in tool_def
                assert "name" in tool_def["function"]
                assert "description" in tool_def["function"]
                assert "parameters" in tool_def["function"]
        
        event_loop.run_until_complete(run_test())


class TestBrowserSessionManagement:
    """Test browser session management."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_create_session(self, event_loop, browser_tool):
        """Test creating a browser session."""
        async def run_test():
            session_id = "test_session_001"
            
            # Navigate to create session
            result = await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            
        event_loop.run_until_complete(run_test())
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_close_session(self, event_loop, browser_tool):
        """Test closing a browser session."""
        async def run_test():
            session_id = "test_session_002"
            
            # Create session
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Close session
            result = await browser_tool.browser_close(session_id=session_id)
            result_data = json.loads(result)
            
            assert result_data["success"] is True
        
        event_loop.run_until_complete(run_test())


class TestBrowserNavigation:
    """Test browser navigation."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_navigate_to_url(self, event_loop, browser_tool):
        """Test navigating to a URL."""
        async def run_test():
            session_id = "test_nav_001"
            url = "https://example.com"
            
            result = await browser_tool.browser_navigate(
                url=url,
                session_id=session_id
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert "example.com" in result_data.get("url", "")
        
        event_loop.run_until_complete(run_test())
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_navigate_invalid_url(self, event_loop, browser_tool):
        """Test navigating to an invalid URL."""
        async def run_test():
            session_id = "test_nav_002"
            url = "not-a-valid-url"
            
            result = await browser_tool.browser_navigate(
                url=url,
                session_id=session_id
            )
            
            result_data = json.loads(result)
            # Should handle gracefully (may fail or succeed depending on URL parsing)
            assert "message" in result_data or "error" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserSnapshot:
    """Test browser snapshot functionality."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_get_snapshot(self, event_loop, browser_tool):
        """Test getting page snapshot."""
        async def run_test():
            session_id = "test_snapshot_001"
            
            # Navigate first
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Get snapshot
            result = await browser_tool.browser_snapshot(session_id=session_id)
            result_data = json.loads(result)
            
            assert result_data["success"] is True
            assert "snapshot" in result_data
            assert "elements" in result_data
            assert "url" in result_data
            assert "title" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserInteraction:
    """Test browser element interaction."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_click_element(self, event_loop, browser_tool):
        """Test clicking an element."""
        async def run_test():
            session_id = "test_click_001"
            
            # Navigate to a page with elements
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Try to click (may not exist, should handle gracefully)
            result = await browser_tool.browser_click(
                element_ref="a",  # CSS selector
                session_id=session_id
            )
            
            result_data = json.loads(result)
            # Should handle gracefully (success or proper error)
            assert "success" in result_data or "error" in result_data
        
        event_loop.run_until_complete(run_test())
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_type_text(self, event_loop, browser_tool):
        """Test typing into an element."""
        async def run_test():
            session_id = "test_type_001"
            
            # Navigate to a page with input field
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Try to type (may not have input, should handle gracefully)
            result = await browser_tool.browser_type(
                element_ref="input",
                text="Hello World",
                session_id=session_id
            )
            
            result_data = json.loads(result)
            # Should handle gracefully
            assert "success" in result_data or "error" in result_data
        
        event_loop.run_until_complete(run_test())
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_get_text(self, event_loop, browser_tool):
        """Test getting element text."""
        async def run_test():
            session_id = "test_gettext_001"
            
            # Navigate to a page
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Get text from h1 element
            result = await browser_tool.browser_get_text(
                element_ref="h1",
                session_id=session_id
            )
            
            result_data = json.loads(result)
            # Should handle gracefully
            assert "success" in result_data or "error" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserJavaScript:
    """Test JavaScript execution."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_execute_js(self, event_loop, browser_tool):
        """Test executing JavaScript."""
        async def run_test():
            session_id = "test_js_001"
            
            # Navigate first
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Execute simple JS
            result = await browser_tool.browser_execute_js(
                script="document.title",
                session_id=session_id
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert "result" in result_data
        
        event_loop.run_until_complete(run_test())
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_execute_js_with_error(self, event_loop, browser_tool):
        """Test executing JavaScript with error."""
        async def run_test():
            session_id = "test_js_002"
            
            # Navigate first
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Execute JS with error
            result = await browser_tool.browser_execute_js(
                script="throw new Error('Test error')",
                session_id=session_id
            )
            
            result_data = json.loads(result)
            # Should return error gracefully
            assert "success" in result_data or "error" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserScreenshot:
    """Test browser screenshot."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_screenshot(self, event_loop, browser_tool):
        """Test taking a screenshot."""
        async def run_test():
            session_id = "test_screenshot_001"
            
            # Navigate first
            await browser_tool.browser_navigate(
                url="https://example.com",
                session_id=session_id
            )
            
            # Take screenshot
            result = await browser_tool.browser_screenshot(
                session_id=session_id,
                full_page=False
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert "screenshot_base64" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserErrorHandling:
    """Test error handling."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_session_not_found(self, event_loop, browser_tool):
        """Test handling of non-existent session."""
        async def run_test():
            result = await browser_tool.browser_snapshot(
                session_id="nonexistent_session"
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is False
            assert "error" in result_data
        
        event_loop.run_until_complete(run_test())
    
    def test_invalid_json_parameters(self, event_loop):
        """Test handling of invalid parameters."""
        async def run_test():
            tool = BrowserTool()
            
            # Try to execute tool with invalid parameters
            result = await tool.execute_tool(
                tool_name="browser_navigate",
                params={}  # Missing required 'url' parameter
            )
            
            result_data = json.loads(result)
            # Should handle gracefully
            assert "error" in result_data or "success" in result_data
        
        event_loop.run_until_complete(run_test())


class TestBrowserCleanup:
    """Test browser cleanup."""
    
    @pytest.mark.skip(reason="Requires Playwright installation")
    def test_cleanup_all(self, event_loop, browser_tool):
        """Test cleaning up all browser sessions."""
        async def run_test():
            # Create multiple sessions
            for i in range(3):
                await browser_tool.browser_navigate(
                    url="https://example.com",
                    session_id=f"cleanup_test_{i}"
                )
            
            # Cleanup all
            await browser_tool.cleanup_all()
            
            # Should complete without error
            assert True
        
        event_loop.run_until_complete(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
