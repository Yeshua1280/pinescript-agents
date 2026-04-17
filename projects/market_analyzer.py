#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  MARKET ANALYZER AGENT v1.0                                        ║
║  Fusiona HyperTracker (WhalePilot) + TradingView (CDP Chart)       ║
║  en un solo reporte de análisis cruzado.                            ║
║                                                                     ║
║  Uso: python market_analyzer.py                                     ║
║  Output: JSON estructurado con el análisis completo a stdout        ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import json
import sys
import os
import time
import subprocess
import io
from datetime import datetime, timezone

# Forzar UTF-8 en Windows (soporta emojis)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════
LIVE_STATE_PATH = r"C:\Users\ivan\AppData\Roaming\Hypertracker\live_state.json"
CDP_PORT = 9222
MAX_STALE_SECONDS = 600  # 10 minutos = datos obsoletos

# ═══════════════════════════════════════════════════════════════
# FUENTE 1: HyperTracker (live_state.json)
# ═══════════════════════════════════════════════════════════════
def read_hypertracker() -> dict:
    """Lee el archivo de telemetría del HyperTracker Dashboard."""
    result = {
        "source": "HyperTracker WhalePilot v3.0",
        "status": "ERROR",
        "data": None,
        "age_seconds": None,
    }
    
    if not os.path.exists(LIVE_STATE_PATH):
        result["error"] = "live_state.json no encontrado. Asegúrate de que el dashboard está corriendo."
        return result
    
    try:
        with open(LIVE_STATE_PATH, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result["error"] = f"Error leyendo live_state.json: {e}"
        return result
    
    # Verificar frescura de datos
    ts = data.get("timestamp", 0)
    age = time.time() - ts
    result["age_seconds"] = round(age, 1)
    
    if age > MAX_STALE_SECONDS:
        result["status"] = "STALE"
        result["warning"] = f"Datos obsoletos ({age:.0f}s). El dashboard puede estar pausado."
    else:
        result["status"] = "OK"
    
    result["data"] = data
    return result


# ═══════════════════════════════════════════════════════════════
# FUENTE 2: TradingView (CDP Screenshot + Indicator State)
# ═══════════════════════════════════════════════════════════════
def read_tradingview() -> dict:
    """Captura estado de TradingView via CDP (puerto 9222)."""
    result = {
        "source": "TradingView Desktop (CDP)",
        "status": "ERROR",
        "data": None,
    }
    
    try:
        import http.client
        conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
        conn.request("GET", "/json")
        resp = conn.getresponse()
        targets = json.loads(resp.read().decode())
        conn.close()
        
        # Buscar la pestaña de TradingView
        tv_target = None
        for t in targets:
            url = t.get("url", "")
            if "tradingview" in url.lower() or "chart" in url.lower():
                tv_target = t
                break
        
        if not tv_target:
            # Tomar la primera pestaña disponible que no sea devtools
            for t in targets:
                if t.get("type") == "page" and "devtools" not in t.get("url", ""):
                    tv_target = t
                    break
        
        if tv_target:
            result["status"] = "CONNECTED"
            result["data"] = {
                "title": tv_target.get("title", "Unknown"),
                "url": tv_target.get("url", ""),
                "ws_url": tv_target.get("webSocketDebuggerUrl", ""),
            }
        else:
            result["status"] = "NO_CHART"
            result["error"] = "TradingView no encontrado entre las pestañas CDP."
            
    except ConnectionRefusedError:
        result["error"] = "CDP no disponible (puerto 9222). TradingView puede no estar abierto."
    except Exception as e:
        result["error"] = f"Error CDP: {e}"
    
    return result


# ═══════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS CRUZADO
# ═══════════════════════════════════════════════════════════════
def analyze_market(ht_data: dict | None) -> dict:
    """
    Produce el análisis cruzado del estado del mercado.
    Interpreta los datos crudos del HyperTracker y genera
    conclusiones legibles para el agente IA.
    """
    analysis = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict": "INDETERMINADO",
        "risk_level": "MEDIO",
        "key_observations": [],
        "institutional_positioning": {},
        "order_flow": {},
        "liquidation_analysis": {},
        "factors_summary": {},
        "recommendation": "",
    }
    
    if not ht_data:
        analysis["verdict"] = "SIN DATOS"
        analysis["key_observations"].append("No hay datos del HyperTracker disponibles.")
        return analysis

    price = ht_data.get("price", 0)
    signal = ht_data.get("signal", "NEUTRAL")
    confidence = ht_data.get("confidence", 0)
    funding_pct = ht_data.get("funding_pct", 0)
    oi_delta = ht_data.get("oi_delta_usd", 0)
    book_pct = ht_data.get("order_book_pct", 0)
    smart_bias = ht_data.get("smart_bias", 50)
    factors = ht_data.get("factors", {})
    cohorts = ht_data.get("cohorts", {})
    cohorts_24h = ht_data.get("cohorts_24h", {})
    
    # ── ORDER FLOW ──
    if book_pct > 0:
        book_side = "BID (Compradores dominan)"
        book_bias = "ALCISTA"
    elif book_pct < 0:
        book_side = "ASK (Vendedores dominan)"
        book_bias = "BAJISTA"
    else:
        book_side = "EQUILIBRADO"
        book_bias = "NEUTRAL"
    
    analysis["order_flow"] = {
        "book_imbalance": f"{abs(book_pct):.1f}% {book_side}",
        "book_bias": book_bias,
        "oi_delta": f"{'▲' if oi_delta > 0 else '▼'}${abs(oi_delta):,.0f}",
        "oi_interpretation": "Dinero fresco entrando" if oi_delta > 0 else "Posiciones cerrándose",
        "funding_rate": f"{funding_pct:.4f}%",
    }
    
    # ── POSICIONAMIENTO INSTITUCIONAL (Cohortes) ──
    cohort_analysis = {}
    bulls = 0
    bears = 0
    for name, data in cohorts.items():
        bias = data.get("bias_long_pct", 50)
        vol = data.get("volume_usd", 0)
        side = "LONG" if bias > 53 else ("SHORT" if bias < 47 else "NEUTRAL")
        cohort_analysis[name] = {
            "bias_long": f"{bias:.1f}%",
            "bias_short": f"{100-bias:.1f}%",
            "dominant_side": side,
            "volume": f"${vol:,.0f}" if vol else "N/A",
        }
        if side == "LONG":
            bulls += 1
        elif side == "SHORT":
            bears += 1
    
    # Divergencia 24h vs All-Time para The Money Printer
    mp_alltime = cohorts.get("Money Printer", {}).get("bias_long_pct", 50)
    mp_24h = cohorts_24h.get("Money Printer", {}).get("bias_long_pct", 50)
    if mp_alltime and mp_24h:
        mp_shift = mp_24h - mp_alltime
        cohort_analysis["Money Printer Divergencia 24h"] = {
            "all_time_long": f"{mp_alltime:.1f}%",
            "last_24h_long": f"{mp_24h:.1f}%",
            "shift": f"{'▲' if mp_shift > 0 else '▼'}{abs(mp_shift):.1f}%",
            "interpretation": (
                "Acumulando LONGS en 24h (más alcista que su posición histórica)"
                if mp_shift > 3
                else "Acumulando SHORTS en 24h (más bajista que su posición histórica)"
                if mp_shift < -3
                else "Sin divergencia significativa"
            ),
        }
    
    analysis["institutional_positioning"] = {
        "cohorts": cohort_analysis,
        "consensus": f"{bulls} alcistas / {bears} bajistas de {len(cohorts)} cohortes",
        "smart_bias_total": f"{smart_bias:.1f}% LONG" if smart_bias >= 50 else f"{100-smart_bias:.1f}% SHORT",
    }
    
    # ── LIQUIDACIONES ──
    liq_long_dist = ht_data.get("liq_long_kill_dist", 0)
    liq_long_val = ht_data.get("liq_long_kill_value", 0)
    liq_short_dist = ht_data.get("liq_short_kill_dist", 0)
    liq_short_val = ht_data.get("liq_short_kill_value", 0)
    
    if liq_long_val > liq_short_val and liq_long_val > 0:
        liq_magnet = "ABAJO (Liquidaciones de Longs)"
        liq_risk = "BAJISTA"
    elif liq_short_val > 0:
        liq_magnet = "ARRIBA (Liquidaciones de Shorts)"
        liq_risk = "ALCISTA"
    else:
        liq_magnet = "SIN DATOS"
        liq_risk = "NEUTRAL"
    
    analysis["liquidation_analysis"] = {
        "long_kill_zone": f"{liq_long_dist:.1f}% debajo (${liq_long_val:,.0f})" if liq_long_val else "N/A",
        "short_kill_zone": f"+{liq_short_dist:.1f}% arriba (${liq_short_val:,.0f})" if liq_short_val else "N/A",
        "magnet_direction": liq_magnet,
        "liq_bias": liq_risk,
    }
    
    # ── FACTORES WHALEPILOT ──
    confirmed = sum(1 for v in [
        factors.get("consensus"), factors.get("volume"),
        factors.get("funding"), factors.get("liquidation"),
        factors.get("divergence"), factors.get("momentum")
    ] if v)
    
    analysis["factors_summary"] = {
        "signal": signal,
        "confidence": f"{confidence:.1f}%",
        "confirmed_factors": f"{confirmed}/6",
        "detail": {
            "Consenso": "✅" if factors.get("consensus") else "❌",
            "Volumen": "✅" if factors.get("volume") else "❌",
            "Funding": "✅" if factors.get("funding") else "❌",
            "Liquidación": "✅" if factors.get("liquidation") else "❌",
            "Divergencia": "✅" if factors.get("divergence") else "❌",
            "Momentum": "✅" if factors.get("momentum") else "❌",
        },
        "high_confidence": factors.get("is_high_confidence", False),
        "cohort_consensus": factors.get("cohort_consensus", "?/?"),
    }
    
    # ── VEREDICTO FINAL ──
    bull_signals = 0
    bear_signals = 0
    
    # Factor 1: Señal del motor
    if signal == "BULL":
        bull_signals += 2
    elif signal == "BEAR":
        bear_signals += 2
    
    # Factor 2: Book imbalance
    if book_pct > 5:
        bull_signals += 1
    elif book_pct < -5:
        bear_signals += 1
    
    # Factor 3: OI Delta
    if oi_delta > 50000:
        bull_signals += 1
    elif oi_delta < -50000:
        bear_signals += 1
    
    # Factor 4: Liquidation magnet
    if liq_risk == "ALCISTA":
        bull_signals += 1
    elif liq_risk == "BAJISTA":
        bear_signals += 1
    
    # Factor 5: Money Printer positioning
    if mp_24h > 55:
        bull_signals += 2
    elif mp_24h < 45:
        bear_signals += 2
    
    total = bull_signals + bear_signals
    if total > 0:
        bull_pct = (bull_signals / total) * 100
    else:
        bull_pct = 50
    
    if bull_pct > 65:
        analysis["verdict"] = "ALCISTA"
        analysis["risk_level"] = "BAJO" if confidence > 70 else "MEDIO"
    elif bull_pct < 35:
        analysis["verdict"] = "BAJISTA"
        analysis["risk_level"] = "BAJO" if confidence > 70 else "MEDIO"
    else:
        analysis["verdict"] = "INDECISO / ZONA DE CONFLICTO"
        analysis["risk_level"] = "ALTO"
    
    analysis["cross_score"] = {
        "bull_signals": bull_signals,
        "bear_signals": bear_signals,
        "bull_pct": f"{bull_pct:.0f}%",
    }
    
    # ── OBSERVACIONES CLAVE ──
    if mp_24h and mp_24h < 40:
        analysis["key_observations"].append(
            f"🔴 ALERTA: Money Printer está {100-mp_24h:.1f}% SHORT en 24h. Institución líder apostando a la baja."
        )
    elif mp_24h and mp_24h > 60:
        analysis["key_observations"].append(
            f"🟢 Money Printer está {mp_24h:.1f}% LONG en 24h. Institución líder apostando al alza."
        )
    
    if abs(book_pct) > 20:
        analysis["key_observations"].append(
            f"⚡ Imbalance extremo en el libro: {abs(book_pct):.0f}% {'ASK (venta)' if book_pct < 0 else 'BID (compra)'}."
        )
    
    if abs(oi_delta) > 500000:
        direction = "entrando" if oi_delta > 0 else "saliendo"
        analysis["key_observations"].append(
            f"💰 Movimiento masivo de OI: ${abs(oi_delta):,.0f} {direction} del mercado."
        )
    
    if confidence > 75:
        analysis["key_observations"].append(
            f"🎯 Confianza alta del motor WhalePilot: {confidence:.0f}%. Señal fuerte."
        )
    elif confidence < 55:
        analysis["key_observations"].append(
            f"⚠️ Confianza baja del motor: {confidence:.0f}%. Mercado indeciso."
        )
    
    return analysis


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    report = {
        "agent": "Market Analyzer v1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # 1. Leer HyperTracker
    ht = read_hypertracker()
    report["hypertracker"] = {
        "status": ht["status"],
        "age_seconds": ht["age_seconds"],
        "raw_data": ht["data"],
    }
    if "error" in ht:
        report["hypertracker"]["error"] = ht["error"]
    if "warning" in ht:
        report["hypertracker"]["warning"] = ht["warning"]
    
    # 2. Leer TradingView
    tv = read_tradingview()
    report["tradingview"] = {
        "status": tv["status"],
        "data": tv["data"],
    }
    if "error" in tv:
        report["tradingview"]["error"] = tv["error"]
    
    # 3. Análisis cruzado
    report["analysis"] = analyze_market(ht.get("data"))
    
    # Output
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
