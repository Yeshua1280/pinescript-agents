import requests
import json
from pprint import pprint

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjIxMTgsIm1pZCI6MjEzNzc1LCJpYXQiOjE3NzM3NTY1MDN9.1grAwC6A89lyR83cBOwtKbYCT3_zOTZ76wJf2X5XwOM"
BASE_URL = "https://ht-api.coinmarketman.com"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def analyze_btc_heatmap():
    url = f"{BASE_URL}/api/external/positions/heatmap?openedWithin=all"
    response = requests.get(url, headers=HEADERS, timeout=10)
    data = response.json()
    
    btc_data = next((item for item in data['heatmap'] if item['coin'] == 'BTC'), None)
    
    if not btc_data:
        print("No BTC data found in heatmap.")
        return
        
    print(f"BTC Global Data:")
    print(f"  Total Value: ${btc_data['totalValue']:,.2f}")
    print(f"  Long Value:  ${btc_data['totalLongValue']:,.2f}")
    print(f"  Short Value: ${btc_data['totalShortValue']:,.2f}")
    print(f"  Global Bias: {(btc_data['totalLongValue'] / btc_data['totalValue']) * 100:.2f}% Long")
    
    # Get segment definitions
    seg_url = f"{BASE_URL}/api/external/segments"
    seg_response = requests.get(seg_url, headers=HEADERS, timeout=10)
    segments_info = {seg['id']: seg['name'] for seg in seg_response.json()}
    
    print("\nBTC Data by Cohort:")
    for seg in btc_data.get('segments', []):
        seg_id = seg['segmentId']
        seg_name = segments_info.get(seg_id, f"Unknown ({seg_id})")
        bias_pct = seg['bias'] * 100
        print(f"  {seg_name:<15}: {bias_pct:>6.2f}% Bias | Value: ${seg['totalValue']:,.2f}")

analyze_btc_heatmap()
