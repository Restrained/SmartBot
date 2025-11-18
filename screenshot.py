from playwright.sync_api import sync_playwright
import math
import time

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 1080})
    page.goto("http://127.0.0.1:5000", wait_until="networkidle")

    total_height = page.evaluate("document.body.scrollHeight")
    viewport_height = page.viewport_size["height"]
    segments = math.ceil(total_height / viewport_height)

    print(f"页面总高度: {total_height}px, 分为 {segments} 段截图")

    for i in range(segments):
        y = i * viewport_height
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(0.5)
        filename = f"screenshot_part_{i+1}.png"
        page.screenshot(path=filename)
        print(f"已截图: {filename}")

    browser.close()
