import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path("/Users/flyingship/development/TTR image/event category")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:3000/zh/debug/motifs", wait_until="networkidle")
    
    # Wait for the elements to render
    page.wait_for_selector(".thumbnail")
    
    thumbnails = page.locator(".thumbnail").all()
    count = 0
    for thumb in thumbnails:
        name = thumb.get_attribute("data-name")
        if name:
            filepath = OUT_DIR / f"{name}.png"
            thumb.screenshot(path=filepath, omit_background=True)
            print(f"Saved {filepath}")
            count += 1
            
    print(f"Successfully saved {count} motif thumbnails.")
    browser.close()
