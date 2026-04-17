"""
WhalePilot Engine v3.0 — Sistema de Trading Inteligente
================================================================================

MEJORAS SOBRE v2.0:
====================
1. DIVERGENCIA 24h vs All-Time: Detecté cuándo el posicionamiento reciente contradice
   el histórico. Si Money Printer está ALL-TIME SHORT pero 24h LONG → está hedgeando.
2. MOMENTUM: Velocidad de cambio del whale_bias. Momentum fuerte en la dirección
   del consenso amplifica la señal. Momentum contrario → posible reversión.
3. REBALANCEO de pesos: 6 factores en vez de 4.

HISTORIAL:
==========
v1.0: Whale bias único + funding binario + OI delta
v2.0: Análisis por cohorte + consenso + funding graduado + liquidación
v3.0: + Divergencia 24h + Momentum temporal + recalibración de pesos

SISTEMA DE PONDERACIÓN v3.0:
=============================
composite = (whale_consensus  * 0.35)     # Consenso + análisis por cohorte
          + (whale_volume_bias * 0.20)    # Bias ponderado por volumen 
          + (liq_proximity     * 0.15)    # Proximidad de muros de liquidación
          + (funding_score     * 0.10)    # Funding graduado
          + (divergence_score  * 0.10)    # Divergencia 24h vs All-Time
          + (momentum_score    * 0.10)    # Velocidad del whale_bias

CONFIANZA FINAL:
===============
confianza = 0.40 * conf_table[consenso] + 0.30 * composite
          + 0.15 * cohort_quality + 0.15 * momentum_alignment
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List
from enum import Enum
import math


class SignalDirection(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


@dataclass
class CohortAnalysis:
    """Análisis individual de una cohorte"""
    name: str
    bias: float          # 0-100 (% long)
    volume: float        # Volumen total en USD
    long_pct: float      # % long
    short_pct: float     # % short
    direction: str       # "LONG" o "SHORT"
    strength: str        # "STRONG", "MODERATE", "WEAK"
    
    
@dataclass
class WhalePilotResult:
    """Resultado del análisis WhalePilot v3.0"""
    direction: SignalDirection
    
    # Análisis de cohortes
    whale_bias: float           # 0-100 (ponderado por volumen)
    whale_direction: str        # "LONG" o "SHORT"
    cohort_consensus: int       # Cuántas cohortes están de acuerdo (0-6)
    total_cohorts: int          # Total de cohortes analizadas
    consensus_direction: str    # Dirección del consenso "LONG"/"SHORT"
    cohort_analyses: List[CohortAnalysis]  # Detalle por cohorte
    
    # Scores individuales (0-100)
    consensus_score: float      # Score de cuántas cohortes están de acuerdo
    volume_bias_score: float    # Score del bias ponderado por volumen
    funding_score: float        # Score de funding (graduado)
    liq_score: float            # Score de proximidad de liquidación
    divergence_score: float     # Score de divergencia 24h vs All-Time
    momentum_score: float       # Score de momentum del whale_bias
    
    # Confirmaciones
    funding_confirms: bool
    liq_confirms: bool
    volume_confirms: bool
    consensus_confirms: bool
    divergence_confirms: bool   # True si 24h y all-time van en la misma dirección
    momentum_confirms: bool     # True si el momentum refuerza la señal
    
    # Resultados
    composite_score: float      # 0-100
    confidence: float           # 0-100%
    confirmation_count: int     # 0-6
    is_high_confidence: bool    # True si >= 80%
    is_tradeable: bool          # True si >= 55% confianza
    
    # Metadata
    quality_label: str          # "EXCELENTE", "ALTA", "MEDIA", "BAJA", "NO OPERAR"
    price: float
    funding_rate: float
    liq_long_kill_dist: float   # Distancia % al Long Kill
    liq_short_kill_dist: float  # Distancia % al Short Kill
    divergence_detail: str      # Detalle de las divergencias detectadas
    momentum_value: float       # Valor crudo del momentum (-50 a +50)
    
    # Resumen de texto para UI
    reason: str                 # Explicación en texto de la señal


class WhalePilot:
    """
    Motor de señal v3.0 — Análisis inteligente multi-factor.
    
    v3.0: Añade Divergencias (24h vs All-Time) y Momentum temporal.
    6 factores independientes, 6 confirmaciones, composite recalibrado.
    """
    
    # Cohortes de alta calidad (más informadas / mayor winrate)
    SMART_COHORTS = {"Money Printer", "Smart Money"}
    
    def __init__(
        self,
        # Pesos del composite (6 factores, suman 1.0)
        consensus_weight: float = 0.35,
        volume_bias_weight: float = 0.20,
        liq_weight: float = 0.15,
        funding_weight: float = 0.10,
        divergence_weight: float = 0.10,
        momentum_weight: float = 0.10,
        # Umbrales
        cohort_bull_threshold: float = 53.0,   # Cohorte > 53% = LONG
        cohort_bear_threshold: float = 47.0,   # Cohorte < 47% = SHORT
        min_confidence_for_trade: float = 55.0,
        high_confidence_threshold: float = 80.0,
        # Funding
        funding_neutral_zone: float = 0.005,   # ±0.005% = zona neutra
        funding_extreme_zone: float = 0.02,    # ±0.02% = zona extrema
        # Divergencia
        divergence_threshold: float = 12.0,    # Diferencia de bias > 12pp = divergencia
        # Momentum
        momentum_strong_threshold: float = 4.0, # Cambio > 4pp en 30min = momentum fuerte
    ):
        # Validar pesos
        total = consensus_weight + volume_bias_weight + liq_weight + funding_weight + divergence_weight + momentum_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Pesos deben sumar 1.0, actual: {total}")
        
        self.consensus_weight = consensus_weight
        self.volume_bias_weight = volume_bias_weight
        self.liq_weight = liq_weight
        self.funding_weight = funding_weight
        self.divergence_weight = divergence_weight
        self.momentum_weight = momentum_weight
        
        self.cohort_bull_threshold = cohort_bull_threshold
        self.cohort_bear_threshold = cohort_bear_threshold
        self.min_confidence_for_trade = min_confidence_for_trade
        self.high_confidence_threshold = high_confidence_threshold
        self.funding_neutral_zone = funding_neutral_zone
        self.funding_extreme_zone = funding_extreme_zone
        self.divergence_threshold = divergence_threshold
        self.momentum_strong_threshold = momentum_strong_threshold
        
        self.last_result: Optional[WhalePilotResult] = None
    
    def analyze(
        self,
        cohort_data: Dict[str, dict],   # {"Money Printer": {"bias": 28.0, "vol": 601e6, "l_val": X, "s_val": Y}, ...}
        funding: float,                  # Tasa de funding (ej: 0.0013 = 0.0013%)
        liq_long_kill_dist: float = 0.0, # Distancia % al Long Kill (negativo, ej: -2.5)
        liq_short_kill_dist: float = 0.0,# Distancia % al Short Kill (positivo, ej: +18.0)
        liq_long_kill_value: float = 0.0,# Magnitud del Long Kill en USD
        liq_short_kill_value: float = 0.0,# Magnitud del Short Kill en USD
        price: float = 0.0,
        # v3.0: Divergencia
        cohort_data_24h: Optional[Dict[str, dict]] = None,  # Datos de 24h para comparar
        # v3.0: Momentum
        whale_bias_history: Optional[list] = None,  # Historial de bias [áltimo, ..., más antiguo]
        # Legacy support: si no hay cohort_data, usar whale_bias directo
        whale_bias: float = -1.0,        # -1 = no usar (usar cohort_data)
    ) -> WhalePilotResult:
        """
        Analiza todos los factores y retorna una señal de trading.
        
        Args:
            cohort_data: Dict con datos de CADA cohorte.
                         Keys: nombre de cohorte
                         Values: dict con 'bias' (0-100), 'vol' (USD), 
                                 'l_val' (long USD), 's_val' (short USD)
            funding: Tasa de funding en % (ej: 0.0013)
            liq_long_kill_dist: Distancia % al muro de liquidación de longs (negativo)
            liq_short_kill_dist: Distancia % al muro de liquidación de shorts (positivo)
            liq_long_kill_value: Valor USD del muro de long kill
            liq_short_kill_value: Valor USD del muro de short kill
            price: Precio actual
            whale_bias: Fallback si no hay cohort_data (compatibilidad v1.0)
        """
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 1: ANÁLISIS POR COHORTE INDIVIDUAL
        # ═══════════════════════════════════════════════════════════════
        
        cohort_analyses = []
        longs_count = 0
        shorts_count = 0
        neutrals_count = 0
        total_long_volume = 0.0
        total_short_volume = 0.0
        smart_cohort_direction = None  # Dirección de las cohortes "inteligentes"
        smart_cohort_agreement = 0     # Cuántas cohortes smart están de acuerdo
        smart_total = 0
        
        if cohort_data and len(cohort_data) > 0:
            for name, data in cohort_data.items():
                bias = data.get('bias', 50.0)
                vol = data.get('vol', 0)
                l_val = data.get('l_val', vol * bias / 100)
                s_val = data.get('s_val', vol * (100 - bias) / 100)
                
                long_pct = bias
                short_pct = 100 - bias
                
                # Determinar dirección individual
                if bias >= self.cohort_bull_threshold:
                    direction = "LONG"
                    longs_count += 1
                elif bias <= self.cohort_bear_threshold:
                    direction = "SHORT"
                    shorts_count += 1
                else:
                    direction = "NEUTRAL"
                    neutrals_count += 1
                
                # Fuerza del posicionamiento
                deviation = abs(bias - 50)
                if deviation >= 20:
                    strength = "STRONG"
                elif deviation >= 8:
                    strength = "MODERATE"
                else:
                    strength = "WEAK"
                
                cohort_analyses.append(CohortAnalysis(
                    name=name,
                    bias=bias,
                    volume=vol,
                    long_pct=long_pct,
                    short_pct=short_pct,
                    direction=direction,
                    strength=strength
                ))
                
                total_long_volume += l_val
                total_short_volume += s_val
                
                # Track Smart Cohorts
                if name in self.SMART_COHORTS:
                    smart_total += 1
                    if direction == "LONG":
                        smart_cohort_agreement += 1
                    elif direction == "SHORT":
                        smart_cohort_agreement -= 1
            
            total_cohorts = longs_count + shorts_count + neutrals_count
            total_volume = total_long_volume + total_short_volume
            
            # Bias ponderado por volumen (REAL, no promedio simple)
            volume_weighted_bias = (total_long_volume / total_volume * 100) if total_volume > 0 else 50.0
            
        else:
            # Fallback v1.0: si no hay cohort_data, usar whale_bias
            wb = whale_bias if whale_bias >= 0 else 50.0
            volume_weighted_bias = wb
            total_cohorts = 1
            
            if wb >= self.cohort_bull_threshold:
                longs_count = 1
            elif wb <= self.cohort_bear_threshold:
                shorts_count = 1
            else:
                neutrals_count = 1
            
            total_long_volume = 0
            total_short_volume = 0
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 2: CONSENSO — ¿Cuántas cohortes están de acuerdo?
        # ═══════════════════════════════════════════════════════════════
        
        if longs_count > shorts_count:
            consensus_direction = "LONG"
            cohort_consensus = longs_count
        elif shorts_count > longs_count:
            consensus_direction = "SHORT"
            cohort_consensus = shorts_count
        else:
            consensus_direction = "NEUTRAL"
            cohort_consensus = max(longs_count, shorts_count)
        
        # Score de consenso (0-100)
        # 6/6 = 100, 5/6 = 90, 4/6 = 75, 3/6 = 55, 2/6 = 35, 1/6 = 15
        if total_cohorts > 0:
            consensus_ratio = cohort_consensus / total_cohorts
            # Curva exponencial: más consenso = mucho más score
            consensus_score = min(100.0, (consensus_ratio ** 0.7) * 100)
        else:
            consensus_score = 50.0
        
        # Bonus por Smart Cohorts de acuerdo
        if smart_total > 0:
            if (consensus_direction == "SHORT" and smart_cohort_agreement <= -smart_total) or \
               (consensus_direction == "LONG" and smart_cohort_agreement >= smart_total):
                # Smart Money está 100% alineado con el consenso
                consensus_score = min(100.0, consensus_score + 8)
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 3: BIAS PONDERADO POR VOLUMEN
        # ═══════════════════════════════════════════════════════════════
        
        # Convertir bias a score direccional (0-100 donde 100 = máxima convicción)
        if consensus_direction == "LONG":
            volume_bias_score = volume_weighted_bias  # Más alto = más bullish
        elif consensus_direction == "SHORT":
            volume_bias_score = 100 - volume_weighted_bias  # Más bajo = más bearish
        else:
            volume_bias_score = 50.0
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 4: FUNDING GRADUADO (no binario)
        # ═══════════════════════════════════════════════════════════════
        #
        # Funding POSITIVO (> 0): Longs pagan → overcrowded longs → bearish signal
        # Funding NEGATIVO (< 0): Shorts pagan → overcrowded shorts → bullish signal
        # Funding ≈ 0: Neutro, no da información
        #
        # CONFIRMACIÓN:
        #   - Si consenso = LONG y funding < 0 → CONFIRMA (shorts pagan, squeeze alcista)
        #   - Si consenso = SHORT y funding > 0 → CONFIRMA (longs pagan, squeeze bajista)
        #   - Si contradice → RECHAZA pero de forma graduada
        # ═══════════════════════════════════════════════════════════════
        
        funding_pct = funding * 100 if abs(funding) < 1 else funding  # Normalizar
        # Si el valor ya viene como porcentaje (ej: 0.0013), mantenerlo
        # Si viene como decimal puro (ej: 0.000013), convertir
        if abs(funding) < 0.01:
            funding_pct = funding * 100  # 0.0013 → 0.13 (no, queremos 0.0013%)
            # Actually, Hyperliquid devuelve funding como decimal: 0.000013 = 0.0013%
            # Pero en el código actual se pasa funding raw, vamos a normalizar:
            funding_pct = funding  # Mantener como está, el umbral se ajusta

        # Graduación del funding
        abs_funding = abs(funding)
        
        if abs_funding <= self.funding_neutral_zone / 100:
            # Zona neutra: funding ≈ 0, no da info
            funding_intensity = 0.0  # 0 = completamente neutro
        elif abs_funding >= self.funding_extreme_zone / 100:
            # Zona extrema: señal contraria fuerte
            funding_intensity = 1.0  # 100% de intensidad
        else:
            # Zona intermedia: interpolación lineal
            neutral = self.funding_neutral_zone / 100
            extreme = self.funding_extreme_zone / 100
            funding_intensity = (abs_funding - neutral) / (extreme - neutral)
        
        if consensus_direction == "LONG":
            # LONG: funding negativo confirma, positivo rechaza
            if funding < 0:
                funding_confirms = True
                funding_score = 50.0 + (funding_intensity * 50.0)  # 50-100
            else:
                funding_confirms = False
                funding_score = 50.0 - (funding_intensity * 50.0)  # 0-50
                
        elif consensus_direction == "SHORT":
            # SHORT: funding positivo confirma, negativo rechaza
            if funding > 0:
                funding_confirms = True
                funding_score = 50.0 + (funding_intensity * 50.0)  # 50-100
            else:
                funding_confirms = False
                funding_score = 50.0 - (funding_intensity * 50.0)  # 0-50
        else:
            funding_confirms = False
            funding_score = 50.0
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 5: PROXIMIDAD DE LIQUIDACIÓN (Gravedad)
        # ═══════════════════════════════════════════════════════════════
        #
        # CONCEPTO: El precio es atraído hacia los muros de liquidación
        # como un imán. Si el Long Kill está a -2.5% y el Short Kill a +18%,
        # el precio tiene MUCHO más probabilidad de ir hacia abajo.
        #
        # FACTORES:
        #   1. Distancia relativa: ¿Cuál muro está más cerca?
        #   2. Magnitud: ¿Cuántos dólares se liquidan en cada muro?
        #   3. Asimetría: Gran diferencia = señal fuerte
        # ═══════════════════════════════════════════════════════════════
        
        abs_long_dist = abs(liq_long_kill_dist) if liq_long_kill_dist != 0 else 999
        abs_short_dist = abs(liq_short_kill_dist) if liq_short_kill_dist != 0 else 999
        
        if abs_long_dist < 999 and abs_short_dist < 999 and (abs_long_dist + abs_short_dist) > 0:
            # Ratio de distancia: qué tan asimétrico es
            # Si Long Kill está a 2.5% y Short Kill a 18%, ratio = 2.5/(2.5+18) = 0.12
            # Un ratio bajo = Long Kill MUY cerca = presión bajista
            distance_ratio = abs_long_dist / (abs_long_dist + abs_short_dist)
            
            # Si distance_ratio < 0.3 → Long Kill mucho más cerca → BAJISTA
            # Si distance_ratio > 0.7 → Short Kill mucho más cerca → ALCISTA
            # Si distance_ratio ≈ 0.5 → Equilibrado → NEUTRO
            
            # También considerar la magnitud de cada muro
            total_liq_value = liq_long_kill_value + liq_short_kill_value
            if total_liq_value > 0:
                long_kill_weight = liq_long_kill_value / total_liq_value
            else:
                long_kill_weight = 0.5
            
            # Score combinado: distancia + magnitud
            # distance_ratio bajo + long_kill_weight alto = BAJISTA extremo
            # distance_ratio alto + long_kill_weight bajo = ALCISTA extremo
            liq_bearish_pressure = (1 - distance_ratio) * 0.6 + long_kill_weight * 0.4
            
            if consensus_direction == "SHORT":
                # Ballenas SHORT + Long Kill cercano = CONFIRMA
                liq_confirms = liq_bearish_pressure > 0.55
                liq_score = liq_bearish_pressure * 100
            elif consensus_direction == "LONG":
                # Ballenas LONG + Short Kill cercano = CONFIRMA
                liq_confirms = liq_bearish_pressure < 0.45
                liq_score = (1 - liq_bearish_pressure) * 100
            else:
                liq_confirms = False
                liq_score = 50.0
            
            # Bonus por proximidad extrema (< 3% de distancia)
            min_dist = min(abs_long_dist, abs_short_dist)
            if min_dist < 3.0:
                # Muro MUY cercano amplifica la señal
                proximity_bonus = (3.0 - min_dist) / 3.0 * 15  # Hasta +15 puntos
                if (consensus_direction == "SHORT" and abs_long_dist < abs_short_dist) or \
                   (consensus_direction == "LONG" and abs_short_dist < abs_long_dist):
                    liq_score = min(100.0, liq_score + proximity_bonus)
        else:
            # Sin datos de liquidación
            liq_confirms = False
            liq_score = 50.0
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 5.5: DIVERGENCIA 24h vs ALL-TIME (v3.0)
        # ═══════════════════════════════════════════════════════════════
        #
        # CONCEPTO: Si una cohorte está ALL-TIME SHORT pero 24h LONG,
        # está hedgeando o revirtiendo. Esto crea incertidumbre y
        # debería PENALIZAR la confianza en esa dirección.
        #
        # SCORE:
        #   - Sin divergencias = 80 (confirma, todo alineado)
        #   - Divergencia leve (1 cohorte) = 60
        #   - Divergencia fuerte (2+ cohortes o Smart Cohort) = 30-40
        #   - Total contradicción = 20 (máxima penalización)
        # ═══════════════════════════════════════════════════════════════
        
        divergence_details = []
        divergence_count = 0
        smart_divergence = False
        
        if cohort_data and cohort_data_24h and len(cohort_data_24h) > 0:
            for c_name in cohort_data:
                if c_name in cohort_data_24h:
                    bias_alltime = cohort_data[c_name].get('bias', 50)
                    bias_24h = cohort_data_24h[c_name].get('bias', 50)
                    diff = abs(bias_24h - bias_alltime)
                    
                    if diff >= self.divergence_threshold:
                        divergence_count += 1
                        at_dir = "L" if bias_alltime > 50 else "S"
                        h24_dir = "L" if bias_24h > 50 else "S"
                        divergence_details.append(f"{c_name}: AT={at_dir} 24h={h24_dir} Δ{diff:.0f}")
                        
                        if c_name in self.SMART_COHORTS:
                            smart_divergence = True
            
            # Calcular score de divergencia
            if divergence_count == 0:
                divergence_score = 80.0  # Todo alineado = bueno
                divergence_confirms = True
            elif smart_divergence:
                # Smart Cohort diverge = penalización fuerte
                divergence_score = 30.0
                divergence_confirms = False
            elif divergence_count == 1:
                divergence_score = 60.0  # Leve
                divergence_confirms = True
            elif divergence_count >= 2:
                divergence_score = 35.0  # Múltiples divergencias
                divergence_confirms = False
            else:
                divergence_score = 50.0
                divergence_confirms = False
        else:
            # Sin datos de 24h → neutro (no penalizar ni premiar)
            divergence_score = 50.0
            divergence_confirms = False
            divergence_details = []
        
        divergence_detail_str = " | ".join(divergence_details) if divergence_details else "Sin divergencias"
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 5.6: MOMENTUM DEL WHALE BIAS (v3.0)
        # ═══════════════════════════════════════════════════════════════
        #
        # CONCEPTO: No solo importa DÓNDE está el bias, sino HACIA DÓNDE
        # se mueve. Si el bias era 45% hace 30min y ahora es 55%,
        # las ballenas están rotando agresivamente a LONG.
        #
        # momentum > 0 = ballenas moviéndose hacia LONG
        # momentum < 0 = ballenas moviéndose hacia SHORT
        #
        # SCORE:
        #   - Momentum fuerte alineado con consenso = 85 (amplifica)
        #   - Momentum débil/neutro = 50
        #   - Momentum fuerte CONTRA el consenso = 20 (alerta de reversión)
        # ═══════════════════════════════════════════════════════════════
        
        momentum_value = 0.0
        
        if whale_bias_history and len(whale_bias_history) >= 2:
            # Momentum = diferencia entre bias actual y el más antiguo disponible
            current_bias = whale_bias_history[0] if whale_bias_history else volume_weighted_bias
            oldest_bias = whale_bias_history[-1]
            momentum_value = current_bias - oldest_bias  # positivo = hacia LONG
            
            abs_momentum = abs(momentum_value)
            
            if abs_momentum < 1.0:
                # Momentum despreciable
                momentum_score = 50.0
                momentum_confirms = False
            elif abs_momentum >= self.momentum_strong_threshold:
                # Momentum fuerte
                if (consensus_direction == "LONG" and momentum_value > 0) or \
                   (consensus_direction == "SHORT" and momentum_value < 0):
                    # Alineado con consenso = amplifica
                    momentum_score = min(95.0, 70.0 + abs_momentum * 3)
                    momentum_confirms = True
                else:
                    # Contra el consenso = alerta de reversión
                    momentum_score = max(15.0, 40.0 - abs_momentum * 3)
                    momentum_confirms = False
            else:
                # Momentum moderado (1-4pp)
                intensity = abs_momentum / self.momentum_strong_threshold
                if (consensus_direction == "LONG" and momentum_value > 0) or \
                   (consensus_direction == "SHORT" and momentum_value < 0):
                    momentum_score = 50.0 + intensity * 20.0  # 50-70
                    momentum_confirms = True
                else:
                    momentum_score = 50.0 - intensity * 15.0  # 35-50
                    momentum_confirms = False
        else:
            # Sin historial = neutro
            momentum_score = 50.0
            momentum_confirms = False
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 6: COMPOSITE SCORE v3.0 (6 Factores)
        # ═══════════════════════════════════════════════════════════════
        
        composite_score = (
            (consensus_score * self.consensus_weight) +
            (volume_bias_score * self.volume_bias_weight) +
            (liq_score * self.liq_weight) +
            (funding_score * self.funding_weight) +
            (divergence_score * self.divergence_weight) +
            (momentum_score * self.momentum_weight)
        )
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 7: CONFIANZA FINAL v3.0 (6 Confirmaciones)
        # ═══════════════════════════════════════════════════════════════
        
        # Confirmaciones totales (ahora 6)
        confirmation_count = 0
        if consensus_confirms := (cohort_consensus >= max(2, total_cohorts * 0.6)):
            confirmation_count += 1
        if volume_confirms := (volume_bias_score >= 55 if consensus_direction in ("SHORT", "LONG") else False):
            confirmation_count += 1
        if funding_confirms:
            confirmation_count += 1
        if liq_confirms:
            confirmation_count += 1
        if divergence_confirms:
            confirmation_count += 1
        if momentum_confirms:
            confirmation_count += 1
        
        # Tabla de confianza recalibrada para 6 confirmaciones
        confidence_table = {
            6: 95.0,   # Confluencia perfecta
            5: 88.0,   # Casi perfecta
            4: 78.0,   # Fuerte
            3: 65.0,   # Moderada
            2: 50.0,   # Débil
            1: 32.0,   # Muy débil
            0: 12.0    # Nada se alinea
        }
        
        confidence_base = confidence_table.get(confirmation_count, 12.0)
        
        # Calidad de cohortes: Smart Money + Money Printer de acuerdo = bonus
        cohort_quality_bonus = 0
        if smart_total > 0:
            if abs(smart_cohort_agreement) == smart_total:
                cohort_quality_bonus = 8  # Todas las smart cohorts alineadas
            elif abs(smart_cohort_agreement) >= 1:
                cohort_quality_bonus = 4  # Al menos 1 smart cohort alineada
        
        # Consenso fuerte bonus
        if total_cohorts >= 4:
            consensus_ratio_check = cohort_consensus / total_cohorts
            if consensus_ratio_check >= 0.83:  # 5/5 o 5/6
                cohort_quality_bonus += 6
            elif consensus_ratio_check >= 0.67:  # 4/5 o 4/6
                cohort_quality_bonus += 3
        
        # Momentum alignment bonus/penalty
        momentum_alignment = 0
        if momentum_confirms and abs(momentum_value) >= self.momentum_strong_threshold:
            momentum_alignment = 6  # Momentum fuerte alineado
        elif not momentum_confirms and abs(momentum_value) >= self.momentum_strong_threshold:
            momentum_alignment = -4  # Momentum fuerte en contra = penalización
        
        # Confianza final v3.0: 4 componentes
        confidence = (
            confidence_base * 0.40 +
            composite_score * 0.30 +
            cohort_quality_bonus * 0.15 * 10 +  # Normalizado a escala 0-100ish
            max(0, momentum_alignment) * 0.15 * 10
        )
        # Penalización por momentum en contra (se resta, no se mezcla)
        if momentum_alignment < 0:
            confidence += momentum_alignment
        
        confidence = max(0.0, min(100.0, confidence))
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 8: DIRECCIÓN FINAL Y CALIDAD
        # ═══════════════════════════════════════════════════════════════
        
        if consensus_direction == "LONG" and confidence >= self.min_confidence_for_trade:
            final_direction = SignalDirection.BULL
        elif consensus_direction == "SHORT" and confidence >= self.min_confidence_for_trade:
            final_direction = SignalDirection.BEAR
        else:
            final_direction = SignalDirection.NEUTRAL
        
        is_high_confidence = confidence >= self.high_confidence_threshold and final_direction != SignalDirection.NEUTRAL
        is_tradeable = confidence >= self.min_confidence_for_trade and final_direction != SignalDirection.NEUTRAL
        
        # Etiqueta de calidad
        if confidence >= 85:
            quality_label = "EXCELENTE"
        elif confidence >= 75:
            quality_label = "ALTA"
        elif confidence >= 60:
            quality_label = "MEDIA"
        elif confidence >= 45:
            quality_label = "BAJA"
        else:
            quality_label = "NO OPERAR"
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 9: GENERAR RAZÓN EN TEXTO
        # ═══════════════════════════════════════════════════════════════
        
        reason = self._generate_reason(
            consensus_direction, cohort_consensus, total_cohorts,
            volume_weighted_bias, funding, funding_confirms,
            abs_long_dist, abs_short_dist, liq_confirms,
            confidence, cohort_analyses,
            divergence_count, smart_divergence,
            momentum_value, momentum_confirms
        )
        
        # ═══════════════════════════════════════════════════════════════
        # CREAR RESULTADO v3.0
        # ═══════════════════════════════════════════════════════════════
        
        result = WhalePilotResult(
            direction=final_direction,
            
            whale_bias=volume_weighted_bias,
            whale_direction=consensus_direction,
            cohort_consensus=cohort_consensus,
            total_cohorts=total_cohorts,
            consensus_direction=consensus_direction,
            cohort_analyses=cohort_analyses,
            
            consensus_score=consensus_score,
            volume_bias_score=volume_bias_score,
            funding_score=funding_score,
            liq_score=liq_score,
            divergence_score=divergence_score,
            momentum_score=momentum_score,
            
            funding_confirms=funding_confirms,
            liq_confirms=liq_confirms,
            volume_confirms=volume_confirms,
            consensus_confirms=consensus_confirms,
            divergence_confirms=divergence_confirms,
            momentum_confirms=momentum_confirms,
            
            composite_score=composite_score,
            confidence=confidence,
            confirmation_count=confirmation_count,
            is_high_confidence=is_high_confidence,
            is_tradeable=is_tradeable,
            
            quality_label=quality_label,
            price=price,
            funding_rate=funding,
            liq_long_kill_dist=liq_long_kill_dist,
            liq_short_kill_dist=liq_short_kill_dist,
            divergence_detail=divergence_detail_str,
            momentum_value=momentum_value,
            
            reason=reason
        )
        
        self.last_result = result
        return result
    
    def _generate_reason(
        self, consensus_dir, consensus_count, total, 
        vol_bias, funding, funding_confirms,
        long_dist, short_dist, liq_confirms,
        confidence, cohort_analyses,
        divergence_count=0, smart_divergence=False,
        momentum_value=0.0, momentum_confirms=False
    ) -> str:
        """Genera una explicación en texto de la señal v3.0"""
        parts = []
        
        # Consenso
        if total > 0:
            parts.append(f"{consensus_count}/{total} cohortes {consensus_dir}")
        
        # Cohortes fuertes
        strong = [c for c in cohort_analyses if c.strength == "STRONG"]
        if strong:
            names = ", ".join([c.name for c in strong[:3]])
            parts.append(f"Fuertes: {names}")
        
        # Funding
        if funding_confirms:
            parts.append("Funding confirma")
        elif abs(funding) > 0.0001:
            parts.append("Funding contradice")
        
        # Liquidaciones
        if liq_confirms:
            if consensus_dir == "SHORT" and long_dist < 999:
                parts.append(f"Long Kill cerca (-{long_dist:.1f}%)")
            elif consensus_dir == "LONG" and short_dist < 999:
                parts.append(f"Short Kill cerca (+{short_dist:.1f}%)")
        
        # v3.0: Divergencia
        if divergence_count > 0:
            if smart_divergence:
                parts.append(f"⚠️ Divergencia Smart ({divergence_count})")
            else:
                parts.append(f"Divergencia x{divergence_count}")
        
        # v3.0: Momentum
        if abs(momentum_value) >= self.momentum_strong_threshold:
            m_dir = "↑LONG" if momentum_value > 0 else "↓SHORT"
            if momentum_confirms:
                parts.append(f"Momentum {m_dir} ✓")
            else:
                parts.append(f"⚠️ Momentum {m_dir} contradice")
        
        return " | ".join(parts) if parts else "Sin datos suficientes"
    
    def get_signal_strength(self, confidence: float) -> Tuple[str, str]:
        """Retorna descripción y color de la fuerza de señal"""
        if confidence >= 85:
            return "EXCELENTE", "#00ff88"
        elif confidence >= 75:
            return "ALTA", "#66ff99"
        elif confidence >= 60:
            return "MEDIA", "#ffaa00"
        elif confidence >= 45:
            return "BAJA", "#ff8800"
        else:
            return "NO OPERAR", "#ff3333"


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN HELPER PARA INTEGRACIÓN RÁPIDA
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_trade(
    cohort_data: Dict[str, dict],
    funding: float,
    liq_long_kill_dist: float = 0.0,
    liq_short_kill_dist: float = 0.0,
    liq_long_kill_value: float = 0.0,
    liq_short_kill_value: float = 0.0,
    price: float = 0.0,
    cohort_data_24h: Optional[Dict[str, dict]] = None,
    whale_bias_history: Optional[list] = None
) -> WhalePilotResult:
    """Función helper para análisis rápido con configuración por defecto v3.0."""
    pilot = WhalePilot()
    return pilot.analyze(
        cohort_data=cohort_data,
        funding=funding,
        liq_long_kill_dist=liq_long_kill_dist,
        liq_short_kill_dist=liq_short_kill_dist,
        liq_long_kill_value=liq_long_kill_value,
        liq_short_kill_value=liq_short_kill_value,
        price=price,
        cohort_data_24h=cohort_data_24h,
        whale_bias_history=whale_bias_history
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TESTING con datos REALES de la captura del usuario
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("[WHALEPILOT ENGINE v3.0] - TEST CON DATOS REALES")
    print("=" * 70)
    
    pilot = WhalePilot()
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO REAL: Datos captura (Whales Top 5 - v4 cohorts)
    # ─────────────────────────────────────────────────────────────────────
    print("\n📊 CASO 1: BEAR con divergencia (MP SHORT all-time, LONG 24h)")
    print("-" * 50)
    
    real_cohort_data = {
        "Money Printer": {"bias": 28.0, "vol": 601e6, "l_val": 601e6 * 0.28, "s_val": 601e6 * 0.72},
        "Leviathan":     {"bias": 50.7, "vol": 494e6, "l_val": 494e6 * 0.507, "s_val": 494e6 * 0.493},
        "Tidal Whale":   {"bias": 44.6, "vol": 482e6, "l_val": 482e6 * 0.446, "s_val": 482e6 * 0.554},
        "Smart Money":   {"bias": 26.6, "vol": 202e6, "l_val": 202e6 * 0.266, "s_val": 202e6 * 0.734},
        "Giga-Rekt":     {"bias": 65.0, "vol": 80e6, "l_val": 80e6 * 0.65, "s_val": 80e6 * 0.35},
    }
    
    # v3.0: datos de 24h simulando divergencia en Money Printer
    real_24h_data = {
        "Money Printer": {"bias": 58.0, "vol": 200e6},  # ¡24h LONG vs All-time SHORT! Divergencia
        "Leviathan":     {"bias": 48.0, "vol": 150e6},
        "Tidal Whale":   {"bias": 42.0, "vol": 180e6},
        "Smart Money":   {"bias": 30.0, "vol": 90e6},
        "Giga-Rekt":     {"bias": 60.0, "vol": 30e6},
    }
    
    # v3.0: historial de bias simulado (bias bajando = momentum SHORT)
    bias_history = [38.0, 39.5, 41.0, 43.0, 44.5, 46.0]  # Último=38, antiguo=46 → momentum -8
    
    r1 = pilot.analyze(
        cohort_data=real_cohort_data,
        funding=0.000013,
        liq_long_kill_dist=-2.5,
        liq_short_kill_dist=18.0,
        liq_long_kill_value=50e6,
        liq_short_kill_value=41e6,
        price=65735.0,
        cohort_data_24h=real_24h_data,
        whale_bias_history=bias_history
    )
    
    print(f"\n{'─' * 50}")
    print(f"  DIRECCIÓN: {r1.direction.value}")
    print(f"  CONFIANZA: {r1.confidence:.1f}% ({r1.quality_label})")
    print(f"  OPERABLE:  {'✅ SÍ' if r1.is_tradeable else '❌ NO'}")
    print(f"  ALTA CONF: {'✅ SÍ' if r1.is_high_confidence else '❌ NO'}")
    print(f"{'─' * 50}")
    
    print(f"\n📋 ANÁLISIS POR COHORTE:")
    for ca in r1.cohort_analyses:
        emoji = "🟢" if ca.direction == "LONG" else "🔴" if ca.direction == "SHORT" else "⚪"
        print(f"  {emoji} {ca.name:20s} → {ca.direction:6s} ({ca.long_pct:.1f}% L / {ca.short_pct:.1f}% S) [{ca.strength}] ${ca.volume/1e6:.0f}M")
    
    print(f"\n🔢 SCORES (6 factores):")
    print(f"  Consenso:    {r1.consensus_score:.1f}/100  ({r1.cohort_consensus}/{r1.total_cohorts} {r1.consensus_direction})")
    print(f"  Vol Bias:    {r1.volume_bias_score:.1f}/100  (Bias ponderado: {r1.whale_bias:.1f}%)")
    print(f"  Liquidación: {r1.liq_score:.1f}/100  (LK: {r1.liq_long_kill_dist:.1f}% / SK: +{r1.liq_short_kill_dist:.1f}%)")
    print(f"  Funding:     {r1.funding_score:.1f}/100  ({'✓' if r1.funding_confirms else '✗'})")
    print(f"  Divergencia: {r1.divergence_score:.1f}/100  ({'✓' if r1.divergence_confirms else '✗'})  [{r1.divergence_detail}]")
    print(f"  Momentum:    {r1.momentum_score:.1f}/100  ({'✓' if r1.momentum_confirms else '✗'})  [Δ{r1.momentum_value:+.1f}pp]")
    print(f"  COMPOSITE:   {r1.composite_score:.1f}/100")
    
    print(f"\n✅ CONFIRMACIONES: {r1.confirmation_count}/6")
    print(f"  {'✓' if r1.consensus_confirms else '✗'} Consenso")
    print(f"  {'✓' if r1.volume_confirms else '✗'} Volumen")
    print(f"  {'✓' if r1.funding_confirms else '✗'} Funding")
    print(f"  {'✓' if r1.liq_confirms else '✗'} Liquidación")
    print(f"  {'✓' if r1.divergence_confirms else '✗'} Divergencia")
    print(f"  {'✓' if r1.momentum_confirms else '✗'} Momentum")
    
    print(f"\n💬 RAZÓN: {r1.reason}")
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 2: Mercado BULL fuerte SIN divergencia + momentum alineado
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 70}")
    print("📊 CASO 2: Mercado BULL fuerte con momentum alineado")
    print("-" * 50)
    
    bull_data = {
        "Money Printer": {"bias": 72.0, "vol": 500e6, "l_val": 360e6, "s_val": 140e6},
        "Leviathan":     {"bias": 65.0, "vol": 400e6, "l_val": 260e6, "s_val": 140e6},
        "Tidal Whale":   {"bias": 68.0, "vol": 350e6, "l_val": 238e6, "s_val": 112e6},
        "Smart Money":   {"bias": 74.0, "vol": 200e6, "l_val": 148e6, "s_val": 52e6},
        "Giga-Rekt":     {"bias": 30.0, "vol": 60e6, "l_val": 18e6, "s_val": 42e6},
    }
    
    bull_24h = {
        "Money Printer": {"bias": 75.0, "vol": 250e6},
        "Leviathan":     {"bias": 67.0, "vol": 200e6},
        "Tidal Whale":   {"bias": 70.0, "vol": 180e6},
        "Smart Money":   {"bias": 76.0, "vol": 100e6},
        "Giga-Rekt":     {"bias": 28.0, "vol": 30e6},
    }
    
    bull_momentum = [68.0, 65.0, 62.0, 58.0, 55.0, 52.0]  # Subiendo → momentum LONG +16
    
    r2 = pilot.analyze(
        cohort_data=bull_data,
        funding=-0.0001,
        liq_long_kill_dist=-15.0,
        liq_short_kill_dist=3.5,
        liq_long_kill_value=30e6,
        liq_short_kill_value=80e6,
        price=68000.0,
        cohort_data_24h=bull_24h,
        whale_bias_history=bull_momentum
    )
    
    print(f"\n  DIRECCIÓN: {r2.direction.value} | CONFIANZA: {r2.confidence:.1f}% ({r2.quality_label})")
    print(f"  Consenso: {r2.cohort_consensus}/{r2.total_cohorts} {r2.consensus_direction}")
    print(f"  Divergencia: {r2.divergence_score:.1f} [{r2.divergence_detail}]")
    print(f"  Momentum: {r2.momentum_score:.1f} [Δ{r2.momentum_value:+.1f}pp]")
    print(f"  CONFIRMACIONES: {r2.confirmation_count}/6")
    print(f"  💬 {r2.reason}")
    
    # ─────────────────────────────────────────────────────────────────────
    # CASO 3: Mercado dividido con momentum contra consenso
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 70}")
    print("📊 CASO 3: DIVIDIDO con momentum CONTRA consenso")
    print("-" * 50)
    
    mixed_data = {
        "Money Printer": {"bias": 55.0, "vol": 400e6, "l_val": 220e6, "s_val": 180e6},
        "Leviathan":     {"bias": 45.0, "vol": 380e6, "l_val": 171e6, "s_val": 209e6},
        "Tidal Whale":   {"bias": 52.0, "vol": 300e6, "l_val": 156e6, "s_val": 144e6},
        "Smart Money":   {"bias": 48.0, "vol": 200e6, "l_val": 96e6, "s_val": 104e6},
        "Giga-Rekt":     {"bias": 50.0, "vol": 50e6, "l_val": 25e6, "s_val": 25e6},
    }
    
    mixed_momentum = [49.0, 50.0, 52.0, 56.0, 58.0, 60.0]  # Bajando → momentum SHORT -11
    
    r3 = pilot.analyze(
        cohort_data=mixed_data,
        funding=0.00001,
        liq_long_kill_dist=-8.0,
        liq_short_kill_dist=10.0,
        liq_long_kill_value=40e6,
        liq_short_kill_value=45e6,
        price=67000.0,
        whale_bias_history=mixed_momentum
    )
    
    print(f"\n  DIRECCIÓN: {r3.direction.value} | CONFIANZA: {r3.confidence:.1f}% ({r3.quality_label})")
    print(f"  Consenso: {r3.cohort_consensus}/{r3.total_cohorts} {r3.consensus_direction}")
    print(f"  Momentum: {r3.momentum_score:.1f} [Δ{r3.momentum_value:+.1f}pp]")
    print(f"  CONFIRMACIONES: {r3.confirmation_count}/6")
    print(f"  💬 {r3.reason}")
    
    print(f"\n\n{'=' * 70}")
    print("✅ TESTS COMPLETADOS — WhalePilot v3.0")
    print("=" * 70)

