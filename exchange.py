# exchange.py
# ============================================================
# exchange.py – Cliente OKX V5 (Futuros SWAP)
# Versión final consistente con Position Manager.
# Soporta firma con query string, attachAlgoOrds, todas las órdenes.
# ============================================================

import time
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union

# ============================================================
# CONFIGURACIÓN (se puede importar desde config.py o definir aquí)
# ============================================================
MAX_RETRIES = 3
RETRY_DELAY = 2

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

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
        self._sync_interval = 60
        self._instrument_cache = {}
        self._account_mode = None
        self._account_mode_fetched = False

    def _instrument_id(self, symbol: str) -> str:
        symbol = symbol.upper().strip()
        if symbol.endswith("-USDT-SWAP"):
            return symbol
        return f"{symbol}-USDT-SWAP"

    def _iso_timestamp(self) -> str:
        now_ms = int(time.time() * 1000) + self._time_offset
        dt = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _sync_time(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (now - self._last_sync_time) < self._sync_interval:
            return True
        try:
            resp = self.session.get(f"{self.base_url}/api/v5/public/time", timeout=10)
            data = resp.json()
            if data.get("code") == "0":
                server_ts = int(data['data'][0]['ts'])
                local_ts = int(time.time() * 1000)
                self._time_offset = server_ts - local_ts
                self._last_sync_time = now
                return True
        except Exception:
            return True  # No fallar, usar offset anterior
        return False

    def _ensure_time_synced(self) -> None:
        if not self._sync_time(force=True):
            self._time_offset = 0

    def _get_account_mode(self) -> str:
        if self._account_mode_fetched:
            return self._account_mode
        resp = self._request("GET", "/api/v5/account/config")
        if resp.get('ok') and resp.get('data'):
            config = resp['data'][0]
            pos_mode = config.get('posMode', 'net_mode')
            self._account_mode = 'long_short' if 'long_short' in pos_mode else 'net'
            self._account_mode_fetched = True
        else:
            self._account_mode = 'net'
            self._account_mode_fetched = True
        return self._account_mode

    def _sign_request(self, method: str, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None) -> Tuple[Dict, str]:
        self._ensure_time_synced()
        timestamp = self._iso_timestamp()

        if body:
            body_str = json.dumps(body, separators=(', ', ': '), sort_keys=True)
        else:
            body_str = ""

        # 🔧 FIRMA CON QUERY STRING (compatible con el repositorio original)
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
            return {"ok": False, "error": "Invalid JSON", "raw": response.text}
        if data.get("code") != "0":
            msg = data.get("msg", "Unknown error")
            if "sMsg" in data:
                msg = data["sMsg"]
            return {"ok": False, "error": msg, "raw": data, "code": data.get("code")}
        return {"ok": True, "data": data.get("data", [])}

    def _request(self, method: str, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None, retry: bool = True, attempt: int = 0) -> Dict:
        self._ensure_time_synced()
        headers, body_str = self._sign_request(method, path, params, body)
        url = f"{self.base_url}{path}"

        try:
            if method == "GET":
                if params:
                    resp = self.session.get(url, headers=headers, params=params, timeout=15)
                else:
                    resp = self.session.get(url, headers=headers, timeout=15)
            else:
                resp = self.session.post(url, headers=headers, data=body_str, timeout=15)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * (attempt + 1))
                return self._request(method, path, params, body, retry, attempt + 1)
            return {"ok": False, "error": f"Request error: {e}"}

        result = self._handle_response(resp)
        if not result.get('ok') and retry and attempt < MAX_RETRIES:
            code = result.get('code', '')
            if code in ['50113', '50102', '50111', '50112']:
                time.sleep(RETRY_DELAY * (attempt + 1))
                return self._request(method, path, params, body, retry, attempt + 1)
        return result

    # ----------------------------------------------------------------
    # MÉTODOS PÚBLICOS
    # ----------------------------------------------------------------
    def connect(self) -> bool:
        try:
            self._ensure_time_synced()
            resp = self.session.get(f"{self.base_url}/api/v5/public/time", timeout=10)
            data = resp.json()
            if data.get("code") == "0":
                self._connected = True
                self._get_account_mode()
                return True
        except Exception:
            pass
        return False

    def get_balance(self) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        return self._request("GET", "/api/v5/account/balance")

    def get_positions(self, symbol: Optional[str] = None) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        params = {}
        if symbol:
            params["instId"] = self._instrument_id(symbol)
        return self._request("GET", "/api/v5/account/positions", params=params)

    def get_mark_price(self, symbol: str) -> Optional[float]:
        inst = self._instrument_id(symbol)
        resp = self._request("GET", "/api/v5/public/mark-price", params={"instId": inst})
        if resp.get('ok') and resp.get('data'):
            return safe_float(resp['data'][0].get('markPx'))
        return None

    def get_last_price(self, symbol: str) -> Optional[float]:
        inst = self._instrument_id(symbol)
        resp = self._request("GET", "/api/v5/public/ticker", params={"instId": inst})
        if resp.get('ok') and resp.get('data'):
            return safe_float(resp['data'][0].get('last'))
        return None

    def get_instrument_info(self, symbol: str) -> Dict:
        inst = self._instrument_id(symbol)
        if inst in self._instrument_cache:
            return self._instrument_cache[inst]
        resp = self._request("GET", "/api/v5/public/instruments", params={"instId": inst, "instType": "SWAP"})
        if resp.get('ok') and resp.get('data'):
            info = resp['data'][0]
            self._instrument_cache[inst] = {
                'tick_size': safe_float(info.get('tickSz')),
                'lot_size': safe_float(info.get('lotSz')),
                'min_sz': safe_float(info.get('minSz')),
            }
            return self._instrument_cache[inst]
        return {}

    def place_market_order(self, symbol: str, side: str, size: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "market",
            "sz": str(size),
        }
        return self._request("POST", "/api/v5/trade/order", body=body)

    def place_limit_order(self, symbol: str, side: str, price: float, size: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "limit",
            "px": str(price),
            "sz": str(size),
        }
        return self._request("POST", "/api/v5/trade/order", body=body)

    def place_market_order_with_tp_sl(self, symbol: str, side: str, size: float, tp_price: float, sl_price: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        close_side = "sell" if pos_side == "long" else "buy"

        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "market",
            "sz": str(size),
            "attachAlgoOrds": [
                {
                    "ordType": "conditional",
                    "tpTriggerPx": str(tp_price),
                    "tpOrdPx": "-1",
                    "tpTriggerPxType": "last",
                    "side": close_side
                },
                {
                    "ordType": "conditional",
                    "slTriggerPx": str(sl_price),
                    "slOrdPx": "-1",
                    "slTriggerPxType": "last",
                    "side": close_side
                }
            ]
        }
        return self._request("POST", "/api/v5/trade/order", body=body)

    def place_limit_order_with_tp_sl(self, symbol: str, side: str, price: float, size: float, tp_price: float, sl_price: float) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        pos_side = "long" if side.lower() == "buy" else "short"
        close_side = "sell" if pos_side == "long" else "buy"

        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "posSide": pos_side,
            "ordType": "limit",
            "px": str(price),
            "sz": str(size),
            "attachAlgoOrds": [
                {
                    "ordType": "conditional",
                    "tpTriggerPx": str(tp_price),
                    "tpOrdPx": str(tp_price),
                    "tpTriggerPxType": "last",
                    "side": close_side
                },
                {
                    "ordType": "conditional",
                    "slTriggerPx": str(sl_price),
                    "slOrdPx": str(sl_price),
                    "slTriggerPxType": "last",
                    "side": close_side
                }
            ]
        }
        return self._request("POST", "/api/v5/trade/order", body=body)

    def place_algo_order(self, body: Dict) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        return self._request("POST", "/api/v5/trade/order-algo", body=body)

    def place_conditional_order(self, symbol: str, side: str, size: float, trigger_price: float,
                                order_price: float, trigger_px_type: str = "last", pos_side: Optional[str] = None) -> Dict:
        inst = self._instrument_id(symbol)
        if pos_side is None:
            pos_side = "long" if side.lower() == "sell" else "short"
        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "trigger",
            "sz": str(size),
            "triggerPx": str(trigger_price),
            "orderPx": str(order_price),
            "triggerPxType": trigger_px_type,
            "posSide": pos_side,
        }
        return self.place_algo_order(body)

    def place_oco_order(self, symbol: str, side: str, size: float,
                        tp_trigger: float, tp_price: float,
                        sl_trigger: float, sl_price: float,
                        tp_trigger_px_type: str = "last",
                        sl_trigger_px_type: str = "last") -> Dict:
        inst = self._instrument_id(symbol)
        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "oco",
            "sz": str(size),
            "tpTriggerPx": str(tp_trigger),
            "tpOrdPx": str(tp_price),
            "tpTriggerPxType": tp_trigger_px_type,
            "slTriggerPx": str(sl_trigger),
            "slOrdPx": str(sl_price),
            "slTriggerPxType": sl_trigger_px_type,
            "posSide": "long" if side.lower() == "sell" else "short",
        }
        return self.place_algo_order(body)

    def place_trailing_order(self, symbol: str, side: str, size: float, callback_ratio: float,
                             trigger_px_type: str = "last", pos_side: Optional[str] = None) -> Dict:
        inst = self._instrument_id(symbol)
        if pos_side is None:
            pos_side = "long" if side.lower() == "sell" else "short"
        body = {
            "instId": inst,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "move_order_stop",
            "sz": str(size),
            "callbackRatio": str(callback_ratio),
            "triggerPxType": trigger_px_type,
            "posSide": pos_side,
        }
        return self.place_algo_order(body)

    def get_pending_orders(self, symbol: Optional[str] = None) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        params = {}
        if symbol:
            params["instId"] = self._instrument_id(symbol)
        return self._request("GET", "/api/v5/trade/orders-pending", params=params)

    def get_pending_algo_orders(self, symbol: Optional[str] = None, ord_type: Optional[str] = None) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        params = {}
        if symbol:
            params["instId"] = self._instrument_id(symbol)
        if ord_type:
            params["ordType"] = ord_type
        return self._request("GET", "/api/v5/trade/orders-algo-pending", params=params)

    def get_all_pending_algo_orders(self, symbol: Optional[str] = None) -> Dict:
        all_orders = []
        for ord_type in ["conditional", "trigger", "oco", "move_order_stop"]:
            resp = self.get_pending_algo_orders(symbol, ord_type)
            if resp.get('ok'):
                all_orders.extend(resp.get('data', []))
        return {"ok": True, "data": all_orders}

    def amend_algo_order(self, algo_id: str, symbol: str, **kwargs) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        body = {"algoId": algo_id, "instId": inst}
        for key, value in kwargs.items():
            if value is not None:
                body[key] = str(value)
        return self._request("POST", "/api/v5/trade/amend-algos", body=body)

    def cancel_algo_order(self, algo_id: str, symbol: str) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        body = [{"algoId": algo_id, "instId": inst}]
        return self._request("POST", "/api/v5/trade/cancel-algos", body=body)

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        body = {"ordId": order_id, "instId": inst}
        return self._request("POST", "/api/v5/trade/cancel-order", body=body)

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        body = {"instId": inst, "lever": str(leverage), "mgnMode": "cross"}
        return self._request("POST", "/api/v5/account/set-leverage", body=body)

    def get_leverage_info(self, symbol: str) -> Dict:
        if not self._connected:
            return {"ok": False, "error": "No conectado"}
        inst = self._instrument_id(symbol)
        params = {"instId": inst, "mgnMode": "cross"}
        return self._request("GET", "/api/v5/account/leverage-info", params=params)
