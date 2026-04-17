"""Captura screenshot del chart de TradingView via CDP (puerto 9222)."""
import json
import http.client
import base64
import asyncio
import sys
import os

CDP_PORT = 9222
OUTPUT_PATH = r"C:\Users\ivan\AppData\Roaming\Hypertracker\tv_chart.png"

def get_chart_target():
    conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=5)
    conn.request("GET", "/json")
    targets = json.loads(conn.getresponse().read().decode())
    conn.close()
    
    # Preferir targets con "chart" en la URL
    for t in targets:
        if t.get("type") == "page" and "chart" in t.get("url", ""):
            return t
    # Fallback: primer page
    for t in targets:
        if t.get("type") == "page":
            return t
    return None

async def capture_screenshot(ws_url):
    try:
        import websockets
    except ImportError:
        os.system("pip install websockets")
        import websockets
    
    async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
        msg = json.dumps({
            "id": 1,
            "method": "Page.captureScreenshot",
            "params": {"format": "png"}
        })
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        
        if "result" in resp and "data" in resp["result"]:
            img_data = base64.b64decode(resp["result"]["data"])
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "wb") as f:
                f.write(img_data)
            return len(img_data)
        else:
            print(f"CDP error: {resp}", file=sys.stderr)
            return 0

def main():
    target = get_chart_target()
    if not target:
        print("ERROR: No se encontro target de TradingView en CDP")
        return 1
    
    print(f"Target: {target.get('title', 'N/A')[:60]}")
    print(f"URL: {target.get('url', 'N/A')}")
    
    ws_url = target.get("webSocketDebuggerUrl", "")
    if not ws_url:
        print("ERROR: No webSocketDebuggerUrl disponible")
        return 1
    
    size = asyncio.run(capture_screenshot(ws_url))
    if size > 0:
        print(f"Screenshot OK: {OUTPUT_PATH} ({size:,} bytes)")
        return 0
    else:
        print("ERROR: No se pudo capturar screenshot")
        return 1

if __name__ == "__main__":
    sys.exit(main())
