# telemetry.py
# ============================================================
# SISTEMA DE LOGGING ESTRUCTURADO
# ============================================================

import logging
import json
import os
from logging.handlers import RotatingFileHandler

class Telemetry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger("PiDelta")
        self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Consola
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Archivo de logs
        os.makedirs('logs', exist_ok=True)
        fh = RotatingFileHandler('logs/runtime.log', maxBytes=10*1024*1024, backupCount=5)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Archivo JSON estructurado
        self.json_logger = logging.getLogger("PiDeltaJSON")
        self.json_logger.setLevel(logging.INFO)
        json_handler = RotatingFileHandler('logs/runtime.json', maxBytes=10*1024*1024, backupCount=5)
        json_handler.setFormatter(logging.Formatter('%(message)s'))
        self.json_logger.addHandler(json_handler)

    def _log(self, level, module, message, data=None):
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'module': module,
            'level': level,
            'message': message,
            'data': data or {}
        }
        getattr(self.logger, level)(f"[{module}] {message} {json.dumps(data) if data else ''}")
        getattr(self.json_logger, level)(json.dumps(entry))

    def log_info(self, module, message, data=None):
        self._log('info', module, message, data)

    def log_warning(self, module, message, data=None):
        self._log('warning', module, message, data)

    def log_error(self, module, message, data=None):
        self._log('error', module, message, data)

    def log_debug(self, module, message, data=None):
        self._log('debug', module, message, data)

from datetime import datetime
telemetry = Telemetry()
