"""
Logging system for the trading agent.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any


class TradingLogger:
    """Custom logger for trading operations."""
    
    def __init__(self, name: str = "TradingAgent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
        
        # Create logs directory
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Console handler with color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        # File handler for detailed logs
        log_file = log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        # Operations log file (Migrate to .jsonl for robustness)
        self.operations_file_json = log_dir / "operations.json"
        self.operations_file = log_dir / "operations.jsonl"
        
        # Handle legacy corruption/migration
        if self.operations_file_json.exists():
            try:
                # Rename potentially corrupted file if it's too big or causes issues
                if self.operations_file_json.stat().st_size > 1024 * 1024: # > 1MB
                    backup_name = f"operations_legacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.bak"
                    self.operations_file_json.rename(log_dir / backup_name)
                    self.info(f"Legacy operations.json was too large and was backed up to {backup_name}")
            except Exception:
                pass

    def log_operation(self, operation_type: str, data: Dict[str, Any]):
        """Log a trading operation to JSONL file (append only)."""
        try:
            operation = {
                "timestamp": datetime.now().isoformat(),
                "type": operation_type,
                "data": data
            }
            # Append as a single line (JSONL format)
            with open(self.operations_file, 'a') as f:
                f.write(json.dumps(operation) + "\n")
        
        except Exception as e:
            self.logger.error(f"Failed to log operation: {e}")
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def success(self, message: str):
        """Log success message."""
        self.logger.info(f"✅ {message}")
    
    def progress(self, step: str, total_steps: int = None, current_step: int = None):
        """Log progress message."""
        if total_steps and current_step:
            self.logger.info(f"[{current_step}/{total_steps}] {step}")
        else:
            self.logger.info(f"⏳ {step}")


# Global logger instance
logger = TradingLogger()
