from datetime import datetime
from typing import Dict, Any, Optional
import aiosqlite

async def get_active_account_id(db: aiosqlite.Connection) -> int:
    """Lấy ID của tài khoản đang active"""
    async with db.execute("SELECT id FROM accounts WHERE is_active = 1 LIMIT 1") as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 1

async def get_config_value(db: aiosqlite.Connection, key: str, account_id: Optional[int] = None) -> Optional[str]:
    """Lấy giá trị cấu hình theo key cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    async with db.execute("SELECT value FROM config WHERE account_id = ? AND key = ?", (account_id, key)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

async def update_config_value(db: aiosqlite.Connection, key: str, value: str, account_id: Optional[int] = None) -> bool:
    """Cập nhật hoặc thêm mới cấu hình cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        INSERT INTO config (account_id, key, value, updated_at) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(account_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (account_id, key, value, now)
    )
    await db.commit()
    return True

async def get_all_configs(db: aiosqlite.Connection, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Lấy toàn bộ cấu hình, bao gồm cả lot overrides cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    configs = {}
    async with db.execute("SELECT key, value FROM config WHERE account_id = ?", (account_id,)) as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            configs[r["key"]] = r["value"]
            
    # Lấy lot overrides
    lot_overrides = {}
    async with db.execute("SELECT symbol, lot_size FROM lot_overrides WHERE account_id = ?", (account_id,)) as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            lot_overrides[r["symbol"]] = r["lot_size"]
            
    configs["lot_overrides"] = lot_overrides
    return configs

async def get_all_lot_overrides(db: aiosqlite.Connection, account_id: Optional[int] = None) -> Dict[str, float]:
    """Lấy danh sách lot overrides cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    overrides = {}
    async with db.execute("SELECT symbol, lot_size FROM lot_overrides WHERE account_id = ?", (account_id,)) as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            overrides[r["symbol"]] = r["lot_size"]
    return overrides

async def update_lot_override(db: aiosqlite.Connection, symbol: str, lot_size: float, account_id: Optional[int] = None) -> bool:
    """Cập nhật hoặc thêm mới lot override cho symbol cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    symbol_upper = symbol.upper()
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        INSERT INTO lot_overrides (account_id, symbol, lot_size, updated_at) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(account_id, symbol) DO UPDATE SET lot_size = excluded.lot_size, updated_at = excluded.updated_at
        """,
        (account_id, symbol_upper, lot_size, now)
    )
    await db.commit()
    return True

async def delete_lot_override(db: aiosqlite.Connection, symbol: str, account_id: Optional[int] = None) -> bool:
    """Xóa lot override của symbol cho tài khoản chỉ định"""
    if account_id is None:
        account_id = await get_active_account_id(db)
    symbol_upper = symbol.upper()
    cursor = await db.execute("DELETE FROM lot_overrides WHERE account_id = ? AND symbol = ?", (account_id, symbol_upper))
    await db.commit()
    return cursor.rowcount > 0
