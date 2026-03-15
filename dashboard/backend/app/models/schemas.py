from pydantic import BaseModel
from typing import Optional, List, Dict

class MT5Credentials(BaseModel):
    account: int
    password: str
    server: str

class BotConfig(BaseModel):
    risk_per_trade: float = 0.004
    max_exposure_pct: float = 0.05
    terra_mode: bool = True  # True = Mega Grid ON, False = Off
    mt5: Optional[MT5Credentials] = None

class BotStatus(BaseModel):
    is_running: bool
    pid: Optional[int] = None
    uptime: Optional[str] = None
    account_status: str
    telegram_status: str
    mega_grid_active: bool
    polimata_retrains: int = 0
    last_retrain: Optional[str] = None

class MarketSignal(BaseModel):
    time: str
    symbol: str
    type: str
    strategy: str
    source: str

class TradeStats(BaseModel):
    daily_pnl: float
    total_pnl: float
    equity: float
    balance: float
    active_trades: int
    polimata_retrains: int
    margin: float
    free_margin: float
    margin_level: float
    is_micro_sizing: bool = False
    risk_label: Optional[str] = None
