from PIL import Image

def analyze_ico(path):
    try:
        img = Image.open(path)
        print(f'\n--- Analyzing ICO: {path} ---')
        print(f'Contained sizes: {img.info.get("sizes")}')
    except Exception as e:
        print(f'Error: {e}')

analyze_ico(r'C:\Users\ivan\Desktop\TradingView\inscribe_extracted.ico')
analyze_ico(r'C:\Users\ivan\Desktop\TradingView\projects\hypertracker.ico')
