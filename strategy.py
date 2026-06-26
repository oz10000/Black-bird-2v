# strategy.py
# ============================================================
# SELECTOR DE ESTRATEGIAS – CARGA DINÁMICA
# ============================================================

import importlib
from typing import List, Dict, Optional
from models import Signal
from config import ACTIVE_STRATEGY, STRATEGY_MODULES

# Cargar el módulo de estrategia activa
_strategy_name = STRATEGY_MODULES.get(ACTIVE_STRATEGY, 'strategy_production')
_strategy_module = importlib.import_module(_strategy_name)

# Exponer la función get_best_signal del módulo cargado
get_best_signal = _strategy_module.get_best_signal

# Redirigir también la función generate_signal si existe (para compatibilidad)
if hasattr(_strategy_module, 'generate_signal'):
    generate_signal = _strategy_module.generate_signal
else:
    # Fallback: usar la función del módulo original (si está disponible)
    try:
        from signals import generate_signal as _gen_signal
        generate_signal = _gen_signal
    except ImportError:
        generate_signal = None
