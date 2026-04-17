import customtkinter as ctk
import requests
import threading
import time
import winsound
import csv
import os
import sys
from datetime import datetime
from collections import deque
from whale_pilot import WhalePilot, SignalDirection

# --- CONFIGURACIÓN DE APIS ---
API_KEYS = [
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjIxMTgsIm1pZCI6MjEzNzc1LCJpYXQiOjE3NzM3NTY1MDN9.1grAwC6A89lyR83cBOwtKbYCT3_zOTZ76wJf2X5XwOM",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjQsIm1pZCI6MjI3NTM4LCJpYXQiOjE3NzM3NzM0Mzd9.S3EiENLZukTJHn6qClx9Tl1oHcGjPnQOpiv95SDrbTo",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjUsIm1pZCI6MjI3NTM5LCJpYXQiOjE3NzM3NzM2NTR9.mjJkUHKRSzSpN16281zGRr2fRAcPH82W0MhU3C2eEd0",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNTY2LCJtaWQiOjIyODA2MywiaWF0IjoxNzc0NjE2MDYwfQ.aNQt3FfjoEjyFS17jOW4JIuy4l3-CwwbYSFdvYkNBfo",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNTY4LCJtaWQiOjIyODA2NSwiaWF0IjoxNzc0NjE2MzU4fQ.nRFuQoR8fxgUPqTPojvpV5dw6tTJV7MK065qQgWUQ5A",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNTk5LCJtaWQiOjIyODA2NiwiaWF0IjoxNzc0NjE5NTA0fQ.VisUBhXxPjGbkwmx_kNlbK0ZfeypU-TBkZm5kAn0o0s",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNjAwLCJtaWQiOjIyODA2NywiaWF0IjoxNzc0NjE5NzQzfQ.f81OgMneiJsMRy5_rv6Wer-sHWiXBpiXaREZk1DEqFg",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNjAxLCJtaWQiOjIyODA2OCwiaWF0IjoxNzc0NjE5OTc2fQ.47dOcMMYnhkye85HJnS8P2FlWc0CKbHL9YBLD4uJ6Yc",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNjMyLCJtaWQiOjIyODA3MiwiaWF0IjoxNzc0NjIwNDU1fQ.Ny_PL51pvkX-9b0V7_BjK7umcRKekJrw5RoR3ePofAs",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEwNjMzLCJtaWQiOjIyODA3MywiaWF0IjoxNzc0NjIwNjU3fQ.A8f548r929_qKwnLIBL0GQ5ODbT6Mwlo96XXEdKLUMI"
]
current_key_idx = 0
BASE_URL = "https://ht-api.coinmarketman.com"

# --- ENDPOINTS GRATUITOS (SIN API KEY, SIN LÍMITE) ---
LIQUIDATION_URL = "https://dw3ji7n7thadj.cloudfront.net/aggregator/assets/BTC/liquidation-heatmap.json"
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

# ══════════════════════════════════════════════════════════════════════════════
# COHORT SYSTEM v4.0 — Pesos ponderados por calidad de señal
# Eliminados: Whale (follower, contradice a grandes), Grinder (regresión al neutro)
# Agregado:   Giga-Rekt como INDICADOR CONTRARIO (su bias se invierte)
# ══════════════════════════════════════════════════════════════════════════════
TARGET_COHORTS = ["Money Printer", "Tidal Whale", "Leviathan", "Smart Money", "Giga-Rekt"]

# Pesos ponderados: sum = 1.0
COHORT_WEIGHTS = {
    "Money Printer":  0.40,   # Estrella: mejor PNL histórico, mayor convicción
    "Tidal Whale":    0.30,   # Núcleo: balance capital/muestra perfecto
    "Leviathan":      0.15,   # Market movers pero muestra pequeña (112 wallets)
    "Smart Money":    0.10,   # Confirmador, peso bajo
    "Giga-Rekt":      0.05,   # Indicador CONTRARIO (bias invertido)
}

# Cohorts cuyo bias se INVIERTE (señal contraria)
CONTRARIAN_COHORTS = {"Giga-Rekt"}

COHORT_EMOJIS = {
    "Money Printer": "💰",
    "Tidal Whale": "🌊",
    "Leviathan": "🐉",
    "Smart Money": "📈",
    "Giga-Rekt": "💀",
}

# Configuración de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HyperTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("")
        self.geometry("400x1100")
        self.attributes("-topmost", True)
        self.resizable(False, True)
        
        # Variables de control
        self.auto_update = ctk.BooleanVar(value=True)
        self.update_interval = ctk.IntVar(value=5)
        self.is_fetching = False
        self.last_price = 0.0
        self.next_update_timestamp = time.time() + (self.update_interval.get() * 60)
        self.sources_ok = 0
        self.current_signal_mode = "UNKNOWN"
        self.last_smart_bias = 50.0
        self.last_oi = 0.0
        
        self.cached_segments = None
        self.api_key_lock = threading.Lock()
        self.api_exhausted_until = 0
        
        # OI rolling window: 30 ticks × 10s = 5 minutos de historial
        self.oi_history = deque(maxlen=30)
        
        # Whale Momentum: historial de bias para rastrear velocidad
        self.whale_bias_history = deque(maxlen=6)  # ~30 min (6 × 5min)
        
        # ═══ DATOS COMPARTIDOS ENTRE THREADS (GIL-safe: dict/deque atomic assign) ═══
        # price_ticker thread ESCRIBE, main thread LEE via self.after()
        self.last_order_flow = {'delta': 0.0, 'buy_vol': 0.0, 'sell_vol': 0.0, 'delta_pct': 0.0}
        self.oi_delta_usd = 0.0  # Cambio de OI en USD vs tick anterior
        
        # ══ DATOS COMPARTIDOS entre fetch y engine (thread-safe) ══
        self.last_cohort_data = {}           # Datos por cohorte para el motor
        self.last_cohort_data_24h = {}       # v3.0: Datos 24h para divergencia
        self.last_liq_long_kill_dist = 0.0   # Distancia % al Long Kill
        self.last_liq_short_kill_dist = 0.0  # Distancia % al Short Kill
        self.last_liq_long_kill_value = 0.0  # Magnitud USD del Long Kill
        self.last_liq_short_kill_value = 0.0 # Magnitud USD del Short Kill
        
        # WHALEPILOT ENGINE v3.0 - Análisis 6 factores: consenso + volumen + liq + funding + divergencia + momentum
        self.whale_pilot = WhalePilot(
            consensus_weight=0.35,
            volume_bias_weight=0.20,
            liq_weight=0.15,
            funding_weight=0.10,
            divergence_weight=0.10,
            momentum_weight=0.10,
            cohort_bull_threshold=53.0,
            cohort_bear_threshold=47.0,
            min_confidence_for_trade=55.0,
            high_confidence_threshold=80.0,
            funding_neutral_zone=0.005,
            funding_extreme_zone=0.02,
            divergence_threshold=12.0,
            momentum_strong_threshold=4.0,
        )
        self.current_confidence = 0.0
        self.current_pilot_result = None
        
        # Determine application path for PyInstaller support
        if getattr(sys, 'frozen', False):
            # Use %APPDATA%/Hypertracker instead of the exe's directory
            appdata_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
            application_path = os.path.join(appdata_dir, "Hypertracker")
            if not os.path.exists(application_path):
                os.makedirs(application_path)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        # Signal Log: CSV para backtesting
        self.signal_log_file = os.path.join(application_path, "signal_log.csv")
        self._init_signal_log()
        

        
        self.setup_ui()
        self.start_auto_update()
        self._tick_countdown()
        self.refresh_data()
    
    def _init_signal_log(self):
        """Crea/verifica el CSV de señales v3.0 (WhalePilot 6-factor) para backtesting"""
        v3_columns = ['timestamp', 'direction', 'confidence', 'quality',
                      'consensus', 'whale_bias', 'whale_dir',
                      'funding_conf', 'liq_conf', 'vol_conf', 'consensus_conf',
                      'divergence_conf', 'momentum_conf',
                      'conf_count', 'composite_score', 'price',
                      'divergence_detail', 'momentum_value', 'reason']
        
        if os.path.exists(self.signal_log_file):
            try:
                with open(self.signal_log_file, 'r') as f:
                    first_line = f.readline().strip()
                    if 'divergence_conf' not in first_line:
                        # CSV antiguo (v2) → backup y recrear con formato v3.0
                        backup = self.signal_log_file.replace('.csv', f'_v2_{int(time.time())}.csv')
                        os.rename(self.signal_log_file, backup)
                        print(f"Signal log v2 migrado a: {backup}")
            except Exception as e:
                print(f"Signal log migration error: {e}")
        
        if not os.path.exists(self.signal_log_file):
            with open(self.signal_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(v3_columns)

    def setup_ui(self):
        # ========== PRECIO EN TIEMPO REAL ==========
        self.price_frame = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=10)
        self.price_frame.pack(pady=(6,3), padx=15, fill="x")
        
        self.price_header = ctk.CTkLabel(self.price_frame, text="₿ BTC/USD", font=ctk.CTkFont(size=10), text_color="gray")
        self.price_header.pack(pady=(3,0))
        
        self.price_lbl = ctk.CTkLabel(self.price_frame, text="Cargando...", font=ctk.CTkFont(size=22, weight="bold"), text_color="white")
        self.price_lbl.pack(pady=(0,0))
        
        self.signal_entry_lbl = ctk.CTkLabel(self.price_frame, text="Esperando señal...", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.signal_entry_lbl.pack(pady=(0,1))

        # ========== 🧠 PANEL DE ANÁLISIS v2.0 ==========
        self.diag_frame = ctk.CTkFrame(self.price_frame, fg_color="#161b22", corner_radius=6)
        self.diag_frame.pack(padx=10, pady=(0, 4), fill="x")

        # Fila 1: Consenso Ballenas + Funding
        self.diag_row1 = ctk.CTkFrame(self.diag_frame, fg_color="transparent")
        self.diag_row1.pack(fill="x", padx=8, pady=(3, 0))

        self.diag_whales_lbl = ctk.CTkLabel(self.diag_row1, text="🐋 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="w")
        self.diag_whales_lbl.pack(side="left")

        self.diag_funding_lbl = ctk.CTkLabel(self.diag_row1, text="💸 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="e")
        self.diag_funding_lbl.pack(side="right")

        # Fila 2: Muro cercano + Confirmaciones
        self.diag_row2 = ctk.CTkFrame(self.diag_frame, fg_color="transparent")
        self.diag_row2.pack(fill="x", padx=8, pady=(0, 3))

        self.diag_liq_lbl = ctk.CTkLabel(self.diag_row2, text="💀 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="w")
        self.diag_liq_lbl.pack(side="left")

        self.diag_conf_lbl = ctk.CTkLabel(self.diag_row2, text="-- /6", font=ctk.CTkFont(size=10, weight="bold"), anchor="e", text_color="gray")
        self.diag_conf_lbl.pack(side="right")

        # ========== ESTADO DE ACTUALIZACIÓN ==========
        self.status_lbl = ctk.CTkLabel(self.price_frame, text="Conectando...", text_color="gray", font=ctk.CTkFont(size=10))
        self.status_lbl.place(x=10, y=10)
        
        self.version_lbl = ctk.CTkLabel(self.price_frame, text="v5.0", font=ctk.CTkFont(size=8), text_color="#333333")
        self.version_lbl.place(relx=1.0, y=12, anchor="ne", x=-10)


        # ========== PERPETUOS BTC (Hyperliquid) ==========
        self.perp_frame = ctk.CTkFrame(self, fg_color="#1a2636")
        self.perp_frame.pack(pady=3, padx=15, fill="x")

        # Fila 1: Titulo + Bias
        self.perp_row1 = ctk.CTkFrame(self.perp_frame, fg_color="transparent")
        self.perp_row1.pack(fill="x", padx=10, pady=(4, 0))

        self.perp_title_lbl = ctk.CTkLabel(self.perp_row1, text="⚡ PERPETUOS BTC", font=ctk.CTkFont(size=10, weight="bold"), text_color="#ffaa00", anchor="w")
        self.perp_title_lbl.pack(side="left")

        self.prob_lbl = ctk.CTkLabel(self.perp_row1, text="--", font=ctk.CTkFont(size=10, weight="bold"), text_color="#ff5555")
        self.prob_lbl.pack(side="right")

        # Fila 2: Mark + OI | Vol + Fund
        self.perp_row2 = ctk.CTkFrame(self.perp_frame, fg_color="transparent")
        self.perp_row2.pack(fill="x", padx=10, pady=(2, 4))

        self.mark_lbl = ctk.CTkLabel(self.perp_row2, text="Mark: $--", font=ctk.CTkFont(size=10), anchor="w", text_color="#aaaaaa")
        self.mark_lbl.pack(side="left")

        self.oi_lbl = ctk.CTkLabel(self.perp_row2, text="OI: $--", font=ctk.CTkFont(size=10), text_color="#aaaaaa")
        self.oi_lbl.pack(side="left", padx=(8, 0))

        self.funding_lbl = ctk.CTkLabel(self.perp_row2, text="Fund: --%", font=ctk.CTkFont(size=10), anchor="e", text_color="#aaaaaa")
        self.funding_lbl.pack(side="right")

        self.vol24h_lbl = ctk.CTkLabel(self.perp_row2, text="Vol: $--", font=ctk.CTkFont(size=10), anchor="e", text_color="#aaaaaa")
        self.vol24h_lbl.pack(side="right", padx=(0, 8))

        # Fila 3: OI Delta + Order Book Imbalance
        self.perp_row3 = ctk.CTkFrame(self.perp_frame, fg_color="transparent")
        self.perp_row3.pack(fill="x", padx=10, pady=(0, 4))

        self.oi_delta_lbl = ctk.CTkLabel(self.perp_row3, text="ΔOI: --", font=ctk.CTkFont(size=10, weight="bold"), anchor="w", text_color="#555555")
        self.oi_delta_lbl.pack(side="left")

        self.order_flow_lbl = ctk.CTkLabel(self.perp_row3, text="Book: --", font=ctk.CTkFont(size=10, weight="bold"), anchor="e", text_color="#555555")
        self.order_flow_lbl.pack(side="right")

        # ========== MUROS DE LIQUIDACIÓN ==========
        self.liq_frame = ctk.CTkFrame(self, fg_color="#2d1a1a")
        self.liq_frame.pack(pady=3, padx=15, fill="x")

        # Fila 1: Short Kill (sube)
        self.liq_up_frame = ctk.CTkFrame(self.liq_frame, fg_color="transparent")
        self.liq_up_frame.pack(fill="x", padx=10, pady=(4, 1))

        self.liq_up_arrow = ctk.CTkLabel(self.liq_up_frame, text="↑ SHORT KILL:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#00ff88")
        self.liq_up_arrow.pack(side="left")
        self.liq_up_detail = ctk.CTkLabel(self.liq_up_frame, text="", font=ctk.CTkFont(size=10, weight="bold"), text_color="white")
        self.liq_up_detail.pack(side="right")
        self.liq_up_val = ctk.CTkLabel(self.liq_up_frame, text="--", font=ctk.CTkFont(size=10), text_color="#00ff88")
        self.liq_up_val.pack(side="right", padx=(0, 6))

        # Fila 2: Long Kill (baja)
        self.liq_dn_frame = ctk.CTkFrame(self.liq_frame, fg_color="transparent")
        self.liq_dn_frame.pack(fill="x", padx=10, pady=(1, 4))

        self.liq_dn_arrow = ctk.CTkLabel(self.liq_dn_frame, text="↓ LONG KILL:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#ff3333")
        self.liq_dn_arrow.pack(side="left")
        self.liq_dn_detail = ctk.CTkLabel(self.liq_dn_frame, text="", font=ctk.CTkFont(size=10, weight="bold"), text_color="white")
        self.liq_dn_detail.pack(side="right")
        self.liq_dn_val = ctk.CTkLabel(self.liq_dn_frame, text="--", font=ctk.CTkFont(size=10), text_color="#ff3333")
        self.liq_dn_val.pack(side="right", padx=(0, 6))


        # ========== MERCADO GLOBAL BTC ==========
        self.global_frame = ctk.CTkFrame(self, fg_color="#1a1a2e")
        self.global_frame.pack(pady=3, padx=15, fill="x")

        self.global_title_lbl = ctk.CTkLabel(self.global_frame, text="🌍 MERCADO GLOBAL BTC", font=ctk.CTkFont(size=10, weight="bold"), text_color="#aaaaff")
        self.global_title_lbl.pack(pady=(3, 0))

        self.global_bias_lbl = ctk.CTkLabel(self.global_frame, text="--%", font=ctk.CTkFont(size=14, weight="bold"))
        self.global_bias_lbl.pack(pady=(1, 1))

        self.global_money_row = ctk.CTkFrame(self.global_frame, fg_color="transparent")
        self.global_money_row.pack(fill="x", padx=15, pady=(0, 3))

        self.global_long_lbl = ctk.CTkLabel(self.global_money_row, text="$--", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00ff88", anchor="w")
        self.global_long_lbl.pack(side="left")

        self.global_short_lbl = ctk.CTkLabel(self.global_money_row, text="$--", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff3333", anchor="e")
        self.global_short_lbl.pack(side="right")

        # Tabla de cohorts 24h (igual que WHALES)
        self.global_cohorts_frame = ctk.CTkFrame(self.global_frame, fg_color="transparent")
        self.global_cohorts_frame.pack(pady=(0, 4), padx=10, fill="x")

        self.global_cohort_frames = {}
        self.global_cohort_widgets = {}
        for cohort in TARGET_COHORTS:
            row_frame = ctk.CTkFrame(self.global_cohorts_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            self.global_cohort_frames[cohort] = row_frame

            row_frame.grid_columnconfigure(0, weight=0, minsize=130)
            row_frame.grid_columnconfigure(1, weight=1)
            row_frame.grid_columnconfigure(2, weight=0, minsize=55)

            text_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            text_frame.grid(row=0, column=1, sticky="ew", pady=0)

            l_lbl = ctk.CTkLabel(text_frame, text="--%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#00ff88")
            l_lbl.pack(side="left")

            s_lbl = ctk.CTkLabel(text_frame, text="--%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#ff3333")
            s_lbl.pack(side="right")

            emoji = COHORT_EMOJIS.get(cohort, "")
            display_name = cohort
            name_lbl = ctk.CTkLabel(row_frame, text=f"{emoji} {display_name}", font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
            name_lbl.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 5))

            bar = ctk.CTkProgressBar(row_frame, orientation="horizontal", progress_color="#00ff88", fg_color="#ff3333", height=4)
            bar.grid(row=1, column=1, sticky="ew", padx=(0, 3), pady=(0, 1))
            bar.set(0.5)

            vol_lbl = ctk.CTkLabel(row_frame, text="--", font=ctk.CTkFont(size=10, weight="bold"), anchor="e")
            vol_lbl.grid(row=0, column=2, rowspan=2, sticky="e")

            self.global_cohort_widgets[cohort] = {
                'vol': vol_lbl, 'l_lbl': l_lbl, 's_lbl': s_lbl, 'bar': bar, 'name': name_lbl
            }

        # ========== SUMATORIA BALLENAS ==========
        self.smart_frame = ctk.CTkFrame(self, fg_color="#1f2c3d")
        self.smart_frame.pack(pady=3, padx=15, fill="x")
        
        self.smart_title_lbl = ctk.CTkLabel(self.smart_frame, text="🐋 WHALES (Top 5 v4)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#00ff88")
        self.smart_title_lbl.pack(pady=(3,0))

        self.smart_bias_lbl = ctk.CTkLabel(self.smart_frame, text="--%", font=ctk.CTkFont(size=14, weight="bold"))
        self.smart_bias_lbl.pack(pady=(1, 1))

        # Fila montos Long / Short
        self.smart_money_row = ctk.CTkFrame(self.smart_frame, fg_color="transparent")
        self.smart_money_row.pack(fill="x", padx=15, pady=(0, 3))

        self.smart_long_lbl = ctk.CTkLabel(self.smart_money_row, text="$--", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00ff88", anchor="w")
        self.smart_long_lbl.pack(side="left")

        self.smart_short_lbl = ctk.CTkLabel(self.smart_money_row, text="$--", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff3333", anchor="e")
        self.smart_short_lbl.pack(side="right")

        # ========== TABLA DE COHORTS (dentro del smart_frame) ==========
        self.cohorts_frame = ctk.CTkFrame(self.smart_frame, fg_color="transparent")
        self.cohorts_frame.pack(pady=(0, 4), padx=10, fill="x")
        
        self.cohort_frames = {}
        self.cohort_widgets = {}
        for idx, cohort in enumerate(TARGET_COHORTS):
            row_frame = ctk.CTkFrame(self.cohorts_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            self.cohort_frames[cohort] = row_frame

            row_frame.grid_columnconfigure(0, weight=0, minsize=115)
            row_frame.grid_columnconfigure(1, weight=1)
            row_frame.grid_columnconfigure(2, weight=0, minsize=48)

            text_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            text_frame.grid(row=0, column=1, sticky="ew", pady=0)

            l_lbl = ctk.CTkLabel(text_frame, text="--%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#00ff88")
            l_lbl.pack(side="left")

            s_lbl = ctk.CTkLabel(text_frame, text="--%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#ff3333")
            s_lbl.pack(side="right")

            emoji = COHORT_EMOJIS.get(cohort, "")
            # Mostrar peso ponderado junto al nombre para transparencia
            weight_pct = COHORT_WEIGHTS.get(cohort, 0) * 100
            contrarian_tag = "⟲" if cohort in CONTRARIAN_COHORTS else ""
            display_name = f"{cohort} {contrarian_tag}" if contrarian_tag else cohort
            name_lbl = ctk.CTkLabel(row_frame, text=f"{emoji} {display_name}", font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
            name_lbl.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 5))

            bar = ctk.CTkProgressBar(row_frame, orientation="horizontal", progress_color="#00ff88", fg_color="#ff3333", height=4)
            bar.grid(row=1, column=1, sticky="ew", padx=(0, 3), pady=(0, 1))
            bar.set(0.5)

            vol_lbl = ctk.CTkLabel(row_frame, text="--", font=ctk.CTkFont(size=10, weight="bold"), anchor="e")
            vol_lbl.grid(row=0, column=2, rowspan=2, sticky="e")

            self.cohort_widgets[cohort] = {
                'vol': vol_lbl, 'l_lbl': l_lbl, 's_lbl': s_lbl, 'bar': bar, 'name': name_lbl
            }

        # ========== CONTROLES ==========
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(side="bottom", pady=10, fill="x")
        
        self.refresh_btn = ctk.CTkButton(self.controls_frame, text="🔄 Actualizar", width=120, command=self.refresh_data)
        self.refresh_btn.pack(side="left", padx=20)
        
        self.timer_opt = ctk.CTkOptionMenu(self.controls_frame, values=["1 min", "5 min", "10 min", "15 min", "30 min"], width=100, command=self.change_interval)
        self.timer_opt.set("5 min")
        self.timer_opt.pack(side="right", padx=20)

    def change_interval(self, selection):
        if selection == "1 min":
            self.update_interval.set(1)
        elif selection == "5 min":
            self.update_interval.set(5)
        elif selection == "10 min":
            self.update_interval.set(10)
        elif selection == "15 min":
            self.update_interval.set(15)
        elif selection == "30 min":
            self.update_interval.set(30)
        self.next_update_timestamp = time.time() + (self.update_interval.get() * 60)

    def start_auto_update(self):
        # Hilo de precio en tiempo real (cada 10 segundos)
        def price_ticker():
            while True:
                try:
                    r = requests.post(HYPERLIQUID_URL,
                                     json={"type": "metaAndAssetCtxs"},
                                     timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        meta = data[0]
                        ctxs = data[1]
                        btc_idx = next(i for i, c in enumerate(meta['universe']) if c['name'] == 'BTC')
                        btc_ctx = ctxs[btc_idx]
                        self.after(0, self._update_live_data, btc_ctx)
                except Exception as e:
                    print(f"Price tick error: {e}")
                
                # Order Book Imbalance: bid vs ask pressure (L2 book, gratis)
                try:
                    r_book = requests.post(HYPERLIQUID_URL,
                                           json={"type": "l2Book", "coin": "BTC"},
                                           timeout=5)
                    if r_book.status_code == 200:
                        book_data = r_book.json()
                        levels = book_data.get('levels', [[], []])
                        bids = levels[0] if len(levels) > 0 else []
                        asks = levels[1] if len(levels) > 1 else []
                        # Top 10 niveles de cada lado del book
                        bid_size = sum(float(b['sz']) for b in bids[:10])
                        ask_size = sum(float(a['sz']) for a in asks[:10])
                        total_book = bid_size + ask_size
                        if total_book > 0:
                            self.last_order_flow = {
                                'buy_vol': bid_size,
                                'sell_vol': ask_size,
                                'delta': bid_size - ask_size,
                                'delta_pct': ((bid_size - ask_size) / total_book) * 100
                            }
                except Exception:
                    pass  # Book data es suplementario, no romper el loop principal
                
                time.sleep(10)  # Actualizar cada 10 segundos
        
        threading.Thread(target=price_ticker, daemon=True).start()

    def _tick_countdown(self):
        if self.is_fetching:
            self.status_lbl.configure(text=f"Actualizando... (API {current_key_idx + 1})", text_color="yellow")
        else:
            now = time.time()
            remaining = int(self.next_update_timestamp - now)
            
            if remaining <= 0:
                if self.auto_update.get():
                    self.refresh_data()
            else:
                mins, secs = divmod(remaining, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                self.status_lbl.configure(
                    text=time_str,
                    text_color="green" if getattr(self, 'sources_ok', 0) >= 2 else "orange"
                )
        
        self.after(1000, self._tick_countdown)
    
    def _update_live_data(self, btc_ctx):
        """Actualiza todo lo que es a tiempo real (Precio Header + Todo el panel Perpetuos)"""
        price = float(btc_ctx['markPx'])
        funding = float(btc_ctx['funding'])
        oi = float(btc_ctx['openInterest'])
        vol24 = float(btc_ctx['dayNtlVlm'])
        
        # OI tracking para delta (rolling window)
        oi_usd = oi * price
        self.oi_history.append(oi_usd)
        if len(self.oi_history) >= 2:
            self.oi_delta_usd = self.oi_history[-1] - self.oi_history[-2]
        
        # 1. Update Ticker Header
        self.price_lbl.configure(text=f"${price:,.2f}")
        self.last_price = price

        # 2. Update Perpetuos Panel
        self.mark_lbl.configure(text=f"Mark: ${price:,.1f}")
        
        fr_color = "#00ff88" if funding >= 0 else "#ff3333"
        self.funding_lbl.configure(text=f"Fund: {funding*100:.4f}%", text_color=fr_color)
        
        self.oi_lbl.configure(text=f"OI: {self.format_money(oi_usd)}")
        self.vol24h_lbl.configure(text=f"Vol24h: {self.format_money(vol24)}")
        
        # 3. Update OI Delta
        if abs(self.oi_delta_usd) > 1000:
            delta_color = "#00ff88" if self.oi_delta_usd > 0 else "#ff3333"
            delta_arrow = "▲" if self.oi_delta_usd > 0 else "▼"
            self.oi_delta_lbl.configure(
                text=f"ΔOI: {delta_arrow}{self.format_money(abs(self.oi_delta_usd))}",
                text_color=delta_color
            )
        else:
            self.oi_delta_lbl.configure(text="ΔOI: ═", text_color="#555555")
        
        # 4. Update Order Book Imbalance
        flow = self.last_order_flow
        flow_pct = flow.get('delta_pct', 0)
        if abs(flow_pct) > 0.1:
            if flow_pct > 5:
                flow_color = "#00ff88"
            elif flow_pct > 0:
                flow_color = "#66ffb2"
            elif flow_pct < -5:
                flow_color = "#ff3333"
            else:
                flow_color = "#ff8080"
            flow_label = "BID" if flow_pct > 0 else "ASK"
            self.order_flow_lbl.configure(
                text=f"Book: {abs(flow_pct):.0f}% {flow_label}",
                text_color=flow_color
            )
        else:
            self.order_flow_lbl.configure(text="Book: ═", text_color="#555555")
        
        # ═══════════════════════════════════════════════════════════════════════════
        # WHALEPILOT ENGINE v3.0 — ANÁLISIS 6 FACTORES
        # Consenso + Volumen + Liquidación + Funding + Divergencia + Momentum
        # ═══════════════════════════════════════════════════════════════════════════
        
        pilot_result = self.whale_pilot.analyze(
            cohort_data=self.last_cohort_data,
            funding=funding,
            liq_long_kill_dist=self.last_liq_long_kill_dist,
            liq_short_kill_dist=self.last_liq_short_kill_dist,
            liq_long_kill_value=self.last_liq_long_kill_value,
            liq_short_kill_value=self.last_liq_short_kill_value,
            price=price,
            # v3.0: Divergencia 24h vs All-Time
            cohort_data_24h=self.last_cohort_data_24h if self.last_cohort_data_24h else None,
            # v3.0: Momentum temporal del whale_bias
            whale_bias_history=list(self.whale_bias_history) if len(self.whale_bias_history) >= 2 else None,
            whale_bias=self.last_smart_bias,  # Fallback v1.0 si no hay cohort_data
        )
        
        # Guardar resultado para logging
        self.current_pilot_result = pilot_result
        self.current_confidence = pilot_result.confidence
        
        # --- EXPORTAR ESTADO EN VIVO A JSON PARA EL AGENTE ---
        try:
            import json, time as _t
            state_file = r"C:\Users\ivan\AppData\Roaming\Hypertracker\live_state.json"
            
            # Cohortes individuales (All-Time positions)
            cohorts_snapshot = {}
            if getattr(self, 'last_cohort_data', None):
                for name, data in self.last_cohort_data.items():
                    if isinstance(data, dict):
                        cohorts_snapshot[name] = {
                            "bias_long_pct": round(data.get('bias', 50), 1),
                            "volume_usd": data.get('vol', 0),
                        }
            
            # Cohortes 24h (divergencia temporal)
            cohorts_24h_snapshot = {}
            if getattr(self, 'last_cohort_data_24h', None):
                for name, data in self.last_cohort_data_24h.items():
                    if isinstance(data, dict):
                        cohorts_24h_snapshot[name] = {
                            "bias_long_pct": round(data.get('bias', 50), 1),
                            "volume_usd": data.get('vol', 0),
                        }
            
            # Factores de confirmación del motor WhalePilot
            factors = {
                "consensus": pilot_result.consensus_confirms,
                "volume": pilot_result.volume_confirms,
                "funding": pilot_result.funding_confirms,
                "liquidation": pilot_result.liq_confirms,
                "divergence": pilot_result.divergence_confirms,
                "momentum": pilot_result.momentum_confirms,
                "cohort_consensus": f"{pilot_result.cohort_consensus}/{pilot_result.total_cohorts}",
                "is_high_confidence": pilot_result.is_high_confidence,
            }
            
            live_data = {
                "price": price,
                "funding": funding,
                "funding_pct": round(funding * 100, 4),
                "oi_usd": oi_usd,
                "oi_delta_usd": getattr(self, 'oi_delta_usd', 0),
                "vol_24h": vol24,
                "order_book_pct": flow_pct,
                "signal": pilot_result.direction.name if pilot_result.direction else "NEUTRAL",
                "confidence": round(pilot_result.confidence, 1),
                "factors": factors,
                "smart_bias": getattr(self, 'last_smart_bias', 50),
                "cohorts": cohorts_snapshot,
                "cohorts_24h": cohorts_24h_snapshot,
                "liq_long_kill_dist": getattr(self, 'last_liq_long_kill_dist', 0),
                "liq_long_kill_value": getattr(self, 'last_liq_long_kill_value', 0),
                "liq_short_kill_dist": getattr(self, 'last_liq_short_kill_dist', 0),
                "liq_short_kill_value": getattr(self, 'last_liq_short_kill_value', 0),
                "timestamp": _t.time(),
            }
            with open(state_file, 'w') as f:
                json.dump(live_data, f, indent=2)
        except Exception:
            pass  # Falla silenciosa para no interrumpir el UI
        
        # Convertir direccion para compatibilidad
        if pilot_result.direction == SignalDirection.BULL:
            new_mode = "ALCISTA"
        elif pilot_result.direction == SignalDirection.BEAR:
            new_mode = "BAJISTA"
        else:
            new_mode = "NEUTRAL"
        
        # ── ACTUALIZAR UI CON RESULTADOS v2.0 ──
        
        # Mostrar confirmaciones como iconos compactos (6 factores v3.0)
        icons = ""
        icons += "C" if pilot_result.consensus_confirms else "-"
        icons += "V" if pilot_result.volume_confirms else "-"
        icons += "F" if pilot_result.funding_confirms else "-"
        icons += "L" if pilot_result.liq_confirms else "-"
        icons += "D" if pilot_result.divergence_confirms else "-"
        icons += "M" if pilot_result.momentum_confirms else "-"
        
        # Consenso info
        consensus_info = f"{pilot_result.cohort_consensus}/{pilot_result.total_cohorts}"
        
        if new_mode == "ALCISTA":
            if pilot_result.is_high_confidence:
                self.prob_lbl.configure(
                    text=f"ALCISTA {pilot_result.confidence:.0f}% [{consensus_info}]",
                    text_color="#00ff88"
                )
                self.price_lbl.configure(text_color="#00ff88")
            else:
                self.prob_lbl.configure(
                    text=f"ALCISTA {pilot_result.confidence:.0f}% {icons}",
                    text_color="#88ff00"
                )
                self.price_lbl.configure(text_color="#88ff00")
                
        elif new_mode == "BAJISTA":
            if pilot_result.is_high_confidence:
                self.prob_lbl.configure(
                    text=f"BAJISTA {pilot_result.confidence:.0f}% [{consensus_info}]",
                    text_color="#ff3333"
                )
                self.price_lbl.configure(text_color="#ff3333")
            else:
                self.prob_lbl.configure(
                    text=f"BAJISTA {pilot_result.confidence:.0f}% {icons}",
                    text_color="#ff8800"
                )
                self.price_lbl.configure(text_color="#ff8800")
        else:
            self.prob_lbl.configure(
                text=f"NEUTRAL {pilot_result.confidence:.0f}%",
                text_color="gray"
            )
            self.price_lbl.configure(text_color="white")

        # ══════════════════════════════════════════════════════════════════
        # CAMBIO DE SEÑAL: Log + Sonido
        # GUARD: Ignorar transiciones espurias cuando no hay datos reales.
        # Si total_cohorts <= 1 es un tick de precio sin respuesta de CMM
        # (fallback a whale_bias=50 → NEUTRAL falso). Mantener señal actual.
        # ══════════════════════════════════════════════════════════════════
        has_real_data = pilot_result.total_cohorts > 1
        
        if new_mode != self.current_signal_mode and has_real_data:
            self.current_signal_mode = new_mode
            
            if new_mode == "ALCISTA":
                self.signal_entry_lbl.configure(
                    text=f"🟢 LONG @ ${price:,.2f} | {pilot_result.quality_label}",
                    text_color="#00ff88"
                )
                self._log_signal_v2(pilot_result)
                
                if pilot_result.is_high_confidence:
                    def _triple_beep():
                        winsound.Beep(1500, 200)
                        time.sleep(0.1)
                        winsound.Beep(1500, 200)
                        time.sleep(0.1)
                        winsound.Beep(2000, 500)
                    threading.Thread(target=_triple_beep, daemon=True).start()
                else:
                    threading.Thread(target=lambda: winsound.Beep(1200, 300), daemon=True).start()
                    
            elif new_mode == "BAJISTA":
                self.signal_entry_lbl.configure(
                    text=f"🔴 SHORT @ ${price:,.2f} | {pilot_result.quality_label}",
                    text_color="#ff3333"
                )
                self._log_signal_v2(pilot_result)
                
                if pilot_result.is_high_confidence:
                    def _triple_beep_low():
                        winsound.Beep(400, 200)
                        time.sleep(0.1)
                        winsound.Beep(400, 200)
                        time.sleep(0.1)
                        winsound.Beep(300, 500)
                    threading.Thread(target=_triple_beep_low, daemon=True).start()
                else:
                    threading.Thread(target=lambda: winsound.Beep(600, 400), daemon=True).start()
            else:
                self.signal_entry_lbl.configure(
                    text=f"⚪ NEUTRAL @ ${price:,.2f} | Esperar",
                    text_color="gray"
                )
                self._log_signal_v2(pilot_result)
        
        # Actualizar diagnostico vivo
        self._update_diag_live(pilot_result)


    # _log_signal v1 ELIMINADO — Reemplazado por _log_signal_v2 (WhalePilot)

    def _log_signal_v2(self, pilot_result):
        """Registra cada cambio de señal v3.0 (WhalePilot 6-factor) en CSV para backtesting"""
        try:
            with open(self.signal_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    pilot_result.direction.value,
                    f"{pilot_result.confidence:.2f}",
                    pilot_result.quality_label,
                    f"{pilot_result.cohort_consensus}/{pilot_result.total_cohorts}",
                    f"{pilot_result.whale_bias:.2f}",
                    pilot_result.whale_direction,
                    'OK' if pilot_result.funding_confirms else 'NO',
                    'OK' if pilot_result.liq_confirms else 'NO',
                    'OK' if pilot_result.volume_confirms else 'NO',
                    'OK' if pilot_result.consensus_confirms else 'NO',
                    'OK' if pilot_result.divergence_confirms else 'NO',
                    'OK' if pilot_result.momentum_confirms else 'NO',
                    f"{pilot_result.confirmation_count}/6",
                    f"{pilot_result.composite_score:.2f}",
                    f"{pilot_result.price:.2f}",
                    pilot_result.divergence_detail,
                    f"{pilot_result.momentum_value:+.2f}",
                    pilot_result.reason
                ])
        except Exception as e:
            print(f"Log v3 Error: {e}")

    def format_money(self, amount):
        if amount >= 1_000_000_000:
            return f"${amount/1_000_000_000:.2f}B"
        elif amount >= 1_000_000:
            return f"${amount/1_000_000:.0f}M"
        elif amount >= 1_000:
            return f"${amount/1_000:.0f}K"
        return f"${amount:,.0f}"
    
    def format_money_signed(self, amount):
        """format_money pero con signo +/- para deltas"""
        sign = "+" if amount >= 0 else "-"
        abs_amount = abs(amount)
        return f"{sign}{self.format_money(abs_amount)}"

    def get_color(self, bias):
        if bias >= 55: return "#00ff88"
        if bias > 50: return "#66ffb2"
        if bias <= 45: return "#ff3333"
        if bias < 50: return "#ff8080"
        return "gray"

    def refresh_data(self):
        if self.is_fetching: return
        self.is_fetching = True
        self.status_lbl.configure(text=f"Actualizando... (API {current_key_idx + 1})", text_color="yellow")
        self.refresh_btn.configure(state="disabled")
        threading.Thread(target=self._fetch_all_data).start()

    def _fetch_all_data(self):
        """Obtener datos de las 3 fuentes en paralelo"""
        results = {}
        
        def fetch_cmm():
            results['cmm'] = self._fetch_cmm()

        def fetch_cmm24h():
            results['cmm24h'] = self._fetch_cmm_24h()
        
        def fetch_liq():
            results['liq'] = self._fetch_liquidations()
        
        threads = [
            threading.Thread(target=fetch_cmm),
            threading.Thread(target=fetch_cmm24h),
            threading.Thread(target=fetch_liq)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        
        # Actualizar UI con todos los datos
        self.after(0, self._update_all_ui, results)

    def _fetch_cmm(self):
        """Sentimiento de Ballenas (API CMM con rotación de keys)"""
        global current_key_idx
        
        url_segments = f"{BASE_URL}/api/external/segments"
        url_heatmap = f"{BASE_URL}/api/external/positions/heatmap?openedWithin=all"
        
        if time.time() < self.api_exhausted_until:
            return {'success': False}
            
        attempts = 0
        max_attempts = len(API_KEYS)
        
        while attempts < max_attempts:
            with self.api_key_lock:
                key = API_KEYS[current_key_idx]
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            try:
                if not self.cached_segments:
                    res_seg = requests.get(url_segments, headers=headers, timeout=8)
                    if res_seg.status_code == 429:
                        with self.api_key_lock:
                            if key == API_KEYS[current_key_idx]:
                                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                        attempts += 1
                        continue
                    elif res_seg.status_code != 200:
                        raise Exception(f"Seg Error {res_seg.status_code}")
                    self.cached_segments = {item['id']: item['name'] for item in res_seg.json()}
                
                seg_map = self.cached_segments
                
                res_heat = requests.get(url_heatmap, headers=headers, timeout=8)
                if res_heat.status_code == 429:
                    with self.api_key_lock:
                        if key == API_KEYS[current_key_idx]:
                            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                    attempts += 1
                    continue
                    
                data = res_heat.json()
                
                # Formato confirmado: data es un dict con clave 'heatmap'
                # Dentro, cada item tiene clave 'coin' (no 'asset')
                heatmap_list = data.get('heatmap', []) if isinstance(data, dict) else data
                btc_data = next((item for item in heatmap_list if item.get('coin') == 'BTC'), None)
                
                if not btc_data:
                    # Fallback: intentar con 'asset' por si cambian el formato
                    btc_data = next((item for item in heatmap_list if item.get('asset') == 'BTC'), None)
                
                if btc_data:
                    global_bias = (btc_data['totalLongValue'] / btc_data['totalValue']) * 100
                    global_vol = btc_data['totalValue']
                    
                    cohort_data = {}
                    smart_longs = 0
                    smart_shorts = 0
                    
                    for seg in btc_data.get('segments', []):
                        s_name = seg_map.get(seg['segmentId'], "Unknown")
                        # Compatibilidad: CMM puede retornar "Consistent Grinder" o "Grinder"
                        if s_name == "Consistent Grinder":
                            s_name = "Grinder"  # Normalizar nombre
                        s_bias = seg['bias'] * 100
                        l_val = seg.get('totalLongValue') or 0
                        s_val = seg.get('totalShortValue') or 0
                        s_vol = l_val + s_val
                        cohort_data[s_name] = {'bias': s_bias, 'vol': s_vol}
                        
                        if s_name in TARGET_COHORTS:
                            smart_longs += l_val
                            smart_shorts += s_val
                    
                    # ══ SMART BIAS v4.0: Suma ponderada por calidad (no promedio ciego) ══
                    # Cada cohort contribuye según su peso en COHORT_WEIGHTS
                    weighted_bias = 0.0
                    weight_sum = 0.0
                    for c_name, weight in COHORT_WEIGHTS.items():
                        if c_name in cohort_data:
                            bias_raw = cohort_data[c_name]['bias']
                            # Invertir bias para cohorts contrarios (Giga-Rekt)
                            if c_name in CONTRARIAN_COHORTS:
                                bias_raw = 100.0 - bias_raw
                            weighted_bias += bias_raw * weight
                            weight_sum += weight
                    
                    smart_bias = (weighted_bias / weight_sum) if weight_sum > 0 else 50.0
                    smart_total = smart_longs + smart_shorts
                    
                    # Datos por cohorte de ballenas (solo TARGET_COHORTS con l_val/s_val reales)
                    whale_cohorts = {}
                    for seg in btc_data.get('segments', []):
                        s_name = seg_map.get(seg['segmentId'], "Unknown")
                        if s_name == "Consistent Grinder":
                            s_name = "Grinder"  # Normalizar
                        if s_name in TARGET_COHORTS:
                            l_val = seg.get('totalLongValue') or 0
                            s_val = seg.get('totalShortValue') or 0
                            vol = l_val + s_val
                            w_bias = (l_val / vol * 100) if vol > 0 else 50
                            whale_cohorts[s_name] = {
                                'bias': w_bias,
                                'vol': vol,
                                'l_val': l_val,
                                's_val': s_val,
                                'weight': COHORT_WEIGHTS.get(s_name, 0),
                                'is_contrarian': s_name in CONTRARIAN_COHORTS,
                            }
                    
                    return {
                        'success': True,
                        'global_bias': global_bias,
                        'global_vol': global_vol,
                        'smart_bias': smart_bias,
                        'smart_vol': smart_total,
                        'smart_longs': smart_longs,
                        'smart_shorts': smart_shorts,
                        'cohorts': cohort_data,
                        'whale_cohorts': whale_cohorts,
                    }
                    
            except Exception as e:
                print(f"CMM Error: {e}")
                attempts += 1
                with self.api_key_lock:
                    if key == API_KEYS[current_key_idx]:
                        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        
        self.api_exhausted_until = time.time() + 900
        return {'success': False}

    def _fetch_cmm_24h(self):
        """Sentimiento de las 6 Ballenas en las ÚLTIMAS 24h (openedWithin=24h)"""
        global current_key_idx

        url_segments = f"{BASE_URL}/api/external/segments"
        url_heatmap = f"{BASE_URL}/api/external/positions/heatmap?openedWithin=24h"

        if time.time() < self.api_exhausted_until:
            return {'success': False}

        attempts = 0
        max_attempts = len(API_KEYS)

        while attempts < max_attempts:
            with self.api_key_lock:
                key = API_KEYS[current_key_idx]
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            try:
                if not self.cached_segments:
                    res_seg = requests.get(url_segments, headers=headers, timeout=8)
                    if res_seg.status_code == 429:
                        with self.api_key_lock:
                            if key == API_KEYS[current_key_idx]:
                                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                        attempts += 1
                        continue
                    elif res_seg.status_code != 200:
                         raise Exception(f"Seg Error {res_seg.status_code}")
                    self.cached_segments = {item['id']: item['name'] for item in res_seg.json()}

                seg_map = self.cached_segments

                res_heat = requests.get(url_heatmap, headers=headers, timeout=8)
                if res_heat.status_code == 429:
                    with self.api_key_lock:
                        if key == API_KEYS[current_key_idx]:
                            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                    attempts += 1
                    continue

                data = res_heat.json()
                heatmap_list = data.get('heatmap', []) if isinstance(data, dict) else data
                btc_data = next((item for item in heatmap_list if item.get('coin') == 'BTC'), None)
                if not btc_data:
                    btc_data = next((item for item in heatmap_list if item.get('asset') == 'BTC'), None)

                if btc_data:
                    longs_24h = 0
                    shorts_24h = 0
                    cohorts_24h = {}
                    for seg in btc_data.get('segments', []):
                        s_name = seg_map.get(seg['segmentId'], "Unknown")
                        if s_name == "Consistent Grinder":
                            s_name = "Grinder"  # Normalizar
                        if s_name in TARGET_COHORTS:
                            l_val = seg.get('totalLongValue') or 0
                            s_val = seg.get('totalShortValue') or 0
                            longs_24h += l_val
                            shorts_24h += s_val
                            vol = l_val + s_val
                            bias = (l_val / vol * 100) if vol > 0 else 50
                            cohorts_24h[s_name] = {'bias': bias, 'vol': vol, 'l_val': l_val, 's_val': s_val}

                    total_24h = longs_24h + shorts_24h
                    bias_24h = (longs_24h / total_24h) * 100 if total_24h > 0 else 50

                    return {
                        'success': True,
                        'longs_24h': longs_24h,
                        'shorts_24h': shorts_24h,
                        'bias_24h': bias_24h,
                        'cohorts_24h': cohorts_24h
                    }

            except Exception as e:
                print(f"CMM 24h Error: {e}")
                attempts += 1
                with self.api_key_lock:
                    if key == API_KEYS[current_key_idx]:
                        current_key_idx = (current_key_idx + 1) % len(API_KEYS)

        self.api_exhausted_until = time.time() + 900
        return {'success': False}



    def _fetch_liquidations(self):
        """Muros de Liquidación desde CloudFront (GRATIS, SIN LÍMITE)"""
        try:
            r = requests.get(LIQUIDATION_URL, timeout=15)
            if r.status_code == 200:
                data = r.json()
                heatmap = data.get('heatmap', data if isinstance(data, list) else [])
                
                if not heatmap:
                    return {'success': False}
                
                return {
                    'success': True,
                    'heatmap': heatmap
                }
        except Exception as e:
            print(f"Liq Error: {e}")
        
        return {'success': False}

    def _find_liquidation_walls(self, heatmap_bins, current_price):
        """Encuentra el muro de liquidación más grande arriba y abajo del precio actual"""
        above = []
        below = []
        
        for b in heatmap_bins:
            mid_price = (b['priceBinStart'] + b['priceBinEnd']) / 2
            if mid_price > current_price:
                above.append(b)
            elif mid_price < current_price:
                below.append(b)
        
        # Encontrar el muro más grande arriba (donde se liquidan SHORTS)
        wall_up = None
        if above:
            # Filtrar solo rangos cercanos (dentro de ±30% del precio)
            nearby_above = [b for b in above if b['priceBinStart'] < current_price * 1.3]
            if nearby_above:
                wall_up = max(nearby_above, key=lambda x: x['liquidationValue'])
        
        # Encontrar el muro más grande abajo (donde se liquidan LONGS)
        wall_dn = None
        if below:
            nearby_below = [b for b in below if b['priceBinEnd'] > current_price * 0.7]
            if nearby_below:
                wall_dn = max(nearby_below, key=lambda x: x['liquidationValue'])
        
        return wall_up, wall_dn

    def _update_all_ui(self, results):
        """Actualización central de toda la UI"""
        self.is_fetching = False
        self.refresh_btn.configure(state="normal")
        
        cmm = results.get('cmm', {})
        liq = results.get('liq', {})
        
        # Determinar el precio actual (usamos last_price que se actualiza cada 10s si está disponible)
        current_price = self.last_price if self.last_price > 0 else 70000
        
        # === STATUS ===
        cmm24h = results.get('cmm24h', {})
        self.sources_ok = sum([cmm.get('success', False), liq.get('success', False), cmm24h.get('success', False)])
        self.next_update_timestamp = time.time() + (self.update_interval.get() * 60)
        
        # cmm24h ya extraído en bloque STATUS

        # === MERCADO GLOBAL BTC (6 Whales, últimas 24h) ===
        if cmm24h.get('success'):
            g_longs = cmm24h.get('longs_24h', 0)
            g_shorts = cmm24h.get('shorts_24h', 0)
            g_total = g_longs + g_shorts
            if g_total > 0:
                g_bias = cmm24h.get('bias_24h', 50)
                g_dir = "LONG" if g_bias >= 50 else "SHORT"
                g_color = "#00ff88" if g_bias >= 50 else "#ff3333"
                g_pct = g_bias if g_bias >= 50 else 100 - g_bias
                self.global_bias_lbl.configure(
                    text=f"{g_pct:.1f}% {g_dir}",
                    text_color=g_color
                )
                self.global_long_lbl.configure(text=self.format_money(g_longs))
                self.global_short_lbl.configure(text=self.format_money(g_shorts))

            # Tabla de cohorts 24h (ordenadas por volumen)
            cohorts_24h = cmm24h.get('cohorts_24h', {})
            # ══ ALIMENTAR MOTOR v3.0 con datos 24h para detección de divergencias ══
            self.last_cohort_data_24h = cohorts_24h
            sorted_24h = sorted(TARGET_COHORTS, key=lambda c: cohorts_24h.get(c, {}).get('vol', 0), reverse=True)
            for c_name in sorted_24h:
                frame = self.global_cohort_frames[c_name]
                frame.pack_forget()
                frame.pack(fill="x", pady=2)
                widgets = self.global_cohort_widgets[c_name]
                if c_name in cohorts_24h:
                    cd = cohorts_24h[c_name]
                    long_pct = cd['bias']
                    short_pct = 100 - long_pct
                    widgets['l_lbl'].configure(text=f"{long_pct:.1f}%")
                    widgets['s_lbl'].configure(text=f"{short_pct:.1f}%")
                    widgets['vol'].configure(text=self.format_money(cd['vol']), text_color=self.get_color(long_pct))
                    widgets['bar'].set(long_pct / 100.0)
                else:
                    widgets['l_lbl'].configure(text="--%")
                    widgets['s_lbl'].configure(text="--%")
                    widgets['vol'].configure(text="N/A", text_color="gray")
                    widgets['bar'].set(0.5)

        # === SUMATORIA 6 BALLENAS (todas las posiciones) ===
        if cmm.get('success'):
            # Sumatoria 6 Ballenas
            s_bias = cmm['smart_bias']
            self.smart_bias_lbl.configure(
                text=f"{s_bias:.1f}% LONG" if s_bias >= 50 else f"{100-s_bias:.1f}% SHORT",
                text_color=self.get_color(s_bias)
            )
            
            # Mostrar montos Long / Short de las 6 ballenas
            s_longs = cmm.get('smart_longs', 0)
            s_shorts = cmm.get('smart_shorts', 0)
            self.smart_long_lbl.configure(text=f"{self.format_money(s_longs)}")
            self.smart_short_lbl.configure(text=f"{self.format_money(s_shorts)}")

            # Guardar bias + historial para señal compuesta y momentum
            self.last_smart_bias = s_bias
            self.whale_bias_history.append(s_bias)
            
            # ══ ALIMENTAR MOTOR v3.0 con datos POR COHORTE (Whale Top 5 reales) ══
            whale_cohorts = cmm.get('whale_cohorts', {})
            if whale_cohorts:
                self.last_cohort_data = whale_cohorts
            else:
                # Fallback: construir desde cohorts globales si whale_cohorts falta
                cohort_for_engine = {}
                for c_name in TARGET_COHORTS:
                    if c_name in cmm['cohorts']:
                        data = cmm['cohorts'][c_name]
                        vol = data['vol']
                        bias = data['bias']
                        cohort_for_engine[c_name] = {
                            'bias': bias, 'vol': vol,
                            'l_val': vol * bias / 100,
                            's_val': vol * (100 - bias) / 100,
                        }
                self.last_cohort_data = cohort_for_engine
            
            # Cohorts individuales (ordenadas por volumen)
            target_cohorts_data = []
            for c_name in TARGET_COHORTS:
                if c_name in cmm['cohorts']:
                    data = cmm['cohorts'][c_name]
                    target_cohorts_data.append((c_name, data['bias'], data['vol']))
                else:
                    target_cohorts_data.append((c_name, None, 0))
            
            target_cohorts_data.sort(key=lambda x: x[2], reverse=True)
            
            for c_name, val, vol in target_cohorts_data:
                frame = self.cohort_frames[c_name]
                frame.pack_forget()
                frame.pack(fill="x", pady=2)
                
                widgets = self.cohort_widgets[c_name]
                if val is not None:
                    long_pct = val
                    short_pct = 100 - val
                    widgets['l_lbl'].configure(text=f"{long_pct:.1f}%")
                    widgets['s_lbl'].configure(text=f"{short_pct:.1f}%")
                    widgets['vol'].configure(text=self.format_money(vol), text_color=self.get_color(val))
                    widgets['bar'].set(val / 100.0)
                else:
                    widgets['l_lbl'].configure(text="--%")
                    widgets['s_lbl'].configure(text="--%")
                    widgets['vol'].configure(text="N/A", text_color="gray")
                    widgets['bar'].set(0.5)
        

        
        # === MUROS DE LIQUIDACIÓN ===
        if liq.get('success') and current_price > 0:
            wall_up, wall_dn = self._find_liquidation_walls(liq['heatmap'], current_price)
            
            if wall_up:
                up_price = (wall_up['priceBinStart'] + wall_up['priceBinEnd']) / 2
                up_val = wall_up['liquidationValue']
                up_dist = ((up_price - current_price) / current_price) * 100
                self.liq_up_val.configure(text=f"${up_price:,.0f} (+{up_dist:.1f}%)")
                self.liq_up_detail.configure(text=self.format_money(up_val))
                # ══ ALIMENTAR MOTOR v2.0 con Short Kill ══
                self.last_liq_short_kill_dist = up_dist
                self.last_liq_short_kill_value = up_val
            else:
                self.liq_up_val.configure(text="Sin datos")
                self.liq_up_detail.configure(text="")
                self.last_liq_short_kill_dist = 0.0
                self.last_liq_short_kill_value = 0.0
            
            if wall_dn:
                dn_price = (wall_dn['priceBinStart'] + wall_dn['priceBinEnd']) / 2
                dn_val = wall_dn['liquidationValue']
                dn_dist = ((dn_price - current_price) / current_price) * 100
                self.liq_dn_val.configure(text=f"${dn_price:,.0f} ({dn_dist:.1f}%)")
                self.liq_dn_detail.configure(text=self.format_money(dn_val))
                # ══ ALIMENTAR MOTOR v2.0 con Long Kill ══
                self.last_liq_long_kill_dist = dn_dist
                self.last_liq_long_kill_value = dn_val
            else:
                self.liq_dn_val.configure(text="Sin datos")
                self.liq_dn_detail.configure(text="")
                self.last_liq_long_kill_dist = 0.0
                self.last_liq_long_kill_value = 0.0
        elif not liq.get('success'):
            self.liq_up_val.configure(text="Error")
            self.liq_dn_val.configure(text="Error")

        # === 🧠 ACTUALIZAR DIAGNÓSTICO EN VIVO ===
        self._update_diag_cmm_liq(cmm, liq, current_price)
    
    def _update_diag_cmm_liq(self, cmm, liq, price):
        """Actualiza Diagnóstico: Consensus Ballenas + Muro más cercano"""
        # 1. Consenso de Ballenas — usa whale_cohorts DIRECTO del CMM (no fallbacks)
        whale_cohorts = cmm.get('whale_cohorts', {}) if cmm.get('success') else {}
        
        if whale_cohorts:
            shorts = 0
            longs = 0
            total = 0
            for c_name, data in whale_cohorts.items():
                bias = data.get('bias', 50)
                total += 1
                if bias < 47:      # Mismo umbral que el motor v2.0
                    shorts += 1
                elif bias > 53:    # Mismo umbral que el motor v2.0
                    longs += 1
                # Entre 47-53 = neutral, no cuenta para ningún lado
            
            if total > 0:
                if shorts > longs:
                    self.diag_whales_lbl.configure(text=f"🐋 {shorts}/{total} SHORT", text_color="#ff3333")
                elif longs > shorts:
                    self.diag_whales_lbl.configure(text=f"🐋 {longs}/{total} LONG", text_color="#00ff88")
                else:
                    self.diag_whales_lbl.configure(text="🐋 Divididas", text_color="white")
                
        # 4. Muro mas cercano (iman magnetico)
        if liq.get('success') and price > 0:
            wall_up, wall_dn = self._find_liquidation_walls(liq['heatmap'], price)
            up_dist = 999
            dn_dist = 999
            if wall_up:
                up_mid = (wall_up['priceBinStart'] + wall_up['priceBinEnd']) / 2
                up_dist = ((up_mid - price) / price) * 100
                up_val = wall_up.get('liquidationValue', 0)
            else:
                up_val = 0
                
            if wall_dn:
                dn_mid = (wall_dn['priceBinStart'] + wall_dn['priceBinEnd']) / 2
                dn_dist = abs(((dn_mid - price) / price) * 100)
                dn_val = wall_dn.get('liquidationValue', 0)
            else:
                dn_val = 0
            
            if dn_val > up_val and dn_val > 0:
                self.diag_liq_lbl.configure(text=f"💀 Iman: LONGS -{dn_dist:.1f}%", text_color="#ff3333")
                self.liq_up_frame.pack_forget()
                self.liq_dn_frame.pack_forget()
                self.liq_dn_frame.pack(fill="x", padx=10, pady=2)
                self.liq_up_frame.pack(fill="x", padx=10, pady=(2, 5))
            elif up_val > 0:
                self.diag_liq_lbl.configure(text=f"💀 Iman: SHORTS +{up_dist:.1f}%", text_color="#00ff88")
                self.liq_up_frame.pack_forget()
                self.liq_dn_frame.pack_forget()
                self.liq_up_frame.pack(fill="x", padx=10, pady=2)
                self.liq_dn_frame.pack(fill="x", padx=10, pady=(2, 5))

    def _update_diag_live(self, pilot_result):
        """Actualiza diagnóstico en vivo con resultados del motor v2.0"""
        
        # Funding — color según la TENDENCIA (rojo=BEAR, verde=BULL)
        f_score = pilot_result.funding_score
        is_bull = pilot_result.direction.value == "BULL"
        is_bear = pilot_result.direction.value == "BEAR"
        trend_color = "#00ff88" if is_bull else ("#ff3333" if is_bear else "gray")
        
        if pilot_result.funding_confirms:
            self.diag_funding_lbl.configure(
                text=f"💸 Fund ✓ ({f_score:.0f})",
                text_color=trend_color
            )
        elif f_score < 40:
            self.diag_funding_lbl.configure(
                text=f"💸 Fund ✗ ({f_score:.0f})",
                text_color="gray"
            )
        else:
            self.diag_funding_lbl.configure(
                text=f"💸 Fund ~ ({f_score:.0f})",
                text_color="gray"
            )
        
        # Color base segun la dirección de la senal
        cc = pilot_result.confirmation_count
        is_bull = pilot_result.direction.value == "BULL"
        is_bear = pilot_result.direction.value == "BEAR"
        
        if cc >= 4:
            conf_color = "#00ff88" if is_bull else ("#ff3333" if is_bear else "#ffffff")
            conf_icon = "✅"
        elif cc >= 3:
            conf_color = "#88ff00" if is_bull else ("#ff6666" if is_bear else "#aaaaaa")
            conf_icon = "🟢" if is_bull else ("🔴" if is_bear else "⚪")
        elif cc >= 2:
            conf_color = "#ffaa00"
            conf_icon = "🟡"
        else:
            conf_color = "gray"
            conf_icon = "❌"
            
        # Mostrar que confirma: C=Consenso V=Volumen F=Funding L=Liquidacion D=Divergencia M=Momentum
        c_str = "C" if pilot_result.consensus_confirms else "·"
        v_str = "V" if pilot_result.volume_confirms else "·"
        f_str = "F" if pilot_result.funding_confirms else "·"
        l_str = "L" if pilot_result.liq_confirms else "·"
        d_str = "D" if pilot_result.divergence_confirms else "·"
        m_str = "M" if pilot_result.momentum_confirms else "·"
        
        self.diag_conf_lbl.configure(
            text=f"{conf_icon} {cc}/6 [{c_str}{v_str}{f_str}{l_str}{d_str}{m_str}]",
            text_color=conf_color
        )


if __name__ == "__main__":
    app = HyperTrackerApp()
    app.mainloop()
