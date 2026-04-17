"""
Test de Integracion WhalePilot + Hypertracker Dashboard
=======================================================
Verifica que la logica de WHALES COMO CAPITAN funciona correctamente
"""

import sys
sys.path.insert(0, '.')

from whale_pilot import WhalePilot, analyze_trade, SignalDirection

print("=" * 70)
print("TEST DE INTEGRACION - WHALEPILOT ENGINE v1.0")
print("=" * 70)

# Crear instancia del motor
pilot = WhalePilot()

print("\n[1] SENAL PERFECTA BULL (85%+)")
print("-" * 40)
# Ballenas: 68% en LONG
# Funding: -0.0001 (shorts pagan a longs = confirma LONG)
# OI: +3% (subiendo = confirma LONG)
# Delta: 72 (compra agresiva = confirma LONG)
r = pilot.analyze(
    whale_bias=68.0,
    funding=-0.0001,
    oi_change_pct=3.0,
    delta_score=72.0,
    price=97500.0
)
print(f"Direccion: {r.direction.value}")
print(f"Whale Bias: {r.whale_bias}% -> {r.whale_direction}")
print(f"Funding confirma: {r.funding_confirms}")
print(f"OI confirma: {r.oi_confirms}")
print(f"Delta confirma: {r.delta_confirms}")
print(f"Confirmaciones: {r.confirmation_count}/4")
print(f"Composite Score: {r.composite_score:.1f}")
print(f"CONFIANZA: {r.confidence:.1f}%")
print(f"Alta Confianza (85%+): {'SI' if r.is_high_confidence else 'NO'}")
print(f"Operable: {'SI' if r.is_tradeable else 'NO'}")

print("\n[2] SENAL PERFECTA BEAR (85%+)")
print("-" * 40)
r = pilot.analyze(
    whale_bias=32.0,  # 68% en SHORT (100-32=68)
    funding=0.00015,  # longs pagan a shorts = confirma SHORT
    oi_change_pct=-2.5,
    delta_score=28.0,
    price=96500.0
)
print(f"Direccion: {r.direction.value}")
print(f"Whale Bias: {r.whale_bias}% -> {r.whale_direction}")
print(f"Funding confirma: {r.funding_confirms}")
print(f"OI confirma: {r.oi_confirms}")
print(f"Delta confirma: {r.delta_confirms}")
print(f"Confirmaciones: {r.confirmation_count}/4")
print(f"CONFIANZA: {r.confidence:.1f}%")
print(f"Alta Confianza (85%+): {'SI' if r.is_high_confidence else 'NO'}")

print("\n[3] DIVERGENCIA - WHALES LONG pero funding/delta contradicen")
print("-" * 40)
r = pilot.analyze(
    whale_bias=58.0,  # Ballenas ligeramente en LONG
    funding=0.0002,   # Funding positivo = longs pagan = ballenas NO estan en longs!
    oi_change_pct=-1.0,  # OI bajando
    delta_score=35.0,   # Delta bajo = venta
    price=97000.0
)
print(f"Direccion: {r.direction.value}")
print(f"Funding confirma: {r.funding_confirms}")
print(f"OI confirma: {r.oi_confirms}")
print(f"Delta confirma: {r.delta_confirms}")
print(f"Confirmaciones: {r.confirmation_count}/4")
print(f"CONFIANZA: {r.confidence:.1f}%")
print(f"Alta Confianza (85%+): {'SI' if r.is_high_confidence else 'NO'}")
print(f"Operable: {'SI' if r.is_tradeable else 'NO'}")

print("\n[4] CASO REALISTA - 3/4 confirmaciones")
print("-" * 40)
r = pilot.analyze(
    whale_bias=65.0,  # Ballenas en LONG fuerte
    funding=-0.00005,  # Funding negativo pequeno
    oi_change_pct=1.5,  # OI subiendo
    delta_score=58.0,  # Delta ligeramente positifo
    price=97000.0
)
print(f"Direccion: {r.direction.value}")
print(f"Funding confirma: {r.funding_confirms}")
print(f"OI confirma: {r.oi_confirms}")
print(f"Delta confirma: {r.delta_confirms}")
print(f"Confirmaciones: {r.confirmation_count}/4")
print(f"CONFIANZA: {r.confidence:.1f}%")
print(f"Alta Confianza (85%+): {'SI' if r.is_high_confidence else 'NO'}")
print(f"Operable: {'SI' if r.is_tradeable else 'NO'}")

print("\n[5] CASO REALISTA - Solo 2/4 confirmaciones")
print("-" * 40)
r = pilot.analyze(
    whale_bias=56.0,  # Ballenas ligeramente en LONG
    funding=0.0001,  # Funding positivo (contradice)
    oi_change_pct=2.0,  # OI subiendo (confirma)
    delta_score=60.0,  # Delta alto (confirma)
    price=97000.0
)
print(f"Direccion: {r.direction.value}")
print(f"Funding confirma: {r.funding_confirms}")
print(f"OI confirma: {r.oi_confirms}")
print(f"Delta confirma: {r.delta_confirms}")
print(f"Confirmaciones: {r.confirmation_count}/4")
print(f"CONFIANZA: {r.confidence:.1f}%")
print(f"Alta Confianza (85%+): {'SI' if r.is_high_confidence else 'NO'}")
print(f"Operable: {'SI' if r.is_tradeable else 'NO'}")

print("\n" + "=" * 70)
print("RESUMEN DE LA LOGICA")
print("=" * 70)
print("""
WHALEPILOT ENGINE - FILOSOFIA
=============================

El sistema ahora funciona asi:

1. WHALES son el CAPITAN (70% del peso)
   - Si whale_bias >= 55 -> Direccion LONG
   - Si whale_bias <= 45 -> Direccion SHORT
   - Si 45 < bias < 55 -> NEUTRAL (no operar)

2. Las demas herramientas son CONFIRMACIONES:
   - FUNDING (contrario): Funding < 0 confirma LONG, Funding > 0 confirma SHORT
   - OI: OI subiendo confirma LONG, OI bajando confirma SHORT
   - DELTA: Delta > 50 confirma LONG, Delta < 50 confirma SHORT

3. SISTEMA DE CONFIANZA:
   - 4/4 confirmaciones -> 95% confianza
   - 3/4 confirmaciones -> 85% confianza
   - 2/4 confirmaciones -> 65% confianza
   - 1/4 confirmaciones -> 40% confianza
   - 0/4 confirmaciones -> 20% confianza

4. UMBRAL DE ALTA CONFIANZA (85%+):
   - Necesitas 3/4 confirmaciones (85%)
   - MAS whale_bias >= 60 (para LONG) o <= 40 (para SHORT)

5. OPERABILIDAD:
   - Alta Confianza (85%+) -> OPERAR (senal fuerte)
   - Confianza 50-85% -> Operar con cuidado
   - Confianza < 50% -> NO OPERAR
""")

print("=" * 70)
print("TEST COMPLETADO")
print("=" * 70)
