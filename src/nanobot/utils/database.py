import os
import json
import threading
import logging
from datetime import datetime

logger = logging.getLogger("Nanobot.SecureDB")

class SecureDatabaseManager:
    """
    ARQUITECTO DE DATOS OMEGA+: Garantiza persistencia atómica y resiliente.
    - Escrituras Atómicas via TMP-Move.
    - Thread-Safe con Locks internos.
    - Sanity Checks para reglas FTMO.
    """
    
    _lock = threading.Lock()

    @staticmethod
    def save_json(file_path, data, indent=4):
        """Guarda un JSON de forma atómica y segura."""
        with SecureDatabaseManager._lock:
            temp_path = f"{file_path}.tmp"
            try:
                # 1. Asegurar directorio
                os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
                
                # 2. Escritura en archivo temporal
                with open(temp_path, "w") as f:
                    json.dump(data, f, indent=indent)
                    f.flush()
                    os.fsync(f.fileno()) # Forzar vaciado al disco físico
                
                # 4. Reemplazo Atómico (os.replace es atómico en la mayoría de OS modernos)
                os.replace(temp_path, file_path)
                return True
            except Exception as e:
                logger.error(f"❌ ATOMIC WRITE FAILED for {file_path}: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False

    @staticmethod
    def load_json(file_path, default=None):
        """Carga un JSON con manejo de errores."""
        if default is None: default = {}
        try:
            if not os.path.exists(file_path):
                return default
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ READ FAILED for {file_path}: {e}")
            return default

    @staticmethod
    def append_log(file_path, line):
        """Escribe una línea en un CSV/Log con Lock de hilo."""
        with SecureDatabaseManager._lock:
            try:
                with open(file_path, "a") as f:
                    f.write(f"{line}\n")
            except Exception as e:
                logger.error(f"❌ LOG APPEND FAILED for {file_path}: {e}")

    @staticmethod
    def validate_account_data(current_val, previous_val, max_deviation=0.10):
        """
        Sanity Check para Reglas FTMO.
        Evita lecturas fallidas del broker (ej. Balance = 0).
        """
        if current_val <= 100: # Valor absurdo para una cuenta FTMO de 50k
            return False
        
        if previous_val > 0:
            deviation = abs(current_val - previous_val) / previous_val
            if deviation > max_deviation:
                logger.warning(f"🚨 SANITY CHECK FAILED: Desviación inusual ({deviation*100:.2f}%) en balance.")
                return False
        return True
