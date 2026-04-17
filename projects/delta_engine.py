"""
Order Flow Delta Engine v2.0 — Intensidad de Fuerza (estilo Delta Barcode Pro V3)
=================================================================================
Captura trades en tiempo real por WebSocket de Hyperliquid y calcula:
  - Up Volume / Down Volume en ventanas de tiempo
  - Buy Power / Sell Power normalizados (0.0 a 1.0) para evitar ruido
  - Delta Score (0 a 100) compatible con la señal compuesta del Dashboard
  - EMA suavizada para evitar señales falsas por trades individuales grandes

Notas técnicas:
  - Corre en su propio Thread con asyncio independiente
  - Limpia trades > 15 minutos para prevenir memory leaks
  - Reconexión automática con backoff de 5 segundos
"""

import asyncio
import websockets
import json
import threading
import time
import math
from collections import deque


class OrderFlowDeltaEngine:
    def __init__(self, coin="BTC"):
        self.coin = coin
        # Cada entrada: (timestamp, up_vol_usd, down_vol_usd)
        self.trades = deque()
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.max_age_seconds = 15 * 60  # 15 min max en RAM

        # EMA del delta_score para suavizar ruido
        self._ema_score = 50.0
        self._ema_alpha = 0.25  # Factor de suavizado (0.25 = reactivo y letal)
        
        # Volumen mínimo en USD para considerar datos válidos
        self.min_volume_threshold = 50_000  # $50K mínimo para evitar señales en mercado muerto

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self.thread.start()
            print(f"[Delta Engine v2] WebSocket iniciado para {self.coin}")

    def stop(self):
        self.running = False

    def _run_async_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.running:
            try:
                loop.run_until_complete(self._listen_to_ws())
            except Exception as e:
                print(f"[Delta Engine v2] Error WS: {e}. Reconectando en 5s...")
                time.sleep(5)
        loop.close()

    async def _listen_to_ws(self):
        uri = "wss://api.hyperliquid.xyz/ws"
        async with websockets.connect(uri) as ws:
            msg = {"method": "subscribe", "subscription": {"type": "trades", "coin": self.coin}}
            await ws.send(json.dumps(msg))

            while self.running:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue

                data = json.loads(response)

                if data.get("channel") == "trades":
                    now = time.time()
                    up_vol_acc = 0.0
                    down_vol_acc = 0.0

                    for trade in data["data"]:
                        px = float(trade["px"])
                        sz = float(trade["sz"])
                        side = trade["side"]
                        vol_usd = px * sz

                        # Hyperliquid: Side 'B' = Taker Buy, Side 'A' = Taker Sell
                        if side == "B":
                            up_vol_acc += vol_usd
                        elif side == "A":
                            down_vol_acc += vol_usd

                    if up_vol_acc > 0 or down_vol_acc > 0:
                        with self.lock:
                            self.trades.append((now, up_vol_acc, down_vol_acc))

                    self._cleanup_old_trades(now)

    def _cleanup_old_trades(self, current_time):
        with self.lock:
            cutoff = current_time - self.max_age_seconds
            while self.trades and self.trades[0][0] < cutoff:
                self.trades.popleft()

    # ══════════════════════════════════════════════════════════════
    # API PÚBLICA: Métodos para el Dashboard
    # ══════════════════════════════════════════════════════════════

    def get_raw_delta(self, timeframe_minutes):
        """Retorna (up_vol, down_vol, delta_raw) en USD para los últimos N minutos."""
        current_time = time.time()
        cutoff = current_time - (timeframe_minutes * 60)
        total_up = 0.0
        total_down = 0.0

        with self.lock:
            for t, up, down in self.trades:
                if t >= cutoff:
                    total_up += up
                    total_down += down

        return total_up, total_down, total_up - total_down

    def get_intensity_score(self, timeframe_minutes=2):
        """
        Calcula Buy Power & Sell Power con volumen acumulado absoluto en USD.
        Versión LETAL v3.0 — Corregidos 5 bugs de la auditoría.
        
        Retorna (buy_power, sell_power, delta_score)
          - buy_power: 0.0 a 1.0 (proporción de compra sobre total)
          - sell_power: 0.0 a 1.0 (proporción de venta sobre total)
          - delta_score: 0 a 100 (para integrar en la señal compuesta)
        """
        current_time = time.time()
        cutoff = current_time - (timeframe_minutes * 60)

        # Acumular volumen absoluto en USD (no normalización relativa)
        total_buy_usd = 0.0
        total_sell_usd = 0.0

        with self.lock:
            for t, up, down in self.trades:
                if t >= cutoff:
                    total_buy_usd += up
                    total_sell_usd += down

        total_vol = total_buy_usd + total_sell_usd

        # FIX 5: Filtro de volumen mínimo — mercado muerto = neutral
        if total_vol < self.min_volume_threshold:
            return 0.0, 0.0, self._ema_score  # Mantener EMA anterior, no contaminar

        # Paso 1: Buy/Sell Power basado en proporción real de USD
        buy_power = total_buy_usd / total_vol  # 0.0 a 1.0
        sell_power = total_sell_usd / total_vol  # 0.0 a 1.0

        # Paso 2: Convertir a delta_score 0-100
        net_force = buy_power - sell_power  # -1.0 a +1.0
        raw_score = 50.0 + (net_force * 50.0)
        raw_score = max(5.0, min(95.0, raw_score))  # FIX 4: Clamp amplio

        # Paso 3: Aplicar EMA para suavizar (alpha=0.25 = reactivo y letal)
        self._ema_score = (self._ema_alpha * raw_score) + ((1 - self._ema_alpha) * self._ema_score)

        return buy_power, sell_power, self._ema_score

    def get_confluence_data(self):
        """
        Retorna un diccionario con toda la información relevante para
        el sistema de confluencia 'Santo Grial' del Dashboard.
        """
        up_1m, down_1m, delta_1m = self.get_raw_delta(1)
        up_5m, down_5m, delta_5m = self.get_raw_delta(5)
        buy_power, sell_power, delta_score = self.get_intensity_score(2)

        total_1m = up_1m + down_1m
        total_5m = up_5m + down_5m

        return {
            # Datos crudos para display
            'delta_1m': delta_1m,
            'delta_5m': delta_5m,
            'up_1m': up_1m,
            'down_1m': down_1m,
            'total_vol_1m': total_1m,
            'total_vol_5m': total_5m,
            # Intensidad normalizada (estilo Barcode V3)
            'buy_power': buy_power,
            'sell_power': sell_power,
            # Score 0-100 para señal compuesta (suavizado EMA)
            'delta_score': delta_score,
            # Ratio simple para la barra visual
            'bar_ratio': up_1m / total_1m if total_1m > 0 else 0.5,
            # Flag: ¿hay suficientes datos para confiar? (>30 segundos de trades)
            'data_ready': total_1m > 0
        }


# ══════════════════════════════════════════════════════════════
# TESTING INDEPENDIENTE
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    engine = OrderFlowDeltaEngine()
    engine.start()

    try:
        while True:
            time.sleep(5)
            data = engine.get_confluence_data()
            score = data['delta_score']
            bp = data['buy_power']
            sp = data['sell_power']
            d1 = data['delta_1m']
            d5 = data['delta_5m']

            bias = "COMPRA" if score > 55 else ("VENTA" if score < 45 else "NEUTRAL")
            print(f"Score: {score:.1f} [{bias}] | BuyPwr: {bp:.3f} | SellPwr: {sp:.3f} | 1m: ${d1:+,.0f} | 5m: ${d5:+,.0f}")
    except KeyboardInterrupt:
        engine.stop()
        print("Engine detenido.")
