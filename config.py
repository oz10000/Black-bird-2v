# config.py
# ============================================================
# CONFIGURACIÓN GLOBAL – OPTIMIZADA Y CERTIFICADA
# CORREGIDA: Añadidas todas las variables que el verificador espera
# ============================================================

# ---- Símbolos y operativa ----
SYMBOLS = [
    'BTC', 'ETH', 'SOL', 'ADA', 'XRP',
    'DOT', 'AVAX', 'POL',  # POL es el ticker correcto en OKX
    'LINK',  # UNI no existe, se eliminó
]
TRADE_NOTIONAL = 1000.0
LEVERAGE = 8  # Apalancamiento fijo (optimizado)

# ---- Parámetros de estrategia ----
TP_MULT = 1.0
SL_MULT = 1.2
ATR_PERIOD = 14
BE_GAIN = 0.0005
BE_UMBRAL = 0.25

# ---- Trailing Stop ----
TRAILING_ENABLED = True
TRAILING_MODE = 'native'
TRAILING_DISTANCE_ATR = 0.6
TRAILING_ACTIVATION_PROFIT = 0.6

# ---- Niveles de velocidad ----
SPEED_LEVELS = [
    {"nivel": 1, "raw_min": 0.45, "roc_min": 0.30},
    {"nivel": 2, "raw_min": 0.40, "roc_min": 0.25},
    {"nivel": 3, "raw_min": 0.35, "roc_min": 0.20},
    {"nivel": 4, "raw_min": 0.30, "roc_min": 0.15},
    {"nivel": 5, "raw_min": 0.25, "roc_min": 0.10},
    {"nivel": 6, "raw_min": 0.20, "roc_min": 0.05},
]
DEFAULT_SPEED_LEVEL = SPEED_LEVELS[1]  # N2

# ---- Configuración individual por activo ----
PER_ASSET_CONFIG = {
    'BTC': {'speed_level': SPEED_LEVELS[1], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.25, 'trailing_dist': 0.6, 'trailing_act': 0.6},
    'ETH': {'speed_level': SPEED_LEVELS[1], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.25, 'trailing_dist': 0.6, 'trailing_act': 0.6},
    'SOL': {'speed_level': SPEED_LEVELS[2], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'ADA': {'speed_level': SPEED_LEVELS[2], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'XRP': {'speed_level': SPEED_LEVELS[3], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'DOT': {'speed_level': SPEED_LEVELS[2], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'AVAX': {'speed_level': SPEED_LEVELS[2], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'POL': {'speed_level': SPEED_LEVELS[3], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
    'LINK': {'speed_level': SPEED_LEVELS[2], 'tp_mult': 1.0, 'sl_mult': 1.2, 'be_umbral': 0.30, 'trailing_dist': 0.5, 'trailing_act': 0.5},
}

# ---- Niveles optimizados por activo ----
OPTIMIZED_LEVELS = {
    symbol: {'Long': cfg['speed_level'], 'Short': cfg['speed_level']}
    for symbol, cfg in PER_ASSET_CONFIG.items()
}

# ---- Filtros horarios (24/7) ----
TIME_FILTER_ENABLED = False
TIME_FILTER_START = 12
TIME_FILTER_END = 18
TIME_FILTER_WEEKDAYS = [0, 1, 2, 3, 4]

# ---- Filtros por activo ----
FILTERS = {
    'BTC': {'Long': {'ker_min': 0.55, 'zscore_min': 1.2},
            'Short': {'zscore_max': -1.8, 'vol_rel_min': 1.8}},
    'ETH': {'Long': {'ker_min': 0.50, 'atr_percent_min': 0.75},
            'Short': {'zscore_max': -1.5, 'ker_min': 0.50}},
    'SOL': {'Long': {'vol_rel_min': 1.8, 'ema_pend_min': 0.0015},
            'Short': {'ker_min': 0.60, 'zscore_max': -1.2}},
    'ADA': {'Long': {'ker_min': 0.45, 'vol_rel_min': 1.5, 'atr_percent_min': 0.80},
            'Short': {'ker_min': 0.45, 'zscore_max': -1.0, 'vol_rel_min': 1.5}},
    'XRP': {'Long': {'ker_min': 0.40, 'vol_rel_min': 1.5, 'zscore_min': 0.8},
            'Short': {'ker_min': 0.40, 'zscore_max': -0.8, 'vol_rel_min': 1.5}},
    'DOT': {'Long': {'ker_min': 0.45, 'vol_rel_min': 1.5, 'atr_percent_min': 0.75},
            'Short': {'ker_min': 0.45, 'zscore_max': -1.0, 'vol_rel_min': 1.5}},
    'AVAX': {'Long': {'ker_min': 0.45, 'vol_rel_min': 1.5, 'atr_percent_min': 0.75},
             'Short': {'ker_min': 0.45, 'zscore_max': -1.0, 'vol_rel_min': 1.5}},
    'POL': {'Long': {'ker_min': 0.40, 'vol_rel_min': 1.5, 'atr_percent_min': 0.70},
            'Short': {'ker_min': 0.40, 'zscore_max': -0.8, 'vol_rel_min': 1.5}},
    'LINK': {'Long': {'ker_min': 0.45, 'vol_rel_min': 1.5, 'atr_percent_min': 0.75},
             'Short': {'ker_min': 0.45, 'zscore_max': -1.0, 'vol_rel_min': 1.5}},
}

# ---- Parámetros de instrumentos OKX ----
INSTRUMENT_PARAMS = {
    'BTC': {'ctVal': 0.01, 'lotSz': 0.01, 'minSz': 0.01},
    'ETH': {'ctVal': 0.1, 'lotSz': 0.01, 'minSz': 0.01},
    'SOL': {'ctVal': 1.0, 'lotSz': 0.01, 'minSz': 0.01},
    'ADA': {'ctVal': 100.0, 'lotSz': 0.01, 'minSz': 0.01},
    'XRP': {'ctVal': 100.0, 'lotSz': 0.01, 'minSz': 0.01},
    'DOT': {'ctVal': 1.0, 'lotSz': 0.1, 'minSz': 0.1},
    'AVAX': {'ctVal': 1.0, 'lotSz': 0.1, 'minSz': 0.1},
    'POL': {'ctVal': 1.0, 'lotSz': 0.01, 'minSz': 0.01},
    'LINK': {'ctVal': 1.0, 'lotSz': 0.01, 'minSz': 0.01},
}

# ---- Recuperación y reintentos ----
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF = 5
BACKOFF_BASE = 5
MAX_RETRIES_PER_ORDER = 3
ORDER_TIMEOUT = 15
LOCK_FILE = '.lock'
LOCK_TIMEOUT = 10
SYNC_TIME_ENABLED = True
MAX_CONSECUTIVE_ERRORS = 5
MAX_REPAIR_ATTEMPTS = 3

# ---- Control de Riesgo ----
MAX_DAILY_LOSS_PERCENT = 2.0
MAX_WEEKLY_LOSS_PERCENT = 4.0
MAX_OPEN_POSITIONS = 1

# ---- Backtesting ----
BACKTEST_DAYS = 5
BACKTEST_FEE_MAKER = 0.0005
BACKTEST_FEE_TAKER = 0.0007
BACKTEST_SLIPPAGE = 0.0002

# ---- Logging ----
LOG_DIR = 'logs'
LOG_LEVEL = 'INFO'
LOG_CONSOLE = True
LOG_FILE = True
LOG_JSON = True
MAX_LOG_SIZE_MB = 10
MAX_LOG_FILES = 5

# ---- Modo demo ----
OKX_DEMO = True

# ---- Modo de prueba ----
TEST_MODE = False
TEST_IGNORE_FILTERS = True
TEST_SPEED_LEVEL = {"nivel": 6, "raw_min": 0.05, "roc_min": 0.01}
CYCLE_INTERVAL_TEST = 10

# ---- Selección de estrategia ----
ACTIVE_STRATEGY = 'production'
STRATEGY_MODULES = {
    'production': 'strategy_production',
    'test_fast': 'strategy_test_fast',
    'test_simple': 'strategy_test_simple',
    'experimental': 'strategy_experimental',
}

# ============================================================
# VERIFICACIÓN DE CONFIGURACIÓN (autodiagnóstico)
# ============================================================
if __name__ == "__main__":
    required = [
        'SYMBOLS', 'TRADE_NOTIONAL', 'LEVERAGE',
        'TP_MULT', 'SL_MULT', 'ATR_PERIOD',
        'DEFAULT_SPEED_LEVEL', 'OPTIMIZED_LEVELS', 'PER_ASSET_CONFIG',
        'FILTERS', 'INSTRUMENT_PARAMS',
        'MAX_REPAIR_ATTEMPTS', 'BACKOFF_BASE', 'SYNC_TIME_ENABLED',
        'MAX_OPEN_POSITIONS',
        'BACKTEST_DAYS', 'LOG_DIR',
        'TEST_MODE', 'ACTIVE_STRATEGY', 'STRATEGY_MODULES'
    ]
    all_ok = True
    for var in required:
        if var not in globals():
            print(f"❌ Falta: {var}")
            all_ok = False
        else:
            print(f"✅ {var}")
    if all_ok:
        print("✅ CONFIGURACIÓN COMPLETA Y CORRECTA")
    else:
        print("❌ ERRORES DETECTADOS – REVISAR")
