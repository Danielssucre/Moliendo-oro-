"""
DUAL-GATEKEEPER v2: VALIDACIÓN ASIMÉTRICA
==========================================
Cambios V2:
- Filtro de datos FTMO (solo operaciones reales)
- Estados independientes por NEM: HEAVY/MODERATE/SCOUT/VOID
- Lógica asimétrica: cada NEM se evalúa independientemente
- XOR Gate: nunca dos HEAVY en direcciones opuestas
- MODERATE: 3 niveles (L1, L3, L5)

Parámetros:
- HEAVY: GHI >= 75 Y trades >= 6
- MODERATE: GHI >= 50 Y trades >= 6
- SCOUT: GHI < 50 O trades < 6
- VOID: Sin datos
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import json
import os
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger("DualGatekeeper")

class NEMState(Enum):
    VOID = "VOID"       # Sin datos
    SCOUT = "SCOUT"     # 1 nivel, 0.01 lots (recolección)
    MODERATE = "MODERATE"  # 3 niveles (L1,L3,L5), ~0.14%
    HEAVY = "HEAVY"     # 7 niveles, 0.25%

class RegimeState(Enum):
    UNKNOWN = "UNKNOWN"
    DUAL_SCOUT = "DUAL_SCOUT"
    ASYMMETRIC_NEM1_HEAVY = "ASYMMETRIC_NEM1_HEAVY"
    ASYMMETRIC_NEM2_HEAVY = "ASYMMETRIC_NEM2_HEAVY"
    SYMMETRIC_BOTH_VALID = "SYMMETRIC_BOTH_VALID"

@dataclass
class NEMStats:
    ghi: float = 50.0
    pf: float = 0.0
    win_rate: float = 0.0
    trades: int = 0
    state: NEMState = NEMState.VOID
    
    def __post_init__(self):
        if self.trades < 6:
            self.state = NEMState.SCOUT
        elif self.ghi >= 75:
            self.state = NEMState.HEAVY
        elif self.ghi >= 50:
            self.state = NEMState.MODERATE
        else:
            self.state = NEMState.SCOUT

def is_real_trade(trade: dict) -> bool:
    """Filtro: Solo operaciones reales FTMO"""
    account = trade.get('account')
    server = trade.get('server', '')
    
    # Account FTMO
    if account == 1513194377:
        return True
    # Server FTMO
    if 'FTMO' in str(server).upper():
        return True
    # Filtrar cuentas de prueba
    if account in ['LEGACY_RECOVERY', 'SHADOW_RECOVERY', 'RESEARCH_DATA']:
        return False
    if server in ['LOCAL_LOGS', 'RESEARCH_DATA']:
        return False
    
    return True

class DualGatekeeperV2:
    """
    State Machine V2 con Validación Asimétrica.
    
    Diferencias con V1:
    - Filtra solo trades reales (FTMO)
    - Evalúa cada NEM independientemente
    - Estados: VOID/SCOUT/MODERATE/HEAVY
    - XOR: No envía dos HEAVY opuestos
    """
    
    GHI_HEAVY = 75
    GHI_MODERATE = 50
    MIN_TRADES = 6
    FLIP_WINDOW = 5
    FLIP_MULTIPLIER = 2.0
    
    def __init__(self, config_path="config/health_history.json"):
        self.config_path = config_path
        self.symbol_states: Dict[str, Dict] = {}
        self._load_states()
    
    def _load_states(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.symbol_states = data.get('symbol_states', {})
                    logger.info(f"DualGatekeeperV2: {len(self.symbol_states)} symbol states loaded")
            except Exception as e:
                logger.warning(f"Error loading states: {e}")
                self.symbol_states = {}
    
    def _save_states(self):
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            data['symbol_states'] = self.symbol_states
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving states: {e}")
    
    def get_state(self, symbol: str) -> RegimeState:
        state = self.symbol_states.get(symbol.upper(), {})
        status = state.get('regime_status', 'UNKNOWN')
        try:
            return RegimeState(status)
        except:
            return RegimeState.UNKNOWN
    
    def get_best_nem(self, symbol: str) -> Optional[str]:
        return self.symbol_states.get(symbol.upper(), {}).get('best_nem')
    
    def get_nem_state(self, symbol: str, nem: str) -> NEMState:
        """Retorna el estado de un NEM específico"""
        state = self.symbol_states.get(symbol.upper(), {})
        key = f'nem{nem.lower()}_state'
        try:
            return NEMState(state.get(key, 'VOID'))
        except:
            return NEMState.VOID
    
    def get_execution_plan(self, symbol: str) -> dict:
        """Retorna el plan de ejecución basado en estados asimétricos"""
        state = self.symbol_states.get(symbol.upper(), {})
        
        best_nem = state.get('best_nem', 'NEM2')
        nem1_state = NEMState(state.get('nem1_state', 'VOID'))
        nem2_state = NEMState(state.get('nem2_state', 'VOID'))
        
        # Determinar niveles según estado
        def get_levels(nem_state: NEMState) -> int:
            if nem_state == NEMState.HEAVY:
                return 7
            elif nem_state == NEMState.MODERATE:
                return 3
            elif nem_state == NEMState.SCOUT:
                return 1
            return 0
        
        # Si best_nem tiene señal, enviar HEAVY/MODERATE
        # El otro siempre es SCOUT (XOR - nunca dos HEAVY)
        
        if best_nem == 'NEM1':
            heavy_nem = 'NEM1'
            scout_nem = 'NEM2'
            heavy_state = nem1_state
            scout_state = nem2_state
        else:
            heavy_nem = 'NEM2'
            scout_nem = 'NEM1'
            heavy_state = nem2_state
            scout_state = nem1_state
        
        # Descripción
        heavy_label = heavy_state.name
        scout_label = scout_state.name
        
        return {
            'action': 'ASYMMETRIC_EXECUTION',
            'best_nem': best_nem,
            'heavy_nem': heavy_nem,
            'scout_nem': scout_nem,
            'heavy_state': heavy_label,
            'scout_state': scout_label,
            'heavy_levels': get_levels(heavy_state),
            'scout_levels': 1,  # Siempre 1 para scout
            'lot_size': 0.01,
            'description': f'{heavy_label} {heavy_nem} ({get_levels(heavy_state)} levels) + {scout_label} {scout_nem} (1 level)'
        }
    
    def calculate_stats(self, trades: List[dict], symbol: str) -> NEMStats:
        """Calcula estadísticas filtrando solo trades reales"""
        symbol_upper = symbol.upper()
        
        # FILTRO FTMO: Solo operaciones reales
        real_trades = [t for t in trades if is_real_trade(t)]
        
        # Filtrar por símbolo
        sym_trades = [t for t in real_trades if t.get('symbol', '').upper() == symbol_upper]
        
        if len(sym_trades) < 3:
            return NEMStats(trades=len(sym_trades), state=NEMState.VOID)
        
        profits = [t.get('profit', 0) for t in sym_trades]
        
        profits_arr = np.array(profits)
        wins = profits_arr[profits_arr > 0]
        losses = np.abs(profits_arr[profits_arr < 0])
        
        n = len(profits)
        n_wins = len(wins)
        
        win_rate = (n_wins / n * 100) if n > 0 else 0
        pf = sum(wins) / (sum(losses) + 0.01) if len(losses) > 0 else 0
        
        ghi = (win_rate / 100 * 0.4 + min(1.0, pf / 2.0) * 0.6) * 100
        
        stats = NEMStats(
            ghi=ghi,
            pf=pf,
            win_rate=win_rate,
            trades=n,
            state=NEMState.VOID  # Se calcula en __post_init__
        )
        
        return stats
    
    def evaluate_and_transition(self, symbol: str, nem1_trades: list, nem2_trades: list) -> RegimeState:
        """Evalúa y determina estados asimétricos"""
        symbol_upper = symbol.upper()
        
        # Calcular stats con filtro FTMO
        nem1_stats = self.calculate_stats(nem1_trades, symbol_upper)
        nem2_stats = self.calculate_stats(nem2_trades, symbol_upper)
        
        # Determinar estados individuales
        nem1_state = nem1_stats.state
        nem2_state = nem2_stats.state
        
        # Determinar best_nem (el que tiene mayor GHI)
        if nem1_stats.trades >= self.MIN_TRADES and nem2_stats.trades >= self.MIN_TRADES:
            if nem1_stats.ghi > nem2_stats.ghi:
                best_nem = 'NEM1'
            else:
                best_nem = 'NEM2'
        elif nem1_stats.trades >= self.MIN_TRADES and nem1_stats.ghi >= self.GHI_MODERATE:
            best_nem = 'NEM1'
        elif nem2_stats.trades >= self.MIN_TRADES and nem2_stats.ghi >= self.GHI_MODERATE:
            best_nem = 'NEM2'
        else:
            best_nem = 'NEM2'  # Default
        
        # Guardar estados
        self.symbol_states[symbol_upper] = self.symbol_states.get(symbol_upper, {})
        self.symbol_states[symbol_upper].update({
            'best_nem': best_nem,
            'nem1_state': nem1_state.value,
            'nem2_state': nem2_state.value,
            'nem1_stats': {
                'ghi': round(nem1_stats.ghi, 1),
                'pf': round(nem1_stats.pf, 2),
                'trades': nem1_stats.trades,
                'state': nem1_state.value
            },
            'nem2_stats': {
                'ghi': round(nem2_stats.ghi, 1),
                'pf': round(nem2_stats.pf, 2),
                'trades': nem2_stats.trades,
                'state': nem2_state.value
            },
            'last_update': datetime.now().isoformat()
        })
        
        # Determinar régimen
        if nem1_state == NEMState.HEAVY and nem2_state == NEMState.HEAVY:
            regime = RegimeState.SYMMETRIC_BOTH_VALID
        elif best_nem == 'NEM1':
            regime = RegimeState.ASYMMETRIC_NEM1_HEAVY
        else:
            regime = RegimeState.ASYMMETRIC_NEM2_HEAVY
        
        self.symbol_states[symbol_upper]['regime_status'] = regime.value
        
        logger.info(f"[GATEKEEPER V2] {symbol_upper}: NEM1={nem1_state.value}(GHI={nem1_stats.ghi:.0f}) | NEM2={nem2_state.value}(GHI={nem2_stats.ghi:.0f}) | Best: {best_nem}")
        
        self._save_states()
        return regime
    
    def force_evaluate_all(self, nem1_trades: list, nem2_trades: list):
        """Fuerza evaluación de todos los símbolos"""
        symbols = set()
        
        for t in nem1_trades + nem2_trades:
            sym = t.get('symbol', '').upper()
            if sym:
                symbols.add(sym)
        
        for sym in symbols:
            self.evaluate_and_transition(sym, nem1_trades, nem2_trades)
        
        logger.info(f"[GATEKEEPER V2] Force evaluation complete: {len(symbols)} symbols")


# Alias para compatibilidad
DualGatekeeper = DualGatekeeperV2