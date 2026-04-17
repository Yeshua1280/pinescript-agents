import os
from PIL import Image
from PyInstaller.utils.win32.icon import CopyIcons

source_ico = r"C:\Users\ivan\Desktop\TradingView\inscribe_extracted.ico"
target_exe = r"C:\Users\ivan\Desktop\Inscribe System.exe"
perfect_ico = r"C:\Users\ivan\Desktop\TradingView\inscribe_perfect.ico"

print("Cargando imagen original de Inscribe...")
# Open original icon
img = Image.open(source_ico)

# Load the largest size if it's an ICO
if hasattr(img, 'n_frames'):
    largest_size = (0, 0)
    best_frame = 0
    for i in range(img.n_frames):
        img.seek(i)
        if img.size[0] > largest_size[0]:
            largest_size = img.size
            best_frame = i
    img.seek(best_frame)

img_rgba = img.convert("RGBA")

# El cuadrado perfecto que acordamos para Trading y Hypertracker es 220x220.
# Inscribe es un circulo. Un circulo de 240x240 tiene visualmente la misma "masa/tinta" que un cuadrado de 220x220.
logo_size = 240
CANVAS = 256
padding = (CANVAS - logo_size) // 2

print(f"Redimensionando a {logo_size}x{logo_size}...")
img_resized = img_rgba.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
canvas.paste(img_resized, (padding, padding), img_resized)

# OBLIGATORIO: Guardar UNA sola capa de 256x256, sin tamaños chicos. 
# Esto fuerza a Windows a usar su propio algoritmo de downscaling (igual que HyperTracker).
canvas.save(perfect_ico, format='ICO', sizes=[(256, 256)])
print(f"Icono inscribe_perfect.ico guardado. Resolucion unica: 256x256.")

print(f"Inyectando icono en {target_exe}...")
try:
    CopyIcons(target_exe, perfect_ico)
    print("EXITO: El ejecutable ha sido parcheado correctamente.")
except Exception as e:
    print(f"ERROR al inyectar: {e}")
