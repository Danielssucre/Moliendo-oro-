"""
Shadow Trading System - DEPRECATED
==================================
MegaGridV2 es ahora el único sistema de ejecución.
Este módulo se mantiene para backtesting histórico únicamente.

NUEVO FLUJO:
    StrategyHub -> MegaGridV2 -> MT5
"""

import warnings

from .escalator import MultiTimeframeEscalator
from .shadow_logger import ShadowLogger

__all__ = [
    "MultiTimeframeEscalator",
    "ShadowLogger",
]

DEPRECATED = [
    "ShadowEngine",
    "ShadowUniverse",
    "NemesisDualIntegrator",
    "get_shadow_integrator",
]