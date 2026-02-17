"""
Capital Manager - Gestión dinámica de capital y cálculo de lotes.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from ..utils.logger import logger


class CapitalManager:
    """Gestiona el capital del usuario y calcula tamaños de lote."""
    
    def __init__(self, config_file: str = "data/user_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Carga configuración del usuario."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        
        # Configuración por defecto
        default_config = {
            "capital": 10000.0,
            "risk_percentage": 2.0,
            "currency": "USD",
            "last_updated": datetime.now().isoformat()
        }
        
        # Crear directorio si no existe
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Guardar configuración por defecto
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Guarda configuración."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_capital(self) -> float:
        """Obtiene capital actual."""
        return self.config.get("capital", 10000.0)

    def get_risk_percentage(self) -> float:
        """Obtiene el porcentaje de riesgo actual."""
        return self.config.get("risk_percentage", 2.0)
    
    def update_capital(self, new_capital: float) -> None:
        """
        Actualiza el capital disponible.
        
        Args:
            new_capital: Nuevo monto de capital
        """
        old_capital = self.config.get("capital", 10000.0)
        self.config["capital"] = new_capital
        self.config["last_updated"] = datetime.now().isoformat()
        self._save_config(self.config)
        
        logger.info(f"Capital actualizado: ${old_capital:,.2f} → ${new_capital:,.2f}")

    def update_risk_percentage(self, new_percentage: float) -> None:
        """
        Actualiza el porcentaje de riesgo por operación.
        
        Args:
            new_percentage: Nuevo porcentaje de riesgo
        """
        old_risk = self.config.get("risk_percentage", 2.0)
        self.config["risk_percentage"] = new_percentage
        self.config["last_updated"] = datetime.now().isoformat()
        self._save_config(self.config)
        
        logger.info(f"Riesgo actualizado: {old_risk}% → {new_percentage}%")
    
    def get_risk_amount(self) -> float:
        """Calcula el monto de riesgo por operación."""
        return self.get_capital() * (self.get_risk_percentage() / 100)
    
    def calculate_lot_size(
        self,
        pair: str,
        stop_loss_pips: float,
        pip_value: float = 10.0
    ) -> float:
        """
        Calcula el tamaño del lote basado en el riesgo.
        
        Args:
            pair: Par de divisas
            stop_loss_pips: Distancia del stop loss en pips
            pip_value: Valor de 1 pip para 1 lote estándar (default: $10 para pares mayores)
        
        Returns:
            Tamaño del lote
        """
        risk_amount = self.get_risk_amount()
        
        # Evitar división por cero
        if stop_loss_pips <= 0:
            logger.warning("Stop loss debe ser mayor a 0 pips")
            return 0.01
        
        # Fórmula: Lote = Riesgo / (SL en pips × Valor por pip)
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Redondear a 2 decimales (mini lotes)
        lot_size = round(lot_size, 2)
        
        # Mínimo 0.01 lotes
        lot_size = max(0.01, lot_size)
        
        logger.info(
            f"Cálculo de lote para {pair}: "
            f"Riesgo ${risk_amount:.2f} / ({stop_loss_pips} pips × ${pip_value}) = {lot_size} lotes"
        )
        
        return lot_size
    
    def update_capital_after_trade(self, profit_loss: float) -> float:
        """
        Actualiza el capital después de una operación.
        
        Args:
            profit_loss: Ganancia o pérdida de la operación
        
        Returns:
            Nuevo capital
        """
        new_capital = self.config["capital"] + profit_loss
        self.update_capital(new_capital)
        return new_capital
    
    def get_config_summary(self) -> str:
        """Obtiene resumen de configuración."""
        capital = self.config["capital"]
        risk_pct = self.config["risk_percentage"]
        risk_amount = self.get_risk_amount()
        
        return (
            f"📊 Configuración de Capital:\n"
            f"   Capital: ${capital:,.2f}\n"
            f"   Riesgo por operación: {risk_pct}% (${risk_amount:,.2f})\n"
            f"   Última actualización: {self.config['last_updated'][:10]}"
        )
