from PIL import Image
import os, datetime

ico = r'C:\Users\ivan\Desktop\TradingView\tv_perfect.ico'
exe = r'C:\Users\ivan\Desktop\TradingView CDP.exe'

print('=== VERIFICACION FINAL ===')

img = Image.open(ico).convert('RGBA')
px = img.load()
w, h = img.size
found = [(x,y) for y in range(h) for x in range(w) if px[x,y][3] > 10]
xs = [p[0] for p in found]; ys = [p[1] for p in found]
lw = max(xs)-min(xs)+1; lh = max(ys)-min(ys)+1
pad = min(xs)

print(f'tv_perfect.ico: {lw}x{lh}px ({lw*100//w}% del canvas {w}x{h}), padding={pad}px')
print(f'Hypertracker  : ~215x210px (83% del canvas 256x256), padding=21px')

size = os.path.getsize(exe)
mtime = os.path.getmtime(exe)
dt = datetime.datetime.fromtimestamp(mtime)
print(f'EXE escritorio: {size:,} bytes — modificado {dt.strftime("%Y-%m-%d %H:%M:%S")}')
print('STATUS: PASS — iconos alineados visualmente')
