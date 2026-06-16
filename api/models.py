from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

# ── Enums ──

class TradeType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"

class TradeStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class SignalStatus(str, Enum):
    QUEUED = "QUEUED"
    CONFIRMED = "CONFIRMED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PARSE_FAILED = "PARSE_FAILED"

class TradingMode(str, Enum):
    AUTO = "auto"
    QUEUE = "queue"

class CloseReason(str, Enum):
    SL_HIT = "SL_HIT"
    TP_HIT = "TP_HIT"
    MANUAL = "MANUAL"
    TRAILING_STOP = "TRAILING_STOP"

class TradeSource(str, Enum):
    MANUAL = "MANUAL"
    SIGNAL = "SIGNAL"


# ── Trade Models ──

class TradeCreateRequest(BaseModel):
    uuid: str
    symbol: str
    trade_type: TradeType
    lot_size: float = Field(gt=0, le=100)
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    signal_id: Optional[int] = None
    source: TradeSource = TradeSource.MANUAL
    account_id: Optional[int] = None

class TradeUpdateRequest(BaseModel):
    status: TradeStatus
    ticket: Optional[int] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    error_code: Optional[int] = None
    error_msg: Optional[str] = None
    close_reason: Optional[CloseReason] = None

class TradeResponse(BaseModel):
    id: int
    uuid: str
    account_id: Optional[int]
    signal_id: Optional[int]
    source: str
    symbol: str
    trade_type: str
    lot_size: float
    price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    status: str
    ticket: Optional[int]
    open_price: Optional[float]
    close_price: Optional[float]
    pnl: Optional[float]
    pnl_pips: Optional[float]
    commission: Optional[float]
    swap: Optional[float]
    error_code: Optional[int]
    error_msg: Optional[str]
    close_reason: Optional[str]
    close_requested: bool
    notified: bool
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# ── Signal Models ──

class SignalCreateRequest(BaseModel):
    group_id: str
    message_id: Optional[int] = None
    raw_message: str
    parsed_type: Optional[str] = None
    parsed_symbol: Optional[str] = None
    parsed_price: Optional[float] = None
    parsed_sl: Optional[float] = None
    parsed_tp: Optional[float] = None
    parse_success: bool = False
    account_id: Optional[int] = None

class SignalConfirmRequest(BaseModel):
    lot_override: Optional[float] = Field(None, gt=0, le=100)

class SignalResponse(BaseModel):
    id: int
    queue_id: str
    account_id: Optional[int]
    group_id: str
    message_id: Optional[int]
    raw_message: str
    parsed_type: Optional[str]
    parsed_symbol: Optional[str]
    parsed_price: Optional[float]
    parsed_sl: Optional[float]
    parsed_tp: Optional[float]
    parse_success: bool
    status: str
    lot_override: Optional[float]
    confirmed_at: Optional[datetime]
    created_at: datetime


# ── Account Models ──

class TradingAccountCreate(BaseModel):
    name: str
    platform: str = "MT5"
    account_number: Optional[str] = None

class TradingAccountResponse(BaseModel):
    id: int
    name: str
    platform: str
    account_number: Optional[str]
    token: str
    is_active: bool
    created_at: datetime

class AccountUpdateRequest(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    server: str
    account_number: int
    account_name: str
    currency: str = "USD"
    leverage: int
    gold_price: Optional[float] = None
    gold_change_1h: Optional[float] = None
    gold_change_4h: Optional[float] = None
    gold_change_1d: Optional[float] = None

class AccountResponse(BaseModel):
    account_id: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    server: str
    account_number: int
    account_name: str
    currency: str
    leverage: int
    gold_price: Optional[float] = None
    gold_change_1h: Optional[float] = None
    gold_change_4h: Optional[float] = None
    gold_change_1d: Optional[float] = None
    updated_at: datetime


# ── Position Models ──

class PositionItem(BaseModel):
    ticket: int
    symbol: str
    trade_type: str
    lot_size: float
    open_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: float
    swap: float
    commission: float
    open_time: datetime

class PositionsSyncRequest(BaseModel):
    positions: list[PositionItem]


# ── Config Models ──

class ConfigUpdateRequest(BaseModel):
    value: str

class ConfigResponse(BaseModel):
    key: str
    value: str

class LotOverrideRequest(BaseModel):
    lot_size: float = Field(gt=0, le=100)


# ── Report Models ──

class DailyBreakdown(BaseModel):
    date: str
    pnl: float
    wins: int
    losses: int

class ReportTradeItem(BaseModel):
    ticket: Optional[int]
    symbol: str
    trade_type: str
    lot_size: float
    open_price: Optional[float]
    close_price: Optional[float]
    pnl: Optional[float]
    close_reason: Optional[str]
    closed_at: Optional[datetime]

class ReportSummary(BaseModel):
    period: str
    date_from: str
    date_to: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    profit_factor: Optional[float]
    max_drawdown: float
    best_trade: float
    worst_trade: float
    current_streak: int
    daily_breakdown: list[DailyBreakdown]
    trades: Optional[list[ReportTradeItem]] = []

class ReportTrend(BaseModel):
    current_period_pnl: float
    previous_period_pnl: float
    change_amount: float
    change_percent: float
    direction: str


# ── Health Models ──

class HeartbeatRequest(BaseModel):
    ea_version: str
    mt5_connected: bool

class HealthResponse(BaseModel):
    api_status: str = "ok"
    ea_online: bool
    ea_last_ping: Optional[datetime]
    ea_version: Optional[str]
    mt5_connected: bool
    db_size_mb: float


# ── Action Log & Manual Sync Models ──

class ActionLogCreate(BaseModel):
    ticket: int
    symbol: str
    action_type: str
    details: str
    pnl: float = 0.0
    current_price: Optional[float] = None
    lot_size: Optional[float] = None
    trade_type: Optional[str] = None
    account_id: Optional[int] = None

class ManualTradeSyncItem(BaseModel):
    ticket: int
    symbol: str
    trade_type: str
    lot_size: float
    open_price: float
    close_price: float
    pnl: float
    commission: float = 0.0
    swap: float = 0.0
    opened_at: datetime
    closed_at: datetime
    close_reason: str

class ManualTradeSyncRequest(BaseModel):
    trades: list[ManualTradeSyncItem]

