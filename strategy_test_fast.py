# strategy_test_fast.py
# ============================================================
# ESTRATEGIA DE PRUEBA – SEÑALES ALEATORIAS CON TP/SL/TRAILING
# ============================================================

import random
from typing import List, Dict, Optional
from datetime import datetime
from models import Signal
from signals import fetch_okx_candles, calculate_atr
from config import SYMBOLS, TRADE_NOTIONAL, TEST_MODE, TEST_SPEED_LEVEL, TRAILING_ENABLED, TRAILING_DISTANCE_ATR

def get_best_signal(symbols: List[str] = None,
                    speed_levels: List[Dict] = None,
                    speed_levels_override: Dict[str, Dict] = None) -> Optional[Signal]:
    """
    Estrategia de prueba: genera señales aleatorias cada 3-5 velas.
    - Alterna Long/Short aleatoriamente.
    - Establece TP y SL basados en ATR.
    - Si TRAILING_ENABLED está activo, se envía trailing stop.
    - Solo para validar infraestructura.
    """
    if symbols is None:
        symbols = SYMBOLS

    # Seleccionar un símbolo aleatorio
    symbol = random.choice(symbols)

    # Descargar datos para ese símbolo
    df = fetch_okx_candles(symbol, limit=50)
    if df.empty:
        return None

    # Usar nivel de prueba si TEST_MODE está activo
    if TEST_MODE:
        level = TEST_SPEED_LEVEL
    else:
        level = speed_levels_override.get(symbol, {}).get('Long', {'nivel': 6, 'raw_min': 0.1, 'roc_min': 0.05})

    # Tomar la última vela
    last = df.iloc[-1]
    entry = last['c']
    atr = calculate_atr(df, 14).iloc[-1]

    # Alternar dirección aleatoriamente
    direction = random.choice(['Long', 'Short'])
    if direction == 'Long':
        tp = entry + atr * 0.8   # TP más cercano para validar
        sl = entry - atr * 1.0
    else:
        tp = entry - atr * 0.8
        sl = entry + atr * 1.0

    confidence = 0.8 + random.random() * 0.2
    speed_score = 1.0 + random.random() * 0.5

    # Registrar en logs que se generó una señal de prueba
    from telemetry import telemetry
    telemetry.log_info("test_fast", f"Señal aleatoria generada: {direction} {symbol} a {entry:.2f}")

    return Signal(
        symbol=symbol,
        direction=direction,
        timestamp=datetime.utcnow(),
        entry_price=entry,
        target_price=tp,
        stop_loss=sl,
        confidence=confidence,
        speed_score=speed_score,
        speed_level="TEST",
        notional=TRADE_NOTIONAL
    )

# No se usa generate_signal en esta estrategia
generate_signal = None
