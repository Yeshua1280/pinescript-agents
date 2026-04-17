"""
HyperTracker Backtester v1.0
===================================
Analiza el hit rate de las señales del signal_log.csv contra el precio real
usando datos de velas históricas de Hyperliquid.

Métricas calculadas:
  - Hit Rate: % de señales que acertaron la dirección
  - MFE (Max Favorable Excursion): mejor movimiento a favor
  - MAE (Max Adverse Excursion): peor movimiento en contra
  - Risk/Reward: MFE/MAE ratio

Uso:
    python backtester.py
    python backtester.py --hours 4
    python backtester.py --file signal_log.csv --hours 2
"""

import csv
import requests
import time
import os
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Optional

HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"


def fetch_candles(start_ts_ms: int, end_ts_ms: int, interval: str = "5m") -> list:
    """
    Obtiene velas históricas de Hyperliquid.
    
    Args:
        start_ts_ms: Timestamp inicio en milisegundos
        end_ts_ms: Timestamp fin en milisegundos
        interval: Intervalo de vela ('1m', '5m', '15m', '1h', '4h', '1d')
    
    Returns:
        Lista de velas con campos: t, T, s, i, o, c, h, l, v, n
    """
    try:
        r = requests.post(HYPERLIQUID_URL, json={
            "type": "candleSnapshot",
            "req": {
                "coin": "BTC",
                "interval": interval,
                "startTime": start_ts_ms,
                "endTime": end_ts_ms
            }
        }, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"  ⚠️ Error fetching candles: {e}")
    return []


def analyze_signal(entry_price: float, direction: str, candles: list) -> Optional[dict]:
    """
    Analiza el rendimiento de una señal contra las velas posteriores.
    
    Calcula:
    - MFE (Max Favorable Excursion): máximo movimiento a favor durante el horizonte
    - MAE (Max Adverse Excursion): máximo movimiento en contra durante el horizonte
    - Final PnL: resultado al final del horizonte temporal
    
    Args:
        entry_price: Precio de entrada de la señal
        direction: 'BULL' o 'BEAR'
        candles: Lista de velas desde el momento de la señal
    
    Returns:
        Dict con mfe, mae, final_pnl, hit; o None si no hay datos
    """
    if not candles or direction == "NEUTRAL":
        return None
    
    max_favorable = 0.0
    max_adverse = 0.0
    final_pnl = 0.0
    
    for candle in candles:
        # Manejar tanto formato dict como array (defensivo)
        if isinstance(candle, dict):
            high = float(candle.get('h', candle.get('high', 0)))
            low = float(candle.get('l', candle.get('low', 0)))
            close = float(candle.get('c', candle.get('close', 0)))
        elif isinstance(candle, (list, tuple)) and len(candle) >= 5:
            high = float(candle[2])
            low = float(candle[3])
            close = float(candle[4])
        else:
            continue
        
        if high == 0 or low == 0 or close == 0:
            continue
            
        if direction == "BULL":
            favorable = (high - entry_price) / entry_price * 100
            adverse = (entry_price - low) / entry_price * 100
            final = (close - entry_price) / entry_price * 100
        else:  # BEAR
            favorable = (entry_price - low) / entry_price * 100
            adverse = (high - entry_price) / entry_price * 100
            final = (entry_price - close) / entry_price * 100
        
        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)
        final_pnl = final
    
    return {
        'mfe': max_favorable,
        'mae': max_adverse,
        'final_pnl': final_pnl,
        'hit': final_pnl > 0
    }


def main(log_file: str = "signal_log.csv", horizon_hours: int = 4):
    """Ejecuta el backtesting completo de señales del HyperTracker."""
    
    print("=" * 70)
    print(f"  🔬 HyperTracker Backtester v1.0")
    print(f"  Horizonte: {horizon_hours}h | Archivo: {log_file}")
    print("=" * 70)
    
    # ═══════════════════════════════════════════════════════════════
    # 1. LEER SIGNAL LOG
    # ═══════════════════════════════════════════════════════════════
    
    if not os.path.exists(log_file):
        print(f"\n❌ Error: '{log_file}' no encontrado.")
        print("   Ejecuta el HyperTracker Dashboard para generar señales primero.")
        return
    
    signals = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                direction = row.get('direction', 'NEUTRAL')
                if direction in ('BULL', 'BEAR'):
                    signals.append(row)
    except Exception as e:
        print(f"\n❌ Error leyendo {log_file}: {e}")
        return
    
    print(f"\n📊 Señales encontradas: {len(signals)} (excluyendo NEUTRAL)")
    
    if not signals:
        print("\n⚠️ No hay señales BULL/BEAR para analizar.")
        print("   El dashboard necesita registrar más señales antes del backtesting.")
        return
    
    # ═══════════════════════════════════════════════════════════════
    # 2. ANALIZAR CADA SEÑAL
    # ═══════════════════════════════════════════════════════════════
    
    results = []
    errors = 0
    
    for i, signal in enumerate(signals):
        ts_str = signal.get('timestamp', '')
        direction = signal['direction']
        
        try:
            price = float(signal.get('price', 0))
        except (ValueError, TypeError):
            errors += 1
            continue
            
        if price <= 0:
            errors += 1
            continue
        
        try:
            ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print(f"  ⚠️ Timestamp inválido: {ts_str}")
            errors += 1
            continue
            
        start_ms = int(ts.timestamp() * 1000)
        end_ms = start_ms + (horizon_hours * 3600 * 1000)
        
        confidence = signal.get('confidence', 'N/A')
        quality = signal.get('quality', 'N/A')
        consensus = signal.get('consensus', 'N/A')
        emoji = "🟢" if direction == "BULL" else "🔴"
        
        print(f"\n  [{i+1}/{len(signals)}] {ts_str}")
        print(f"    {emoji} {direction} @ ${price:,.2f} | Conf: {confidence}% | {quality} | Consenso: {consensus}")
        
        candles = fetch_candles(start_ms, end_ms, "5m")
        time.sleep(0.3)  # Rate limiting cortés
        
        if candles:
            result = analyze_signal(price, direction, candles)
            if result:
                results.append({**signal, **result})
                hit_emoji = "✅" if result['hit'] else "❌"
                print(f"    {hit_emoji} MFE: +{result['mfe']:.2f}% | MAE: -{result['mae']:.2f}% | Final: {result['final_pnl']:+.2f}%")
            else:
                print("    ⚠️ No se pudo analizar (datos de vela inválidos)")
                errors += 1
        else:
            print("    ⚠️ Sin datos de velas disponibles para este período")
            errors += 1
    
    # ═══════════════════════════════════════════════════════════════
    # 3. RESUMEN GENERAL
    # ═══════════════════════════════════════════════════════════════
    
    if not results:
        print(f"\n{'=' * 70}")
        print("  ⚠️ No se pudieron analizar señales.")
        if errors > 0:
            print(f"  Errores: {errors} (posiblemente datos históricos no disponibles)")
        return
    
    total = len(results)
    hits = sum(1 for r in results if r['hit'])
    hit_rate = hits / total * 100
    avg_mfe = sum(r['mfe'] for r in results) / total
    avg_mae = sum(r['mae'] for r in results) / total
    avg_pnl = sum(r['final_pnl'] for r in results) / total
    
    print(f"\n\n{'═' * 70}")
    print(f"  📊 RESUMEN DE BACKTESTING — {total} señales analizadas")
    print(f"{'═' * 70}")
    
    # Score general
    print(f"\n  ┌─────────────────────────────────────────────┐")
    print(f"  │  Hit Rate:    {hits}/{total} = {hit_rate:5.1f}%{'':>20s}│")
    print(f"  │  Avg MFE:     +{avg_mfe:.2f}%  (mejor caso promedio) │")
    print(f"  │  Avg MAE:     -{avg_mae:.2f}%  (peor caso promedio)  │")
    print(f"  │  Avg Final:   {avg_pnl:+.2f}%  (resultado promedio)  │")
    
    if avg_mae > 0:
        rr = avg_mfe / avg_mae
        rr_emoji = "✅" if rr >= 2.0 else ("⚠️" if rr >= 1.0 else "🔴")
        print(f"  │  Risk/Reward: {rr:.2f}x   {rr_emoji}{'':>23s}│")
    
    print(f"  └─────────────────────────────────────────────┘")
    
    # Evaluación
    if hit_rate >= 65:
        print(f"\n  🏆 EVALUACIÓN: EXCELENTE — Hit rate ≥ 65%")
    elif hit_rate >= 55:
        print(f"\n  ✅ EVALUACIÓN: BUENA — Hit rate ≥ 55%")
    elif hit_rate >= 45:
        print(f"\n  ⚠️ EVALUACIÓN: MARGINAL — Hit rate ≈ 50% (equivalente a azar)")
    else:
        print(f"\n  🔴 EVALUACIÓN: DEFICIENTE — Hit rate < 45% (peor que azar)")
    
    # ═══════════════════════════════════════════════════════════════
    # 4. DESGLOSE POR CALIDAD
    # ═══════════════════════════════════════════════════════════════
    
    quality_groups = defaultdict(list)
    for r in results:
        quality_groups[r.get('quality', 'N/A')].append(r)
    
    if len(quality_groups) > 1:
        print(f"\n  ─── Desglose por CALIDAD ───")
        for quality in ['EXCELENTE', 'ALTA', 'MEDIA', 'BAJA', 'NO OPERAR', 'N/A']:
            if quality not in quality_groups:
                continue
            group = quality_groups[quality]
            g_hits = sum(1 for r in group if r['hit'])
            g_total = len(group)
            g_rate = g_hits / g_total * 100
            g_pnl = sum(r['final_pnl'] for r in group) / g_total
            g_emoji = "✅" if g_rate >= 55 else ("⚠️" if g_rate >= 45 else "❌")
            print(f"    {g_emoji} {quality:12s}: {g_hits}/{g_total} ({g_rate:5.1f}%) | PnL: {g_pnl:+.2f}%")
    
    # ═══════════════════════════════════════════════════════════════
    # 5. DESGLOSE POR DIRECCIÓN
    # ═══════════════════════════════════════════════════════════════
    
    print(f"\n  ─── Desglose por DIRECCIÓN ───")
    for direction in ["BULL", "BEAR"]:
        dir_results = [r for r in results if r['direction'] == direction]
        if dir_results:
            d_hits = sum(1 for r in dir_results if r['hit'])
            d_total = len(dir_results)
            d_rate = d_hits / d_total * 100
            d_pnl = sum(r['final_pnl'] for r in dir_results) / d_total
            d_mfe = sum(r['mfe'] for r in dir_results) / d_total
            d_mae = sum(r['mae'] for r in dir_results) / d_total
            emoji = "🟢" if direction == "BULL" else "🔴"
            print(f"    {emoji} {direction:5s}: {d_hits}/{d_total} ({d_rate:5.1f}%) | PnL: {d_pnl:+.2f}% | MFE: +{d_mfe:.2f}% | MAE: -{d_mae:.2f}%")
    
    # ═══════════════════════════════════════════════════════════════
    # 6. DESGLOSE POR CONFIRMACIONES (si disponible)
    # ═══════════════════════════════════════════════════════════════
    
    conf_groups = defaultdict(list)
    for r in results:
        conf_count = r.get('conf_count', 'N/A')
        # Extraer número de "4/6" o "3/4" etc.
        try:
            conf_num = int(conf_count.split('/')[0])
        except (ValueError, AttributeError, IndexError):
            conf_num = -1
        conf_groups[conf_num].append(r)
    
    valid_conf_groups = {k: v for k, v in conf_groups.items() if k >= 0}
    if len(valid_conf_groups) > 1:
        print(f"\n  ─── Desglose por CONFIRMACIONES ───")
        for conf_num in sorted(valid_conf_groups.keys(), reverse=True):
            group = valid_conf_groups[conf_num]
            g_hits = sum(1 for r in group if r['hit'])
            g_total = len(group)
            g_rate = g_hits / g_total * 100
            g_pnl = sum(r['final_pnl'] for r in group) / g_total
            bar = "█" * conf_num + "░" * (6 - conf_num)
            print(f"    [{bar}] {conf_num}/6: {g_hits}/{g_total} ({g_rate:5.1f}%) | PnL: {g_pnl:+.2f}%")
    
    # ═══════════════════════════════════════════════════════════════
    # 7. MEJORES Y PEORES SEÑALES
    # ═══════════════════════════════════════════════════════════════
    
    if len(results) >= 3:
        results_sorted = sorted(results, key=lambda r: r['final_pnl'], reverse=True)
        
        print(f"\n  ─── 🏆 Top 3 MEJORES Señales ───")
        for r in results_sorted[:3]:
            emoji = "🟢" if r['direction'] == "BULL" else "🔴"
            print(f"    {emoji} {r['timestamp']} | {r['direction']} @ ${float(r['price']):,.2f} → {r['final_pnl']:+.2f}% (MFE: +{r['mfe']:.2f}%)")
        
        print(f"\n  ─── 💀 Top 3 PEORES Señales ───")
        for r in results_sorted[-3:]:
            emoji = "🟢" if r['direction'] == "BULL" else "🔴"
            print(f"    {emoji} {r['timestamp']} | {r['direction']} @ ${float(r['price']):,.2f} → {r['final_pnl']:+.2f}% (MAE: -{r['mae']:.2f}%)")
    
    # ═══════════════════════════════════════════════════════════════
    # 8. RECOMENDACIONES
    # ═══════════════════════════════════════════════════════════════
    
    print(f"\n  ─── 💡 Recomendaciones ───")
    
    if hit_rate < 50:
        print("    🔴 Hit rate < 50%. Revisar umbrales del motor WhalePilot.")
    
    if avg_mae > avg_mfe:
        print("    🔴 MAE > MFE. El riesgo supera el beneficio potencial.")
        print("       → Considerar stop-loss más ajustados o filtros de confianza más altos.")
    
    # Verificar si alta confianza realmente rinde mejor
    high_conf = [r for r in results if float(r.get('confidence', 0)) >= 75]
    low_conf = [r for r in results if float(r.get('confidence', 0)) < 60]
    
    if high_conf and low_conf:
        hc_rate = sum(1 for r in high_conf if r['hit']) / len(high_conf) * 100
        lc_rate = sum(1 for r in low_conf if r['hit']) / len(low_conf) * 100
        
        if hc_rate > lc_rate:
            print(f"    ✅ Alta confianza ({hc_rate:.0f}%) rinde mejor que baja ({lc_rate:.0f}%).")
            print("       → El sistema de confianza está calibrado correctamente.")
        else:
            print(f"    ⚠️ Alta confianza ({hc_rate:.0f}%) NO rinde mejor que baja ({lc_rate:.0f}%).")
            print("       → Recalibrar los pesos del composite score.")
    
    if errors > 0:
        print(f"    ⚠️ {errors} señales no pudieron ser analizadas (datos faltantes).")
    
    if total < 20:
        print(f"    ⚠️ Solo {total} señales analizadas. Necesitas ≥30 para significancia estadística.")
        print("       → Deja el dashboard corriendo para acumular más datos.")
    
    print(f"\n{'═' * 70}")
    print("  ✅ Backtesting completado")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HyperTracker Backtester v1.0 — Analiza hit rate contra precio real"
    )
    parser.add_argument(
        "--hours", type=int, default=4,
        help="Horizonte de análisis en horas (default: 4)"
    )
    parser.add_argument(
        "--file", type=str, default="signal_log.csv",
        help="Archivo CSV de señales (default: signal_log.csv)"
    )
    args = parser.parse_args()
    main(args.file, args.hours)
