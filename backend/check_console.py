from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda msg: print(f"Browser console: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"Browser error: {exc}"))
        
        print("Navigating to localhost:3000...")
        page.goto('http://localhost:3000', wait_until='networkidle')
        print("Done.")
        browser.close()

main()
