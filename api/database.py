import os
import aiosqlite
from typing import AsyncGenerator

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/trades.db")

async def get_db_connection() -> aiosqlite.Connection:
    """
    Tạo kết nối mới đến cơ sở dữ liệu SQLite và cấu hình WAL mode để tránh lock.
    """
    # Đảm bảo thư mục dữ liệu tồn tại
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = await aiosqlite.connect(DATABASE_PATH)
    # Kích hoạt WAL mode để tối ưu đọc/ghi đồng thời
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = aiosqlite.Row
    return conn

async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    FastAPI dependency cung cấp database connection và tự động đóng sau khi hoàn thành request.
    """
    conn = await get_db_connection()
    try:
        yield conn
    finally:
        await conn.close()

async def init_database():
    """
    Tạo cấu trúc bảng và chèn dữ liệu mẫu (seed data) nếu cơ sở dữ liệu trống.
    """
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        # 1. Tạo bảng config
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Tạo bảng lot_overrides
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lot_overrides (
                symbol      TEXT PRIMARY KEY,
                lot_size    REAL NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Tạo bảng symbol_mapping
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_mapping (
                alias       TEXT PRIMARY KEY,
                mt5_symbol  TEXT NOT NULL
            );
        """)

        # 4. Tạo bảng signals
        await conn.execute("""
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
        """)

        # 5. Tạo bảng trades
        await conn.execute("""
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
        """)

        # 6. Tạo bảng account_info
        await conn.execute("""
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
        """)

        # 7. Tạo bảng ea_heartbeat
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ea_heartbeat (
                id            INTEGER PRIMARY KEY DEFAULT 1,
                last_ping     DATETIME,
                ea_version    TEXT DEFAULT '1.0',
                mt5_connected BOOLEAN DEFAULT 0
            );
        """)

        # 8. Tạo Indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_close_req ON trades(close_requested) WHERE close_requested = 1;")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_notified ON trades(notified) WHERE notified = 0;")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_queue_id ON signals(queue_id);")

        # 9. Seed data - Config
        configs = [
            ('mode', 'queue'),
            ('default_lot', '0.01'),
            ('queue_expire_minutes', '15'),
            ('sl_buffer_pips', '0')
        ]
        for key, value in configs:
            await conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value)
            )

        # 10. Seed data - Symbol mapping
        mappings = [
            ('GOLD', 'XAUUSD'), ('gold', 'XAUUSD'), ('Gold', 'XAUUSD'),
            ('XAU', 'XAUUSD'), ('xau', 'XAUUSD'),
            ('XAUUSD', 'XAUUSD'), ('xauusd', 'XAUUSD'),
            ('XAUUSDT', 'XAUUSD'), ('xauusdt', 'XAUUSD'),
            ('Vàng', 'XAUUSD'), ('vàng', 'XAUUSD'), ('VÀNG', 'XAUUSD')
        ]
        for alias, mt5_symbol in mappings:
            await conn.execute(
                "INSERT OR IGNORE INTO symbol_mapping (alias, mt5_symbol) VALUES (?, ?)",
                (alias, mt5_symbol)
            )

        # 11. Seed data - Account Info & Heartbeat default rows
        await conn.execute("INSERT OR IGNORE INTO account_info (id) VALUES (1);")
        await conn.execute("INSERT OR IGNORE INTO ea_heartbeat (id) VALUES (1);")

        await conn.commit()
