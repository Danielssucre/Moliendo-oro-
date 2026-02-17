"""
Trade Tracker - Seguimiento automático de operaciones y estadísticas.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from ..utils.logger import logger


@dataclass
class Trade:
    """Representa una operación de trading."""
    id: str
    pair: str
    direction: str  # "BUY" o "SELL"
    entry_price: float
    take_profit: float
    stop_loss: float
    lot_size: float
    entry_time: str
    status: str  # "OPEN", "TP_HIT", "SL_HIT", "CLOSED_MANUAL"
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    profit_loss: Optional[float] = None
    pips: Optional[float] = None
    # Forensics (MAE/MFE)
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion
    time_to_mae: Optional[str] = None
    time_to_mfe: Optional[str] = None
    exit_reason: Optional[str] = None  # "TP", "SL", "MANUAL", "TIME_STOP", "PARTIAL"
    partial_hit: bool = False


class TradeTracker:
    """Rastrea y monitorea operaciones de trading."""
    
    def __init__(self, data_file: str = "data/trades.json"):
        self.data_file = Path(data_file)
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Carga datos de operaciones."""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        
        # Estructura por defecto
        default_data = {
            "open_trades": [],
            "closed_trades": [],
            "statistics": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "current_streak": 0,
                "best_trade": 0.0,
                "worst_trade": 0.0
            }
        }
        
        # Crear directorio si no existe
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Guardar datos por defecto
        with open(self.data_file, 'w') as f:
            json.dump(default_data, f, indent=2)
        return default_data
    
    def _save_data(self) -> None:
        """Guarda datos de operaciones."""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def register_trade(
        self,
        pair: str,
        direction: str,
        entry_price: float,
        take_profit: float,
        stop_loss: float,
        lot_size: float
    ) -> str:
        """
        Registra una nueva operación.
        
        Returns:
            ID de la operación
        """
        trade_id = f"{pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        trade = Trade(
            id=trade_id,
            pair=pair,
            direction=direction,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            lot_size=lot_size,
            entry_time=datetime.now().isoformat(),
            status="OPEN"
        )
        
        self.data["open_trades"].append(asdict(trade))
        self._save_data()
        
        logger.success(f"✅ Operación registrada: {trade_id}")
        logger.info(f"   {direction} {pair} @ {entry_price}")
        logger.info(f"   TP: {take_profit} | SL: {stop_loss} | Lote: {lot_size}")
        
        return trade_id
    
    def check_trades(self, pair: str, current_price: float) -> List[Dict[str, Any]]:
        """
        Verifica si alguna operación alcanzó TP o SL.
        
        Args:
            pair: Par de divisas
            current_price: Precio actual
        
        Returns:
            Lista de operaciones que fueron cerradas
        """
        closed_trades = []
        
        for trade in self.data["open_trades"][:]:  # Copiar lista para modificar
            if trade["pair"] != pair:
                continue
            
            direction = trade["direction"]
            tp = trade["take_profit"]
            sl = trade["stop_loss"]
            
            # Verificar si alcanzó TP o SL
            hit_tp = False
            hit_sl = False
            
            if direction == "BUY":
                hit_tp = current_price >= tp
                hit_sl = current_price <= sl
            else:  # SELL
                hit_tp = current_price <= tp
                hit_sl = current_price >= sl
            
            # --- Actualización de MAE/MFE ---
            # MAE: Mayor pérdida flotante
            # MFE: Mayor ganancia flotante
            if direction == "BUY":
                current_pips = (current_price - trade["entry_price"]) * 10000
            else:
                current_pips = (trade["entry_price"] - current_price) * 10000
            
            # Inicializar mae/mfe si no existen en el diccionario (para trades legacy)
            if "mae" not in trade: trade["mae"] = 0.0
            if "mfe" not in trade: trade["mfe"] = 0.0

            if current_pips > trade["mfe"]:
                trade["mfe"] = round(current_pips, 1)
                trade["time_to_mfe"] = datetime.now().isoformat()
            
            if current_pips < trade["mae"]:
                trade["mae"] = round(current_pips, 1)
                trade["time_to_mae"] = datetime.now().isoformat()
            # -------------------------------

            # --- Lógica de Cierre Parcial (Daniel's Recommendation) ---
            if not trade.get("partial_hit", False):
                entry_p = trade["entry_price"]
                sl_p = trade["sl"]
                risk_pips = abs(entry_p - sl_p) * 10000
                
                # Calcular pips actuales para comparativa
                if direction == "BUY":
                    current_pips_p = (current_price - entry_p) * 10000
                else:
                    current_pips_p = (entry_p - current_price) * 10000

                if current_pips_p >= (risk_pips * 1.3):
                    trade["partial_hit"] = True
                    trade["sl"] = entry_p # Mover a Break-Even
                    trade["exit_reason"] = "PARTIAL"
                    print(f"🎯 PARTIAL EXIT SIGNAL: {trade['symbol']} hit 1.3R. Local SL moved to BE.")
            # ---------------------------------------------------------

            if hit_tp or hit_sl:
                # Cerrar operación
                exit_price = tp if hit_tp else sl
                status = "TP_HIT" if hit_tp else "SL_HIT"
                
                # Calcular P&L
                pips = self._calculate_pips(
                    trade["entry_price"],
                    exit_price,
                    direction
                )
                profit_loss = self._calculate_profit_loss(
                    pips,
                    trade["lot_size"]
                )
                
                # Actualizar operación
                trade["status"] = status
                trade["exit_price"] = exit_price
                trade["exit_time"] = datetime.now().isoformat()
                trade["pips"] = pips
                trade["profit_loss"] = profit_loss
                trade["exit_reason"] = "TP" if hit_tp else "SL"
                
                # Mover a cerradas
                self.data["open_trades"].remove(trade)
                self.data["closed_trades"].append(trade)
                closed_trades.append(trade)
                
                # Actualizar estadísticas
                self._update_statistics(trade)
                
                # Log
                result = "✅ GANANCIA" if hit_tp else "❌ PÉRDIDA"
                logger.info(f"{result}: {trade['id']}")
                logger.info(f"   Salida: {exit_price} ({status})")
                logger.info(f"   P&L: ${profit_loss:+.2f} ({pips:+.1f} pips)")
        
        if closed_trades:
            self._save_data()
        
        return closed_trades
    
    def _calculate_pips(
        self,
        entry: float,
        exit: float,
        direction: str
    ) -> float:
        """Calcula pips ganados/perdidos."""
        if direction == "BUY":
            pips = (exit - entry) * 10000
        else:  # SELL
            pips = (entry - exit) * 10000
        
        return round(pips, 1)
    
    def _calculate_profit_loss(self, pips: float, lot_size: float) -> float:
        """Calcula ganancia/pérdida en dinero."""
        # Asumiendo $10 por pip por lote estándar
        pip_value = 10.0
        profit_loss = pips * lot_size * pip_value
        return round(profit_loss, 2)
    
    def _update_statistics(self, trade: Dict[str, Any]) -> None:
        """Actualiza estadísticas después de cerrar operación."""
        stats = self.data["statistics"]
        
        stats["total_trades"] += 1
        
        pl = trade["profit_loss"]
        
        if pl > 0:
            stats["winning_trades"] += 1
            stats["total_profit"] += pl
            stats["current_streak"] = max(0, stats["current_streak"]) + 1
        else:
            stats["losing_trades"] += 1
            stats["total_loss"] += abs(pl)
            stats["current_streak"] = min(0, stats["current_streak"]) - 1
        
        # Mejor y peor operación
        if pl > stats["best_trade"]:
            stats["best_trade"] = pl
        if pl < stats["worst_trade"]:
            stats["worst_trade"] = pl
    
    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Obtiene operaciones abiertas."""
        return self.data["open_trades"]
    
    def has_open_trade(self, pair: str) -> bool:
        """Verifica si ya hay una operación abierta en el par."""
        return any(t["pair"] == pair for t in self.data["open_trades"])

    def check_management(self, pair: str, current_price: float) -> List[str]:
        """
        Genera recomendaciones de gestión para operaciones abiertas.
        """
        advices = []
        for trade in self.data["open_trades"]:
            if trade["pair"] != pair:
                continue
            
            entry = trade["entry_price"]
            sl = trade["stop_loss"]
            direction = trade["direction"]
            risk_pips = abs(entry - sl)
            
            # Si el SL ya es igual al precio de entrada (o mejor), ya está en BE
            is_at_be = False
            if direction == "BUY":
                is_at_be = sl >= entry - (risk_pips * 0.05)
            else:
                is_at_be = sl <= entry + (risk_pips * 0.05)

            # Lógica de Break Even (cuando el precio llega a 1:1 de beneficio)
            if direction == "BUY":
                profit_reached = current_price - entry
                if profit_reached >= (entry - sl) and not is_at_be:
                    advices.append(f"🛡️ [BREAK EVEN] {pair}: Sugerido mover SL a {entry:.5f} (1:1 alcanzado)")
            else: # SELL
                profit_reached = entry - current_price
                if profit_reached >= (sl - entry) and not is_at_be:
                    advices.append(f"🛡️ [BREAK EVEN] {pair}: Sugerido mover SL a {entry:.5f} (1:1 alcanzado)")
                    
        return advices
    
    def get_closed_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtiene últimas operaciones cerradas."""
        return self.data["closed_trades"][-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de rendimiento."""
        return self.data["statistics"]
    
    def close_trade_manually(self, trade_id: str, exit_price: float) -> bool:
        """Cierra una operación manualmente."""
        for trade in self.data["open_trades"]:
            if trade["id"] == trade_id:
                # Calcular P&L
                pips = self._calculate_pips(
                    trade["entry_price"],
                    exit_price,
                    trade["direction"]
                )
                profit_loss = self._calculate_profit_loss(pips, trade["lot_size"])
                
                # Actualizar
                trade["status"] = "CLOSED_MANUAL"
                trade["exit_price"] = exit_price
                trade["exit_time"] = datetime.now().isoformat()
                trade["pips"] = pips
                trade["profit_loss"] = profit_loss
                trade["exit_reason"] = "MANUAL"
                
                # Mover a cerradas
                self.data["open_trades"].remove(trade)
                self.data["closed_trades"].append(trade)
                
                # Actualizar estadísticas
                self._update_statistics(trade)
                
                self._save_data()
                logger.success(f"✅ Operación cerrada manualmente: {trade_id}")
                return True
        
        logger.warning(f"❌ Operación no encontrada: {trade_id}")
        return False
