import requests
import json

# Lista de las 3 claves API proporcionadas por el usuario
API_KEYS = [
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjIxMTgsIm1pZCI6MjEzNzc1LCJpYXQiOjE3NzM3NTY1MDN9.1grAwC6A89lyR83cBOwtKbYCT3_zOTZ76wJf2X5XwOM", # Clave 1
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjQsIm1pZCI6MjI3NTM4LCJpYXQiOjE3NzM3NzM0Mzd9.S3EiENLZukTJHn6qClx9Tl1oHcGjPnQOpiv95SDrbTo", # Clave 2
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjUsIm1pZCI6MjI3NTM5LCJpYXQiOjE3NzM3NzM2NTR9.mjJkUHKRSzSpN16281zGRr2fRAcPH82W0MhU3C2eEd0"  # Clave 3
]

BASE_URL = "https://ht-api.coinmarketman.com"

def test_api_key(index, key):
    print(f"\n--- Probando API Key #{index} ---")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Test endpoint simple (consume 1 peticion)
    url = f"{BASE_URL}/api/external/segments"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ ESTADO: VALIDA (200 OK)")
            return True
        elif response.status_code == 429:
            print(f"⚠️ ESTADO: LÍMITE ALCANZADO (429 Too Many Requests)")
            return False
        elif response.status_code == 401:
            print(f"❌ ESTADO: INVÁLIDA (401 Unauthorized)")
            return False
        else:
            print(f"❓ ESTADO: ERROR DESCONOCIDO ({response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ESTADO: ERROR DE CONEXIÓN - {e}")
        return False

print("Iniciando prueba de las 3 API Keys...")
for i, key in enumerate(API_KEYS, start=1):
    test_api_key(i, key)
print("\nPrueba completada.")
