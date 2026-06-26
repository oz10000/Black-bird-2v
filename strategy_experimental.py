# strategy_experimental.py
# ============================================================
# ESTRATEGIA EXPERIMENTAL – PLANTILLA PARA DESARROLLO
# ============================================================

from typing import List, Dict, Optional
from models import Signal
from signals import fetch_okx_candles, calculate_atr
from config import SYMBOLS, TRADE_NOTIONAL

def get_best_signal(symbols: List[str] = None,
                    speed_levels: List[Dict] = None,
                    speed_levels_override: Dict[str, Dict] = None) -> Optional[Signal]:
    """
    Estrategia experimental: plantilla para desarrollar nuevas estrategias.
    Modifica esta función para implementar tu propia lógica.
    """
    # ============================================================
    # AQUÍ VA TU LÓGICA DE ESTRATEGIA
    # ============================================================
    # Ejemplo: devolver None (sin señal)
    return None

generate_signal = None
