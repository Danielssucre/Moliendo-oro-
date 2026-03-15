"""
SKYPIE-ENEL ⚡: Crypto Strategy Module
======================================
Specialized in BTCUSD, ETHUSD, and SOLUSD.
Powered by MCA (Multiple Correspondence Analysis) clustering.
Target: High-Probability "Gold Clusters" (Win Rate > 70%).
"""

import logging

logger = logging.getLogger("Nanobot.SkypieEnel")

class SkypieEnel:
    def __init__(self):
        # MCA discovered "Gold Cluster" Parameters
        self.min_adx = 20.0
        self.max_adx = 35.0
        self.max_vol = 5.0      # Death Zone Threshold
        self.min_ai_prob = 0.65 # Confidence Threshold
        self.min_rsi = 40.0
        self.max_rsi = 60.0
        
        self.strategy_name = "SkypieEnel_V1"

    def evaluate(self, symbol, indicators, ml_prob):
        """
        Evaluates specialized crypto filters.
        Returns: bool (True if all Enel conditions are met)
        """
        adx = indicators.get('adx', 0)
        vol = indicators.get('vol', 0)
        rsi = indicators.get('rsi', 50)
        
        # 1. Death Zone Check (The Absolute Filter)
        if vol > self.max_vol:
            # logger.info(f"⚡ [Skypie-Enel] REJECTED: High Volatility Trap (Vol={vol:.1f})")
            return False
            
        # 2. Gold Cluster: Trend Stability
        if not (self.min_adx <= adx <= self.max_adx):
            # logger.info(f"⚡ [Skypie-Enel] REJECTED: Out of Gold ADX Zone (ADX={adx:.1f})")
            return False
            
        # 3. RSI Neutrality (Avoid Over-extension)
        if not (self.min_rsi <= rsi <= self.max_rsi):
            # logger.info(f"⚡ [Skypie-Enel] REJECTED: RSI Over-extended (RSI={rsi:.1f})")
            return False
            
        # 4. AI Elite Confirmation
        if ml_prob < self.min_ai_prob:
            # logger.info(f"⚡ [Skypie-Enel] REJECTED: AI Confidence too low (Prob={ml_prob:.2f})")
            return False
            
        logger.info(f"⚡⚡⚡ [Skypie-Enel] GOLD CLUSTER DETECTED for {symbol}! (WR Hist > 70%)")
        return True

    def get_risk_multiplier(self, ml_prob):
        """
        Elite Strategy gets 1.0 weight (Standard for 1% risk).
        """
        if ml_prob >= 0.85:
            return 1.2 # Bonus for Elite setups
        return 1.0
