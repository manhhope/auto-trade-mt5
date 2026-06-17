import os
import sqlite3
import uuid
from datetime import datetime

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/trades.db")

def run_migration():
    if not os.path.exists(DATABASE_PATH):
        print(f"No database found at {DATABASE_PATH}. Initialization will happen automatically on start.")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if accounts table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts';")
    if cursor.fetchone():
        print("Database already migrated. Accounts table exists.")
        conn.close()
        return

    print("Starting database migration to support multi-account structure...")

    # Extract info from old account_info if it exists
    old_acc_num = 0
    old_acc_name = "BTC - NEW"
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_info';")
    if cursor.fetchone():
        try:
            cursor.execute("SELECT account_number, account_name, server FROM account_info WHERE id=1;")
            row = cursor.fetchone()
            if row:
                old_acc_num = row['account_number'] or 0
                old_acc_name = row['account_name'] or "BTC - NEW"
                row['server'] or "Exness-MT5Real24"
        except Exception as e:
            print(f"Warning: Could not retrieve old account details: {e}")

    # Generate a secure token for the default account
    default_token = uuid.uuid4().hex
    print(f"Generated secure token for default account ({old_acc_name}): {default_token}")

    try:
        cursor.execute("BEGIN TRANSACTION;")

        # Rename old tables
        tables_to_rename = ['config', 'lot_overrides', 'trades', 'account_info', 'ea_heartbeat', 'action_history', 'signals']
        for table in tables_to_rename:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old;")
                print(f"Renamed table {table} to {table}_old")

        # 1. Create accounts table
        cursor.execute("""
            CREATE TABLE accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                platform        TEXT NOT NULL,
                account_number  TEXT,
                token           TEXT UNIQUE NOT NULL,
                is_active       BOOLEAN DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Created accounts table")

        # 2. Insert default account (id=1)
        cursor.execute("""
            INSERT INTO accounts (id, name, platform, account_number, token, is_active)
            VALUES (1, ?, 'MT5', ?, ?, 1);
        """, (old_acc_name, str(old_acc_num), default_token))
        print("Inserted default account (id=1)")

        # 3. Create config table (with account_id)
        cursor.execute("""
            CREATE TABLE config (
                account_id  INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, key)
            );
        """)
        print("Created new config table")

        # Copy config data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_old';")
        if cursor.fetchone():
            cursor.execute("SELECT key, value, updated_at FROM config_old;")
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO config (account_id, key, value, updated_at)
                    VALUES (1, ?, ?, ?);
                """, (row['key'], row['value'], row['updated_at']))
            print("Migrated config data")

        # 4. Create lot_overrides table (with account_id)
        cursor.execute("""
            CREATE TABLE lot_overrides (
                account_id  INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                symbol      TEXT NOT NULL,
                lot_size    REAL NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, symbol)
            );
        """)
        print("Created new lot_overrides table")

        # Copy lot_overrides data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lot_overrides_old';")
        if cursor.fetchone():
            cursor.execute("SELECT symbol, lot_size, updated_at FROM lot_overrides_old;")
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO lot_overrides (account_id, symbol, lot_size, updated_at)
                    VALUES (1, ?, ?, ?);
                """, (row['symbol'], row['lot_size'], row['updated_at']))
            print("Migrated lot_overrides data")

        # 5. Create signals table (with account_id)
        cursor.execute("""
            CREATE TABLE signals (
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
        print("Created new signals table")

        # Copy signals data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals_old';")
        if cursor.fetchone():
            cursor.execute("""
                SELECT id, queue_id, group_id, message_id, raw_message, parsed_type, 
                       parsed_symbol, parsed_price, parsed_sl, parsed_tp, parse_success, 
                       status, lot_override, confirmed_at, created_at 
                FROM signals_old;
            """)
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO signals (
                        id, queue_id, account_id, group_id, message_id, raw_message, parsed_type,
                        parsed_symbol, parsed_price, parsed_sl, parsed_tp, parse_success, status,
                        lot_override, confirmed_at, created_at
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (row['id'], row['queue_id'], row['group_id'], row['message_id'], row['raw_message'],
                      row['parsed_type'], row['parsed_symbol'], row['parsed_price'], row['parsed_sl'],
                      row['parsed_tp'], row['parse_success'], row['status'], row['lot_override'],
                      row['confirmed_at'], row['created_at']))
            print("Migrated signals data")

        # 6. Create trades table (with account_id)
        cursor.execute("""
            CREATE TABLE trades (
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
        print("Created new trades table")

        # Copy trades data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades_old';")
        if cursor.fetchone():
            cursor.execute("""
                SELECT id, uuid, signal_id, source, symbol, trade_type, lot_size, price, 
                       stop_loss, take_profit, status, ticket, open_price, close_price, 
                       pnl, pnl_pips, commission, swap, error_code, error_msg, 
                       opened_at, closed_at, close_reason, close_requested, notified, 
                       created_at, updated_at 
                FROM trades_old;
            """)
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO trades (
                        id, uuid, account_id, signal_id, source, symbol, trade_type, lot_size, price,
                        stop_loss, take_profit, status, ticket, open_price, close_price, pnl, pnl_pips,
                        commission, swap, error_code, error_msg, opened_at, closed_at, close_reason,
                        close_requested, notified, created_at, updated_at
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (row['id'], row['uuid'], row['signal_id'], row['source'], row['symbol'], row['trade_type'],
                      row['lot_size'], row['price'], row['stop_loss'], row['take_profit'], row['status'],
                      row['ticket'], row['open_price'], row['close_price'], row['pnl'], row['pnl_pips'],
                      row['commission'], row['swap'], row['error_code'], row['error_msg'], row['opened_at'],
                      row['closed_at'], row['close_reason'], row['close_requested'], row['notified'],
                      row['created_at'], row['updated_at']))
            print("Migrated trades data")

        # 7. Create account_info table (with account_id PRIMARY KEY)
        cursor.execute("""
            CREATE TABLE account_info (
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
        print("Created new account_info table")

        # Copy account_info data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_info_old';")
        if cursor.fetchone():
            cursor.execute("""
                SELECT balance, equity, margin, free_margin, profit, server, account_number, 
                       account_name, currency, leverage, gold_price, gold_change_1h, 
                       gold_change_4h, gold_change_1d, updated_at 
                FROM account_info_old;
            """)
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO account_info (
                        account_id, balance, equity, margin, free_margin, profit, server, 
                        account_number, account_name, currency, leverage, gold_price, 
                        gold_change_1h, gold_change_4h, gold_change_1d, updated_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (row['balance'], row['equity'], row['margin'], row['free_margin'], row['profit'],
                      row['server'], row['account_number'], row['account_name'], row['currency'],
                      row['leverage'], row['gold_price'], row['gold_change_1h'], row['gold_change_4h'],
                      row['gold_change_1d'], row['updated_at']))
            print("Migrated account_info data")

        # 8. Create ea_heartbeat table (with account_id PRIMARY KEY)
        cursor.execute("""
            CREATE TABLE ea_heartbeat (
                account_id    INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
                last_ping     DATETIME,
                ea_version    TEXT DEFAULT '1.0',
                mt5_connected BOOLEAN DEFAULT 0
            );
        """)
        print("Created new ea_heartbeat table")

        # Copy ea_heartbeat data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ea_heartbeat_old';")
        if cursor.fetchone():
            cursor.execute("SELECT last_ping, ea_version, mt5_connected FROM ea_heartbeat_old;")
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO ea_heartbeat (account_id, last_ping, ea_version, mt5_connected)
                    VALUES (1, ?, ?, ?);
                """, (row['last_ping'], row['ea_version'], row['mt5_connected']))
            print("Migrated ea_heartbeat data")

        # 9. Create action_history table (with account_id)
        cursor.execute("""
            CREATE TABLE action_history (
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
        print("Created new action_history table")

        # Copy action_history data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='action_history_old';")
        if cursor.fetchone():
            cursor.execute("SELECT id, ticket, symbol, action_type, details, pnl, created_at FROM action_history_old;")
            for row in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO action_history (id, account_id, ticket, symbol, action_type, details, pnl, created_at)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?);
                """, (row['id'], row['ticket'], row['symbol'], row['action_type'], row['details'], row['pnl'], row['created_at']))
            print("Migrated action_history data")

        # Drop old tables first to automatically drop their indexes
        for table in tables_to_rename:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}_old';")
            if cursor.fetchone():
                cursor.execute(f"DROP TABLE {table}_old;")
                print(f"Dropped table {table}_old")

        # 10. Re-create Indexes
        cursor.execute("CREATE INDEX idx_trades_account ON trades(account_id);")
        cursor.execute("CREATE INDEX idx_trades_status ON trades(status);")
        cursor.execute("CREATE INDEX idx_trades_closed_at ON trades(closed_at);")
        cursor.execute("CREATE INDEX idx_trades_source ON trades(source);")
        cursor.execute("CREATE INDEX idx_trades_symbol ON trades(symbol);")
        cursor.execute("CREATE INDEX idx_trades_close_req ON trades(close_requested) WHERE close_requested = 1;")
        cursor.execute("CREATE INDEX idx_trades_notified ON trades(notified) WHERE notified = 0;")
        cursor.execute("CREATE INDEX idx_signals_status ON signals(status);")
        cursor.execute("CREATE INDEX idx_signals_created ON signals(created_at);")
        cursor.execute("CREATE INDEX idx_signals_queue_id ON signals(queue_id);")
        cursor.execute("CREATE INDEX idx_action_history_account ON action_history(account_id);")
        cursor.execute("CREATE INDEX idx_action_history_created ON action_history(created_at);")
        print("Re-created indexes")

        conn.commit()
        print("Migration committed successfully!")
        
        # Save token info to a file for reference
        with open("data/default_account_token.txt", "w") as f:
            f.write(f"Account: {old_acc_name}\n")
            f.write(f"Account Number: {old_acc_num}\n")
            f.write(f"Secure Token: {default_token}\n")
            f.write(f"Migration Datetime: {datetime.now().isoformat()}\n")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
