# monitor.py
# ============================================================
# MONITOREO DE POSICIONES – VERSIÓN SIMPLIFICADA (PHASE 1)
# BASADO EN EL POSITION MANAGER PARA CONSISTENCIA DE API
# CORREGIDO: VERIFICACIÓN ADICIONAL DE EXISTENCIA DE POSICIÓN (B3)
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
    En Phase 1, solo se gestionan TP y Trailing (sin SL fijo).
    Verifica la existencia de TP y Trailing usando las funciones del Position Manager.
    🔧 CORRECCIÓN (B3): Verifica que la posición aún exista en OKX antes de tomar decisiones.
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
        # 🔧 Verificar que la posición aún existe en OKX (B3)
        fresh_pos = exchange.get_positions(symbol=position.symbol)
        if not fresh_pos.get('ok') or not fresh_pos.get('data'):
            telemetry.log_warning("monitor", f"Posición {position.symbol} ya no existe en OKX. Forzando limpieza de estado.")
            result["force_clear"] = True
            return result

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

        # 3. Verificar protecciones (TP y Trailing)
        pending = exchange.get_pending_algo_orders(symbol=position.symbol)
        if pending.get('ok'):
            orders = pending.get('data', [])
            has_tp = False
            has_trailing = False
            for o in orders:
                ord_type = o.get('ordType')
                side = o.get('side')
                if ord_type in ['conditional', 'trigger']:
                    if (position.side == 'long' and side == 'sell') or (position.side == 'short' and side == 'buy'):
                        has_tp = True
                elif ord_type == 'move_order_stop':
                    has_trailing = True

            if not has_tp or (TRAILING_ENABLED and not has_trailing):
                telemetry.log_info("monitor", "Falta alguna protección, ejecutando reparación")
                repair_result = repair_protections(exchange, position)
                telemetry.log_info("monitor", "Reparación ejecutada", repair_result)
            else:
                telemetry.log_debug("monitor", "Protecciones existentes (TP y Trailing)")
        else:
            telemetry.log_warning("monitor", "No se pudieron obtener órdenes pendientes", pending)

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

        # 6. TP DINÁMICO (LOGS – PENDIENTE DE IMPLEMENTACIÓN REAL)
        if TP_DYNAMIC:
            gain_pct = result["pnl_pct"]
            if position.side == "long" and gain_pct > 2.0:
                atr = calculate_atr(df, period=14).iloc[-1]
                new_tp = position.entry_price + atr * TP_MULT * (1 + (gain_pct / 100))
                telemetry.log_info("monitor", f"TP dinámico sugerido: {new_tp:.2f} (ganancia {gain_pct:.2f}%)")
                # La modificación real de TP requeriría cancelar y recrear la orden,
                # usando exchange.amend_algo_order o cancel+create.
                # Se implementará en Phase 2.
            elif position.side == "short" and gain_pct > 2.0:
                atr = calculate_atr(df, period=14).iloc[-1]
                new_tp = position.entry_price - atr * TP_MULT * (1 + (gain_pct / 100))
                telemetry.log_info("monitor", f"TP dinámico sugerido: {new_tp:.2f} (ganancia {gain_pct:.2f}%)")

        # 7. TRAILING ADAPTATIVO (LOGS – PENDIENTE DE IMPLEMENTACIÓN REAL)
        if TRAILING_ADAPTIVE and df is not None and not df.empty:
            atr = calculate_atr(df, period=14).iloc[-1]
            price = df['c'].iloc[-1]
            adaptive_dist = max(0.4, min(1.0, atr / price * 10))
            telemetry.log_debug("monitor", f"Trailing adaptativo: distancia sugerida {adaptive_dist:.2f}")
            # En Phase 2 se implementará la modificación real del trailing usando amend_algo_order.

    except Exception as e:
        telemetry.log_error("monitor", f"Error en monitor_position: {e}")

    return result
