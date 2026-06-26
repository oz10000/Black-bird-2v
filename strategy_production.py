# strategy_production.py
# ============================================================
# ESTRATEGIA DE PRODUCCIÓN (PiDelta optimizada)
# ============================================================

from typing import List, Dict, Optional
from models import Signal
from signals import fetch_okx_candles, generate_signal as _generate_signal
from config import SYMBOLS, SPEED_LEVELS, DEFAULT_SPEED_LEVEL

def get_best_signal(symbols: List[str] = None,
                    speed_levels: List[Dict] = None,
                    speed_levels_override: Dict[str, Dict] = None) -> Optional[Signal]:
    """
    Selecciona la mejor señal utilizando PiDelta con nivel N1.
    Comportamiento idéntico a la versión original.
    """
    if symbols is None:
        symbols = SYMBOLS
    if speed_levels is None and speed_levels_override is None:
        speed_levels = SPEED_LEVELS

    best_signal = None
    best_score = -1.0

    for symbol in symbols:
        df = fetch_okx_candles(symbol, limit=150)
        if df.empty:
            continue

        if speed_levels_override and symbol in speed_levels_override:
            for direction, level in speed_levels_override[symbol].items():
                sig = _generate_signal(df, symbol, direction, level)
                if sig and sig.speed_score > best_score:
                    best_score = sig.speed_score
                    best_signal = sig
        else:
            levels = speed_levels if speed_levels is not None else SPEED_LEVELS
            for level in levels:
                for direction in ["Long", "Short"]:
                    sig = _generate_signal(df, symbol, direction, level)
                    if sig and sig.speed_score > best_score:
                        best_score = sig.speed_score
                        best_signal = sig

    return best_signal

# Exponer generate_signal para compatibilidad
generate_signal = _generate_signal
