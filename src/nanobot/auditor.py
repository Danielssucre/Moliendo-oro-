import json
import os
from datetime import datetime, timezone

class ForensicAuditor:
    """
    HIVE FORENSIC AUDITOR 🏛️
    Caja Negra para auditoría de equidad, reconocimiento de errores y aprendizaje continuo.
    """
    def __init__(self, base_path="logs/forensic"):
        self.base_path = base_path
        self.equity_file = "config/equity_timeseries.jsonl"
        self.rejected_file = os.path.join(base_path, "rejected_signals.jsonl")
        self.audit_log = os.path.join(base_path, "system_audit.log")
        
        os.makedirs(base_path, exist_ok=True)
        os.makedirs("config", exist_ok=True)

    def log_equity_snapshot(self, acc_data, active_positions_count, floating_pnl, peak_pnl=0.0):
        """Registra la equidad con contexto de exposición activo y pico de beneficio."""
        try:
            snapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "equity": float(acc_data.equity),
                "balance": float(acc_data.balance),
                "margin_used": float(acc_data.margin),
                "margin_level": float(acc_data.margin_level) if acc_data.margin_level else 0.0,
                "active_pos": active_positions_count,
                "floating_pnl": round(floating_pnl, 2),
                "peak_floating_pnl": round(peak_pnl, 2),
                "dist_from_peak": round(peak_pnl - floating_pnl, 2),
                "risk_usage_pct": round((acc_data.margin / acc_data.equity * 100), 2) if acc_data.equity > 0 else 0
            }
            with open(self.equity_file, "a") as f:
                f.write(json.dumps(snapshot) + "\n")
        except Exception as e:
            self._internal_log(f"Error logging equity: {e}")

    def log_signal_rejection(self, symbol, strategy, signal_type, reason, context=None):
        """Registra por qué una señal fue descartada por el sistema."""
        try:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "strategy": strategy,
                "type": signal_type,
                "reason": reason,
                "context": context or {}
            }
            with open(self.rejected_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self._internal_log(f"Error logging rejection: {e}")

    def log_trade_event(self, event_type, data, peak_r=0.0):
        """Registra eventos críticos de trades incluyendo el MFE (Peak R)."""
        try:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event_type,
                "peak_r": round(peak_r, 2),
                "data": data
            }
            log_path = os.path.join(self.base_path, "trade_events.jsonl")
            with open(log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self._internal_log(f"Error logging trade event: {e}")

    def _internal_log(self, message):
        with open(self.audit_log, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {message}\n")

# Singleton instance
auditor = ForensicAuditor()
