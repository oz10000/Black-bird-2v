# repair.py
# ============================================================
# REPARACIÓN DE PROTECCIONES – SOLO TP Y TRAILING STOP (PHASE 1)
# BASADO EN EL POSITION MANAGER PARA CONSISTENCIA DE API
# CORREGIDO: VERIFICACIÓN DE EXISTENCIA DE POSICIÓN (B2)
# ============================================================

import traceback
from config import TP_MULT, SL_MULT, MAX_REPAIR_ATTEMPTS, TRAILING_ENABLED, TRAILING_MODE, TRAILING_DISTANCE_ATR
from telemetry import telemetry

def repair_protections(exchange, position):
    """
    Verifica que la posición tenga protecciones activas.
    En Phase 1, solo se reparan:
      - Take Profit (TP) si falta
      - Trailing Stop (si está habilitado) si falta
    NO se repara Stop Loss fijo.
    Utiliza las mismas funciones que el Position Manager.
    🔧 CORRECCIÓN (B2): Verifica que la posición aún exista en OKX antes de reparar.
    """
    telemetry.log_info("repair", f"Iniciando reparación para {position.symbol} (intento {position.repair_attempts+1}/{MAX_REPAIR_ATTEMPTS})")
    result = {"tp": False, "trailing": False, "error": None}

    # 🔧 Verificar que la posición aún existe en OKX
    pos_check = exchange.get_positions(symbol=position.symbol)
    if not pos_check.get('ok') or not pos_check.get('data'):
        telemetry.log_warning("repair", f"Posición {position.symbol} ya no existe en OKX. Saltando reparación.")
        result["error"] = "Position no longer exists"
        return result

    if position.repair_attempts >= MAX_REPAIR_ATTEMPTS:
        msg = f"Límite de intentos de reparación alcanzado ({MAX_REPAIR_ATTEMPTS}) para {position.symbol}"
        telemetry.log_error("repair", msg)
        result["error"] = msg
        return result

    try:
        # 1. Obtener órdenes algorítmicas pendientes
        pending = exchange.get_pending_algo_orders(symbol=position.symbol)
        if not pending.get('ok'):
            telemetry.log_error("repair", "No se pudieron obtener órdenes pendientes", pending)
            result["error"] = pending.get("error", "Error desconocido")
            return result

        orders = pending.get('data', [])

        # 2. Identificar protecciones existentes
        has_tp = False
        has_trailing = False
        tp_algo_id = None
        trailing_algo_id = None

        for o in orders:
            ord_type = o.get('ordType')
            side = o.get('side')
            # TP: side opuesto a la posición y ordType = "trigger" (o "conditional")
            if ord_type in ['conditional', 'trigger']:
                if position.side == 'long' and side == 'sell':
                    has_tp = True
                    tp_algo_id = o.get('algoId')
                elif position.side == 'short' and side == 'buy':
                    has_tp = True
                    tp_algo_id = o.get('algoId')
            # Trailing Stop
            elif ord_type == 'move_order_stop':
                has_trailing = True
                trailing_algo_id = o.get('algoId')

        # 3. Reparar TP si falta
        if not has_tp:
            telemetry.log_info("repair", "TP no encontrado, recreando...")
            tp_side = "sell" if position.side == "long" else "buy"
            # Calcular precio de TP basado en el precio de entrada y TP_MULT
            if position.side == 'long':
                tp_price = position.entry_price * (1 + TP_MULT * (position.mark_price / position.entry_price - 1))
            else:
                tp_price = position.entry_price * (1 - TP_MULT * (position.entry_price / position.mark_price - 1))

            tp_resp = exchange.place_conditional_order(
                symbol=position.symbol,
                side=tp_side,
                size=position.size,
                trigger_price=tp_price,
                order_price=tp_price,
                trigger_px_type="last",
                pos_side=position.side
            )
            if tp_resp.get('ok'):
                result['tp'] = True
                telemetry.log_info("repair", "TP recreado correctamente", {"order": tp_resp.get('data')})
            else:
                telemetry.log_error("repair", "Fallo al recrear TP", tp_resp)
                result["error"] = tp_resp.get("error", "Error recreando TP")

        # 4. Reparar Trailing Stop si está habilitado y falta
        if TRAILING_ENABLED and TRAILING_MODE == 'native':
            if not has_trailing:
                telemetry.log_info("repair", "Trailing Stop no encontrado, recreando...")
                trail_side = "sell" if position.side == "long" else "buy"
                callback = TRAILING_DISTANCE_ATR * 0.01
                trail_resp = exchange.place_trailing_order(
                    symbol=position.symbol,
                    side=trail_side,
                    size=position.size,
                    callback_ratio=callback,
                    trigger_px_type="last",
                    pos_side=position.side
                )
                if trail_resp.get('ok'):
                    result['trailing'] = True
                    telemetry.log_info("repair", "Trailing Stop recreado correctamente", {"order": trail_resp.get('data')})
                else:
                    telemetry.log_error("repair", "Fallo al recrear Trailing Stop", trail_resp)
                    if not result["error"]:
                        result["error"] = trail_resp.get("error", "Error recreando Trailing")
            else:
                telemetry.log_debug("repair", "Trailing Stop ya existe, no se repara")
        else:
            telemetry.log_debug("repair", "Trailing Stop desactivado o modo no nativo – omitido")

        position.repair_attempts += 1

    except Exception as e:
        telemetry.log_error("repair", f"Excepción en repair_protections: {e}", {"traceback": traceback.format_exc()})
        result["error"] = str(e)

    return result
