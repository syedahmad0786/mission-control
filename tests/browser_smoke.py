import os
from playwright.sync_api import sync_playwright

url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width, height in ((1280, 800), (390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(url, wait_until="networkidle")
        assert page.locator("main").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert not errors, errors
        page.close()
    browser.close()
