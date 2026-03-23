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

class BasketLockConfig(BaseModel):
    enabled: bool = True
    threshold: float = 5.0
    last_trigger: Optional[str] = None

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
    active_positions: List[Dict] = []
    trade_history: List[Dict] = []
    last_log_lines: List[str] = []

class MT5Trade(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    price_current: float
    profit: float
    time_open: str

class MT5Stats(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    floating_profit: float
    closed_profit: float
    daily_pnl: float
    active_trades: List[MT5Trade]
    trade_history: List[MT5Trade]
    last_log_lines: List[str]

class BinancePosition(BaseModel):
    symbol: str
    entry: float
    current: float
    qty: float
    pnl_pct: float
    pnl_usdt: float

class BinanceStats(BaseModel):
    account_type: str
    can_trade: bool
    balances: Dict[str, float]
    prices: Dict[str, float]
    active_positions: List[BinancePosition]
    last_log_lines: List[str]
