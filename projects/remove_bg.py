import sys
import io
from rembg import remove
from PIL import Image

in_path = r'C:\Users\ivan\.gemini\antigravity\brain\39a3633e-05ea-4e7b-87b0-7b91b4c08de7\hypertracker_logo_1774466317364.png'
out_path = r'C:\Users\ivan\Desktop\TradingView\projects\hypertracker.ico'

print("Reading input image...")
with open(in_path, 'rb') as i:
    input_data = i.read()

print("Removing background (this might download models on first run)...")
output_data = remove(input_data)

print("Converting to ICO and saving...")
img = Image.open(io.BytesIO(output_data))
img.save(out_path, format='ICO', sizes=[(256, 256)])

print("Done!")
