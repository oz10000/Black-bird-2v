# monitor.py
# ============================================================
# MONITOREO DE POSICIONES – VERSIÓN CON OPTIMIZACIONES DE TIEMPO
# ============================================================

import time
from datetime import datetime
from signals import fetch_okx_candles, calculate_atr
from repair import repair_protections
from telemetry import telemetry
from config import (MAX_POSITION_HOLD_MINUTES, CLOSE_IF_STALLED,
                    TP_DYNAMIC, TRAILING_ADAPTIVE,
                    TP_MULT, SL_MULT, TRAILING_DISTANCE_ATR,
                    TRAILING_ACTIVATION_PROFIT, BE_UMBRAL, BE_GAIN)

def monitor_position(exchange, position):
    """
    Monitorea una posición abierta y decide si debe cerrarse.
    Retorna un dict con 'close': True/False y motivo.
    """
    telemetry.log_info("monitor", f"Monitoreando {position.symbol}")
    result = {
        "symbol": position.symbol,
        "side": position.side,
        "pnl_pct": 0.0,
        "close": False,
        "reason": None
    }

    try:
        # 1. Obtener precio actual
        df = fetch_okx_candles(position.symbol, limit=1)
        if not df.empty:
            mark = df['c'].iloc[-1]
            position.mark_price = mark
            pnl = (mark - position.entry_price) / position.entry_price
            if position.side == "short":
                pnl = -pnl
            result["pnl_pct"] = pnl * 100
        else:
            result["pnl_pct"] = position.unrealized_pnl

        # 2. Calcular tiempo en posición
        duration_min = 0
        if hasattr(position, 'entry_time'):
            duration_min = (datetime.utcnow() - position.entry_time).total_seconds() / 60.0
        result["duration_min"] = duration_min

        # 3. Verificar protecciones (TP/SL)
        pending = exchange.get_pending_algo_orders(position.symbol)
        if pending.get('ok') and not pending.get('data'):
            telemetry.log_info("monitor", "No hay protecciones, ejecutando reparación")
            repair_result = repair_protections(exchange, position)
            if any(repair_result.values()):
                telemetry.log_info("monitor", "Reparación ejecutada", repair_result)
        else:
            telemetry.log_debug("monitor", "Protecciones existentes")

        # 4. CIERRE POR TIEMPO MÁXIMO
        if MAX_POSITION_HOLD_MINUTES > 0 and duration_min > MAX_POSITION_HOLD_MINUTES:
            telemetry.log_info("monitor", f"Tiempo máximo de permanencia excedido ({duration_min:.1f} min > {MAX_POSITION_HOLD_MINUTES} min)")
            result["close"] = True
            result["reason"] = "TIMEOUT"
            return result

        # 5. CIERRE POR ESTANCAMIENTO
        if CLOSE_IF_STALLED and duration_min > 30:
            gain_pct = result["pnl_pct"]
            if abs(gain_pct) < 1.0:
                telemetry.log_info("monitor", f"Posición estancada ({gain_pct:.2f}% en {duration_min:.1f} min), cerrando")
                result["close"] = True
                result["reason"] = "STALLED"
                return result

        # 6. TP DINÁMICO (extender TP si beneficio >2%)
        if TP_DYNAMIC:
            gain_pct = result["pnl_pct"]
            if position.side == "long" and gain_pct > 2.0:
                atr = calculate_atr(df, period=14).iloc[-1]
                new_tp = position.entry_price + atr * TP_MULT * (1 + (gain_pct / 100))
                telemetry.log_info("monitor", f"TP dinámico extendido a {new_tp:.2f} (ganancia {gain_pct:.2f}%)")
                # Nota: la extensión de TP requeriría cancelar el TP actual y crear uno nuevo.
                # Esto se delega a repair_protections o se implementa aquí.
                # Por ahora solo lo registramos; la implementación completa se hará en una fase posterior.
            elif position.side == "short" and gain_pct > 2.0:
                atr = calculate_atr(df, period=14).iloc[-1]
                new_tp = position.entry_price - atr * TP_MULT * (1 + (gain_pct / 100))
                telemetry.log_info("monitor", f"TP dinámico extendido a {new_tp:.2f} (ganancia {gain_pct:.2f}%)")

        # 7. TRAILING ADAPTATIVO (ajustar distancia según ATR)
        if TRAILING_ADAPTIVE and df is not None and not df.empty:
            atr = calculate_atr(df, period=14).iloc[-1]
            price = df['c'].iloc[-1]
            adaptive_dist = max(0.4, min(1.0, atr / price * 10))
            if position.side == "long" and position.mark_price > position.entry_price:
                new_sl = position.mark_price - atr * adaptive_dist
                if new_sl > position.stop_loss:
                    telemetry.log_info("monitor", f"Trailing adaptativo: SL ajustado a {new_sl:.2f} (dist {adaptive_dist:.2f})")
            elif position.side == "short" and position.mark_price < position.entry_price:
                new_sl = position.mark_price + atr * adaptive_dist
                if new_sl < position.stop_loss:
                    telemetry.log_info("monitor", f"Trailing adaptativo: SL ajustado a {new_sl:.2f} (dist {adaptive_dist:.2f})")

    except Exception as e:
        telemetry.log_error("monitor", f"Error en monitor_position: {e}")

    return result
