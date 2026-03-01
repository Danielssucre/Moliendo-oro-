"""
Risk management calculations for position sizing and stop loss/take profit.
"""
from typing import Dict, Tuple
from dataclasses import dataclass

from ..utils.config import config
from ..utils.logger import logger


@dataclass
class RiskParameters:
    """Risk management parameters for a trade."""
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_pips: float
    reward_pips: float
    risk_reward_ratio: float
    position_size: float
    risk_amount: float


class RiskCalculator:
    """Calculate risk management parameters."""
    
    def __init__(self, capital: float = None):
        """
        Initialize risk calculator.
        
        Args:
            capital: Trading capital (uses config default if not provided)
        """
        self.capital = capital or config.get_trading_config("risk_management.default_capital")
        self.max_risk_percent = config.get_trading_config("risk_management.max_risk_per_trade_percent")
        self.min_rr_ratio = config.get_trading_config("risk_management.min_risk_reward_ratio")
        self.atr_multiplier = config.get_trading_config("risk_management.atr_multiplier_stop_loss")

    def set_capital(self, capital: float) -> None:
        """Update capital for calculations."""
        self.capital = capital

    def set_risk_percent(self, percent: float) -> None:
        """Update risk percentage for calculations."""
        self.max_risk_percent = percent
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr: float
    ) -> float:
        """
        Calculate stop loss based on ATR.
        
        Args:
            entry_price: Entry price
            direction: "buy" or "sell"
            atr: Current ATR value
        
        Returns:
            Stop loss price
        """
        stop_distance = atr * self.atr_multiplier
        
        if direction == "buy":
            stop_loss = entry_price - stop_distance
        else:  # sell
            stop_loss = entry_price + stop_distance
        
        return round(stop_loss, 5)
    
    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
        rr_ratio_base: float = None,
        atr: float = None
    ) -> float:
        """
        Calculate take profit based on risk-reward ratio and volatility.
        """
        rr_ratio = rr_ratio_base or self.min_rr_ratio
        
        # Calculate risk distance
        risk_distance = abs(entry_price - stop_loss)
        
        # Dynamic Multiplier based on ATR (Institutional standard)
        # In higher volatility, we aim for larger RR ratios
        volatility_boost = 1.0
        if atr:
            # Simple heuristic: if ATR is high relative to avg, boost TP targets
            # This is a simplified version of the "Dynamic Exit Algorithm"
            volatility_boost = min(1.5, max(0.8, (atr * 10 / entry_price) * 100)) # Clamped boost
            logger.debug(f"Volatility Exit Boost: {volatility_boost:.2f}x")
            
        reward_distance = risk_distance * rr_ratio * volatility_boost
        
        if direction == "buy":
            take_profit = entry_price + reward_distance
        else:  # sell
            take_profit = entry_price - reward_distance
        
        return round(take_profit, 5)
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        pair: str = "EURUSD",
        symbol_info: object = None
    ) -> float:
        """
        Calculate position size based on institutional risk formulas.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            pair: Currency pair
            symbol_info: MT5 symbol info object (optional, for precise tick-value math)
        
        Returns:
            Position size in lots
        """
        risk_amount = self.capital * (self.max_risk_percent / 100)
        sl_diff = abs(entry_price - stop_loss)
        
        if sl_diff == 0: return 0.0
        
        # UNIVERSAL FORMULA (Phase 3/4 Implementation)
        if symbol_info:
            tick_size = symbol_info.trade_tick_size
            tick_value = symbol_info.trade_tick_value
            if tick_size > 0 and tick_value > 0:
                lots = risk_amount / ((sl_diff / tick_size) * tick_value)
                return round(lots, 2)
        
        # Legacy/Fallback (only if MT5 info is missing)
        pip_size = 0.01 if "JPY" in pair else 0.0001
        risk_pips = sl_diff / pip_size
        pip_value_per_lot = 10.0 # XXX/USD standard
        
        position_size = risk_amount / (risk_pips * pip_value_per_lot)
        return round(position_size, 2)
    
    def calculate_full_risk_params(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        pair: str = "EURUSD",
        rr_ratio: float = None,
        symbol_info: object = None
    ) -> RiskParameters:
        """
        Calculate all risk parameters.
        
        Args:
            entry_price: Entry price
            direction: "buy" or "sell"
            atr: Current ATR
            pair: Currency pair
            rr_ratio: Risk-reward ratio
        
        Returns:
            RiskParameters object
        """
        logger.progress("Calculating risk management parameters")
        
        # Calculate stop loss
        stop_loss = self.calculate_stop_loss(entry_price, direction, atr)
        
        # Calculate take profit (Dynamic ATR-based targets)
        take_profit = self.calculate_take_profit(
            entry_price, stop_loss, direction, rr_ratio, atr=atr
        )
        
        # Calculate pips
        pip_size = 0.01 if "JPY" in pair else 0.0001
        risk_pips = abs(entry_price - stop_loss) / pip_size
        reward_pips = abs(take_profit - entry_price) / pip_size
        
        # Calculate actual risk-reward ratio
        actual_rr = reward_pips / risk_pips if risk_pips > 0 else 0
        
        # Calculate position size
        position_size = self.calculate_position_size(entry_price, stop_loss, pair, symbol_info=symbol_info)
        
        # Calculate risk amount
        risk_amount = self.capital * (self.max_risk_percent / 100)
        
        logger.success(
            f"Risk params: SL={stop_loss:.5f} ({risk_pips:.1f} pips), "
            f"TP={take_profit:.5f} ({reward_pips:.1f} pips), "
            f"RR=1:{actual_rr:.2f}"
        )
        
        return RiskParameters(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_pips=risk_pips,
            reward_pips=reward_pips,
            risk_reward_ratio=actual_rr,
            position_size=position_size,
            risk_amount=risk_amount
        )
    
    def validate_risk_params(self, risk_params: RiskParameters) -> Tuple[bool, str]:
        """
        Validate risk parameters meet requirements.
        
        Args:
            risk_params: Risk parameters to validate
        
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check minimum risk-reward ratio
        if risk_params.risk_reward_ratio < self.min_rr_ratio:
            return False, f"Risk-reward ratio {risk_params.risk_reward_ratio:.2f} below minimum {self.min_rr_ratio}"
        
        # Check position size is reasonable
        if risk_params.position_size <= 0:
            return False, "Position size is zero or negative"
        
        if risk_params.position_size > 10:  # Max 10 lots
            return False, f"Position size {risk_params.position_size} too large"
        
        # Check risk amount
        max_risk = self.capital * (self.max_risk_percent / 100)
        if risk_params.risk_amount > max_risk:
            return False, f"Risk amount ${risk_params.risk_amount:.2f} exceeds maximum ${max_risk:.2f}"
        
        return True, "Risk parameters valid"
