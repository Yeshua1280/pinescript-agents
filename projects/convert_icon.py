import sys
from PIL import Image

in_path = r'C:\Users\ivan\.gemini\antigravity\brain\39a3633e-05ea-4e7b-87b0-7b91b4c08de7\hypertracker_logo_1774466317364.png'
out_path = r'C:\Users\ivan\Desktop\TradingView\projects\hypertracker.ico'

img = Image.open(in_path)
img.save(out_path, format='ICO', sizes=[(256, 256)])
print("Conversion successful.")
