"""
MEGA-GRID FRACCIONAL V2 - NEME EDITION
======================================
Sistema de ejecución piramidal de 7 niveles con distribución de riesgo decreciente.
MODO NEME: Solo opera con side=-1 (ANTITHESIS de señal base).

Configuración Forex:
- RR: [1.0, 1.1, 1.2, 1.4, 1.6, 1.9, 2.2]
- Riesgo total: 0.25%

Configuración Crypto:
- RR: [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
- Riesgo total: 0.25%
"""

import logging

logger = logging.getLogger("Nanobot.MegaGridV2")

MEGA_GRID_CONFIG = {
    "enabled": True,
    "num_levels": 7,
    "rr_levels": [1.0, 1.1, 1.2, 1.4, 1.6, 1.9, 2.2],
    "distance_multiplier": 0.0,
    "risk_distribution": [
        0.00055,
        0.00045,
        0.00040,
        0.00035,
        0.00030,
        0.00025,
        0.00020,
    ],
    "sl_multiplier": 2.0,
    "comment_prefix": "MEGA_V2_NEME_",
    "force_side": -1,
}

CRYPTO_GRID_CONFIG = {
    "enabled": True,
    "num_levels": 7,
    "rr_levels": [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
    "distance_multiplier": 0.0,
    "risk_distribution": [
        0.00055,
        0.00045,
        0.00040,
        0.00035,
        0.00030,
        0.00025,
        0.00020,
    ],
    "sl_multiplier": 2.0,
    "comment_prefix": "MEGA_V2_CLAB_",
    "force_side": -1,
}


class MegaGridV2:
    def __init__(self, config=None):
        self.config = config or MEGA_GRID_CONFIG

    def generate_pool(
        self,
        symbol,
        entry_price,
        atr,
        direction,
        source_tag="NEME",
        total_risk=None,
        is_scout=False,
        nem_type="NEM1",
        reversal_profile=None
    ):
        """
        Genera pool de niveles con soporte para NEM1/NEM2 y Gravity Well Geometry.
        
        Args:
            is_scout: If True, only returns 1 level (L1) with minimum risk.
            nem_type: "NEM1" (original, side=1) o "NEM2" (inverso, side=-1)
            reversal_profile: Datos históricos de reversión para Gravity Well.
        """
        pool = []
        
        # [v7.0.0] CÁLCULO DE POLARIDAD COHERENTE
        # La dirección (direction) proviene limpia y exacta de StrategyHub.
        final_side = direction
        
        if is_scout:
            num_levels = 1
            risk_pct = 0.0001
        else:
            num_levels = self.config["num_levels"]
        
        base_total = sum(self.config["risk_distribution"])
        scale_factor = (total_risk / base_total) if total_risk is not None else 1.0
        
        # [Fase 4] Obtener geometría de la grilla (Lineal o Gravity Well)
        offsets = self.calculate_gravity_well_offsets(symbol, reversal_profile)
        
        for i in range(num_levels):
            rr = self.config["rr_levels"][i]
            
            if not is_scout:
                risk_pct = self.config["risk_distribution"][i] * scale_factor
            
            # Usar offset dinámico del Pozo de Gravedad si está disponible
            offset_atr = offsets[i] if i < len(offsets) else (i * self.config.get("distance_multiplier", 1.0))
            level_entry = entry_price + ((-1 * final_side) * offset_atr * atr)
            
            pool.append({
                "level": i + 1,
                "entry": level_entry,
                "rr": rr,
                "risk_pct": risk_pct,
                "sl_mult": self.config["sl_multiplier"],
                "tag": f"{self.config['comment_prefix']}L{i+1}_{nem_type}_{source_tag}",
                "side": final_side,
                "is_scout": is_scout,
                "nem_type": nem_type
            })
            
        return pool

    def calculate_gravity_well_offsets(self, symbol, reversal_profile):
        """
        [Fase 4: Gravity Well Grid]
        Calcula los multiplicadores de distancia (en ATR) para cada nivel.
        Clusteriza L3-L5 alrededor de la media histórica de reversión.
        """
        num_levels = self.config.get("num_levels", 7)
        dist_mult = self.config.get("distance_multiplier", 1.0)
        
        # Default lineal: [0, 1, 2, 3, 4, 5, 6] * dist_mult
        default_offsets = [i * dist_mult for i in range(num_levels)]
        
        # Directiva del Arquitecto: Mantenido en FALSE hasta validación de datos del Shadow Harvester
        ENABLE_GRAVITY_WELL = False 
        
        if not ENABLE_GRAVITY_WELL or not reversal_profile or symbol not in reversal_profile:
            return default_offsets
            
        samples = reversal_profile[symbol]
        if len(samples) < 10:
            return default_offsets
            
        try:
            import numpy as np
            mu = np.mean(samples)
            
            # Geometría del Pozo de Gravedad (Gravity Well):
            # L1: 0.0 (Entrada)
            # L2: mu * 0.4 (Aproximación)
            # L3: mu * 0.85 (Borde del Pozo)
            # L4: mu (Centro del Pozo - Zona Cero)
            # L5: mu * 1.15 (Salida del Pozo)
            # L6: mu * 1.8 (Red de Seguridad 1)
            # L7: mu * 2.5 (Red de Seguridad Final)
            
            gravity_offsets = [
                0.0,
                mu * 0.4,
                mu * 0.85,
                mu,
                mu * 1.15,
                mu * 1.8,
                mu * 2.5
            ]
            
            # Asegurar progresión estrictamente creciente
            for i in range(1, len(gravity_offsets)):
                if gravity_offsets[i] <= gravity_offsets[i-1]:
                    gravity_offsets[i] = gravity_offsets[i-1] + 0.1
                    
            return gravity_offsets
            
        except Exception as e:
            logger.error(f"❌ Error en Gravity Well Geometry calculation: {e}")
            return default_offsets

    def is_enabled(self):
        return self.config.get("enabled", False)

    @classmethod
    def for_forex(cls, **kwargs):
        """Factory para crear MegaGridV2 configurado para Forex"""
        config = {**MEGA_GRID_CONFIG, **kwargs}
        return cls(config)

    @classmethod
    def for_crypto(cls, **kwargs):
        """Factory para crear MegaGridV2 configurado para Crypto"""
        config = {**CRYPTO_GRID_CONFIG, **kwargs}
        return cls(config)