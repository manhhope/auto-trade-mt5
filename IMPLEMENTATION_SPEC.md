# 📋 Tài liệu Giải pháp & Kế hoạch Triển khai

## Telegram MT5 Trading Bot — Implementation Specification

> **Mục đích:** Tài liệu này cung cấp đầy đủ chi tiết kỹ thuật để một agent/developer có thể triển khai toàn bộ dự án mà không cần hỏi thêm.

---

## 1. Tổng quan Dự án

### 1.1 Mô tả

Xây dựng hệ thống 3 thành phần cho phép người dùng:
- Đặt lệnh giao dịch trên MT5 thông qua Telegram Bot
- Tự động đọc tín hiệu giao dịch từ 1 group Telegram (chủ yếu XAUUSD)
- Quản lý lệnh, theo dõi P/L, và xem báo cáo

### 1.2 Tech Stack

| Component | Thư viện | Version | PyPI / Nguồn |
|-----------|----------|---------|--------------|
| Telegram Bot | `aiogram` | `^3.15` | `pip install aiogram` |
| REST API | `fastapi` | `^0.115` | `pip install fastapi` |
| ASGI Server | `uvicorn` | `^0.34` | `pip install uvicorn[standard]` |
| Database | `aiosqlite` | `^0.21` | `pip install aiosqlite` |
| HTTP Client | `httpx` | `^0.28` | `pip install httpx` |
| Config | `pydantic-settings` | `^2.7` | `pip install pydantic-settings` |
| Scheduler | `apscheduler` | `^3.11` | `pip install apscheduler` |
| EA | MQL5 (built-in) | — | MetaTrader 5 Terminal |

### 1.3 Yêu cầu hệ thống

- Python 3.11+
- MT5 Terminal chạy trên Windows VPS
- Telegram Bot Token (từ @BotFather)
- Telegram User Account (để listen group — cần Telethon hoặc Pyrogram nếu bot không ở trong group)

> **⚠️ QUAN TRỌNG:** `aiogram` chỉ hoạt động với **Bot API**. Để lắng nghe message trong 1 group mà bot là member, bot cần được **add vào group** và tắt **privacy mode** (qua @BotFather → Group Privacy → Turn OFF). Khi đó bot nhận được mọi message trong group.
>
> Nếu bot KHÔNG thể join group (group của bên thứ 3), cần dùng **Telethon** (user account client) để listen. Trong spec này, ta giả định **bot được add vào group**.

---

## 2. Cấu trúc Dự án

```
auto-trade/
│
├── .env                            # Biến môi trường (KHÔNG commit)
├── .env.example                    # Template
├── requirements.txt                # Python dependencies
├── README.md                       # Hướng dẫn cài đặt & sử dụng
├── run.py                          # Entry point — khởi động cả Bot + API
│
├── bot/                            # ── TELEGRAM BOT ──
│   ├── __init__.py
│   ├── main.py                     # Khởi tạo aiogram Bot + Dispatcher
│   ├── config.py                   # BotConfig (pydantic-settings)
│   ├── handlers/
│   │   ├── __init__.py             # Register tất cả routers
│   │   ├── start.py                # /start, /help
│   │   ├── trade.py                # /buy, /sell, /buylimit, /selllimit, /buystop, /sellstop
│   │   ├── manage.py              # /close, /closeall, /orders, /balance, /status
│   │   ├── signal.py              # /confirm, /reject, /confirmall, /rejectall, /queue
│   │   ├── config_cmd.py          # /config, /mode
│   │   └── report.py              # /report
│   ├── services/
│   │   ├── __init__.py
│   │   ├── api_client.py          # Async HTTP client gọi FastAPI
│   │   └── signal_listener.py     # Middleware lắng nghe group messages
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── command_parser.py      # Parse lệnh thủ công từ user
│   │   └── signal_parser.py       # Parse tín hiệu từ group
│   └── utils/
│       ├── __init__.py
│       ├── formatter.py           # Format kết quả gửi Telegram
│       └── validators.py          # Validate symbol, lot, price...
│
├── api/                            # ── REST API SERVER ──
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory
│   ├── config.py                   # APIConfig (pydantic-settings)
│   ├── database.py                 # SQLite connection pool + schema init
│   ├── models.py                   # Pydantic request/response models
│   ├── dependencies.py            # FastAPI dependencies (db, auth)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── trades.py              # /api/trades
│   │   ├── signals.py             # /api/signals
│   │   ├── account.py             # /api/account, /api/positions
│   │   ├── config_router.py       # /api/config
│   │   ├── reports.py             # /api/reports
│   │   └── health.py              # /api/health, /api/heartbeat
│   ├── services/
│   │   ├── __init__.py
│   │   ├── trade_service.py       # CRUD trades + business logic
│   │   ├── signal_service.py      # CRUD signals + confirm/reject logic
│   │   ├── report_service.py      # Aggregation queries cho báo cáo
│   │   └── config_service.py      # CRUD config
│   └── middleware/
│       ├── __init__.py
│       └── auth.py                # API Key validation middleware
│
├── ea/                             # ── EXPERT ADVISOR (MQL5) ──
│   ├── TelegramBridge.mq5          # EA chính
│   ├── HttpClient.mqh              # WebRequest wrapper
│   ├── JsonParser.mqh              # JSON parse helper (simple)
│   └── Config.mqh                  # Cấu hình EA
│
├── data/                           # Runtime data (auto-created)
│   └── .gitkeep
│
└── tests/                          # ── TESTS ──
    ├── __init__.py
    ├── conftest.py                 # Fixtures (test db, test client)
    ├── test_signal_parser.py       # Unit test signal parser
    ├── test_command_parser.py      # Unit test command parser
    ├── test_api_trades.py          # API integration tests
    ├── test_api_signals.py         # API integration tests
    ├── test_api_reports.py         # API integration tests
    └── test_formatter.py           # Unit test formatter
```

---

## 3. Cấu hình Môi trường

### 3.1 File `.env.example`

```env
# ── Telegram ──
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
OWNER_CHAT_ID=123456789
SIGNAL_GROUP_ID=-1001234567890

# ── API ──
API_HOST=127.0.0.1
API_PORT=8000
API_KEY=your-secret-api-key-here

# ── Database ──
DATABASE_PATH=data/trades.db

# ── Trading Defaults ──
DEFAULT_LOT_SIZE=0.01
DEFAULT_MODE=queue
QUEUE_EXPIRE_MINUTES=15
```

### 3.2 File `requirements.txt`

```
aiogram>=3.15,<4.0
fastapi>=0.115,<1.0
uvicorn[standard]>=0.34,<1.0
aiosqlite>=0.21,<1.0
httpx>=0.28,<1.0
pydantic-settings>=2.7,<3.0
apscheduler>=3.11,<4.0
```

---

## 4. Database Schema

### 4.1 Schema SQL

Khi API khởi động, tự động tạo database và tables nếu chưa tồn tại.

```sql
-- ═══════════════════════════════════════════════════════
-- TABLE: config
-- Lưu cấu hình key-value
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- TABLE: lot_overrides
-- Override lot size cho từng symbol cụ thể
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS lot_overrides (
    symbol      TEXT PRIMARY KEY,
    lot_size    REAL NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- TABLE: symbol_mapping
-- Mapping tên gọi phổ biến → MT5 symbol chính xác
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS symbol_mapping (
    alias       TEXT PRIMARY KEY,
    mt5_symbol  TEXT NOT NULL
);

-- ═══════════════════════════════════════════════════════
-- TABLE: signals
-- Tín hiệu từ group Telegram
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id      TEXT UNIQUE NOT NULL,
    group_id      TEXT NOT NULL,
    message_id    INTEGER,
    raw_message   TEXT NOT NULL,
    parsed_type   TEXT,
    parsed_symbol TEXT,
    parsed_price  REAL,
    parsed_sl     REAL,
    parsed_tp     REAL,
    parse_success BOOLEAN DEFAULT 0,
    status        TEXT DEFAULT 'QUEUED',
    lot_override  REAL,
    confirmed_at  DATETIME,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- TABLE: trades
-- Lệnh giao dịch (cả thủ công lẫn từ signal)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid            TEXT UNIQUE NOT NULL,
    signal_id       INTEGER REFERENCES signals(id),
    source          TEXT DEFAULT 'MANUAL',
    symbol          TEXT NOT NULL,
    trade_type      TEXT NOT NULL,
    lot_size        REAL NOT NULL,
    price           REAL,
    stop_loss       REAL,
    take_profit     REAL,
    status          TEXT DEFAULT 'PENDING',
    ticket          INTEGER,
    open_price      REAL,
    close_price     REAL,
    pnl             REAL,
    pnl_pips        REAL,
    commission      REAL DEFAULT 0,
    swap            REAL DEFAULT 0,
    error_code      INTEGER,
    error_msg       TEXT,
    opened_at       DATETIME,
    closed_at       DATETIME,
    close_reason    TEXT,
    close_requested BOOLEAN DEFAULT 0,
    notified        BOOLEAN DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- TABLE: account_info
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS account_info (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    balance         REAL DEFAULT 0,
    equity          REAL DEFAULT 0,
    margin          REAL DEFAULT 0,
    free_margin     REAL DEFAULT 0,
    profit          REAL DEFAULT 0,
    server          TEXT DEFAULT '',
    account_number  INTEGER DEFAULT 0,
    account_name    TEXT DEFAULT '',
    currency        TEXT DEFAULT 'USD',
    leverage        INTEGER DEFAULT 0,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- TABLE: ea_heartbeat
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS ea_heartbeat (
    id            INTEGER PRIMARY KEY DEFAULT 1,
    last_ping     DATETIME,
    ea_version    TEXT DEFAULT '1.0',
    mt5_connected BOOLEAN DEFAULT 0
);

-- ═══════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);
CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_close_req ON trades(close_requested) WHERE close_requested = 1;
CREATE INDEX IF NOT EXISTS idx_trades_notified ON trades(notified) WHERE notified = 0;
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_queue_id ON signals(queue_id);
```

### 4.2 Seed Data

```sql
INSERT OR IGNORE INTO config (key, value) VALUES
    ('mode', 'queue'),
    ('default_lot', '0.01'),
    ('queue_expire_minutes', '15'),
    ('sl_buffer_pips', '0');

INSERT OR IGNORE INTO symbol_mapping (alias, mt5_symbol) VALUES
    ('GOLD', 'XAUUSD'), ('gold', 'XAUUSD'), ('Gold', 'XAUUSD'),
    ('XAU', 'XAUUSD'), ('xau', 'XAUUSD'),
    ('XAUUSD', 'XAUUSD'), ('xauusd', 'XAUUSD'),
    ('XAUUSDT', 'XAUUSD'), ('xauusdt', 'XAUUSD'),
    ('Vàng', 'XAUUSD'), ('vàng', 'XAUUSD'), ('VÀNG', 'XAUUSD');

INSERT OR IGNORE INTO account_info (id) VALUES (1);
INSERT OR IGNORE INTO ea_heartbeat (id) VALUES (1);
```

---

## 5. Pydantic Models (`api/models.py`)

```python
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

class SignalConfirmRequest(BaseModel):
    lot_override: Optional[float] = Field(None, gt=0, le=100)

class SignalResponse(BaseModel):
    id: int
    queue_id: str
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

class AccountResponse(BaseModel):
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
    updated_at: datetime


# ── Position Models ──

class PositionItem(BaseModel):
    ticket: int
    symbol: str
    trade_type: str
    lot_size: float
    open_price: float
    current_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
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
```

---

## 6. API Endpoints Specification

### 6.1 Auth Middleware

Mọi request phải có header `X-API-Key` khớp với `API_KEY` trong `.env`. Nếu thiếu/sai → 401.

### 6.2 Trade Endpoints

#### `POST /api/trades` — Tạo lệnh mới

- **Gọi bởi:** Bot
- **Request:** `TradeCreateRequest`
- **Response:** `TradeResponse` (201)
- **Logic:**
  1. Validate symbol tồn tại trong `symbol_mapping`
  2. Nếu pending order (BUY_LIMIT, etc.), `price` bắt buộc
  3. INSERT vào `trades` với `status='PENDING'`

#### `GET /api/trades` — Lấy danh sách trades

- **Gọi bởi:** EA (poll pending), Bot (xem orders)
- **Query params:** `status` (optional), `close_requested` (optional), `notified` (optional), `limit` (default 50)
- **Response:** `list[TradeResponse]`

#### `PUT /api/trades/{trade_id}` — Cập nhật trade

- **Gọi bởi:** EA
- **Request:** `TradeUpdateRequest`
- **Logic:**
  - Nếu `status=FILLED`: set `opened_at=NOW()`
  - Nếu `status=CLOSED`: set `closed_at=NOW()`
  - Set `updated_at=NOW()`

#### `DELETE /api/trades/{trade_id}` — Huỷ lệnh pending

- **Logic:** Chỉ huỷ nếu `status=PENDING`, set `status=CANCELLED`

#### `PUT /api/trades/{trade_id}/close-request` — Yêu cầu đóng lệnh

- **Gọi bởi:** Bot (khi user /close)
- **Logic:** Set `close_requested=1`
- EA poll trades có `close_requested=1 AND status=FILLED`

#### `PUT /api/trades/{trade_id}/notify` — Đánh dấu đã thông báo

- **Gọi bởi:** Bot (sau khi gửi notification)
- **Logic:** Set `notified=1`

### 6.3 Signal Endpoints

#### `POST /api/signals` — Tạo signal

- **Logic:** Auto-generate `queue_id` = `SIG-{auto_increment:04d}`
- Nếu `parse_success=False` → `status='PARSE_FAILED'`

#### `GET /api/signals` — Lấy signals

- **Query:** `status` (optional)

#### `PUT /api/signals/{id}/confirm` — Xác nhận signal

- **Request:** `SignalConfirmRequest` (optional lot_override)
- **Logic:**
  1. Kiểm tra `status=QUEUED` (nếu EXPIRED/REJECTED → 400)
  2. Set signal `status=CONFIRMED`, `confirmed_at=NOW()`
  3. Xác định lot: `lot_override` > `lot_overrides[symbol]` > `config['default_lot']`
  4. Tạo trade: uuid=UUIDv4, source=SIGNAL, trade_type=signal.parsed_type
  5. **Luôn tạo market order** từ signal (price=NULL)
- **Response:** `TradeResponse`

#### `PUT /api/signals/{id}/reject` — Từ chối

#### `POST /api/signals/confirm-all` — Xác nhận tất cả

- Return `{"confirmed": N, "trades": [...]}`

#### `POST /api/signals/reject-all` — Từ chối tất cả

### 6.4 Config Endpoints

#### `GET /api/config` — Lấy config

```json
{
  "mode": "queue",
  "default_lot": "0.01",
  "queue_expire_minutes": "15",
  "sl_buffer_pips": "0",
  "lot_overrides": {"XAUUSD": 0.02}
}
```

#### `PUT /api/config/{key}` — Cập nhật config

- Allowed keys: `mode`, `default_lot`, `queue_expire_minutes`, `sl_buffer_pips`, `signal_group_id`
- Validation: `mode` phải là "auto"/"queue", numeric values > 0

#### `GET /api/config/lot-overrides`
#### `PUT /api/config/lot-overrides/{symbol}`
#### `DELETE /api/config/lot-overrides/{symbol}`

### 6.5 Account & Position Endpoints

#### `PUT /api/account` — EA sync
#### `GET /api/account` — Bot lấy

#### `PUT /api/positions` — EA sync positions

**Logic quan trọng (auto-close detection):**
1. Nhận `positions` list từ EA (tất cả positions đang mở trên MT5)
2. Lấy trades trong DB có `status=FILLED`
3. So sánh: nếu trade.ticket **không có** trong positions → lệnh đã đóng
4. Cho mỗi trade đã đóng:
   - Tìm position cuối cùng đã biết để lấy close info, hoặc dùng thông tin từ EA
   - Set `status=CLOSED`, `closed_at=NOW()`
   - Xác định `close_reason`: so close_price với SL/TP
5. Return `{"closed_trade_ids": [1, 5], "active_count": 3}`

#### `GET /api/positions` — Bot lấy (trả trades `status=FILLED`)

### 6.6 Report Endpoints

#### `GET /api/reports/summary?period=day|week|month`

**Date ranges:**
- `day`: today 00:00 → now
- `week`: Monday 00:00 → now
- `month`: 1st of month 00:00 → now

**SQL cho summary:**
```sql
SELECT
    COUNT(*) as total_trades,
    COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losing_trades,
    ROUND(COUNT(CASE WHEN pnl > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) as win_rate,
    ROUND(COALESCE(SUM(pnl), 0), 2) as total_pnl,
    ROUND(COALESCE(AVG(pnl), 0), 2) as avg_pnl,
    ROUND(MAX(pnl), 2) as best_trade,
    ROUND(MIN(pnl), 2) as worst_trade,
    ROUND(
        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
        NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0),
    2) as profit_factor
FROM trades
WHERE status = 'CLOSED'
  AND closed_at >= :date_from
  AND closed_at < :date_to;
```

**SQL cho daily breakdown:**
```sql
SELECT
    DATE(closed_at) as date,
    ROUND(SUM(pnl), 2) as pnl,
    COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
    COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losses
FROM trades
WHERE status = 'CLOSED'
  AND closed_at >= :date_from AND closed_at < :date_to
GROUP BY DATE(closed_at)
ORDER BY date;
```

**Max Drawdown** (Python):
```python
def calculate_max_drawdown(daily_pnls: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in daily_pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)
```

**Streak** (Python):
```python
def calculate_streak(trades_ordered_by_closed_at: list[dict]) -> int:
    if not trades_ordered_by_closed_at:
        return 0
    streak = 0
    direction = None
    for t in reversed(trades_ordered_by_closed_at):
        is_win = t["pnl"] > 0
        if direction is None:
            direction = is_win
            streak = 1 if is_win else -1
        elif is_win == direction:
            streak += 1 if is_win else -1
        else:
            break
    return streak
```

#### `GET /api/reports/trend?weeks=4`

So sánh P/L kỳ hiện tại vs kỳ trước.

### 6.7 Health Endpoints

#### `GET /api/health`
- EA online nếu `last_ping` < 30 giây trước

#### `PUT /api/heartbeat`
- Update `ea_heartbeat`

---

## 7. Signal Parser (`bot/parsers/signal_parser.py`)

### 7.1 Regex Patterns (thử theo thứ tự, dừng khi match)

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedSignal:
    trade_type: str      # "BUY" or "SELL"
    symbol: str          # Raw symbol trước mapping
    price: Optional[float]
    sl: Optional[float]
    tp: Optional[float]

PATTERNS = [
    # Pattern 1: Inline EN — "BUY GOLD 2350.50 SL 2340 TP 2370"
    re.compile(
        r'(BUY|SELL)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*[@:]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|stoploss|stop\s*loss)\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:TP|takeprofit|take\s*profit)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
    # Pattern 2: Multiline — BUY GOLD\nEntry: 2350\nSL: 2340\nTP: 2370
    re.compile(
        r'(BUY|SELL)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*\n'
        r'.*?(?:entry|price|giá)\s*[:=]?\s*(\d+\.?\d*)\s*\n'
        r'.*?(?:SL|stoploss|stop\s*loss|cắt\s*lỗ)\s*[:=]?\s*(\d+\.?\d*)\s*\n'
        r'.*?(?:TP|takeprofit|take\s*profit|chốt\s*lời)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE | re.DOTALL
    ),
    # Pattern 3: Vietnamese — "Mua vàng giá 2350 cắt lỗ 2340 chốt lời 2370"
    re.compile(
        r'(Mua|Bán)\s+(GOLD|XAU(?:USD[T]?)?|[Vv]àng|VÀNG)\s*'
        r'(?:giá|entry|price)?\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|cắt\s*lỗ|stoploss)\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:TP|chốt\s*lời|takeprofit)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
    # Pattern 4: Không có TP — "BUY GOLD 2350 SL 2340"
    re.compile(
        r'(BUY|SELL)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*[@:]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|stoploss|stop\s*loss)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
]

VIET_TYPE_MAP = {"mua": "BUY", "bán": "SELL"}

def parse_signal(text: str) -> Optional[ParsedSignal]:
    for pattern in PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            trade_type = VIET_TYPE_MAP.get(groups[0].lower(), groups[0].upper())
            return ParsedSignal(
                trade_type=trade_type,
                symbol=groups[1].upper(),
                price=float(groups[2]) if groups[2] else None,
                sl=float(groups[3]) if len(groups) > 3 and groups[3] else None,
                tp=float(groups[4]) if len(groups) > 4 and groups[4] else None,
            )
    return None
```

### 7.2 Symbol Resolver

```python
async def resolve_symbol(raw_symbol: str, db) -> Optional[str]:
    row = await db.execute(
        "SELECT mt5_symbol FROM symbol_mapping WHERE alias = ?", (raw_symbol,)
    )
    result = await row.fetchone()
    return result[0] if result else None
```

---

## 8. Bot Command Parser (`bot/parsers/command_parser.py`)

```python
def parse_trade_command(text: str) -> dict:
    """
    Parse: /buy XAUUSD 0.01 sl=2340 tp=2370
    Returns: {"symbol", "lot_size", "stop_loss", "take_profit"}
    lot_size is None if not specified (use default).
    """
    parts = text.split()
    if len(parts) < 2:
        raise ValueError("Thiếu symbol. VD: /buy XAUUSD 0.01 sl=2340 tp=2370")

    result = {"symbol": parts[1].upper(), "lot_size": None, "stop_loss": None,
              "take_profit": None, "price": None}

    if len(parts) >= 3 and not "=" in parts[2]:
        result["lot_size"] = float(parts[2])

    for part in parts:
        kv = part.lower().split("=", 1)
        if len(kv) == 2:
            if kv[0] == "sl":
                result["stop_loss"] = float(kv[1])
            elif kv[0] == "tp":
                result["take_profit"] = float(kv[1])
            elif kv[0] == "price":
                result["price"] = float(kv[1])
            elif kv[0] == "lot":
                result["lot_size"] = float(kv[1])
    return result
```

---

## 9. Telegram Bot Display Formats

### 9.1 Auto Mode Notification

```
🤖 AUTO — LỆNH MỚI TỪ SIGNAL
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 BUY XAUUSD
💰 Lot: 0.01
💵 Entry: 2350.50
🛑 SL: 2340.00 (-105 pips)
🎯 TP: 2370.00 (+195 pips)
📢 Nguồn: Signal Group
⏰ 14/06/2026 23:30:15
🔑 UUID: a1b2c3d4
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ Đang chờ EA thực thi...
```

### 9.2 Queue Signal Notification

```
📋 TÍN HIỆU MỚI — SIG-0042
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 BUY XAUUSD
💰 Lot: 0.01 (mặc định)
💵 Entry: 2350.50
🛑 SL: 2340.00
🎯 TP: 2370.00
📢 Nguồn: Signal Group
⏱️ Hết hạn sau: 15 phút
━━━━━━━━━━━━━━━━━━━━━━━━━━

/confirm SIG-0042
/confirm SIG-0042 lot=0.05
/reject SIG-0042
/confirmall
```

### 9.3 Trade Filled Notification

```
✅ LỆNH ĐÃ KHỚP
━━━━━━━━━━━━━━━━━━━━
📊 BUY XAUUSD 0.01
💵 Giá vào: 2350.50
🛑 SL: 2340.00
🎯 TP: 2370.00
🎫 Ticket: #12345
⏰ 14/06/2026 23:30:20
━━━━━━━━━━━━━━━━━━━━
```

### 9.4 Trade Closed Notification

```
🔔 LỆNH ĐÃ ĐÓNG
━━━━━━━━━━━━━━━━━━━━
📊 BUY XAUUSD 0.01
💵 Vào: 2350.50 → Ra: 2370.00
💰 P/L: +$19.50 ✅
📢 Lý do: TP Hit
⏱️ Giữ lệnh: 2h 35m
━━━━━━━━━━━━━━━━━━━━
📈 Hôm nay: +$45.20 (3W / 1L)
```

### 9.5 Orders List

```
📋 LỆNH ĐANG MỞ (2 lệnh)
━━━━━━━━━━━━━━━━━━━━
1. 🟢 #12345 BUY XAUUSD 0.01 @ 2350.50
   P/L: +$19.50 | SL: 2340 | TP: 2370

2. 🔴 #12346 SELL XAUUSD 0.01 @ 2355.00
   P/L: -$8.20 | SL: 2365 | TP: 2340
━━━━━━━━━━━━━━━━━━━━
💰 Tổng P/L: +$11.30
```

### 9.6 Balance

```
💰 THÔNG TIN TÀI KHOẢN
━━━━━━━━━━━━━━━━━━━━
💵 Balance:     $10,250.00
📊 Equity:      $10,280.50
💳 Margin:      $125.00
🆓 Free Margin: $10,155.50
📈 Float P/L:   +$30.50
🏦 Server:      ICMarkets-Demo
🔑 Account:     #12345678
⚙️ Leverage:    1:500
━━━━━━━━━━━━━━━━━━━━
🤖 EA: Online ✅ (v1.0)
```

### 9.7 Report

```
📊 BÁO CÁO TUẦN (10/06 — 14/06/2026)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Tổng P/L:      +$127.50
📈 Lệnh thắng:    12 (75.0%)
📉 Lệnh thua:     4  (25.0%)
📋 Tổng lệnh:     16
💵 TB/lệnh:       +$7.97
⚖️ Profit Factor: 2.35
📉 Max Drawdown:  $18.50
🔥 Streak:        3 thắng liên tiếp

📅 THEO NGÀY
━━━━━━━━━━━━
  T2 (10/06): +$35.00  ███████░░░ 4W/1L
  T3 (11/06): -$12.50  ██░░░░░░░░ 1W/2L
  T4 (12/06): +$48.00  █████████░ 3W/0L
  T5 (13/06): +$22.00  █████░░░░░ 2W/1L
  T6 (14/06): +$35.00  ███████░░░ 2W/0L

📈 XU HƯỚNG
━━━━━━━━━━━
  Tuần trước:  +$95.00
  Tuần này:    +$127.50 (↑ 34.2%) 🚀
```

**ASCII bar helper:**
```python
def make_bar(value: float, max_value: float, width: int = 10) -> str:
    if max_value <= 0:
        return "░" * width
    filled = min(int(abs(value) / max_value * width), width)
    return "█" * filled + "░" * (width - filled)
```

### 9.8 Config Display

```
⚙️ CẤU HÌNH HIỆN TẠI
━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Account: Demo #12345678 (ICMarkets)
📢 Signal Group: -1001234567890
🔀 Mode: 📋 Queue (chờ xác nhận)
💰 Lot mặc định: 0.01
   └─ XAUUSD: 0.02 (override)
⏱️ Queue expire: 15 phút
🛡️ SL buffer: 0 pips
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 10. EA MQL5 Specification

### 10.1 Input Parameters

```mql5
input string InpApiUrl      = "http://127.0.0.1:8000";
input string InpApiKey      = "your-api-key";
input int    InpPollMs       = 500;
input int    InpMaxSlippage  = 10;
input int    InpMagicNumber  = 202606;
```

### 10.2 Main Loop (Pseudocode)

```
OnInit():
    EventSetMillisecondTimer(InpPollMs)
    Load executed_uuids[] from MQL5/Files/executed_trades.csv
    return INIT_SUCCEEDED

OnTimer():
    static int counter = 0
    counter++

    // ═══ Mỗi tick (~500ms): Poll PENDING trades ═══
    response = GET /api/trades?status=PENDING
    trades[] = ParseJson(response)
    for each trade in trades[]:
        if trade.uuid in executed_uuids:
            PUT /api/trades/{id} → FAILED, "DUPLICATE"
            continue
        result = ExecuteTrade(trade)
        if result.success:
            executed_uuids += trade.uuid
            AppendFile("executed_trades.csv", trade.uuid)
            PUT /api/trades/{id} → FILLED, ticket, open_price
        else:
            PUT /api/trades/{id} → FAILED, error_code, error_msg

    // ═══ Mỗi tick: Poll CLOSE requests ═══
    response = GET /api/trades?status=FILLED&close_requested=1
    close_trades[] = ParseJson(response)
    for each trade in close_trades[]:
        success = PositionClose(trade.ticket, InpMaxSlippage)
        // Result sẽ được detect ở position sync

    // ═══ Mỗi 2 ticks (~1s): Sync positions ═══
    if counter % 2 == 0:
        positions[] = CollectAllPositions()
        PUT /api/positions → {positions: [...]}

    // ═══ Mỗi 10 ticks (~5s): Account + heartbeat ═══
    if counter % 10 == 0:
        info = AccountInfoDouble(...)
        PUT /api/account → info
        PUT /api/heartbeat → {ea_version, mt5_connected}
```

### 10.3 ExecuteTrade Function

```mql5
bool ExecuteTrade(TradeData &trade, int &out_ticket, double &out_price) {
    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.magic = InpMagicNumber;
    request.symbol = trade.symbol;
    request.volume = trade.lot_size;
    request.deviation = InpMaxSlippage;
    request.comment = "TG:" + trade.uuid;

    if (trade.type == "BUY" || trade.type == "SELL") {
        request.action = TRADE_ACTION_DEAL;
        request.type = (trade.type == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
        request.price = SymbolInfoDouble(trade.symbol,
            (trade.type == "BUY") ? SYMBOL_ASK : SYMBOL_BID);
    } else {
        // BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP
        request.action = TRADE_ACTION_PENDING;
        request.price = trade.price;
        // Map type string to ORDER_TYPE_* enum
    }

    if (trade.sl > 0) request.sl = trade.sl;
    if (trade.tp > 0) request.tp = trade.tp;

    bool ok = OrderSend(request, result);
    if (ok && result.retcode == TRADE_RETCODE_DONE) {
        out_ticket = (int)result.order;
        out_price = result.price;
        return true;
    }
    return false;
}
```

### 10.4 MT5 Setup Required

1. `Tools → Options → Expert Advisors → Allow WebRequest for listed URL`
   - Add: `http://127.0.0.1:8000`
2. `Allow automated trading`
3. Attach EA to any chart (XAUUSD recommended)

---

## 11. Background Tasks

### 11.1 Queue Expiry (mỗi 60 giây)

```python
async def expire_old_signals(db):
    expire_min = int(await get_config(db, "queue_expire_minutes"))
    cutoff = datetime.utcnow() - timedelta(minutes=expire_min)
    result = await db.execute(
        "UPDATE signals SET status='EXPIRED' WHERE status='QUEUED' AND created_at < ?",
        (cutoff.isoformat(),)
    )
    return result.rowcount
```

### 11.2 Closed Trade Notification (mỗi 2 giây)

```python
async def notify_closed_trades(bot, api_client):
    trades = await api_client.get_trades(status="CLOSED", notified=0)
    for trade in trades:
        msg = format_trade_closed(trade)
        await bot.send_message(OWNER_CHAT_ID, msg)
        await api_client.mark_notified(trade["id"])
```

### 11.3 EA Health Check (mỗi 30 giây)

```python
async def check_ea_health(bot, api_client):
    health = await api_client.get_health()
    if not health["ea_online"]:
        await bot.send_message(OWNER_CHAT_ID,
            "🔴 CẢNH BÁO: EA OFFLINE! Kiểm tra MT5 Terminal.")
```

---

## 12. Entry Point `run.py`

```python
import asyncio
import uvicorn
from bot.main import start_bot
from api.main import create_app
from api.database import init_database

async def main():
    await init_database()
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(
        server.serve(),
        start_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 13. Kế hoạch 6 Phases

### Phase 1: Nền tảng API (2-3 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| Project setup, .env, requirements.txt | Root | `pip install` OK |
| Database init + schema + seed | `api/database.py` | Tables + seed OK |
| Pydantic models | `api/models.py` | All models defined |
| Trade CRUD | `api/routers/trades.py`, `api/services/trade_service.py` | POST/GET/PUT/DELETE work |
| Config endpoints | `api/routers/config_router.py` | GET/PUT work |
| Health endpoints | `api/routers/health.py` | GET health OK |
| Auth middleware | `api/middleware/auth.py` | 401 without key |
| Entry point | `run.py` | API starts on :8000 |

### Phase 2: EA MQL5 (2-3 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| HTTP/JSON helpers | `ea/HttpClient.mqh`, `ea/JsonParser.mqh` | GET/PUT/POST work |
| Main loop | `ea/TelegramBridge.mq5` | Poll → Execute → Report |
| Dedup | EA | UUID file persist + check |
| Position sync | EA | PUT /api/positions every 1s |
| Account + heartbeat | EA | PUT every 5s |

### Phase 3: Bot cơ bản (2-3 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| Bot setup | `bot/main.py` | Online, /start works |
| Parsers | `bot/parsers/` | Parse /buy, /sell |
| Formatter | `bot/utils/formatter.py` | All display formats |
| Trade handlers | `bot/handlers/trade.py` | 6 trade commands work |
| Manage handlers | `bot/handlers/manage.py` | /close /orders /balance |
| API client | `bot/services/api_client.py` | All endpoints callable |

### Phase 4: Signal + Queue (3-4 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| Signal parser | `bot/parsers/signal_parser.py` | 4 patterns match |
| Signal API | `api/routers/signals.py`, `api/services/signal_service.py` | CRUD + confirm |
| Signal listener | `bot/services/signal_listener.py` | Group messages detected |
| Queue handlers | `bot/handlers/signal.py` | /confirm /reject /queue |
| Auto mode | signal_listener | Auto-create trade |
| Queue expiry | Background task | EXPIRED after 15min |

### Phase 5: Config + Auto-close (2-3 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| Config handlers | `bot/handlers/config_cmd.py` | /config /mode |
| Lot override | API + Bot | Per-symbol lot works |
| Close detection | `api/routers/account.py` (PUT /positions) | Detect closed trades |
| Close notification | Background task | Notify on close |
| Close request | API + EA | /close triggers EA close |
| EA health alert | Background task | Alert if offline > 30s |

### Phase 6: Reports + Polish (2-3 ngày)

| Task | Files | Acceptance |
|------|-------|-----------|
| Report API | `api/routers/reports.py`, `api/services/report_service.py` | Summary + trend |
| Report handler | `bot/handlers/report.py` | /report day/week/month |
| ASCII chart | `bot/utils/formatter.py` | Bar chart displays |
| Tests | `tests/` | Parser + API tests pass |
| E2E test | Manual | Full flow on MT5 Demo |
| README | `README.md` | Install guide |

**⏱️ Tổng: ~14-20 ngày**

---

## 14. Quy ước Code

- **Python:** PEP 8, type hints, async/await cho mọi I/O
- **Naming:** files=snake_case, classes=PascalCase, functions=snake_case, constants=UPPER_CASE
- **Error handling:** try/except ở mọi endpoint + handler, log lỗi
- **Logging:** Python `logging` module, level INFO
- **Comments:** tiếng Anh
- **Tests:** pytest + pytest-asyncio, test DB dùng in-memory SQLite
