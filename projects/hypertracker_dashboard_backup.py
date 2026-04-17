import customtkinter as ctk
import requests
import threading
import time
import winsound
import csv
import os
from datetime import datetime
from collections import deque
from delta_engine import OrderFlowDeltaEngine
from whale_pilot import WhalePilot, analyze_trade, SignalDirection

# --- CONFIGURACIÓN DE APIS ---
API_KEYS = [
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjIxMTgsIm1pZCI6MjEzNzc1LCJpYXQiOjE3NzM3NTY1MDN9.1grAwC6A89lyR83cBOwtKbYCT3_zOTZ76wJf2X5XwOM",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjQsIm1pZCI6MjI3NTM4LCJpYXQiOjE3NzM3NzM0Mzd9.S3EiENLZukTJHn6qClx9Tl1oHcGjPnQOpiv95SDrbTo",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjc0NjUsIm1pZCI6MjI3NTM5LCJpYXQiOjE3NzM3NzM2NTR9.mjJkUHKRSzSpN16281zGRr2fRAcPH82W0MhU3C2eEd0"
]
current_key_idx = 0
BASE_URL = "https://ht-api.coinmarketman.com"

# --- ENDPOINTS GRATUITOS (SIN API KEY, SIN LÍMITE) ---
LIQUIDATION_URL = "https://dw3ji7n7thadj.cloudfront.net/aggregator/assets/BTC/liquidation-heatmap.json"
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

# Cohorts que queremos trackear específicamente (Mueven más dinero/Tienen más winrate)
TARGET_COHORTS = ["Leviathan", "Tidal Whale", "Whale", "Money Printer", "Smart Money", "Consistent Grinder"]

COHORT_EMOJIS = {
    "Leviathan": "🐉",
    "Tidal Whale": "🌊",
    "Whale": "🐳",
    "Money Printer": "💰",
    "Smart Money": "🧠",
    "Consistent Grinder": "📈"
}

# Configuración de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HyperTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("")
        self.geometry("400x1050")
        self.attributes("-topmost", True)
        self.resizable(False, True)
        
        # Variables de control
        self.auto_update = ctk.BooleanVar(value=True)
        self.update_interval = ctk.IntVar(value=5)
        self.is_fetching = False
        self.last_price = 0.0
        self.seconds_until_update = self.update_interval.get() * 60
        self.sources_ok = 0
        self.current_signal_mode = "UNKNOWN"
        self.last_smart_bias = 50.0
        self.last_oi = 0.0
        
        # Whale Momentum: historial de bias para rastrear velocidad
        self.whale_bias_history = deque(maxlen=6)  # ~30 min (6 × 5min)
        
        # WHALEPILOT ENGINE v1.0 - Nueva logica de senal donde WHALES son el Capitan
        self.whale_pilot = WhalePilot(
            whale_weight=0.70,
            funding_weight=0.10,
            oi_weight=0.10,
            delta_weight=0.10,
            whale_bull_threshold=52.0,  # Bias >= 52 = BULL (dollar-weighted)
            whale_bear_threshold=48.0,  # Bias <= 48 = BEAR (dollar-weighted)
            min_confidence_for_trade=50.0,
            high_confidence_threshold=85.0,
            extreme_whale_bias=57.0  # Para 85%+ necesitamos bias >= 57 o <= 43
        )
        self.current_confidence = 0.0
        self.current_pilot_result = None
        
        # Signal Log: CSV para backtesting
        self.signal_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal_log.csv")
        self._init_signal_log()
        
        # Order Flow Delta Engine background thread
        self.delta_engine = OrderFlowDeltaEngine()
        self.delta_engine.start()
        
        self.setup_ui()
        self.start_auto_update()
        self._tick_countdown()
        self.refresh_data()
    
    def _init_signal_log(self):
        """Crea el CSV de señales v6 (WhalePilot) si no existe"""
        if not os.path.exists(self.signal_log_file):
            with open(self.signal_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'direction', 'confidence', 'quality',
                    'whale_bias', 'whale_dir',
                    'funding_conf', 'oi_conf', 'delta_conf',
                    'conf_count', 'composite_score', 'price'
                ])

    def setup_ui(self):
        # ========== PRECIO EN TIEMPO REAL ==========
        self.price_frame = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=10)
        self.price_frame.pack(pady=(10,5), padx=15, fill="x")
        
        self.price_header = ctk.CTkLabel(self.price_frame, text="₿ BTC/USD", font=ctk.CTkFont(size=11), text_color="gray")
        self.price_header.pack(pady=(5,0))
        
        self.price_lbl = ctk.CTkLabel(self.price_frame, text="Cargando...", font=ctk.CTkFont(size=28, weight="bold"), text_color="white")
        self.price_lbl.pack(pady=(0,0))
        
        self.signal_entry_lbl = ctk.CTkLabel(self.price_frame, text="Esperando señal...", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray")
        self.signal_entry_lbl.pack(pady=(0,5))

        # ========== 🧠 DIAGNÓSTICO EN VIVO ==========
        self.diag_frame = ctk.CTkFrame(self.price_frame, fg_color="#161b22", corner_radius=6)
        self.diag_frame.pack(padx=10, pady=(0, 8), fill="x")

        # Fila 1: Ballenas + Funding
        self.diag_row1 = ctk.CTkFrame(self.diag_frame, fg_color="transparent")
        self.diag_row1.pack(fill="x", padx=8, pady=(4, 0))

        self.diag_whales_lbl = ctk.CTkLabel(self.diag_row1, text="🐋 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="w")
        self.diag_whales_lbl.pack(side="left")

        self.diag_funding_lbl = ctk.CTkLabel(self.diag_row1, text="💸 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="e")
        self.diag_funding_lbl.pack(side="right")

        # Fila 2: Delta + Muro más cercano
        self.diag_row2 = ctk.CTkFrame(self.diag_frame, fg_color="transparent")
        self.diag_row2.pack(fill="x", padx=8, pady=(0, 4))

        self.diag_liq_lbl = ctk.CTkLabel(self.diag_row2, text="💀 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="w")
        self.diag_liq_lbl.pack(side="left")

        self.diag_delta_lbl = ctk.CTkLabel(self.diag_row2, text="🔥 --", font=ctk.CTkFont(size=10, weight="bold"), anchor="e")
        self.diag_delta_lbl.pack(side="right")

        # ========== ESTADO DE ACTUALIZACIÓN ==========
        self.status_lbl = ctk.CTkLabel(self.price_frame, text="Conectando...", text_color="gray", font=ctk.CTkFont(size=10))
        self.status_lbl.place(x=10, y=10)

        # ========== 🔥 ORDER FLOW DELTA v2 ==========
        self.delta_frame = ctk.CTkFrame(self, fg_color="#1a1a2e")
        self.delta_frame.pack(pady=5, padx=15, fill="x")
        
        self.delta_title_lbl = ctk.CTkLabel(self.delta_frame, text="🔥 ORDER FLOW DELTA (WSS)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffcc00")
        self.delta_title_lbl.pack(pady=(5,0))
        
        # Fila 1: Deltas crudos $
        self.delta_row1 = ctk.CTkFrame(self.delta_frame, fg_color="transparent")
        self.delta_row1.pack(fill="x", padx=10, pady=(2, 0))
        
        self.delta_1m_lbl = ctk.CTkLabel(self.delta_row1, text="1m: $--", font=ctk.CTkFont(size=11), anchor="w")
        self.delta_1m_lbl.pack(side="left")
        
        self.delta_5m_lbl = ctk.CTkLabel(self.delta_row1, text="5m: $--", font=ctk.CTkFont(size=11), anchor="e")
        self.delta_5m_lbl.pack(side="right")
        
        # Fila 2: Score EMA + Buy/Sell Power
        self.delta_row2 = ctk.CTkFrame(self.delta_frame, fg_color="transparent")
        self.delta_row2.pack(fill="x", padx=10, pady=(0, 2))
        
        self.delta_dummy = ctk.CTkLabel(self.delta_row2, text="", width=60)
        self.delta_dummy.pack(side="left")
        
        self.delta_score_lbl = ctk.CTkLabel(self.delta_row2, text="Score: --", font=ctk.CTkFont(size=13, weight="bold"))
        self.delta_score_lbl.pack(side="left", expand=True)
        
        self.delta_power_lbl = ctk.CTkLabel(self.delta_row2, text="B:-- S:--", font=ctk.CTkFont(size=10), text_color="gray", width=60, anchor="e")
        self.delta_power_lbl.pack(side="right")
        
        # Barra simétrica: verde→derecha = compradores, rojo→izquierda = vendedores
        self.delta_bar = ctk.CTkProgressBar(self.delta_frame, orientation="horizontal", progress_color="#00ff88", fg_color="#ff3333", height=8)
        self.delta_bar.pack(pady=(0, 5), padx=10, fill="x")
        self.delta_bar.set(0.5)

        # ========== PERPETUOS BTC (Hyperliquid) ==========
        self.perp_frame = ctk.CTkFrame(self, fg_color="#1a2636")
        self.perp_frame.pack(pady=5, padx=15, fill="x")
        
        self.perp_title_lbl = ctk.CTkLabel(self.perp_frame, text="⚡ PERPETUOS BTC", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffaa00")
        self.perp_title_lbl.pack(pady=(5,0))
        
        # Fila Mark Price + Funding
        self.perp_row1 = ctk.CTkFrame(self.perp_frame, fg_color="transparent")
        self.perp_row1.pack(fill="x", padx=10)
        
        self.mark_lbl = ctk.CTkLabel(self.perp_row1, text="Mark: $--", font=ctk.CTkFont(size=12), anchor="w")
        self.mark_lbl.pack(side="left")
        
        self.prob_lbl = ctk.CTkLabel(self.perp_row1, text="Prob: --%", font=ctk.CTkFont(size=12, weight="bold"))
        self.prob_lbl.pack(side="left", expand=True)
        
        self.funding_lbl = ctk.CTkLabel(self.perp_row1, text="Fund: --%", font=ctk.CTkFont(size=12), anchor="e")
        self.funding_lbl.pack(side="right")
        
        # Fila OI + Vol 24h
        self.perp_row2 = ctk.CTkFrame(self.perp_frame, fg_color="transparent")
        self.perp_row2.pack(fill="x", padx=10, pady=(0,5))
        
        self.oi_lbl = ctk.CTkLabel(self.perp_row2, text="OI: $--", font=ctk.CTkFont(size=12), anchor="w")
        self.oi_lbl.pack(side="left")
        
        self.signal_price_lbl = ctk.CTkLabel(self.perp_row2, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self.signal_price_lbl.pack(side="left", expand=True)
        
        self.vol24h_lbl = ctk.CTkLabel(self.perp_row2, text="Vol24h: $--", font=ctk.CTkFont(size=12), anchor="e")
        self.vol24h_lbl.pack(side="right")

        # ========== MUROS DE LIQUIDACIÓN ==========
        self.liq_frame = ctk.CTkFrame(self, fg_color="#2d1a1a")
        self.liq_frame.pack(pady=5, padx=15, fill="x")
        
        self.liq_title_lbl = ctk.CTkLabel(self.liq_frame, text="💀 LIQUIDATIONS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff5555")
        self.liq_title_lbl.pack(pady=(5,2))
        
        # Muro Arriba (Shorts liquidados si sube)
        self.liq_up_frame = ctk.CTkFrame(self.liq_frame, fg_color="transparent")
        self.liq_up_frame.pack(fill="x", padx=10, pady=2)
        
        self.liq_up_arrow = ctk.CTkLabel(self.liq_up_frame, text="↑ SHORT KILL:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00ff88")
        self.liq_up_arrow.pack(side="left")
        
        self.liq_up_detail = ctk.CTkLabel(self.liq_up_frame, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="white")
        self.liq_up_detail.pack(side="right")
        
        self.liq_up_val = ctk.CTkLabel(self.liq_up_frame, text="--", font=ctk.CTkFont(size=11), text_color="#00ff88")
        self.liq_up_val.pack(side="right", padx=(0, 10))
        
        # Muro Abajo (Longs liquidados si baja)
        self.liq_dn_frame = ctk.CTkFrame(self.liq_frame, fg_color="transparent")
        self.liq_dn_frame.pack(fill="x", padx=10, pady=(2, 5))
        
        self.liq_dn_arrow = ctk.CTkLabel(self.liq_dn_frame, text="↓ LONG KILL:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff3333")
        self.liq_dn_arrow.pack(side="left")
        
        self.liq_dn_detail = ctk.CTkLabel(self.liq_dn_frame, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="white")
        self.liq_dn_detail.pack(side="right")
        
        self.liq_dn_val = ctk.CTkLabel(self.liq_dn_frame, text="--", font=ctk.CTkFont(size=11), text_color="#ff3333")
        self.liq_dn_val.pack(side="right", padx=(0, 10))

        # ========== SUMATORIA BALLENAS ==========
        self.smart_frame = ctk.CTkFrame(self, fg_color="#1f2c3d")
        self.smart_frame.pack(pady=5, padx=15, fill="x")
        
        self.smart_title_lbl = ctk.CTkLabel(self.smart_frame, text="🐋 WHALES (Top 6)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00ff88")
        self.smart_title_lbl.pack(pady=(5,0))

        self.smart_bias_lbl = ctk.CTkLabel(self.smart_frame, text="--%", font=ctk.CTkFont(size=18, weight="bold"))
        self.smart_bias_lbl.pack(pady=(2, 8))

        # ========== TABLA DE COHORTS ==========
        self.cohorts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cohorts_frame.pack(pady=5, padx=15, fill="both", expand=True)
        
        self.cohort_frames = {}
        self.cohort_labels = {}
        for idx, cohort in enumerate(TARGET_COHORTS):
            row_frame = ctk.CTkFrame(self.cohorts_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=3)
            self.cohort_frames[cohort] = row_frame
            
            emoji = COHORT_EMOJIS.get(cohort, "")
            name_lbl = ctk.CTkLabel(row_frame, text=f"{emoji} {cohort}", font=ctk.CTkFont(size=13, weight="bold"), width=150, anchor="w")
            name_lbl.pack(side="left")
            
            val_lbl = ctk.CTkLabel(row_frame, text="--%", font=ctk.CTkFont(size=13, weight="bold"))
            val_lbl.pack(side="right")
            
            self.cohort_labels[cohort] = val_lbl

        # ========== CONTROLES ==========
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(side="bottom", pady=10, fill="x")
        
        self.refresh_btn = ctk.CTkButton(self.controls_frame, text="🔄 Actualizar", width=120, command=self.refresh_data)
        self.refresh_btn.pack(side="left", padx=20)
        
        self.timer_opt = ctk.CTkOptionMenu(self.controls_frame, values=["1 min", "5 min", "15 min"], width=100, command=self.change_interval)
        self.timer_opt.set("5 min")
        self.timer_opt.pack(side="right", padx=20)

    def change_interval(self, selection):
        if selection == "1 min":
            self.update_interval.set(1)
        elif selection == "5 min":
            self.update_interval.set(5)
        elif selection == "15 min":
            self.update_interval.set(15)
        self.seconds_until_update = self.update_interval.get() * 60

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
                time.sleep(10)  # Actualizar cada 10 segundos
        
        threading.Thread(target=price_ticker, daemon=True).start()

    def _tick_countdown(self):
        if self.is_fetching:
            self.status_lbl.configure(text=f"Actualizando... (API {current_key_idx + 1})", text_color="yellow")
        else:
            if self.seconds_until_update <= 0:
                if self.auto_update.get():
                    self.refresh_data()
            else:
                mins, secs = divmod(self.seconds_until_update, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                self.status_lbl.configure(
                    text=time_str,
                    text_color="green" if getattr(self, 'sources_ok', 0) == 2 else "orange"
                )
                self.seconds_until_update -= 1
        
        self.after(1000, self._tick_countdown)
    
    def _update_live_data(self, btc_ctx):
        """Actualiza todo lo que es a tiempo real (Precio Header + Todo el panel Perpetuos)"""
        price = float(btc_ctx['markPx'])
        funding = float(btc_ctx['funding'])
        oi = float(btc_ctx['openInterest'])
        vol24 = float(btc_ctx['dayNtlVlm'])
        
        # 1. Update Ticker Header
        self.price_lbl.configure(text=f"${price:,.2f}")
        self.last_price = price

        # 2. Update Perpetuos Panel
        self.mark_lbl.configure(text=f"Mark: ${price:,.1f}")
        
        fr_color = "#00ff88" if funding >= 0 else "#ff3333"
        self.funding_lbl.configure(text=f"Fund: {funding*100:.4f}%", text_color=fr_color)
        
        self.oi_lbl.configure(text=f"OI: {self.format_money(oi * price)}")
        self.vol24h_lbl.configure(text=f"Vol24h: {self.format_money(vol24)}")
        
        # ══════════════════════════════════════════════════════════════
        # 2.5 ORDER FLOW DELTA v2 — Intensidad + EMA
        # ══════════════════════════════════════════════════════════════
        delta_data = self.delta_engine.get_confluence_data()
        
        d1 = delta_data['delta_1m']
        d5 = delta_data['delta_5m']
        bp = delta_data['buy_power']
        sp = delta_data['sell_power']
        delta_score = delta_data['delta_score']
        bar_ratio = delta_data['bar_ratio']
        
        # Display deltas crudos
        self.delta_1m_lbl.configure(
            text=f"1m: {self.format_money_signed(d1)}",
            text_color="#00ff88" if d1 > 0 else "#ff3333"
        )
        self.delta_5m_lbl.configure(
            text=f"5m: {self.format_money_signed(d5)}",
            text_color="#00ff88" if d5 > 0 else "#ff3333"
        )
        
        # Display score EMA + intensidades
        score_color = "#00ff88" if delta_score > 55 else ("#ff3333" if delta_score < 45 else "gray")
        self.delta_score_lbl.configure(text=f"Score: {delta_score:.1f}", text_color=score_color)
        self.delta_power_lbl.configure(text=f"B:{bp:.2f} S:{sp:.2f}")
        
        # Barra visual
        self.delta_bar.set(bar_ratio)
            
        # ═══════════════════════════════════════════════════════════════════════════
        # WHALEPILOT ENGINE v1.0 - WHALES ES EL CAPITAN
        # Las ballenas determinan la direccion. Las demas herramientas CONFIRMAN.
        # ═══════════════════════════════════════════════════════════════════════════
        
        # Calcular OI change
        current_oi_btc = oi
        oi_change_pct = 0.0
        if self.last_oi > 0:
            oi_change_pct = ((current_oi_btc - self.last_oi) / self.last_oi) * 100
        self.last_oi = current_oi_btc
        
        # Usar el motor WhalePilot para analisis
        fr_pct = funding  # Funding raw para el motor
        pilot_result = self.whale_pilot.analyze(
            whale_bias=self.last_smart_bias,  # 0-100 de las ballenas
            funding=fr_pct,  # Tasa de funding
            oi_change_pct=oi_change_pct,  # Cambio % en OI
            delta_score=delta_score,  # 0-100 del delta engine
            price=price
        )
        
        # Guardar resultado para logging
        self.current_pilot_result = pilot_result
        self.current_confidence = pilot_result.confidence
        
        # Convertir direccion para compatibilidad
        if pilot_result.direction == SignalDirection.BULL:
            new_mode = "ALCISTA"
        elif pilot_result.direction == SignalDirection.BEAR:
            new_mode = "BAJISTA"
        else:
            new_mode = "NEUTRAL"
        
        # ── ACTUALIZAR UI CON RESULTADOS ──
        
        # Mostrar confianza de manera prominente
        conf_color = "#00ff88" if pilot_result.confidence >= 85 else ("#ffaa00" if pilot_result.confidence >= 50 else "#ff3333")
        conf_text = f"CONF: {pilot_result.confidence:.1f}%"
        
        # Mostrar confirmaciones como iconos
        conf_str = ""
        if pilot_result.funding_confirms:
            conf_str += "F"  # Funding OK
        else:
            conf_str += "-"  # Funding no confirma
        if pilot_result.oi_confirms:
            conf_str += " O"  # OI OK
        else:
            conf_str += " -"
        if pilot_result.delta_confirms:
            conf_str += " D"  # Delta OK
        else:
            conf_str += " -"
        
        if new_mode == "ALCISTA":
            if pilot_result.is_high_confidence:
                # SEÑAL DE ALTA CONFIANZA (85%+)
                self.prob_lbl.configure(
                    text=f">>> ALCISTA {pilot_result.confidence:.0f}% <<<",
                    text_color="#00ff88"
                )
                self.price_lbl.configure(text_color="#00ff88")
            else:
                # Senal direction pero baja confianza
                self.prob_lbl.configure(
                    text=f"ALCISTA {pilot_result.confidence:.0f}% {conf_str}",
                    text_color="#88ff00"
                )
                self.price_lbl.configure(text_color="#88ff00")
                
        elif new_mode == "BAJISTA":
            if pilot_result.is_high_confidence:
                # SEÑAL DE ALTA CONFIANZA (85%+)
                self.prob_lbl.configure(
                    text=f">>> BAJISTA {pilot_result.confidence:.0f}% <<<",
                    text_color="#ff3333"
                )
                self.price_lbl.configure(text_color="#ff3333")
            else:
                self.prob_lbl.configure(
                    text=f"BAJISTA {pilot_result.confidence:.0f}% {conf_str}",
                    text_color="#ff8800"
                )
                self.price_lbl.configure(text_color="#ff8800")
        else:
            self.prob_lbl.configure(
                text=f"NEUTRAL {pilot_result.confidence:.0f}%",
                text_color="gray"
            )
            self.price_lbl.configure(text_color="white")

        # ── CAMBIO DE SEÑAL: Log + Sonido ──
        if new_mode != self.current_signal_mode:
            self.current_signal_mode = new_mode
            
            if new_mode == "ALCISTA":
                self.signal_price_lbl.configure(text=f"Senal: ${price:,.1f}", text_color="#00ff88")
                self.signal_entry_lbl.configure(text=f"Ultimo cambio (ALCISTA) en: ${price:,.2f}", text_color="#00ff88")
                
                # Log con nueva estructura
                self._log_signal_v2(pilot_result)
                
                # Sonido basado en confianza
                if pilot_result.is_high_confidence:
                    # Triple beep para alta confianza
                    def _triple_beep():
                        winsound.Beep(1500, 200)
                        time.sleep(0.1)
                        winsound.Beep(1500, 200)
                        time.sleep(0.1)
                        winsound.Beep(2000, 500)  # Tone final mas agudo
                    threading.Thread(target=_triple_beep, daemon=True).start()
                else:
                    # Single beep para senal media
                    threading.Thread(target=lambda: winsound.Beep(1200, 300), daemon=True).start()
                    
            elif new_mode == "BAJISTA":
                self.signal_price_lbl.configure(text=f"Senal: ${price:,.1f}", text_color="#ff3333")
                self.signal_entry_lbl.configure(text=f"Ultimo cambio (BAJISTA) en: ${price:,.2f}", text_color="#ff3333")
                
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
                self.signal_price_lbl.configure(text="", text_color="gray")
                self.signal_entry_lbl.configure(text=f"Ultimo cambio (NEUTRAL) en: ${price:,.2f}", text_color="gray")
                self._log_signal_v2(pilot_result)
                # Sin sonido para neutral
        
        # Actualizar diagnostico vivo
        self._update_diag_live(pilot_result)


    def _log_signal(self, signal, confluence, price, composite, whale_bias,
                    funding_pct, funding_score, oi_change_pct,
                    oi_score, delta_score, buy_power, sell_power):
        """Registra cada cambio de señal v4 en CSV para backtesting"""
        try:
            with open(self.signal_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    signal,
                    'YES' if confluence else 'NO',
                    f"{price:.2f}",
                    f"{composite:.2f}",
                    f"{whale_bias:.2f}",
                    "NA",
                    f"{funding_pct:.6f}",
                    f"{funding_score:.2f}",
                    f"{oi_change_pct:.4f}",
                    f"{oi_score:.2f}",
                    f"{delta_score:.2f}",
                    f"{buy_power:.4f}",
                    f"{sell_power:.4f}"
                ])
        except Exception as e:
            print(f"Log Error: {e}")

    def _log_signal_v2(self, pilot_result):
        """Registra cada cambio de senal v6 (WhalePilot) en CSV para backtesting
        
        El formato nuevo incluye:
        - timestamp, direction, confidence, is_high_conf
        - whale_bias, whale_direction
        - funding_confirms, oi_confirms, delta_confirms
        - confirmation_count, composite_score
        """
        try:
            with open(self.signal_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    pilot_result.direction.value,
                    f"{pilot_result.confidence:.2f}",
                    'HIGH' if pilot_result.is_high_confidence else 'MED' if pilot_result.is_tradeable else 'LOW',
                    f"{pilot_result.whale_bias:.2f}",
                    pilot_result.whale_direction,
                    'OK' if pilot_result.funding_confirms else 'NO',
                    'OK' if pilot_result.oi_confirms else 'NO',
                    'OK' if pilot_result.delta_confirms else 'NO',
                    f"{pilot_result.confirmation_count}/4",
                    f"{pilot_result.composite_score:.2f}",
                    f"{pilot_result.price:.2f}"
                ])
        except Exception as e:
            print(f"Log v2 Error: {e}")

    def format_money(self, amount):
        if amount >= 1_000_000_000:
            return f"${amount/1_000_000_000:.2f}B"
        elif amount >= 1_000_000:
            return f"${amount/1_000_000:.2f}M"
        elif amount >= 1_000:
            return f"${amount/1_000:.1f}K"
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
        
        def fetch_liq():
            results['liq'] = self._fetch_liquidations()
        
        threads = [
            threading.Thread(target=fetch_cmm),
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
        
        attempts = 0
        max_attempts = len(API_KEYS)
        
        while attempts < max_attempts:
            key = API_KEYS[current_key_idx]
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            try:
                res_seg = requests.get(url_segments, headers=headers, timeout=20)
                if res_seg.status_code == 429:
                    print(f"API Key {current_key_idx+1} Agotada. Rotando...")
                    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                    attempts += 1
                    continue
                elif res_seg.status_code != 200:
                    raise Exception(f"Seg Error {res_seg.status_code}")
                
                seg_map = {item['id']: item['name'] for item in res_seg.json()}
                
                res_heat = requests.get(url_heatmap, headers=headers, timeout=20)
                if res_heat.status_code == 429:
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
                        s_bias = seg['bias'] * 100
                        l_val = seg.get('totalLongValue') or 0
                        s_val = seg.get('totalShortValue') or 0
                        s_vol = l_val + s_val
                        cohort_data[s_name] = {'bias': s_bias, 'vol': s_vol}
                        
                        if s_name in TARGET_COHORTS:
                            smart_longs += l_val
                            smart_shorts += s_val
                            
                    smart_total = smart_longs + smart_shorts
                    smart_bias = (smart_longs / smart_total) * 100 if smart_total > 0 else 50
                    
                    return {
                        'success': True,
                        'global_bias': global_bias,
                        'global_vol': global_vol,
                        'smart_bias': smart_bias,
                        'smart_vol': smart_total,
                        'cohorts': cohort_data
                    }
                    
            except Exception as e:
                print(f"CMM Error: {e}")
                attempts += 1
                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        
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
        self.sources_ok = sum([cmm.get('success', False), liq.get('success', False)])
        self.seconds_until_update = self.update_interval.get() * 60
        
        # === GLOBAL BIAS (CMM) ===
        if cmm.get('success'):
            
            # Sumatoria 6 Ballenas
            s_bias = cmm['smart_bias']
            self.smart_bias_lbl.configure(
                text=f"{s_bias:.1f}% LONG" if s_bias >= 50 else f"{100-s_bias:.1f}% SHORT",
                text_color=self.get_color(s_bias)
            )
            
            # Guardar bias + historial para señal compuesta y momentum
            self.last_smart_bias = s_bias
            self.whale_bias_history.append(s_bias)
            
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
                frame.pack(fill="x", pady=3)
                
                if val is not None:
                    txt = f"{val:.1f}% L" if val >= 50 else f"{100-val:.1f}% S"
                    self.cohort_labels[c_name].configure(text=txt, text_color=self.get_color(val))
                else:
                    self.cohort_labels[c_name].configure(text="N/A", text_color="gray")
        

        
        # === MUROS DE LIQUIDACIÓN ===
        if liq.get('success') and current_price > 0:
            wall_up, wall_dn = self._find_liquidation_walls(liq['heatmap'], current_price)
            
            if wall_up:
                up_price = (wall_up['priceBinStart'] + wall_up['priceBinEnd']) / 2
                up_val = wall_up['liquidationValue']
                up_pos = wall_up['positionsCount']
                up_dist = ((up_price - current_price) / current_price) * 100
                self.liq_up_val.configure(text=f"${up_price:,.0f} (+{up_dist:.1f}%)")
                self.liq_up_detail.configure(text=self.format_money(up_val))
            else:
                self.liq_up_val.configure(text="Sin datos")
                self.liq_up_detail.configure(text="")
            
            if wall_dn:
                dn_price = (wall_dn['priceBinStart'] + wall_dn['priceBinEnd']) / 2
                dn_val = wall_dn['liquidationValue']
                dn_pos = wall_dn['positionsCount']
                dn_dist = ((dn_price - current_price) / current_price) * 100
                self.liq_dn_val.configure(text=f"${dn_price:,.0f} ({dn_dist:.1f}%)")
                self.liq_dn_detail.configure(text=self.format_money(dn_val))
            else:
                self.liq_dn_val.configure(text="Sin datos")
                self.liq_dn_detail.configure(text="")
        elif not liq.get('success'):
            self.liq_up_val.configure(text="Error")
            self.liq_dn_val.configure(text="Error")

        # === 🧠 ACTUALIZAR DIAGNÓSTICO EN VIVO ===
        self._update_diag_cmm_liq(cmm, liq, current_price)
    
    def _update_diag_cmm_liq(self, cmm, liq, price):
        """Actualiza la parte del panel diagnostico que depende de requests (Ballenas, Muros)"""
        # 1. Conteo de Ballenas SHORT vs LONG
        shorts = 0
        longs = 0
        total = 0
        if cmm.get('success') and 'cohorts' in cmm:
            for c_name in TARGET_COHORTS:
                if c_name in cmm['cohorts']:
                    val = cmm['cohorts'][c_name]['bias']
                    if val is not None:
                        total += 1
                        if val < 50:
                            shorts += 1
                        else:
                            longs += 1
        
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
        """Actualiza la parte del panel diagnostico que depende de WebSockets (Delta, Funding)
        
        Args:
            pilot_result: WhalePilotResult con toda la informacion de analisis
        """
        # Usar el resultado del piloto para mostrar diagnostico
        fr_pct = pilot_result.whale_score  # No necesitamos fr_pct directo, el piloto ya lo uso
        
        # 2. Funding interpretado (mostrar direccion real)
        if pilot_result.direction.value == "BULL":
            if pilot_result.funding_confirms:
                self.diag_funding_lbl.configure(text="Funding: LONG", text_color="#00ff88")
            else:
                self.diag_funding_lbl.configure(text="Funding: SHORT", text_color="#ff3333")
        elif pilot_result.direction.value == "BEAR":
            if pilot_result.funding_confirms:
                self.diag_funding_lbl.configure(text="Funding: SHORT", text_color="#ff3333") # Era verde, ahora rojo correcto
            else:
                self.diag_funding_lbl.configure(text="Funding: LONG", text_color="#00ff88")
        else:
            self.diag_funding_lbl.configure(text="Funding: Neutro", text_color="gray")
        
        # 3. Delta presion (mostrar direccion real)
        if pilot_result.direction.value == "BULL":
            if pilot_result.delta_confirms:
                self.diag_delta_lbl.configure(text="Delta: LONG", text_color="#00ff88")
            elif pilot_result.delta_score < 45:
                self.diag_delta_lbl.configure(text="Delta: SHORT", text_color="#ff3333")
            else:
                self.diag_delta_lbl.configure(text="Delta: Neutro", text_color="gray")
        elif pilot_result.direction.value == "BEAR":
            if pilot_result.delta_confirms:
                self.diag_delta_lbl.configure(text="Delta: SHORT", text_color="#ff3333") # Era verde, ahora rojo correcto
            elif pilot_result.delta_score < 45:
                self.diag_delta_lbl.configure(text="Delta: LONG", text_color="#00ff88")
            else:
                self.diag_delta_lbl.configure(text="Delta: Neutro", text_color="gray")
        else:
            self.diag_delta_lbl.configure(text="Delta: Neutro", text_color="gray")


if __name__ == "__main__":
    app = HyperTrackerApp()
    app.mainloop()
