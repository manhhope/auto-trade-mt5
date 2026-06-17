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
        # Create users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     TEXT UNIQUE NOT NULL,
                username        TEXT,
                is_approved     BOOLEAN DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 0. Tạo bảng accounts
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
                name            TEXT NOT NULL,
                platform        TEXT NOT NULL,
                account_number  TEXT,
                token           TEXT UNIQUE NOT NULL,
                is_active       BOOLEAN DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Check if user_id column exists in accounts table
        async with conn.execute("PRAGMA table_info(accounts);") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if columns and "user_id" not in columns:
                await conn.execute("ALTER TABLE accounts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;")

        # 1. Tạo bảng config
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                account_id  INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, key)
            );
        """)

        # 2. Tạo bảng lot_overrides
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lot_overrides (
                account_id  INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                symbol      TEXT NOT NULL,
                lot_size    REAL NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, symbol)
            );
        """)

        # 3. Tạo bảng symbol_mapping (Global)
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
                account_id    INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
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
                account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
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
                account_id      INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
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
                gold_price      REAL,
                gold_change_1h  REAL,
                gold_change_4h  REAL,
                gold_change_1d  REAL,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 7. Tạo bảng ea_heartbeat
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ea_heartbeat (
                account_id    INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
                last_ping     DATETIME,
                ea_version    TEXT DEFAULT '1.0',
                mt5_connected BOOLEAN DEFAULT 0
            );
        """)

        # 7.5. Tạo bảng action_history để lưu vết các hành động của EA
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS action_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id    INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                ticket        INTEGER,
                symbol        TEXT,
                action_type   TEXT NOT NULL,
                details       TEXT NOT NULL,
                pnl           REAL DEFAULT 0,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create signal_sources table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_sources (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                source_type     TEXT NOT NULL, -- 'telegram_group' hoặc 'tradingview'
                source_key      TEXT NOT NULL, -- Group ID hoặc Webhook token_key
                name            TEXT NOT NULL, -- Tên hiển thị thân thiện
                mode            TEXT DEFAULT 'queue', -- 'auto' hoặc 'queue'
                is_active       BOOLEAN DEFAULT 1,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, source_type, source_key)
            );
        """)

        # Check if is_active column exists in signal_sources table
        async with conn.execute("PRAGMA table_info(signal_sources);") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if columns and "is_active" not in columns:
                await conn.execute("ALTER TABLE signal_sources ADD COLUMN is_active BOOLEAN DEFAULT 1;")

        # 8. Tạo Indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_close_req ON trades(close_requested) WHERE close_requested = 1;")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_notified ON trades(notified) WHERE notified = 0;")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_queue_id ON signals(queue_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_history_account ON action_history(account_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_history_created ON action_history(created_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_sources_account ON signal_sources(account_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_sources_key ON signal_sources(source_type, source_key);")

        # 9. Seed Default Account if empty
        async with conn.execute("SELECT COUNT(*) FROM accounts") as cursor:
            row = await cursor.fetchone()
            if row[0] == 0:
                await conn.execute("""
                    INSERT INTO accounts (id, name, platform, account_number, token, is_active)
                    VALUES (1, 'Default MT5', 'MT5', '0', 'default-mt5-token', 1);
                """)

        # 10. Seed data - Config for default account
        configs = [
            ('mode', 'queue'),
            ('default_lot', '0.01'),
            ('queue_expire_minutes', '15'),
            ('sl_buffer_pips', '0'),
            ('trailing_enabled', 'true'),
            ('trailing_be_pips', '15'),       # Ngưỡng breakeven
            ('trailing_be_offset', '2'),      # Buffer pip trên entry
            ('trailing_step_pips', '10'),     # Bước trailing
            ('trailing_step_distance', '8'),  # Khoảng dời mỗi bước
            ('partial_close_enabled', 'false'),
            ('partial_close_pips', '30'),     # Ngưỡng chốt 1 phần (cũ)
            ('partial_close_ratio', '0.5'),   # Tỷ lệ chốt (cũ)
            ('partial_close_ratios', '33/33/33'), # Tỷ lệ chốt lời nhiều bước
            ('partial_close_pips_stages', '50/100/'), # Khoảng cách pips tương ứng cho từng bước
            ('trailing_manual_enabled', 'false'),  # Trailing cho lệnh thủ công
            ('default_sl_pips', '0')
        ]
        for key, value in configs:
            await conn.execute(
                "INSERT OR IGNORE INTO config (account_id, key, value) VALUES (1, ?, ?)",
                (key, value)
            )

        # 11. Seed data - Symbol mapping
        mappings = [
            ('GOLD', 'XAUUSDm'), ('gold', 'XAUUSDm'), ('Gold', 'XAUUSDm'),
            ('XAU', 'XAUUSDm'), ('xau', 'XAUUSDm'),
            ('XAUUSD', 'XAUUSDm'), ('xauusd', 'XAUUSDm'),
            ('XAUUSDT', 'XAUUSDm'), ('xauusdt', 'XAUUSDm'),
            ('Vàng', 'XAUUSDm'), ('vàng', 'XAUUSDm'), ('VÀNG', 'XAUUSDm')
        ]
        for alias, mt5_symbol in mappings:
            await conn.execute(
                "INSERT OR IGNORE INTO symbol_mapping (alias, mt5_symbol) VALUES (?, ?)",
                (alias, mt5_symbol)
            )

        # Cập nhật các bản ghi cũ từ XAUUSD -> XAUUSDm
        await conn.execute("UPDATE symbol_mapping SET mt5_symbol = 'XAUUSDm' WHERE mt5_symbol = 'XAUUSD';")

        # 12. Seed data - Account Info & Heartbeat default rows
        await conn.execute("INSERT OR IGNORE INTO account_info (account_id) VALUES (1);")
        await conn.execute("INSERT OR IGNORE INTO ea_heartbeat (account_id) VALUES (1);")

        # 13. Seed default Telegram signal sources from env if not present
        group_id = os.getenv("SIGNAL_GROUP_ID")
        backup_id = os.getenv("SIGNAL_GROUP_BACKUP_ID")
        default_mode = os.getenv("DEFAULT_MODE", "queue")

        async with conn.execute("SELECT id FROM accounts") as cursor:
            accounts = await cursor.fetchall()

        for acc in accounts:
            acc_id = acc[0]
            if group_id:
                await conn.execute("""
                    INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                    VALUES (?, 'telegram_group', ?, 'Kênh tín hiệu chính', ?);
                """, (acc_id, str(group_id), default_mode))
            if backup_id:
                await conn.execute("""
                    INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                    VALUES (?, 'telegram_group', ?, 'Kênh tín hiệu phụ', ?);
                """, (acc_id, str(backup_id), default_mode))

        await conn.commit()
