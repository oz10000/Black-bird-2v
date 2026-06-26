# strategy_test_simple.py
# ============================================================
# ESTRATEGIA SIMPLE – CRUCE DE MEDIAS MÓVILES
# ============================================================

from typing import List, Dict, Optional
from models import Signal
from signals import fetch_okx_candles, calculate_atr
from config import SYMBOLS, TRADE_NOTIONAL

def get_best_signal(symbols: List[str] = None,
                    speed_levels: List[Dict] = None,
                    speed_levels_override: Dict[str, Dict] = None) -> Optional[Signal]:
    """
    Estrategia simple: cruce de media rápida (EMA 9) y lenta (EMA 21).
    - Long: EMA9 cruza por encima de EMA21.
    - Short: EMA9 cruza por debajo de EMA21.
    """
    if symbols is None:
        symbols = SYMBOLS

    for symbol in symbols:
        df = fetch_okx_candles(symbol, limit=50)
        if df.empty:
            continue

        ema9 = df['c'].ewm(span=9, adjust=False).mean()
        ema21 = df['c'].ewm(span=21, adjust=False).mean()

        if len(ema9) < 3:
            continue

        prev_ema9 = ema9.iloc[-2]
        curr_ema9 = ema9.iloc[-1]
        prev_ema21 = ema21.iloc[-2]
        curr_ema21 = ema21.iloc[-1]

        direction = None
        if prev_ema9 < prev_ema21 and curr_ema9 > curr_ema21:
            direction = 'Long'
        elif prev_ema9 > prev_ema21 and curr_ema9 < curr_ema21:
            direction = 'Short'

        if direction is None:
            continue

        entry = df['c'].iloc[-1]
        atr = calculate_atr(df, 14).iloc[-1]

        if direction == 'Long':
            tp = entry + atr * 1.5
            sl = entry - atr * 1.0
        else:
            tp = entry - atr * 1.5
            sl = entry + atr * 1.0

        confidence = 0.7
        speed_score = 0.8

        return Signal(
            symbol=symbol,
            direction=direction,
            timestamp=df['ts'].iloc[-1],
            entry_price=entry,
            target_price=tp,
            stop_loss=sl,
            confidence=confidence,
            speed_score=speed_score,
            speed_level="SIMPLE",
            notional=TRADE_NOTIONAL
        )

    return None

generate_signal = None
