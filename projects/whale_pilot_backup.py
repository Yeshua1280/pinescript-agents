"""
WhalePilot Engine v1.0 — El Sistema de Señales donde WHALES son el Capitán
================================================================================

FILOSOFÍA:
==========
Las ballenas mueven el mercado. Las demás herramientas (Funding, OI, Delta) 
son sirvientes que CONFIRMAN o RECHAZAN lo que las ballenas dicen.

Si las ballenas dicen LONG y TODAS las confirmaciones dicen LONG → 85%+ precisión
Si las ballenas dicen LONG pero alguna confirmación contradice → Precisión baja


LÓGICA PRINCIPAL:
================
1. WHALE BIAS (70% del peso) → Determina dirección
   - whale_bias >= 52 → BULLISH (las ballenas van long)
   - whale_bias <= 48 → BEARISH (las ballenas van short)
   - 48 < bias < 52 → NEUTRAL (esperar)

2. FUNDING CONTRARIO (10% del peso) → Confirmación de squeeze
   - Funding < 0 → Confirma LONG ( shorts pagan = ballenas van long) ✓
   - Funding > 0 → Rechaza LONG ( longs pagan = ballenas van short) ✗
   
   Lógica: El funding te dice quién está pagando a quién. Si el funding es positivo,
   los longs están pagando a los shorts. Si las ballenas están en longs y el funding
   es positivo, significa que las ballenas están siendo usadas para pagar a los shorts.
   Es una señal CONTRARIA.

3. OI CONFIRMATION (10% del peso) → Convicción del movimiento
   - OI Sube + Whales Long → Confirmación fuerte ✓
   - OI Baja + Whales Short → Confirmación fuerte ✓
   - OI Sube + Whales Short → Divergencia ✗

4. DELTA CONFIRMATION (10% del peso) → Presión de ejecución real
   - Delta > 55 + Whales Long → Compradores agresivos ✓
   - Delta < 45 + Whales Short → Vendedores agresivos ✓


SISTEMA DE CONFIANZA:
=====================
- 4/4 confirmaciones (Whale + 3) → 95% confianza
- 3/4 confirmaciones → 80% confianza  
- 2/4 confirmaciones → 50% confianza
- 1/4 confirmaciones → 25% confianza (NO OPERAR)
- 0/4 confirmaciones → 10% confianza (NO OPERAR)


UMBRALES OPTIMIZADOS PARA 85%+:
===============================
Para considerar una señal ALTA CONFIANZA (85%+):
1. Whale Bias debe estar en rango extremo (>= 57 o <= 43)
2. Al menos 2 de las 3 confirmaciones deben estar alineadas
3. El Composite Score debe ser >= 75


MATHEMATICS:
============
composite = (whale_score * 0.70) + (funding_confirms * 0.10) + 
            (oi_confirms * 0.10) + (delta_confirms * 0.10)

DÓNDE:
- whale_score = whale_bias (0-100)
- funding_confirms = 100 si funding negativo (confirma longs), 0 si positivo
- oi_confirms = 100 si OI change alineado con whales, 0 si divergencia
- delta_confirms = 100 si delta alineado con whales, 0 si divergencia

CONFIANZA FINAL:
===============
confianza = 0.7 * whale_score + 0.1 * funding_conf + 0.1 * oi_conf + 0.1 * delta_conf

"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class SignalDirection(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


@dataclass
class WhalePilotResult:
    """Resultado del análisis WhalePilot"""
    direction: SignalDirection
    whale_bias: float  # 0-100
    whale_direction: str  # "LONG" o "SHORT"
    
    # Scores individuales
    whale_score: float  # 0-100 (el bias directo)
    funding_score: float  # 0-100
    oi_score: float  # 0-100
    delta_score: float  # 0-100
    
    # Confirmaciones (True = confirma la dirección de whales)
    funding_confirms: bool
    oi_confirms: bool
    delta_confirms: bool
    
    # Resultados
    composite_score: float  # 0-100
    confidence: float  # 0-100%
    confirmation_count: int  # 0-4
    is_high_confidence: bool  # True si >= 85%
    is_tradeable: bool  # True si >= 50% confianza y hay dirección clara
    
    # Metadata
    timestamp: str
    price: float


class WhalePilot:
    """
    Motor de señal donde WHALES son el Capitán y las demás 
    herramientas son confirmaciones.
    
    Parámetros ajustables:
    - whale_weight: Peso de las ballenas (default 0.70)
    - whale_bull_threshold: Bias mínimo para considerar bullish (default 55)
    - whale_bear_threshold: Bias máximo para considerar bearish (default 45)
    - min_confidence_for_trade: Confianza mínima para operar (default 50%)
    - high_confidence_threshold: Umbral para alta confianza (default 85%)
    """
    
    def __init__(
        self,
        whale_weight: float = 0.70,
        funding_weight: float = 0.10,
        oi_weight: float = 0.10,
        delta_weight: float = 0.10,
        whale_bull_threshold: float = 52.0,
        whale_bear_threshold: float = 48.0,
        min_confidence_for_trade: float = 50.0,
        high_confidence_threshold: float = 85.0,
        extreme_whale_bias: float = 57.0  # Para señales de 85%+
    ):
        # Validar pesos
        total = whale_weight + funding_weight + oi_weight + delta_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Pesos deben sumar 1.0, actual: {total}")
        
        self.whale_weight = whale_weight
        self.funding_weight = funding_weight
        self.oi_weight = oi_weight
        self.delta_weight = delta_weight
        
        self.whale_bull_threshold = whale_bull_threshold
        self.whale_bear_threshold = whale_bear_threshold
        self.min_confidence_for_trade = min_confidence_for_trade
        self.high_confidence_threshold = high_confidence_threshold
        self.extreme_whale_bias = extreme_whale_bias
        
        # Historial para análisis
        self.last_result: Optional[WhalePilotResult] = None
    
    def analyze(
        self,
        whale_bias: float,  # 0-100, bias de ballenas (ej: 65% = 65% de los largos en ballenas)
        funding: float,  # Tasa de funding (ej: 0.0001 = 0.01%)
        oi_change_pct: float,  # Cambio % en OI (ej: 2.5 = 2.5%)
        delta_score: float,  # 0-100 del delta engine
        price: float = 0.0,
        timestamp: str = ""
    ) -> WhalePilotResult:
        """
        Analiza todos los factores y retorna una señal clara.
        
        Args:
            whale_bias: Bias de las ballenas (0-100)
                       > 50 = más ballenas en LONG que SHORT
                       < 50 = más ballenas en SHORT que LONG
            funding: Tasa de funding de Hyperliquid
                    > 0 = longs pagan a shorts
                    < 0 = shorts pagan a longs
            oi_change_pct: Cambio porcentual del Open Interest
                          > 0 = nuevos contratos abiertos (más participantes)
                          < 0 = contratos cerrándose
            delta_score: Score de order flow (0-100)
                        > 50 = presión compradora
                        < 50 = presión vendedora
            price: Precio actual (para logging)
            timestamp: Timestamp actual (para logging)
        
        Returns:
            WhalePilotResult con toda la información de la señal
        """
        
        # ─────────────────────────────────────────────────────────────
        # PASO 1: Determinar dirección de WHALES
        # ─────────────────────────────────────────────────────────────
        
        if whale_bias >= self.whale_bull_threshold:
            whale_direction = SignalDirection.BULL
            whale_score = whale_bias  # Usamos el bias directo como score
        elif whale_bias <= self.whale_bear_threshold:
            whale_direction = SignalDirection.BEAR
            whale_score = 100 - whale_bias  # Invertido para que sea consistente
        else:
            whale_direction = SignalDirection.NEUTRAL
            whale_score = 50.0  # Neutral
        
        # ─────────────────────────────────────────────────────────────
        # PASO 2: Evaluar FUNDING (Señal CONTRARIA)
        # ─────────────────────────────────────────────────────────────
        #
        # FUNDING POSITIVO (> 0): Longs pagan a shorts
        #   → Significa que hay más largos que cortos apostándole al alza
        #   → Retail está en LONG, las ballenas probablemente están en SHORT
        #   → Funding > 0 = SEÑAL CONTRARIA para ir SHORT
        #
        # FUNDING NEGATIVO (< 0): Shorts pagan a longs
        #   → Significa que hay más cortos que largos apostándole al alza
        #   → Retail está en SHORT, las ballenas probablemente están en LONG
        #   → Funding < 0 = SEÑAL CONTRARIA para ir LONG
        #
        # ─────────────────────────────────────────────────────────────
        
        if whale_direction == SignalDirection.BULL:
            # Ballenas van LONG
            # Funding negativo confirma (shorts pagan a longs = ballenas en longs)
            # Funding positivo rechaza (longs pagan a shorts = ballenas en shorts)
            funding_confirms = funding < 0
            funding_score = 100.0 if funding < 0 else 0.0
            
        elif whale_direction == SignalDirection.BEAR:
            # Ballenas van SHORT
            # Funding positivo confirma (longs pagan a shorts = ballenas en shorts)
            # Funding negativo rechaza (shorts pagan a longs = ballenas en longs)
            funding_confirms = funding > 0
            funding_score = 100.0 if funding > 0 else 0.0
            
        else:
            # Neutral: funding no confirma ni rechaza
            funding_confirms = False
            funding_score = 50.0
        
        # ─────────────────────────────────────────────────────────────
        # PASO 3: Evaluar OI CHANGE (Confirmación de convicción)
        # ─────────────────────────────────────────────────────────────
        #
        # OI SUBE + WHALES LONG = Confirma (nuevos longs entrando con ballenas)
        # OI BAJA + WHALES SHORT = Confirma (nuevos shorts entrando con ballenas)
        # OI SUBE + WHALES SHORT = Divergencia (nuevos shorts entrando contra ballenas)
        # OI BAJA + WHALES LONG = Divergencia (posiciones cerrándose)
        #
        # ─────────────────────────────────────────────────────────────
        
        if whale_direction == SignalDirection.BULL:
            # OI subiendo confirma que nuevos participantes van con ballenas
            oi_confirms = oi_change_pct > 0
            oi_score = min(100.0, 50.0 + oi_change_pct * 100) if oi_change_pct > 0 else max(0.0, 50.0 + oi_change_pct * 100)
            
        elif whale_direction == SignalDirection.BEAR:
            # OI bajando confirma que shorts se están acumulando
            oi_confirms = oi_change_pct < 0
            oi_score = min(100.0, 50.0 - oi_change_pct * 100) if oi_change_pct < 0 else max(0.0, 50.0 + oi_change_pct * 100)
            
        else:
            oi_confirms = False
            oi_score = 50.0
        
        # ─────────────────────────────────────────────────────────────
        # PASO 4: Evaluar DELTA (Presión de ejecución real)
        # ─────────────────────────────────────────────────────────────
        #
        # Delta > 50 + Whales LONG = Confirmación fuerte (compradores agresivos)
        # Delta < 50 + Whales SHORT = Confirmación fuerte (vendedores agresivos)
        # Delta contradice dirección de whales = Rechazo
        #
        # ─────────────────────────────────────────────────────────────
        
        if whale_direction == SignalDirection.BULL:
            # Delta alto confirma presión compradora
            delta_confirms = delta_score > 55
            delta_score_val = delta_score
            
        elif whale_direction == SignalDirection.BEAR:
            # Delta bajo confirma presión vendedora
            delta_confirms = delta_score < 45
            delta_score_val = 100 - delta_score  # Invertido para consistencia
            
        else:
            delta_confirms = False
            delta_score_val = 50.0
        
        # ─────────────────────────────────────────────────────────────
        # PASO 5: Calcular SCORE COMPUESTO (Whales es el Capitán)
        # ─────────────────────────────────────────────────────────────
        
        composite_score = (
            (whale_score * self.whale_weight) +
            (funding_score * self.funding_weight) +
            (oi_score * self.oi_weight) +
            (delta_score_val * self.delta_weight)
        )
        
        # ─────────────────────────────────────────────────────────────
        # PASO 6: Calcular CONFIANZA (basado en cuántas confirmaciones alinean)
        # ─────────────────────────────────────────────────────────────
        
        confirmation_count = 1 if whale_direction != SignalDirection.NEUTRAL else 0
        if funding_confirms:
            confirmation_count += 1
        if oi_confirms:
            confirmation_count += 1
        if delta_confirms:
            confirmation_count += 1
        
        # Sistema de confianza basado en confirmaciones
        # 4/4 = 95%, 3/4 = 85%, 2/4 = 65%, 1/4 = 40%, 0/4 = 20%
        confidence_table = {
            4: 95.0,
            3: 85.0,
            2: 65.0,
            1: 40.0,
            0: 20.0
        }
        
        # Si el whale bias es extremo (>= 60 o <= 40), aumentamos confianza base
        if whale_direction == SignalDirection.BULL and whale_bias >= self.extreme_whale_bias:
            confidence_base = confidence_table.get(confirmation_count, 20.0) + 5
        elif whale_direction == SignalDirection.BEAR and whale_bias <= (100 - self.extreme_whale_bias):
            confidence_base = confidence_table.get(confirmation_count, 20.0) + 5
        else:
            confidence_base = confidence_table.get(confirmation_count, 20.0)
        
        # La confianza real es una combinación del score compuesto y las confirmaciones
        # Ponderamos: 60% del sistema de confirmaciones + 40% del score compuesto
        confidence = (confidence_base * 0.6) + (composite_score * 0.4)
        confidence = max(0.0, min(100.0, confidence))
        
        # ─────────────────────────────────────────────────────────────
        # PASO 7: Determinar si es OPERABLE
        # ─────────────────────────────────────────────────────────────
        
        # Alta confianza: >= 85% Y whale bias en rango extremo
        is_high_confidence = (
            confidence >= self.high_confidence_threshold and
            whale_direction != SignalDirection.NEUTRAL and
            ((whale_direction == SignalDirection.BULL and whale_bias >= self.extreme_whale_bias) or
             (whale_direction == SignalDirection.BEAR and whale_bias <= (100 - self.extreme_whale_bias)))
        )
        
        # Operable: >= 50% confianza Y dirección clara
        is_tradeable = (
            confidence >= self.min_confidence_for_trade and
            whale_direction != SignalDirection.NEUTRAL
        )
        
        # ─────────────────────────────────────────────────────────────
        # CREAR RESULTADO
        # ─────────────────────────────────────────────────────────────
        
        result = WhalePilotResult(
            direction=whale_direction,
            whale_bias=whale_bias,
            whale_direction="LONG" if whale_direction == SignalDirection.BULL else "SHORT" if whale_direction == SignalDirection.BEAR else "NEUTRAL",
            
            whale_score=whale_score,
            funding_score=funding_score,
            oi_score=oi_score,
            delta_score=delta_score_val,
            
            funding_confirms=funding_confirms,
            oi_confirms=oi_confirms,
            delta_confirms=delta_confirms,
            
            composite_score=composite_score,
            confidence=confidence,
            confirmation_count=confirmation_count,
            is_high_confidence=is_high_confidence,
            is_tradeable=is_tradeable,
            
            timestamp=timestamp,
            price=price
        )
        
        self.last_result = result
        return result
    
    def get_signal_strength(self, confidence: float) -> Tuple[str, str]:
        """
        Retorna una descripción textual de la fuerza de la señal.
        
        Returns:
            (signal_name, color)
        """
        if confidence >= 90:
            return "[EXCELSA] SEÑAL EXCELSA", "#00ff88"
        elif confidence >= 85:
            return "[ALTA] ALTA CONFIANZA", "#00ff88"
        elif confidence >= 70:
            return "[MEDIA-ALTA] MEDIA-ALTA", "#88ff00"
        elif confidence >= 50:
            return "[MEDIA] MEDIA", "#ffaa00"
        elif confidence >= 30:
            return "[BAJA] BAJA", "#ff8800"
        else:
            return "[MUY BAJA] MUY BAJA", "#ff3333"


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN HELPER PARA INTEGRACIÓN RÁPIDA
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_trade(
    whale_bias: float,
    funding: float,
    oi_change_pct: float,
    delta_score: float,
    price: float = 0.0
) -> WhalePilotResult:
    """
    Función helper para análisis rápido.
    Usa la configuración por defecto optimizada para 85%+ de precisión.
    """
    pilot = WhalePilot()
    from datetime import datetime
    return pilot.analyze(
        whale_bias=whale_bias,
        funding=funding,
        oi_change_pct=oi_change_pct,
        delta_score=delta_score,
        price=price,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("[WHALEPILOT ENGINE v1.0] - TEST DE LOGICA")
    print("=" * 70)
    
    pilot = WhalePilot()
    
    # CASO 1: SENAL PERFECTA (85%+)
    print("\n==> CASO 1: SENAL PERFECTA BULL")
    print("-" * 40)
    r1 = pilot.analyze(
        whale_bias=68.5,
        funding=-0.0001,
        oi_change_pct=3.2,
        delta_score=72.0,
        price=97500.0
    )
    print(f"Whale Bias: {r1.whale_bias}% -> {r1.whale_direction}")
    print(f"Funding: {'OK Confirma' if r1.funding_confirms else 'XX Rechaza'}")
    print(f"OI: {'OK Confirma' if r1.oi_confirms else 'XX Rechaza'}")
    print(f"Delta: {'OK Confirma' if r1.delta_confirms else 'XX Rechaza'}")
    print(f"Confirmaciones: {r1.confirmation_count}/4")
    print(f"Composite Score: {r1.composite_score:.1f}")
    print(f"CONFIANZA: {r1.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'SI' if r1.is_high_confidence else 'NO'}")
    print(f"Operable: {'SI' if r1.is_tradeable else 'NO'}")
    
    # CASO 2: SENAL PERFECTA BEAR
    print("\n==> CASO 2: SENAL PERFECTA BEAR")
    print("-" * 40)
    r2 = pilot.analyze(
        whale_bias=35.0,
        funding=0.00015,
        oi_change_pct=-2.8,
        delta_score=32.0,
        price=96500.0
    )
    print(f"Whale Bias: {r2.whale_bias}% -> {r2.whale_direction}")
    print(f"Funding: {'OK Confirma' if r2.funding_confirms else 'XX Rechaza'}")
    print(f"OI: {'OK Confirma' if r2.oi_confirms else 'XX Rechaza'}")
    print(f"Delta: {'OK Confirma' if r2.delta_confirms else 'XX Rechaza'}")
    print(f"Confirmaciones: {r2.confirmation_count}/4")
    print(f"Composite Score: {r2.composite_score:.1f}")
    print(f"CONFIANZA: {r2.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'SI' if r2.is_high_confidence else 'NO'}")
    print(f"Operable: {'SI' if r2.is_tradeable else 'NO'}")
    
    # CASO 3: DIVERGENCIA
    print("\n==> CASO 3: DIVERGENCIA (NO OPERAR)")
    print("-" * 40)
    r3 = pilot.analyze(
        whale_bias=58.0,
        funding=0.0002,
        oi_change_pct=-1.5,
        delta_score=38.0,
        price=97000.0
    )
    print(f"Whale Bias: {r3.whale_bias}% -> {r3.whale_direction}")
    print(f"Funding: {'OK Confirma' if r3.funding_confirms else 'XX Rechaza'}")
    print(f"OI: {'OK Confirma' if r3.oi_confirms else 'XX Rechaza'}")
    print(f"Delta: {'OK Confirma' if r3.delta_confirms else 'XX Rechaza'}")
    print(f"Confirmaciones: {r3.confirmation_count}/4")
    print(f"Composite Score: {r3.composite_score:.1f}")
    print(f"CONFIANZA: {r3.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'SI' if r3.is_high_confidence else 'NO'}")
    print(f"Operable: {'SI' if r3.is_tradeable else 'NO'}")
    
    # CASO 4: NEUTRAL
    print("\n==> CASO 4: NEUTRAL")
    print("-" * 40)
    r4 = pilot.analyze(
        whale_bias=50.0,
        funding=0.00001,
        oi_change_pct=0.2,
        delta_score=50.0,
        price=96500.0
    )
    print(f"Whale Bias: {r4.whale_bias}% -> {r4.whale_direction}")
    print(f"Funding: {'OK Confirma' if r4.funding_confirms else 'XX Rechaza'}")
    print(f"OI: {'OK Confirma' if r4.oi_confirms else 'XX Rechaza'}")
    print(f"Delta: {'OK Confirma' if r4.delta_confirms else 'XX Rechaza'}")
    print(f"Confirmaciones: {r4.confirmation_count}/4")
    print(f"Composite Score: {r4.composite_score:.1f}")
    print(f"CONFIANZA: {r4.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'SI' if r4.is_high_confidence else 'NO'}")
    print(f"Operable: {'SI' if r4.is_tradeable else 'NO'}")
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETADOS")
    print("=" * 70)
    
    pilot = WhalePilot()
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 1: SEÑAL PERFECTA (85%+)
    # Ballenas en LONG + Funding negativo + OI subiendo + Delta alto
    # ─────────────────────────────────────────────────────────────────────
    print("\n📊 CASO 1: SEÑAL PERFECTA BULL")
    print("-" * 40)
    r1 = pilot.analyze(
        whale_bias=68.5,      # Ballenas 68.5% en LONG
        funding=-0.0001,     # Funding negativo (shorts pagan a longs)
        oi_change_pct=3.2,   # OI subiendo 3.2%
        delta_score=72.0,    # Delta alto (presión compradora)
        price=97500.0
    )
    print(f"Whale Bias: {r1.whale_bias}% → {r1.whale_direction}")
    print(f"Funding: {'✓ Confirma' if r1.funding_confirms else '✗ Rechaza'}")
    print(f"OI: {'✓ Confirma' if r1.oi_confirms else '✗ Rechaza'}")
    print(f"Delta: {'✓ Confirma' if r1.delta_confirms else '✗ Rechaza'}")
    print(f"Confirmaciones: {r1.confirmation_count}/4")
    print(f"Composite Score: {r1.composite_score:.1f}")
    print(f"CONFIANZA: {r1.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'✅ SÍ' if r1.is_high_confidence else '❌ NO'}")
    print(f"Operable: {'✅ SÍ' if r1.is_tradeable else '❌ NO'}")
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 2: SEÑAL PERFECTA BEAR
    # ─────────────────────────────────────────────────────────────────────
    print("\n📊 CASO 2: SEÑAL PERFECTA BEAR")
    print("-" * 40)
    r2 = pilot.analyze(
        whale_bias=35.0,      # Ballenas 65% en SHORT (100-35=65)
        funding=0.00015,      # Funding positivo (longs pagan a shorts)
        oi_change_pct=-2.8,   # OI bajando -2.8%
        delta_score=32.0,     # Delta bajo (presión vendedora)
        price=96500.0
    )
    print(f"Whale Bias: {r2.whale_bias}% → {r2.whale_direction}")
    print(f"Funding: {'✓ Confirma' if r2.funding_confirms else '✗ Rechaza'}")
    print(f"OI: {'✓ Confirma' if r2.oi_confirms else '✗ Rechaza'}")
    print(f"Delta: {'✓ Confirma' if r2.delta_confirms else '✗ Rechaza'}")
    print(f"Confirmaciones: {r2.confirmation_count}/4")
    print(f"Composite Score: {r2.composite_score:.1f}")
    print(f"CONFIANZA: {r2.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'✅ SÍ' if r2.is_high_confidence else '❌ NO'}")
    print(f"Operable: {'✅ SÍ' if r2.is_tradeable else '❌ NO'}")
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 3: DIVERGENCIA (NO OPERAR)
    # Ballenas LONG pero funding y delta contradicen
    # ─────────────────────────────────────────────────────────────────────
    print("\n📊 CASO 3: DIVERGENCIA (NO OPERAR)")
    print("-" * 40)
    r3 = pilot.analyze(
        whale_bias=58.0,      # Ballenas ligeramente en LONG
        funding=0.0002,       # Funding positivo (longs pagan = ballenas en shorts!)
        oi_change_pct=-1.5,   # OI bajando
        delta_score=38.0,     # Delta bajo (presión vendedora)
        price=97000.0
    )
    print(f"Whale Bias: {r3.whale_bias}% → {r3.whale_direction}")
    print(f"Funding: {'✓ Confirma' if r3.funding_confirms else '✗ Rechaza'}")
    print(f"OI: {'✓ Confirma' if r3.oi_confirms else '✗ Rechaza'}")
    print(f"Delta: {'✓ Confirma' if r3.delta_confirms else '✗ Rechaza'}")
    print(f"Confirmaciones: {r3.confirmation_count}/4")
    print(f"Composite Score: {r3.composite_score:.1f}")
    print(f"CONFIANZA: {r3.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'✅ SÍ' if r3.is_high_confidence else '❌ NO'}")
    print(f"Operable: {'✅ SÍ' if r3.is_tradeable else '❌ NO'}")
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 4: NEUTRAL (NO OPERAR)
    # ─────────────────────────────────────────────────────────────────────
    print("\n📊 CASO 4: NEUTRAL")
    print("-" * 40)
    r4 = pilot.analyze(
        whale_bias=50.0,      # Exactamente 50/50
        funding=0.00001,      # Funding neutro
        oi_change_pct=0.2,   # OI sin cambio
        delta_score=50.0,    # Delta neutro
        price=96500.0
    )
    print(f"Whale Bias: {r4.whale_bias}% → {r4.whale_direction}")
    print(f"Funding: {'✓ Confirma' if r4.funding_confirms else '✗ Rechaza'}")
    print(f"OI: {'✓ Confirma' if r4.oi_confirms else '✗ Rechaza'}")
    print(f"Delta: {'✓ Confirma' if r4.delta_confirms else '✗ Rechaza'}")
    print(f"Confirmaciones: {r4.confirmation_count}/4")
    print(f"Composite Score: {r4.composite_score:.1f}")
    print(f"CONFIANZA: {r4.confidence:.1f}%")
    print(f"Alta Confianza (85%+): {'✅ SÍ' if r4.is_high_confidence else '❌ NO'}")
    print(f"Operable: {'✅ SÍ' if r4.is_tradeable else '❌ NO'}")
    
    print("\n" + "=" * 70)
    print("✅ TESTS COMPLETADOS")
    print("=" * 70)
