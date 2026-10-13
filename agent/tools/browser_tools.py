"""Playwright-based browser automation tools with ARIA snapshotting and screenshot tracking."""

import os
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from agent.tools.schemas import ToolResult


class BrowserSession:
    """Singleton managing a shared Playwright browser instance and page."""

    _instance: Optional["BrowserSession"] = None

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.run_id: str = "default_run"

    @classmethod
    def get_instance(cls) -> "BrowserSession":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_run_id(self, run_id: str) -> None:
        self.run_id = run_id

    def ensure_page(self) -> Page:
        if self.page is None or self.page.is_closed():
            if self.playwright is None:
                self.playwright = sync_playwright().start()
            if self.browser is None or not self.browser.is_connected():
                headless = os.environ.get("HEADLESS", "1") == "1"
                self.browser = self.playwright.chromium.launch(headless=headless)
            if self.context is None:
                self.context = self.browser.new_context(
                    viewport={"width": 1280, "height": 800},
                )
            self.page = self.context.new_page()
            self.page.set_default_timeout(10000)
        return self.page

    def close(self) -> None:
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        self.page = None


def browser_open(url: str) -> ToolResult:
    """Navigate to a URL."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()
        response = page.goto(url, wait_until="networkidle")
        status_code = response.status if response else 200
        current_url = page.url
        title = page.title()
        return ToolResult(
            ok=True,
            data={
                "url": current_url,
                "title": title,
                "status_code": status_code,
            },
        )
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to open URL '{url}': {str(e)}")


def browser_snapshot() -> ToolResult:
    """Capture current page DOM accessibility tree using aria_snapshot."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()
        # Use locator('body').aria_snapshot() per spec
        try:
            snapshot = page.locator("body").aria_snapshot()
        except Exception:
            snapshot = page.content()

        return ToolResult(
            ok=True,
            data={
                "url": page.url,
                "title": page.title(),
                "snapshot": snapshot,
            },
        )
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to capture snapshot: {str(e)}")


def browser_click(selector_or_text: str) -> ToolResult:
    """Click an element by ARIA role, selector, or visible text."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()

        # Try selector or text match
        if page.locator(selector_or_text).count() > 0:
            page.locator(selector_or_text).first.click()
        elif page.get_by_role("button", name=selector_or_text).count() > 0:
            page.get_by_role("button", name=selector_or_text).first.click()
        elif page.get_by_text(selector_or_text, exact=False).count() > 0:
            page.get_by_text(selector_or_text, exact=False).first.click()
        else:
            page.click(selector_or_text)

        # Wait briefly for potential navigation or dom updates
        page.wait_for_timeout(300)
        return ToolResult(ok=True, data={"clicked": selector_or_text, "current_url": page.url})
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to click '{selector_or_text}': {str(e)}")


def browser_type(target: str, text: str) -> ToolResult:
    """Type text into an input field identified by selector, label, or placeholder."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()

        if page.locator(target).count() > 0:
            loc = page.locator(target).first
        elif page.get_by_label(target, exact=False).count() > 0:
            loc = page.get_by_label(target, exact=False).first
        elif page.get_by_placeholder(target, exact=False).count() > 0:
            loc = page.get_by_placeholder(target, exact=False).first
        else:
            loc = page.locator(f"input[name='{target}'], textarea[name='{target}']").first

        loc.fill(text)
        return ToolResult(ok=True, data={"target": target, "typed_length": len(text)})
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to type into '{target}': {str(e)}")


def browser_select(target: str, value: str) -> ToolResult:
    """Select option by label or value in a dropdown select element."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()

        if page.locator(target).count() > 0:
            loc = page.locator(target).first
        elif page.get_by_label(target, exact=False).count() > 0:
            loc = page.get_by_label(target, exact=False).first
        else:
            loc = page.locator(f"select[name='{target}']").first

        loc.select_option(value=value)
        return ToolResult(ok=True, data={"target": target, "selected_value": value})
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to select '{value}' in '{target}': {str(e)}")


def browser_screenshot(label: str = "screenshot") -> ToolResult:
    """Capture screenshot and store under reports/screenshots/<run_id>/<timestamp>_<label>.png."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()

        run_id = session.run_id
        out_dir = Path("reports") / "screenshots" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{int(time.time())}_{label.replace(' ', '_')}.png"
        filepath = out_dir / filename
        page.screenshot(path=str(filepath))

        rel_path = str(filepath)
        return ToolResult(
            ok=True,
            data={"filepath": rel_path, "label": label, "run_id": run_id},
        )
    except Exception as e:
        return ToolResult(ok=False, error=f"Failed to take screenshot: {str(e)}")


def browser_wait_for(text: str, timeout_ms: int = 10000) -> ToolResult:
    """Wait for text to appear in current page viewport."""
    try:
        session = BrowserSession.get_instance()
        page = session.ensure_page()
        page.wait_for_selector(f"text={text}", timeout=timeout_ms)
        return ToolResult(ok=True, data={"found_text": text})
    except Exception as e:
        return ToolResult(ok=False, error=f"Timed out waiting for text '{text}': {str(e)}")
