import os
import sqlite3
from dotenv import load_dotenv

# Load env variables
load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/trades.db")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "717160491")

def run_migration():
    if not os.path.exists(DATABASE_PATH):
        print(f"No database found at {DATABASE_PATH}. No migration needed.")
        return

    print(f"Starting database migration v2 on {DATABASE_PATH}...")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION;")

        # 1. Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     TEXT UNIQUE NOT NULL,
                username        TEXT,
                is_approved     BOOLEAN DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Ensured users table exists.")

        # 2. Insert default Admin user
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, telegram_id, username, is_approved)
            VALUES (1, ?, 'admin', 1);
        """, (str(OWNER_CHAT_ID),))
        print(f"Ensured Admin user (telegram_id={OWNER_CHAT_ID}) exists with ID 1.")

        # 3. Add user_id column to accounts if missing
        cursor.execute("PRAGMA table_info(accounts);")
        columns = [row['name'] for row in cursor.fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;")
            print("Added user_id column to accounts table.")
        
        # 4. Associate existing accounts with Admin user (id=1)
        cursor.execute("UPDATE accounts SET user_id = 1 WHERE user_id IS NULL;")
        print("Associated existing accounts with Admin user.")

        # 5. Create signal_sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_sources (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                source_type     TEXT NOT NULL, -- 'telegram_group' hoặc 'tradingview'
                source_key      TEXT NOT NULL, -- Group ID hoặc Webhook token_key
                name            TEXT NOT NULL, -- Tên hiển thị thân thiện
                mode            TEXT DEFAULT 'queue', -- 'auto' hoặc 'queue'
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, source_type, source_key)
            );
        """)
        print("Ensured signal_sources table exists.")

        # Create indexes for signal_sources
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_sources_account ON signal_sources(account_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_sources_key ON signal_sources(source_type, source_key);")
        print("Ensured indexes for signal_sources exist.")

        # 6. Migrate existing signal_group_id config to signal_sources
        # We find signal_group_id and mode config for each account
        cursor.execute("SELECT DISTINCT account_id FROM config;")
        account_ids = [row['account_id'] for row in cursor.fetchall()]

        for acc_id in account_ids:
            # Get signal_group_id
            cursor.execute("SELECT value FROM config WHERE account_id = ? AND key = 'signal_group_id';", (acc_id,))
            group_row = cursor.fetchone()
            # Get mode
            cursor.execute("SELECT value FROM config WHERE account_id = ? AND key = 'mode';", (acc_id,))
            mode_row = cursor.fetchone()

            group_id = group_row['value'] if group_row else None
            mode_val = mode_row['value'] if mode_row else 'queue'

            if group_id:
                # Insert primary source
                cursor.execute("""
                    INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                    VALUES (?, 'telegram_group', ?, 'Default Group', ?);
                """, (acc_id, str(group_id), mode_val))
                print(f"Migrated signal_group_id config for account {acc_id} to signal_sources.")

            # Also check if signal_group_backup_id config exists
            cursor.execute("SELECT value FROM config WHERE account_id = ? AND key = 'signal_group_backup_id';", (acc_id,))
            backup_row = cursor.fetchone()
            backup_id = backup_row['value'] if backup_row else None

            if backup_id:
                # Insert backup source
                cursor.execute("""
                    INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                    VALUES (?, 'telegram_group', ?, 'Backup Group', ?);
                """, (acc_id, str(backup_id), mode_val))
                print(f"Migrated signal_group_backup_id config for account {acc_id} to signal_sources.")

        conn.commit()
        print("Migration v2 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration v2 FAILED: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
