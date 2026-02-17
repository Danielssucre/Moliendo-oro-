"""
Backtester - Simulación histórica para validación de estrategias.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..api.api_manager import api_manager
from ..trading_agent import TradingAgent
from ..utils.logger import logger
from ..utils.config import config

@dataclass
class BacktestResult:
    """Resultados de una simulación de backtesting."""
    pair: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    trades: List[Dict]

class Backtester:
    """Motor de backtesting para el Trading Agent."""
    
    def __init__(self, agent: TradingAgent):
        self.agent = agent
        
    @property
    def timeframes(self):
        """Dynamic access to timeframes."""
        return config.timeframes
        
    def run(self, pair: str, days: int = 30, config_override: Optional[Dict] = None, allowed_hours: Optional[List[int]] = None, step_skip: int = 1) -> BacktestResult:
        """Original run method that fetches data and executes simulation."""
        logger.info(f"⏳ Iniciando Backtesting para {pair} ({days} días)...")
        
        tfs = config_override.get('timeframes') if config_override and 'timeframes' in config_override else self.timeframes
        data_bundles = self._get_historical_bundles(pair, days, timeframes_dict=tfs)
        if not data_bundles:
            raise RuntimeError(f"No se pudieron obtener datos suficientes para {pair}")
            
        return self.run_with_data(pair, data_bundles, config_override, allowed_hours, step_skip)

    def run_with_data(self, pair: str, data_bundles: Dict[str, pd.DataFrame], config_override: Optional[Dict] = None, allowed_hours: Optional[List[int]] = None, step_skip: int = 1) -> BacktestResult:
        """
        Ejecuta backtesting usando un bundle de datos ya cargado.
        Ideal para validación In-Sample / Out-of-Sample.
        """
        # Sincronizar timestamps (usamos el timeframe corto como base)
        tfs = config_override.get('timeframes') if config_override and 'timeframes' in config_override else self.timeframes
        base_tf = tfs['short']
        
        if base_tf not in data_bundles:
            # Fallback if key is the interval itself
            base_tf_interval = tfs['short']
            base_data = data_bundles.get(base_tf_interval)
        else:
            base_data = data_bundles[base_tf]

        if base_data is None:
            raise ValueError(f"Base data for timeframe {base_tf} not found in bundles")

        # 3. Simulación
        trades = []
        total_steps = len(base_data)
        start_idx = 100 # Reducido para permitir periodos cortos
        active_trade_until = -1
        cooldown_steps = 12
        
        for i in range(start_idx, total_steps, step_skip):
            if i < active_trade_until:
                continue
                
            current_timestamp = base_data.index[i]
            
            if allowed_hours is not None and current_timestamp.hour not in allowed_hours:
                continue
            
            window_data = {}
            for tf_interval, df in data_bundles.items():
                window_data[tf_interval] = df[df.index <= current_timestamp].tail(500)
            
            signal = self.agent.analyze_pair(
                pair, 
                manual_data=window_data, 
                override_timestamp=current_timestamp,
                config_override=config_override
            )
            
            if signal:
                trade_result, exit_idx = self._simulate_trade_v2(base_data, i, signal)
                if trade_result:
                    trades.append(trade_result)
                    active_trade_until = exit_idx + cooldown_steps
        
        return self._calculate_metrics(pair, trades)

    def _get_historical_bundles(self, pair: str, days: int, timeframes_dict: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """Obtiene y limpia datos para todos los timeframes."""
        bundles = {}
        for tf_name, tf_interval in timeframes_dict.items():
            try:
                # Nota: El API Manager actual maneja caché y fallback
                # Para backtesting largo, idealmente necesitaríamos un endpoint de historial extenso
                df = api_manager.get_forex_data(pair, tf_interval, outputsize="full")
                bundles[tf_interval] = df
            except Exception as e:
                logger.error(f"Error descargando {tf_interval}: {e}")
        return bundles

    def _simulate_trade_v2(self, df_future: pd.DataFrame, start_idx: int, signal, config_override: Optional[Dict] = None) -> Tuple[Optional[Dict], int]:
        """
        Simula el resultado de una señal mirando el futuro en el DataFrame.
        Retorna (registro_operacion, indice_de_salida).
        """
        entry_price = signal.entry_price
        sl = signal.stop_loss
        tp = signal.take_profit
        direction = signal.direction
        
        # Miramos las siguientes velas (máximo configurable / por defecto 48 horas para velas H1)
        max_lookahead = 48
        if config_override and "max_lookahead" in config_override:
            max_lookahead = config_override["max_lookahead"]
        elif config.get_cfg("max_lookahead") is not None:
             max_lookahead = config.get_cfg("max_lookahead")
             
        last_idx = min(start_idx + max_lookahead, len(df_future) - 1)
        
        for j in range(start_idx + 1, last_idx + 1):
            curr_low = df_future.iloc[j]['low']
            curr_high = df_future.iloc[j]['high']
            
            if direction == "BUY":
                if curr_low <= sl:
                    return self._create_trade_record(signal, "SL", sl), j
                if curr_high >= tp:
                    return self._create_trade_record(signal, "TP", tp), j
            else: # SELL
                if curr_high >= sl:
                    return self._create_trade_record(signal, "SL", sl), j
                if curr_low <= tp:
                    return self._create_trade_record(signal, "TP", tp), j
        
        # Si expira sin tocar nada
        exit_price = df_future.iloc[last_idx]['close']
        return self._create_trade_record(signal, "EXPIRED", exit_price), last_idx

    def _create_trade_record(self, signal, status: str, exit_price: float) -> Dict:
        # Simplificación de P&L: asumimos $10 por pip por lote
        pip_size = 0.0001 if "JPY" not in signal.pair else 0.01
        pips = (exit_price - signal.entry_price) / pip_size
        if signal.direction == "SELL":
            pips = -pips
            
        profit_loss = pips * 10 * signal.position_size
        
        return {
            'pair': signal.pair,
            'direction': signal.direction,
            'status': status,
            'pips': pips,
            'profit_loss': profit_loss,
            'timestamp': signal.timestamp
        }

    def _calculate_metrics(self, pair: str, trades: List[Dict]) -> BacktestResult:
        if not trades:
            return BacktestResult(pair, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, [])
            
        winning = [t for t in trades if t['profit_loss'] > 0]
        losing = [t for t in trades if t['profit_loss'] <= 0]
        
        total_profit = sum(t['profit_loss'] for t in winning)
        total_loss = abs(sum(t['profit_loss'] for t in losing))
        net_profit = total_profit - total_loss
        
        # Calcular Max Drawdown (simplificado)
        balance = 0
        balances = []
        for t in trades:
            balance += t['profit_loss']
            balances.append(balance)
        
        max_val = np.maximum.accumulate(balances)
        drawdowns = max_val - balances
        max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        return BacktestResult(
            pair=pair,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(trades),
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=net_profit,
            profit_factor=total_profit / total_loss if total_loss > 0 else total_profit,
            max_drawdown=max_dd,
            sharpe_ratio=self._calculate_sharpe(trades),
            sortino_ratio=self._calculate_sortino(trades),
            trades=trades
        )

    def _calculate_sharpe(self, trades: List[Dict], risk_free_rate: float = 0.0) -> float:
        if not trades: return 0.0
        returns = [t['profit_loss'] for t in trades]
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0: return 0.0
        return (avg_return - risk_free_rate) / std_return

    def _calculate_sortino(self, trades: List[Dict], risk_free_rate: float = 0.0) -> float:
        if not trades: return 0.0
        returns = [t['profit_loss'] for t in trades]
        avg_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns: return 10.0 # Arbitrary high value for no losses
        downside_std = np.std(downside_returns)
        if downside_std == 0: return 0.0
        return (avg_return - risk_free_rate) / downside_std
