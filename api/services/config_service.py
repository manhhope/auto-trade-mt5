from datetime import datetime
from typing import Dict, Any, Optional
import aiosqlite

async def get_config_value(db: aiosqlite.Connection, key: str) -> Optional[str]:
    """Lấy giá trị cấu hình theo key"""
    async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

async def update_config_value(db: aiosqlite.Connection, key: str, value: str) -> bool:
    """Cập nhật hoặc thêm mới cấu hình"""
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        INSERT INTO config (key, value, updated_at) 
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now)
    )
    await db.commit()
    return True

async def get_all_configs(db: aiosqlite.Connection) -> Dict[str, Any]:
    """Lấy toàn bộ cấu hình, bao gồm cả lot overrides"""
    configs = {}
    async with db.execute("SELECT key, value FROM config") as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            configs[r["key"]] = r["value"]
            
    # Lấy lot overrides
    lot_overrides = {}
    async with db.execute("SELECT symbol, lot_size FROM lot_overrides") as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            lot_overrides[r["symbol"]] = r["lot_size"]
            
    configs["lot_overrides"] = lot_overrides
    return configs

async def get_all_lot_overrides(db: aiosqlite.Connection) -> Dict[str, float]:
    """Lấy danh sách lot overrides"""
    overrides = {}
    async with db.execute("SELECT symbol, lot_size FROM lot_overrides") as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            overrides[r["symbol"]] = r["lot_size"]
    return overrides

async def update_lot_override(db: aiosqlite.Connection, symbol: str, lot_size: float) -> bool:
    """Cập nhật hoặc thêm mới lot override cho symbol"""
    symbol_upper = symbol.upper()
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        INSERT INTO lot_overrides (symbol, lot_size, updated_at) 
        VALUES (?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET lot_size = excluded.lot_size, updated_at = excluded.updated_at
        """,
        (symbol_upper, lot_size, now)
    )
    await db.commit()
    return True

async def delete_lot_override(db: aiosqlite.Connection, symbol: str) -> bool:
    """Xóa lot override của symbol"""
    symbol_upper = symbol.upper()
    cursor = await db.execute("DELETE FROM lot_overrides WHERE symbol = ?", (symbol_upper,))
    await db.commit()
    return cursor.rowcount > 0
