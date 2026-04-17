from playwright.sync_api import sync_playwright
import sys

def take_snapshot():
    path = "C:\\Users\\ivan\\Desktop\\TradingView\\live-chart.png"
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            # Podría haber múltiples páginas en TV, buscamos la que tenga 'chart'
            target_page = context.pages[0]
            for page in context.pages:
                if "chart" in page.url or "tradingview" in page.url:
                    target_page = page
                    break
            
            # Tomar screenshot a pantalla completa
            target_page.screenshot(path=path, full_page=True)
            print(f"OK: {path}")
            browser.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    take_snapshot()
