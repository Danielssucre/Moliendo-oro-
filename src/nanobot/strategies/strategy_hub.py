"""
STRATEGY HUB: Router Unificado de Estrategias
==============================================
Centraliza el routing entre ForexInfantry y CryptoLab según el tipo de activo.

MODO NEME/ANTITHESIS: El sistema opera SOLO con señales inversas.
- ForexInfantry → NEMESIS (invierte señal base)
- CryptoLab → ANTITHESIS (invierte señal base)
- MegaGridV2 → Solo side=-1

Uso:
    hub = StrategyHub()
    result = hub.get_signal(symbol, df)  # 默认 NEME/ANTITHESIS
    
    if result.signal != 0:
        pool = hub.generate_mega_grid_pool(symbol, entry_price, atr, result.signal, result.strategy)
"""

import logging
import json
import os
from typing import Tuple, Dict, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("Nanobot.StrategyHub")

CRYPTO_SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD", "BTC", "ETH", "SOL"]

FOREX_METALS_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",
    "GBPJPY", "EURJPY", "EURGBP", "AUDJPY", "CHFJPY", "CADJPY",
    "EURAUD", "GBPAUD", "EURNZD", "NZDJPY", "USDCHF", "GBPCAD",
    "XAUUSD", "XAGUSD",
]

AFFINITY_MAP_PATH = "data/research/affinity_map.json"


class AssetClass(Enum):
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    METALS = "METALS"
    UNKNOWN = "UNKNOWN"


@dataclass
class SignalResult:
    signal: int
    strategy: str
    asset_class: AssetClass
    metadata: Dict
    recommended_rr: float
    source: str


class StrategyHub:
    """
    Router unificado NEME/ANTITHESIS.
    
    El sistema opera EXCLUSIVAMENTE con señales inversas:
    - ForexInfantry para Forex y Metales → NEMESIS
    - CryptoLab para BTCUSD, ETHUSD, SOLUSD → ANTITHESIS
    - MegaGridV2 para ejecución fraccional (solo side=-1)
    """
    
    DEFAULT_MODE = "ANTITHESIS"
    
    def __init__(self):
        self._init_engines()
        
    def _init_engines(self):
        """Lazy initialization de los motores de estrategia"""
        self._forex_infantry = None
        self._crypto_lab = None
        
    @property
    def forex_infantry(self):
        if self._forex_infantry is None:
            from src.nanobot.strategies.forex_infantry import ForexInfantry
            self._forex_infantry = ForexInfantry()
            logger.info("⚔️ ForexInfantry NEMESIS engine loaded")
        return self._forex_infantry
    
    @property
    def crypto_lab(self):
        if self._crypto_lab is None:
            from src.nanobot.strategies.crypto_lab import CryptoLab
            self._crypto_lab = CryptoLab()
            logger.info("🧪 CryptoLab ANTITHESIS engine loaded")
        return self._crypto_lab
    
    def get_asset_class(self, symbol: str) -> AssetClass:
        """Clasifica el símbolo en su asset class"""
        sym = symbol.upper()
        
        if any(c in sym for c in CRYPTO_SYMBOLS):
            return AssetClass.CRYPTO
        elif "XAU" in sym or "XAG" in sym:
            return AssetClass.METALS
        elif any(f in sym for f in ["EUR", "GBP", "USD", "AUD", "NZD", "CAD", "CHF", "JPY", "NOK", "SEK"]):
            return AssetClass.FOREX
        else:
            return AssetClass.UNKNOWN
    
    def is_crypto(self, symbol: str) -> bool:
        """Check if symbol is crypto"""
        return self.get_asset_class(symbol) == AssetClass.CRYPTO
    
    def is_forex_or_metal(self, symbol: str) -> bool:
        """Check if symbol is forex or metals"""
        ac = self.get_asset_class(symbol)
        return ac in [AssetClass.FOREX, AssetClass.METALS]
    
    def get_signal(
        self, 
        symbol: str, 
        df, 
        mode: str = None
    ) -> SignalResult:
        """
        Obtiene señal NEME/ANTITHESIS para el símbolo dado.
        
        MODO NEME (default):
        - Forex: NEMESIS (invierte señal base)
        - Crypto: ANTITHESIS (invierte señal base)
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
            df: DataFrame con datos OHLCV e indicadores
            mode: "ANTITHESIS" (default) o None para usar modo NEME
            
        Returns:
            SignalResult con señal invertida, strategy, metadata
        """
        if df is None or len(df) < 20:
            return SignalResult(
                signal=0,
                strategy="NONE",
                asset_class=self.get_asset_class(symbol),
                metadata={},
                recommended_rr=2.0,
                source="HUB"
            )
        
        asset_class = self.get_asset_class(symbol)
        
        if asset_class == AssetClass.CRYPTO:
            return self._get_crypto_signal(symbol, df, mode=mode)
        elif asset_class in [AssetClass.FOREX, AssetClass.METALS]:
            return self._get_forex_signal(symbol, df)
        else:
            return SignalResult(
                signal=0,
                strategy="NONE",
                asset_class=asset_class,
                metadata={"error": "Unknown asset class"},
                recommended_rr=2.0,
                source="HUB"
            )
    
    def _get_crypto_signal(self, symbol: str, df, mode: str = None) -> SignalResult:
        """Obtiene señal según modo (THESIS/ANTITHESIS) usando CryptoLab"""
        try:
            # Convertir nombres de Dashboard (N1, N2) a modos de CryptoLab
            clab_mode = "ANTITHESIS" # Default histórico
            if mode == "N1": clab_mode = "THESIS"
            elif mode == "N2": clab_mode = "ANTITHESIS"
            elif mode == "THESIS": clab_mode = "THESIS"
            
            sig, strat, meta = self.crypto_lab.get_signal_with_mode(df, mode=clab_mode)
            
            rr = self.crypto_lab.get_recommended_rr(df)
            
            return SignalResult(
                signal=sig,
                strategy=f"NEME_{strat}" if sig != 0 else "NONE",
                asset_class=AssetClass.CRYPTO,
                metadata=meta,
                recommended_rr=rr,
                source="CRYPTO_LAB_ANTITHESIS"
            )
        except Exception as e:
            logger.error(f"Error in CryptoLab ANTITHESIS for {symbol}: {e}")
            return SignalResult(
                signal=0,
                strategy="ERROR",
                asset_class=AssetClass.CRYPTO,
                metadata={"error": str(e)},
                recommended_rr=3.0,
                source="CRYPTO_LAB_ANTITHESIS"
            )
    
    def _get_affinity_reco(self, symbol: str) -> str:
        """Consulta el Mapa de Afinidad para obtener la recomendación (NEM1/NEM2)"""
        if not os.path.exists(AFFINITY_MAP_PATH):
            return "NEM2 (Antith)" # Default conservador
        
        try:
            with open(AFFINITY_MAP_PATH, "r") as f:
                data = json.load(f)
                return data.get(symbol, {}).get("reco", "NEM2 (Antith)")
        except Exception as e:
            logger.warning(f"⚠️ Error leyendo Mapa de Afinidad para {symbol}: {e}")
            return "NEM2 (Antith)"

    def _get_forex_signal(self, symbol: str, df) -> SignalResult:
        """Obtiene señal NEMESIS o THESIS según la inteligencia del Mapa de Afinidad"""
        try:
            # 1. Obtener señal NEME (Invertida) por defecto
            sig, strat = self.forex_infantry.get_nemesis_signal_with_strategy(df)
            
            # 2. Consultar Inteligencia de Afinidad
            reco = self._get_affinity_reco(symbol)
            mode = "NEMESIS"
            
            # [Opción C] Si la IA detecta que la tendencia (NEM1) funciona mejor, revertimos la inversión.
            if sig != 0 and "NEM1" in reco:
                sig = -sig # Revertimos la inversión (doble inversión = original)
                strat = strat.replace("NEME_", "INTEL_")
                mode = "THESIS (IA OVERRIDE)"
                logger.info(f"🧠 [INTEL-ALPHA] {symbol} detectado como NEM1 (Trend). Revertiendo NEME a {strat}")

            return SignalResult(
                signal=sig,
                strategy=strat,
                asset_class=self.get_asset_class(symbol),
                metadata={"mode": mode, "intel_reco": reco},
                recommended_rr=1.5,
                source="FOREX_INFANTRY_SMART_HUB"
            )
        except Exception as e:
            logger.error(f"Error in ForexInfantry NEMESIS for {symbol}: {e}")
            return SignalResult(
                signal=0,
                strategy="ERROR",
                asset_class=self.get_asset_class(symbol),
                metadata={"error": str(e)},
                recommended_rr=1.5,
                source="FOREX_INFANTRY_NEMESIS"
            )
    
    def generate_mega_grid_pool(
        self,
        symbol: str,
        entry_price: float,
        atr: float,
        direction: int,
        strategy_tag: str,
        total_risk: float = None,
        is_scout: bool = False
    ) -> List[Dict]:
        """
        Genera pool de niveles para MegaGridV2 NEME (solo side=-1).
        
        Crypto usa RRs más altos (3-6) vs Forex (1.0-2.2)
        Todos los niveles tienen side=-1 (antithesis)
        """
        from src.nanobot.strategies.mega_grid_v2 import MegaGridV2
        
        if is_crypto(symbol):
            rr_levels = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
            source_prefix = "CLAB"
        else:
            rr_levels = [1.0, 1.1, 1.2, 1.4, 1.6, 1.9, 2.2]
            source_prefix = "NEME"
        
        config = {
            "enabled": True,
            "num_levels": 7,
            "rr_levels": rr_levels,
            "distance_multiplier": 0.0,
            "risk_distribution": [
                0.00055, 0.00045, 0.00040, 0.00035,
                0.00030, 0.00025, 0.00020
            ],
            "sl_multiplier": 2.0,
            "comment_prefix": f"MEGA_V2_{source_prefix}_",
        }
        
        mega_grid = MegaGridV2(config)
        pool = mega_grid.generate_pool(
            symbol=symbol,
            entry_price=entry_price,
            atr=atr,
            direction=-1,
            source_tag=f"{source_prefix}_{strategy_tag[:10]}",
            total_risk=total_risk,
            is_scout=is_scout
        )
        
        return pool
    
    def get_execution_params(self, symbol: str, df) -> Dict:
        """
        Obtiene parámetros de ejecución NEME según asset class.
        """
        asset_class = self.get_asset_class(symbol)
        
        if asset_class == AssetClass.CRYPTO:
            regime = self.crypto_lab._get_regime(df) if hasattr(self.crypto_lab, '_get_regime') else "RANGE"
            return {
                "sl_mult": 2.0,
                "tp_mult": 6.0 if regime == "VOLATILE" else 4.0,
                "max_risk_pct": 0.0025,
                "timeframes": {"short": "M15", "medium": "H1", "long": "H4"},
                "min_adx": 18,
                "max_spread_pips": 50,
                "mode": "ANTITHESIS",
            }
        else:
            return {
                "sl_mult": 1.5,
                "tp_mult": 2.25,
                "max_risk_pct": 0.0025,
                "timeframes": {"short": "M15", "medium": "H1", "long": "H4"},
                "min_adx": 18,
                "max_spread_pips": 4.0,
                "mode": "NEMESIS",
            }
    
    def log_signal(self, symbol: str, result: SignalResult, price: float):
        """Log signal NEME for debugging/auditing"""
        direction = "LONG" if result.signal == 1 else "SHORT" if result.signal == -1 else "NONE"
        logger.info(
            f"📡 [NEME] {symbol} | {direction} | {result.strategy} | "
            f"RR:{result.recommended_rr} | Source:{result.source} @ {price:.5f}"
        )