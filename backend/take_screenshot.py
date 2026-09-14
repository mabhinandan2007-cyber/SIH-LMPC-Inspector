from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('http://localhost:3000', timeout=60000)
    page.wait_for_timeout(10000)
    page.evaluate("() => { const tabs = document.querySelectorAll('button'); for(let t of tabs) { if(t.innerText.includes('Review Queue')) t.click(); } }")
    page.wait_for_timeout(2000)
    page.screenshot(path='../storage/review_queue.png')
    browser.close()
