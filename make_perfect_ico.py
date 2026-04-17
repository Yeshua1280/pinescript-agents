import urllib.request
from PIL import Image, ImageDraw

url = 'https://github.com/tradingview.png'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

with urllib.request.urlopen(req) as r:
    img = Image.open(r).convert("RGBA")

CANVAS = 256

# ===================================================================
# 125x125 es el tamano opticamente equivalente a Hypertracker/Inscribe
# segun pruebas del 11-Abril-2026. El truco anti-crop de Windows es
# un borde fantasma al 1% opacidad que extiende el bounding box.
# ===================================================================
logo_size = 200
radius = 44  # esquinas redondeadas del logo cuadrado

img = img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

# Mascara con esquinas redondeadas
mask = Image.new('L', (logo_size, logo_size), 0)
draw = ImageDraw.Draw(mask)
draw.rounded_rectangle((0, 0, logo_size - 1, logo_size - 1), radius=radius, fill=255)
img.putalpha(mask)

# Canvas transparente 256x256, logo centrado
canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
offset = (CANVAS - logo_size) // 2
canvas.paste(img, (offset, offset), img)

# Anti-crop: borde fantasma casi invisible en el perimetro completo
# Esto le dice a Windows que el bounding box es 256x256, no solo el logo
ghost = ImageDraw.Draw(canvas)
# Linea superior e inferior a 1% opacidad
for x in range(CANVAS):
    canvas.putpixel((x, 0), (0, 0, 0, 3))
    canvas.putpixel((x, CANVAS - 1), (0, 0, 0, 3))
# Linea izquierda y derecha a 1% opacidad
for y in range(CANVAS):
    canvas.putpixel((0, y), (0, 0, 0, 3))
    canvas.putpixel((CANVAS - 1, y), (0, 0, 0, 3))

output = r'C:\Users\ivan\Desktop\TradingView\tv_perfect.ico'

# Exportar TODAS las resoluciones estandar para que Windows no interpole mal
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
frames = []
for sz in sizes:
    frame = canvas.resize(sz, Image.Resampling.LANCZOS)
    frames.append(frame)

frames[0].save(output, format='ICO', sizes=sizes, append_images=frames[1:])
print(f"Icono guardado en: {output}")
print(f"Logo: {logo_size}x{logo_size}, Canvas: {CANVAS}x{CANVAS}")
print(f"Resoluciones: {[f'{s[0]}x{s[1]}' for s in sizes]}")
