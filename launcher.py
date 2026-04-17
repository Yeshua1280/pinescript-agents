import os
import subprocess
import sys

# Ruta exacta a la version extraida Portable
portable_path = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'TradingView', 'TradingView-Portable', 'TradingView.exe')

if os.path.exists(portable_path):
    # Lanza TV de manera desacoplada sin consola
    subprocess.Popen([portable_path, '--remote-debugging-port=9222'], 
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
sys.exit(0)
