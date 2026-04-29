import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger("Nanobot.Volatility")

class VolatilityEngine:
    """
    MOTOR DE VOLATILIDAD OMEGA+: Calcula ATR y factores de riesgo dinámicos.
    - Caché de 15 minutos para optimizar llamadas a MT5.
    - Normalización institucional de volatilidad.
    """
    def __init__(self, mt5_client):
        self.client = mt5_client
        self.atr_cache: Dict[str, Dict] = {}
        self.cache_duration = 900 # 15 minutos
        self.base_volatility = 0.0015 # 0.15% como volatilidad base estándar

    def get_symbol_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Obtiene el ATR actual para un símbolo con caché."""
        now = time.time()
        
        if symbol in self.atr_cache:
            cache_data = self.atr_cache[symbol]
            if now - cache_data['timestamp'] < self.cache_duration:
                return cache_data['atr']

        try:
            # Pedimos histórico (H1 para volatilidad de swing/intradía)
            # Usamos eval para siliconmt5
            res = self.client.eval(f"mt5.copy_rates_from_pos('{symbol}', mt5.TIMEFRAME_H1, 0, {period + 1})")
            if res is None or len(res) < period:
                return None
            
            df = pd.DataFrame(res)
            
            # Cálculo de True Range
            df['prev_close'] = df['close'].shift(1)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = (df['high'] - df['prev_close']).abs()
            df['tr3'] = (df['low'] - df['prev_close']).abs()
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            atr = df['tr'].tail(period).mean()
            
            self.atr_cache[symbol] = {
                'atr': atr,
                'timestamp': now,
                'price': df['close'].iloc[-1]
            }
            return atr
        except Exception as e:
            logger.error(f"❌ Error calculando ATR para {symbol}: {e}")
            return None

    def get_symbol_atr_pips(self, symbol: str) -> float:
        """Retorna el ATR expresado en pips."""
        atr = self.get_symbol_atr(symbol)
        if not atr: return 50.0 # Fallback conservador
        
        info = self.client.symbol_info(symbol)
        if not info: return 50.0
        
        # Factor pips (10 para 5 dígitos)
        multiplier = (10 if info.digits == 3 or info.digits == 5 else 1)
        return atr / info.point / multiplier

    def get_account_volatility_factor(self, active_symbols: list) -> float:
        """
        Calcula el Factor de Volatilidad Global de la cuenta.
        Normaliza el ATR de todos los pares activos frente a una base.
        """
        if not active_symbols: return 1.0
        
        vol_pcts = []
        for s in active_symbols:
            atr = self.get_symbol_atr(s)
            if not atr: continue
            
            price = self.atr_cache[s]['price']
            vol_pct = atr / price
            vol_pcts.append(vol_pct)
        
        if not vol_pcts: return 1.0
        
        avg_vol = sum(vol_pcts) / len(vol_pcts)
        # Factor = Volatilidad Actual / Volatilidad Base
        factor = avg_vol / self.base_volatility
        
        # Clamp: No permitimos que el factor sea menor a 0.7 o mayor a 2.5 por seguridad
        return max(0.7, min(2.5, factor))
