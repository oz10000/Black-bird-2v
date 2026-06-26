# repair.py
# ============================================================
# REPARACIÓN DE PROTECCIONES
# ============================================================

import traceback
from config import TP_MULT, SL_MULT, MAX_REPAIR_ATTEMPTS
from telemetry import telemetry

def repair_protections(exchange, position):
    telemetry.log_info("repair", f"Iniciando reparación para {position.symbol} (intento {position.repair_attempts+1}/{MAX_REPAIR_ATTEMPTS})")
    result = {"tp": False, "sl": False, "trail": False, "error": None}

    if position.repair_attempts >= MAX_REPAIR_ATTEMPTS:
        msg = f"Límite de intentos de reparación alcanzado ({MAX_REPAIR_ATTEMPTS}) para {position.symbol}"
        telemetry.log_error("repair", msg)
        result["error"] = msg
        return result

    try:
        pending = exchange.get_pending_algo_orders(position.symbol)
        if not pending.get('ok'):
            telemetry.log_error("repair", "No se pudieron obtener órdenes pendientes", pending)
            result["error"] = pending.get("error", "Error desconocido")
            return result

        orders = pending.get('data', [])
        has_tp = any(o.get('ordType') == 'conditional' and o.get('side') != position.side for o in orders)
        has_sl = any(o.get('ordType') == 'conditional' and o.get('side') == position.side for o in orders)

        if not has_tp:
            tp_price = position.entry_price * (1 + TP_MULT * (position.mark_price / position.entry_price - 1))
            side = "sell" if position.side == "long" else "buy"
            telemetry.log_info("repair", f"Creando TP a {tp_price:.2f}")
            tp_resp = exchange.place_algo_order(position.symbol, side, tp_price, tp_price, position.size, "conditional")
            if tp_resp.get('ok'):
                result['tp'] = True
                telemetry.log_info("repair", "TP creado", {"order": tp_resp.get('data')})
            else:
                telemetry.log_error("repair", "Fallo al crear TP", tp_resp)
                result["error"] = tp_resp.get("error", "Error creando TP")

        if not has_sl:
            sl_price = position.entry_price * (1 - SL_MULT * (position.entry_price / position.mark_price - 1))
            side = "sell" if position.side == "long" else "buy"
            telemetry.log_info("repair", f"Creando SL a {sl_price:.2f}")
            sl_resp = exchange.place_algo_order(position.symbol, side, sl_price, sl_price, position.size, "conditional")
            if sl_resp.get('ok'):
                result['sl'] = True
                telemetry.log_info("repair", "SL creado", {"order": sl_resp.get('data')})
            else:
                telemetry.log_error("repair", "Fallo al crear SL", sl_resp)
                if not result["error"]:
                    result["error"] = sl_resp.get("error", "Error creando SL")

        position.repair_attempts += 1

    except Exception as e:
        telemetry.log_error("repair", f"Excepción: {e}", {"traceback": traceback.format_exc()})
        result["error"] = str(e)

    return result
