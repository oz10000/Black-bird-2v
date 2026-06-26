# main.py
# ============================================================
# BOT PRINCIPAL – ORQUESTADOR CON SOPORTE MULTIESTRATEGIA
# VERSIÓN CON set_leverage EN LA CONEXIÓN
# ============================================================

import os
import sys
import time
import json
import fcntl
import traceback
from datetime import datetime
from enum import Enum
import numpy as np

from config import *
from telemetry import telemetry
from exchange import Exchange
from strategy import get_best_signal
from monitor import monitor_position
from repair import repair_protections
from utils import acquire_lock, release_lock, validate_config, is_trading_time, health_check
from models import Position

# ============================================================
# PERSISTENCIA
# ============================================================

STATE_FILE = 'state.json'

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'trades': [],
            'stats': {},
            'daily_pnl': {},
            'weekly_pnl': {},
            'optimized_configs': {},
            'cooldown_until': None,
            'last_run': None
        }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)

# ============================================================
# CLASE BOT
# ============================================================

class BotState(Enum):
    INIT = 1
    LOAD_CONFIG = 2
    CONNECT_OKX = 3
    SYNC_EXCHANGE = 4
    SEARCH_SIGNAL = 5
    OPEN_POSITION = 6
    WAIT_NEXT_CYCLE = 7
    ERROR_RECOVERY = 8
    SHUTDOWN = 9

class Bot:
    def __init__(self, api_key, secret_key, passphrase, demo=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.demo = demo
        self.state = BotState.INIT
        self.exchange = None
        self.position = None
        self.signal = None
        self.error_count = 0
        self.max_errors = MAX_CONSECUTIVE_ERRORS
        self.running = True
        self.cycle_interval = CYCLE_INTERVAL_TEST if TEST_MODE else 60
        self.state_data = load_state()
        telemetry.log_info("main", f"Bot inicializado (modo: {'TEST' if TEST_MODE else 'PRODUCCIÓN'})")

    def run(self):
        while self.running:
            try:
                self._step()
                if self.state == BotState.SHUTDOWN:
                    break
                time.sleep(self.cycle_interval)
            except KeyboardInterrupt:
                telemetry.log_info("main", "Interrupción del usuario")
                break
            except Exception as e:
                telemetry.log_error("main", f"Error inesperado: {e}", {'traceback': traceback.format_exc()})
                self.state = BotState.ERROR_RECOVERY

    def _step(self):
        telemetry.log_debug("main", f"Estado: {self.state.name}")
        if self.state == BotState.INIT:
            self._init()
        elif self.state == BotState.LOAD_CONFIG:
            self._load_config()
        elif self.state == BotState.CONNECT_OKX:
            self._connect_okx()
        elif self.state == BotState.SYNC_EXCHANGE:
            self._sync_exchange()
        elif self.state == BotState.SEARCH_SIGNAL:
            self._search_signal()
        elif self.state == BotState.OPEN_POSITION:
            self._open_position()
        elif self.state == BotState.WAIT_NEXT_CYCLE:
            self._wait_next_cycle()
        elif self.state == BotState.ERROR_RECOVERY:
            self._error_recovery()
        elif self.state == BotState.SHUTDOWN:
            self._shutdown()

    def _init(self):
        telemetry.log_info("main", "Inicializando...")
        self.state = BotState.LOAD_CONFIG

    def _load_config(self):
        telemetry.log_info("main", "Cargando configuración...")
        if validate_config(globals()):
            self.state = BotState.CONNECT_OKX
        else:
            self.state = BotState.ERROR_RECOVERY

    def _connect_okx(self):
        telemetry.log_info("main", "Conectando a OKX...")
        self.exchange = Exchange(self.api_key, self.secret_key, self.passphrase, self.demo)
        if self.exchange.connect():
            self.error_count = 0
            # 🔥 NUEVO: Establecer apalancamiento para todos los símbolos
            for symbol in SYMBOLS:
                try:
                    result = self.exchange.set_leverage(symbol, LEVERAGE)
                    if result.get('ok'):
                        telemetry.log_info("main", f"Apalancamiento {LEVERAGE}x establecido para {symbol}")
                        # Confirmar (opcional, para logging)
                        confirm = self.exchange.get_leverage_info(symbol)
                        if confirm.get('ok'):
                            lever = confirm.get('data', [{}])[0].get('lever', 'N/A')
                            telemetry.log_debug("main", f"Leverage confirmado para {symbol}: {lever}x")
                    else:
                        telemetry.log_warning("main", f"Fallo al establecer leverage para {symbol}: {result}")
                except Exception as e:
                    telemetry.log_error("main", f"Excepción al establecer leverage para {symbol}: {e}")
            self.state = BotState.SYNC_EXCHANGE
        else:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                self.state = BotState.SHUTDOWN
            else:
                self.state = BotState.ERROR_RECOVERY

    def _sync_exchange(self):
        telemetry.log_info("main", "Sincronizando estado...")
        positions = self.exchange.get_positions()
        if positions.get('ok') and positions.get('data'):
            pos_data = positions['data'][0]
            if self.position is None:
                self.position = Position(
                    symbol=pos_data['instId'].replace('-USDT-SWAP', ''),
                    side=pos_data['posSide'],
                    size=float(pos_data['pos']),
                    entry_price=float(pos_data['avgPx']),
                    mark_price=float(pos_data['markPx']),
                    unrealized_pnl=float(pos_data['upl']),
                    leverage=float(pos_data['lever']),
                    repair_attempts=0
                )
            else:
                self.position.mark_price = float(pos_data['markPx'])
                self.position.unrealized_pnl = float(pos_data['upl'])
            telemetry.log_info("main", f"Posición activa: {self.position.symbol} {self.position.side} | PnL: {self.position.unrealized_pnl:.2f}")
            self.state = BotState.WAIT_NEXT_CYCLE
        else:
            self.position = None
            self.state = BotState.SEARCH_SIGNAL

    def _search_signal(self):
        telemetry.log_info("main", "Buscando señal...")
        if not is_trading_time():
            telemetry.log_info("main", "Fuera de horario de trading")
            self.state = BotState.WAIT_NEXT_CYCLE
            return

        # Verificar que no haya posición abierta
        if self.position is not None:
            telemetry.log_info("main", f"Posición activa ({self.position.symbol}), no se abrirán nuevas posiciones")
            self.state = BotState.WAIT_NEXT_CYCLE
            return

        # Verificar órdenes pendientes (market orders en curso)
        try:
            pending_orders = self.exchange.get_pending_orders()
            if pending_orders.get('ok') and pending_orders.get('data'):
                telemetry.log_info("main", f"{len(pending_orders.get('data', []))} órdenes pendientes, esperando")
                self.state = BotState.WAIT_NEXT_CYCLE
                return
        except:
            pass

        if MAX_OPEN_POSITIONS <= 0:
            telemetry.log_error("main", "MAX_OPEN_POSITIONS es 0, no se puede operar")
            self.state = BotState.WAIT_NEXT_CYCLE
            return

        signal = get_best_signal()
        if signal:
            self.signal = signal
            telemetry.log_info("main", f"Señal encontrada: {signal.direction} {signal.symbol} (confianza {signal.confidence:.2f})")
            self.state = BotState.OPEN_POSITION
        else:
            self.signal = None
            telemetry.log_info("main", "No se encontró señal")
            self.state = BotState.WAIT_NEXT_CYCLE

    def _open_position(self):
        telemetry.log_info("main", f"Abriendo posición: {self.signal.symbol} {self.signal.direction}")

        # ============================================================
        # 1. Consultar balance disponible
        # ============================================================
        balance_resp = self.exchange.get_balance()
        if not balance_resp.get('ok'):
            telemetry.log_error("main", "No se pudo obtener balance", balance_resp)
            self.state = BotState.ERROR_RECOVERY
            return

        usdt_balance = 0.0
        try:
            details = balance_resp.get('data', [{}])[0].get('details', [])
            for bal in details:
                if bal.get('ccy') == 'USDT':
                    usdt_balance = float(bal.get('availBal', 0))
                    break
        except Exception as e:
            telemetry.log_error("main", f"Error al parsear balance: {e}")
            self.state = BotState.ERROR_RECOVERY
            return

        telemetry.log_info("main", f"Balance disponible: {usdt_balance:.2f} USDT")

        # ============================================================
        # 2. Obtener parámetros del instrumento (ctVal, lotSz)
        # ============================================================
        symbol = self.signal.symbol
        params = INSTRUMENT_PARAMS.get(symbol, {'ctVal': 1.0, 'lotSz': 0.01, 'minSz': 0.01})
        ct_val = params['ctVal']
        lot_sz = params['lotSz']
        min_sz = params['minSz']

        telemetry.log_info("main", f"ctVal={ct_val}, lotSz={lot_sz}, minSz={min_sz} para {symbol}")

        # ============================================================
        # 3. Calcular notional con leverage y ctVal
        # ============================================================
        safety_factor = 0.98
        available_capital = usdt_balance * safety_factor
        telemetry.log_info("main", f"Capital utilizable: {available_capital:.2f} USDT")

        # Notional deseado = capital disponible * leverage
        desired_notional = available_capital * LEVERAGE
        telemetry.log_info("main", f"Notional deseado: {desired_notional:.2f} USDT (leverage {LEVERAGE}x)")

        # Tamaño en contratos = notional / (precio * ctVal)
        size = desired_notional / (self.signal.entry_price * ct_val)

        # Redondear al múltiplo de lotSz
        if lot_sz > 0:
            size = round(size / lot_sz) * lot_sz
        else:
            size = round(size)

        # Asegurar mínimo
        if size < min_sz:
            size = min_sz

        # Asegurar que no sea cero
        if size < min_sz:
            size = min_sz

        # Redondear a 2 decimales para evitar problemas de precisión
        size = round(size, 2)

        actual_notional = size * self.signal.entry_price * ct_val

        telemetry.log_info("main", f"Tamaño ajustado: {size} contratos (notional real ~{actual_notional:.2f} USDT)")
        telemetry.log_info("main", f"Valor nominal enviado a la API: {actual_notional:.2f} USDT")

        # ============================================================
        # 4. Enviar orden
        # ============================================================
        side = "buy" if self.signal.direction == "Long" else "sell"

        order = self.exchange.place_market_order(self.signal.symbol, side, size)
        if not order.get('ok'):
            telemetry.log_error("main", "Fallo al abrir posición", order)
            self.error_count += 1
            if self.error_count >= self.max_errors:
                self.state = BotState.SHUTDOWN
            else:
                self.state = BotState.ERROR_RECOVERY
            return

        telemetry.log_info("main", "Orden de mercado ejecutada", order)
        time.sleep(1)

        positions = self.exchange.get_positions(self.signal.symbol)
        if not positions.get('ok') or not positions.get('data'):
            telemetry.log_error("main", "No se encontró la posición abierta")
            self.state = BotState.ERROR_RECOVERY
            return

        pos_data = positions['data'][0]
        entry_price = float(pos_data['avgPx'])
        mark_price = float(pos_data['markPx'])
        size = float(pos_data['pos'])
        side = pos_data['posSide']

        self.position = Position(
            symbol=pos_data['instId'].replace('-USDT-SWAP', ''),
            side=side,
            size=size,
            entry_price=entry_price,
            mark_price=mark_price,
            unrealized_pnl=float(pos_data['upl']),
            leverage=float(pos_data['lever']),
            repair_attempts=0
        )

        # ============================================================
        # 5. Enviar TP/SL
        # ============================================================
        if self.signal.target_price and self.signal.stop_loss:
            if self.position.side == 'long':
                tp_side, sl_side = 'sell', 'sell'
            else:
                tp_side, sl_side = 'buy', 'buy'

            tp_resp = self.exchange.place_algo_order(
                symbol=self.position.symbol,
                side=tp_side,
                trigger_price=self.signal.target_price,
                order_price=self.signal.target_price,
                size=self.position.size,
                order_type="conditional"
            )
            sl_resp = self.exchange.place_algo_order(
                symbol=self.position.symbol,
                side=sl_side,
                trigger_price=self.signal.stop_loss,
                order_price=self.signal.stop_loss,
                size=self.position.size,
                order_type="conditional"
            )

            if tp_resp.get('ok'):
                telemetry.log_info("main", "TP enviado correctamente")
            else:
                telemetry.log_error("main", "Fallo al enviar TP", tp_resp)

            if sl_resp.get('ok'):
                telemetry.log_info("main", "SL enviado correctamente")
            else:
                telemetry.log_error("main", "Fallo al enviar SL", sl_resp)

            if TRAILING_ENABLED and TRAILING_MODE == 'native':
                callback = TRAILING_DISTANCE_ATR * 0.01
                trail_resp = self.exchange.place_trailing_order(
                    symbol=self.position.symbol,
                    side=tp_side,
                    size=self.position.size,
                    callback_rate=callback
                )
                if trail_resp.get('ok'):
                    telemetry.log_info("main", "Trailing stop enviado correctamente")
                else:
                    telemetry.log_error("main", "Fallo al enviar trailing", trail_resp)

        # ============================================================
        # 6. Guardar estado
        # ============================================================
        self.state_data['trades'].append({
            'symbol': self.position.symbol,
            'side': self.position.side,
            'entry': self.position.entry_price,
            'tp': self.signal.target_price,
            'sl': self.signal.stop_loss,
            'size': self.position.size,
            'notional': actual_notional,
            'leverage': LEVERAGE,
            'ctVal': ct_val,
            'timestamp': datetime.utcnow().isoformat()
        })
        save_state(self.state_data)

        self.state = BotState.WAIT_NEXT_CYCLE

    def _wait_next_cycle(self):
        telemetry.log_info("main", "Esperando siguiente ciclo...")
        self.error_count = 0
        self.state = BotState.SEARCH_SIGNAL

    def _error_recovery(self):
        wait_time = RECONNECT_BACKOFF * (2 ** self.error_count)
        telemetry.log_warning("main", f"Recuperando error, esperando {wait_time}s")
        time.sleep(wait_time)
        self.state = BotState.CONNECT_OKX

    def _shutdown(self):
        telemetry.log_info("main", "Apagando bot...")
        self.running = False
        self.state = BotState.SHUTDOWN

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    api_key = os.environ.get('OKX_API_KEY')
    secret = os.environ.get('OKX_SECRET_KEY')
    passphrase = os.environ.get('OKX_PASSPHRASE')
    demo = os.environ.get('OKX_DEMO', 'true').lower() == 'true'

    if not api_key or not secret or not passphrase:
        telemetry.log_error("main", "Faltan credenciales")
        sys.exit(1)

    if not acquire_lock(LOCK_FILE, LOCK_TIMEOUT):
        telemetry.log_warning("main", "Otra instancia ejecutándose")
        sys.exit(0)

    try:
        bot = Bot(api_key, secret, passphrase, demo)
        bot.run()
    except Exception as e:
        telemetry.log_error("main", f"Error crítico: {e}", {'traceback': traceback.format_exc()})
    finally:
        release_lock(LOCK_FILE)
        telemetry.log_info("main", "Fin")
