# exchange.py
# ============================================================
# CLIENTE OKX V5 PARA FUTUROS (SWAP) – CONVERSIÓN INTERNA DE SÍMBOLOS
# CON SOPORTE PARA set_leverage Y get_leverage_info
# ============================================================

import time
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from telemetry import telemetry
from config import MAX_RETRIES_PER_ORDER, ORDER_TIMEOUT, SYNC_TIME_ENABLED

class Exchange:
    def __init__(self, api_key: str, secret_key: str, passphrase: str, demo: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.demo = demo
        self.base_url = "https://www.okx.com"
        self.session = requests.Session()
        self._connected = False
        self._time_offset = 0
        self._last_sync_time = 0
        self._sync_interval = 30

    # ------------------------------------------------------------
    # Conversión de símbolos (único punto de verdad)
    # ------------------------------------------------------------
    def _instrument_id(self, symbol: str) -> str:
        symbol = symbol.upper().strip()
        if symbol.endswith("-USDT-SWAP"):
            return symbol
        return f"{symbol}-USDT-SWAP"

    def _symbol_from_instrument(self, instrument_id: str) -> str:
        if instrument_id.endswith("-USDT-SWAP"):
            return instrument_id[:-len("-USDT-SWAP")]
        return instrument_id

    # ------------------------------------------------------------
    # Sincronización horaria
    # ------------------------------------------------------------
    def _iso_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _sync_time(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (now - self._last_sync_time) < self._sync_interval:
            return True
        try:
            resp = self.session.get(f"{self.base_url}/api/v5/public/time", timeout=5)
            data = resp.json()
            if data.get("code") == "0":
                server_ts = int(data['data'][0]['ts'])
                local_ts = int(time.time() * 1000)
                self._time_offset = server_ts - local_ts
                self._last_sync_time = now
                telemetry.log_debug("exchange", f"Offset horario: {self._time_offset}ms")
                return True
        except Exception as e:
            telemetry.log_error("exchange", f"Error en _sync_time: {e}")
        return False

    def _ensure_sync(self):
        self._sync_time()

    # ------------------------------------------------------------
    # Firma y peticiones
    # ------------------------------------------------------------
    def _sign_request(self, method: str, path: str, params: Dict = None, body: Dict = None):
        self._ensure_sync()
        timestamp = self._iso_timestamp()
        if body:
            body_str = json.dumps(body, separators=(",", ":"))
        else:
            body_str = ""
        if params:
            query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            full_path = f"{path}?{query}"
        else:
            full_path = path
        sign_str = timestamp + method + full_path + body_str
        signature = base64.b64encode(
            hmac.new(self.secret_key.encode(), sign_str.encode(), hashlib.sha256).digest()
        ).decode()
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        if self.demo:
            headers["x-simulated-trading"] = "1"
        return headers, body_str

    def _handle_response(self, response: requests.Response) -> Dict:
        try:
            data = response.json()
        except:
            return {"ok": False, "error": "Invalid JSON response"}
        if data.get("code") != "0":
            msg = data.get("msg", "Unknown error")
            if "sMsg" in data:
                msg = data["sMsg"]
            return {"ok": False, "error": msg, "raw": data}
        return {"ok": True, "data": data.get("data", [])}

    def _request_with_retry(self, method: str, path: str, params: Dict = None, body: Dict = None) -> Dict:
        headers, body_str = self._sign_request(method, path, params, body)
        try:
            if method == "GET":
                resp = self.session.get(
                    f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                    timeout=ORDER_TIMEOUT
                )
            else:
                resp = self.session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=body_str,
                    timeout=ORDER_TIMEOUT
                )
        except requests.exceptions.Timeout:
            return {"ok": False, "error": "Timeout"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        result = self._handle_response(resp)
        if not result.get("ok") and "50102" in str(result.get("raw", {}).get("code", "")):
            telemetry.log_warning("exchange", "Error 50102 detectado, resincronizando")
            self._sync_time(force=True)
            headers2, body_str2 = self._sign_request(method, path, params, body)
            if method == "GET":
                resp2 = self.session.get(f"{self.base_url}{path}", headers=headers2, params=params, timeout=ORDER_TIMEOUT)
            else:
                resp2 = self.session.post(f"{self.base_url}{path}", headers=headers2, data=body_str2, timeout=ORDER_TIMEOUT)
            return self._handle_response(resp2)
        return result

    # ------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------
    def connect(self) -> bool:
        try:
            self._sync_time(force=True)
            resp = self.session.get(f"{self.base_url}/api/v5/public/time", timeout=10)
            data = resp.json()
            if data.get("code") == "0":
                self._connected = True
                telemetry.log_info("exchange", "Conectado a OKX correctamente")
                return True
        except Exception as e:
            telemetry.log_error("exchange", f"Error en connect: {e}")
        return False

    # ------------------------------------------------------------
    # Cuenta y balance
    # ------------------------------------------------------------
    def get_balance(self) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        return self._request_with_retry("GET", "/api/v5/account/balance")

    # ------------------------------------------------------------
    # Posiciones (acepta símbolo lógico)
    # ------------------------------------------------------------
    def get_positions(self, symbol: Optional[str] = None) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        params = {}
        if symbol:
            params["instId"] = self._instrument_id(symbol)
        return self._request_with_retry("GET", "/api/v5/account/positions", params=params)

    # ------------------------------------------------------------
    # Órdenes de mercado (acepta símbolo lógico)
    # ------------------------------------------------------------
    def place_market_order(self, symbol: str, side: str, size: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        body = {
            "instId": instrument,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "market",
            "sz": str(size),
        }
        telemetry.log_debug("exchange", f"Market order: {instrument} {side} size={size}")
        return self._request_with_retry("POST", "/api/v5/trade/order", body=body)

    # ------------------------------------------------------------
    # Órdenes condicionadas (TP/SL) (acepta símbolo lógico)
    # ------------------------------------------------------------
    def place_algo_order(self, symbol: str, side: str, trigger_price: float, order_price: float,
                         size: float, order_type: str = "conditional") -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        body = {
            "instId": instrument,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "trigger",
            "sz": str(size),
            "triggerPx": str(trigger_price),
            "orderPx": str(order_price),
            "triggerPxType": "last",
        }
        telemetry.log_debug("exchange", f"Algo order: {instrument} {side} trigger={trigger_price}")
        return self._request_with_retry("POST", "/api/v5/trade/order-algo", body=body)

    # ------------------------------------------------------------
    # Trailing stop (acepta símbolo lógico)
    # ------------------------------------------------------------
    def place_trailing_order(self, symbol: str, side: str, size: float, callback_rate: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        body = {
            "instId": instrument,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "move_order_stop",
            "sz": str(size),
            "callbackRatio": str(callback_rate),
        }
        telemetry.log_debug("exchange", f"Trailing order: {instrument} callback={callback_rate}")
        return self._request_with_retry("POST", "/api/v5/trade/order-algo", body=body)

    # ------------------------------------------------------------
    # Cancelaciones (acepta símbolo lógico)
    # ------------------------------------------------------------
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        body = {"ordId": order_id, "instId": instrument}
        return self._request_with_retry("POST", "/api/v5/trade/cancel-order", body=body)

    def cancel_algo_order(self, algo_id: str, symbol: str) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        body = [{"algoId": algo_id, "instId": instrument}]
        return self._request_with_retry("POST", "/api/v5/trade/cancel-algos", body=body)

    # ------------------------------------------------------------
    # Consulta de órdenes pendientes (acepta símbolo lógico)
    # ------------------------------------------------------------
    def get_pending_algo_orders(self, symbol: Optional[str] = None) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        params = {"ordType": "trigger,move_order_stop"}
        if symbol:
            params["instId"] = self._instrument_id(symbol)
        return self._request_with_retry("GET", "/api/v5/trade/orders-algo-pending", params=params)

    # ============================================================
    # GESTIÓN DE APALANCAMIENTO (NUEVO)
    # ============================================================

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """
        Establece el apalancamiento para un instrumento en modo Cross.
        """
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        body = {
            "instId": instrument,
            "lever": str(leverage),
            "mgnMode": "cross",
        }
        telemetry.log_debug("exchange", f"Estableciendo leverage {leverage}x para {instrument}")
        return self._request_with_retry("POST", "/api/v5/account/set-leverage", body=body)

    def get_leverage_info(self, symbol: str) -> Dict:
        """
        Consulta el leverage actual de un instrumento.
        """
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        instrument = self._instrument_id(symbol)
        params = {"instId": instrument, "mgnMode": "cross"}
        telemetry.log_debug("exchange", f"Consultando leverage para {instrument}")
        return self._request_with_retry("GET", "/api/v5/account/leverage-info", params=params)
