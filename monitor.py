# monitor.py
# ============================================================
# MONITOREO DE POSICIONES
# ============================================================

from signals import fetch_okx_candles, calculate_atr
from repair import repair_protections
from telemetry import telemetry

def monitor_position(exchange, position):
    telemetry.log_info("monitor", f"Monitoreando {position.symbol}")
    result = {
        "symbol": position.symbol,
        "side": position.side,
        "pnl_pct": 0.0,
        "repair": False,
        "trailing_updated": False
    }
    try:
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

        pending = exchange.get_pending_algo_orders(position.symbol)
        if pending.get('ok') and not pending.get('data'):
            telemetry.log_info("monitor", "No hay protecciones, ejecutando reparación")
            repair_result = repair_protections(exchange, position)
            result["repair"] = any(repair_result.values())
            telemetry.log_info("monitor", "Reparación ejecutada", repair_result)
        else:
            telemetry.log_debug("monitor", "Protecciones existentes, no se requiere reparación")

    except Exception as e:
        telemetry.log_error("monitor", f"Error en monitor_position: {e}")
    return result
