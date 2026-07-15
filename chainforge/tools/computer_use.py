# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Computer Use tools — browser automation for agents.

Wraps Playwright for web navigation, form filling, screenshot, and data extraction.

Usage:
    from chainforge.tools.computer_use import PlaywrightTool

    browser = await PlaywrightTool.create(headless=True)
    result = await browser.navigate("https://example.com")
    text = await browser.get_text("h1")
    await browser.screenshot("page.png")
"""

from __future__ import annotations

from typing import Any

from chainforge.core.tool import ToolSpec, FunctionTool
from chainforge.logging import get_logger

logger = get_logger("tools.computer_use")


class PlaywrightTool:
    """Browser automation using Playwright.

    Requires: playwright install

    Usage:
        pwt = await PlaywrightTool.create(headless=True)
        await pwt.navigate("https://example.com")
        text = await pwt.get_text("h1")
        print(text)
        await pwt.close()
    """

    def __init__(self, browser=None, page=None):
        self._browser = browser
        self._page = page

    @classmethod
    async def create(cls, headless: bool = True, viewport: dict | None = None) -> "PlaywrightTool":
        """Create a PlaywrightTool with a new browser instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "PlaywrightTool requires `playwright`. Install: pip install playwright && playwright install"
            )

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(viewport=viewport or {"width": 1280, "height": 720})
        page = await ctx.new_page()
        return cls(browser=browser, page=page)

    async def navigate(self, url: str, timeout: int = 30000) -> str:
        """Navigate to a URL and return the page title."""
        if self._page is None:
            return "Error: browser not initialized"
        await self._page.goto(url, timeout=timeout, wait_until="networkidle")
        title = await self._page.title()
        logger.info(f"Navigated to {url}, title: {title}")
        return title

    async def get_text(self, selector: str) -> str:
        """Get text content of the first element matching selector."""
        if self._page is None:
            return "Error: browser not initialized"
        try:
            el = await self._page.wait_for_selector(selector, timeout=5000)
            if el:
                return await el.inner_text()
            return f"Element '{selector}' not found"
        except Exception as e:
            return f"Error finding '{selector}': {e}"

    async def click(self, selector: str) -> str:
        """Click an element by selector."""
        if self._page is None:
            return "Error: browser not initialized"
        try:
            await self._page.click(selector, timeout=5000)
            return f"Clicked '{selector}'"
        except Exception as e:
            return f"Error clicking '{selector}': {e}"

    async def fill(self, selector: str, value: str) -> str:
        """Fill a form field by selector."""
        if self._page is None:
            return "Error: browser not initialized"
        try:
            await self._page.fill(selector, value, timeout=5000)
            return f"Filled '{selector}' with '{value[:50]}...'"
        except Exception as e:
            return f"Error filling '{selector}': {e}"

    async def screenshot(self, path: str = "screenshot.png") -> str:
        """Take a screenshot and save to file."""
        if self._page is None:
            return "Error: browser not initialized"
        await self._page.screenshot(path=path, full_page=True)
        return f"Screenshot saved to {path}"

    async def get_html(self, selector: str = "body") -> str:
        """Get inner HTML of a selector."""
        if self._page is None:
            return "Error: browser not initialized"
        try:
            el = await self._page.wait_for_selector(selector, timeout=5000)
            if el:
                return await el.inner_html()
            return f"Element '{selector}' not found"
        except Exception as e:
            return f"Error: {e}"

    async def close(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()


def playwright_tools(headless: bool = True) -> list[FunctionTool]:
    """Create a set of Playwright-based browser tools.

    Returns [navigate, get_text, click, fill, screenshot] as FunctionTool list.
    The returned tools share a single browser instance.

    Usage:
        tools = playwright_tools()
        agent = Agent(llm=llm, tools=tools)
    """
    _instance: PlaywrightTool | None = None

    async def _ensure():
        nonlocal _instance
        if _instance is None:
            _instance = await PlaywrightTool.create(headless=headless)
        return _instance

    async def navigate(url: str) -> str:
        pwt = await _ensure()
        return await pwt.navigate(url)
    navigate.__doc__ = "Navigate to a URL and return page title"

    async def click(selector: str) -> str:
        pwt = await _ensure()
        return await pwt.click(selector)
    click.__doc__ = "Click an element matching CSS selector"

    async def fill(selector: str, value: str) -> str:
        pwt = await _ensure()
        return await pwt.fill(selector, value)
    fill.__doc__ = "Fill a form field with value"

    async def get_text(selector: str) -> str:
        pwt = await _ensure()
        return await pwt.get_text(selector)
    get_text.__doc__ = "Get text of first matching element"

    async def screenshot(path: str = "screenshot.png") -> str:
        pwt = await _ensure()
        return await pwt.screenshot(path)
    screenshot.__doc__ = "Capture page screenshot"

    async def get_html(selector: str = "body") -> str:
        pwt = await _ensure()
        return await pwt.get_html(selector)
    get_html.__doc__ = "Get inner HTML of element"

    return [
        FunctionTool(navigate),
        FunctionTool(click),
        FunctionTool(fill),
        FunctionTool(get_text),
        FunctionTool(screenshot),
        FunctionTool(get_html),
    ]
