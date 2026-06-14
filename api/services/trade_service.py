import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import aiosqlite
from api.models import (
    TradeCreateRequest, TradeUpdateRequest, TradeResponse, 
    TradeStatus, TradeSource, CloseReason
)

async def dict_from_row(row: aiosqlite.Row) -> Dict[str, Any]:
    """Helper to convert row to dict, converting boolean ints to bools"""
    d = dict(row)
    if "close_requested" in d:
        d["close_requested"] = bool(d["close_requested"])
    if "notified" in d:
        d["notified"] = bool(d["notified"])
    return d

async def get_mapped_symbol(db: aiosqlite.Connection, symbol_alias: str) -> Optional[str]:
    """Lấy MT5 symbol thực tế từ alias"""
    async with db.execute(
        "SELECT mt5_symbol FROM symbol_mapping WHERE alias = ? OR mt5_symbol = ?", 
        (symbol_alias, symbol_alias)
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

async def create_trade(db: aiosqlite.Connection, req: TradeCreateRequest) -> Dict[str, Any]:
    """Tạo mới một trade ở trạng thái PENDING"""
    # 1. Resolve symbol
    mt5_symbol = await get_mapped_symbol(db, req.symbol)
    if not mt5_symbol:
        raise ValueError(f"Symbol '{req.symbol}' không được hỗ trợ hoặc chưa được cấu hình mapping.")
        
    # 2. Check duplicate UUID
    async with db.execute("SELECT id FROM trades WHERE uuid = ?", (req.uuid,)) as cursor:
        if await cursor.fetchone():
            raise ValueError(f"Trade với UUID '{req.uuid}' đã tồn tại (Duplicate).")
            
    # 3. Validate pending order
    if req.trade_type in ["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"] and req.price is None:
        raise ValueError("Lệnh chờ (limit/stop) yêu cầu phải có giá (price).")
        
    # 4. Insert into DB
    cursor = await db.execute(
        """
        INSERT INTO trades (
            uuid, signal_id, source, symbol, trade_type, lot_size, 
            price, stop_loss, take_profit, status, close_requested, notified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, 0)
        """,
        (
            req.uuid, req.signal_id, req.source.value, mt5_symbol, req.trade_type.value,
            req.lot_size, req.price, req.stop_loss, req.take_profit
        )
    )
    trade_id = cursor.lastrowid
    await db.commit()
    
    # 5. Fetch and return
    async with db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)) as c:
        row = await c.fetchone()
        return await dict_from_row(row)

async def get_trades(
    db: aiosqlite.Connection,
    status: Optional[str] = None,
    close_requested: Optional[bool] = None,
    notified: Optional[bool] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lấy danh sách trades theo các bộ lọc"""
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    
    if status is not None:
        query += " AND status = ?"
        params.append(status)
        
    if close_requested is not None:
        query += " AND close_requested = ?"
        params.append(1 if close_requested else 0)
        
    if notified is not None:
        query += " AND notified = ?"
        params.append(1 if notified else 0)
        
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [await dict_from_row(row) for row in rows]

async def get_trade_by_id(db: aiosqlite.Connection, trade_id: int) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết trade theo ID"""
    async with db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)) as cursor:
        row = await cursor.fetchone()
        return await dict_from_row(row) if row else None

async def update_trade(
    db: aiosqlite.Connection, 
    trade_id: int, 
    req: TradeUpdateRequest
) -> Optional[Dict[str, Any]]:
    """Cập nhật trạng thái trade (gọi bởi EA)"""
    # 1. Check if trade exists
    existing = await get_trade_by_id(db, trade_id)
    if not existing:
        return None
        
    now = datetime.utcnow().isoformat()
    
    # Chuẩn bị câu lệnh SQL động
    updates = ["status = ?", "updated_at = ?"]
    params = [req.status.value, now]
    
    if req.ticket is not None:
        updates.append("ticket = ?")
        params.append(req.ticket)
        
    if req.open_price is not None:
        updates.append("open_price = ?")
        params.append(req.open_price)
        
    if req.close_price is not None:
        updates.append("close_price = ?")
        params.append(req.close_price)
        
    if req.pnl is not None:
        updates.append("pnl = ?")
        params.append(req.pnl)
        
    if req.pnl_pips is not None:
        updates.append("pnl_pips = ?")
        params.append(req.pnl_pips)
        
    if req.commission is not None:
        updates.append("commission = ?")
        params.append(req.commission)
        
    if req.swap is not None:
        updates.append("swap = ?")
        params.append(req.swap)
        
    if req.error_code is not None:
        updates.append("error_code = ?")
        params.append(req.error_code)
        
    if req.error_msg is not None:
        updates.append("error_msg = ?")
        params.append(req.error_msg)
        
    if req.close_reason is not None:
        updates.append("close_reason = ?")
        params.append(req.close_reason.value)

    # Tự động ghi nhận thời gian khớp lệnh và đóng lệnh
    if req.status == TradeStatus.FILLED and not existing.get("opened_at"):
        updates.append("opened_at = ?")
        params.append(now)
        
    if req.status == TradeStatus.CLOSED and not existing.get("closed_at"):
        updates.append("closed_at = ?")
        params.append(now)
        
    query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
    params.append(trade_id)
    
    await db.execute(query, params)
    await db.commit()
    
    return await get_trade_by_id(db, trade_id)

async def cancel_pending_trade(db: aiosqlite.Connection, trade_id: int) -> Optional[Dict[str, Any]]:
    """Huỷ lệnh pending (chuyển sang CANCELLED)"""
    existing = await get_trade_by_id(db, trade_id)
    if not existing:
        return None
        
    if existing["status"] != TradeStatus.PENDING.value:
        raise ValueError(f"Không thể hủy lệnh đang ở trạng thái {existing['status']}. Chỉ có thể hủy lệnh PENDING.")
        
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE trades SET status = 'CANCELLED', updated_at = ? WHERE id = ?",
        (now, trade_id)
    )
    await db.commit()
    return await get_trade_by_id(db, trade_id)

async def request_close_trade(db: aiosqlite.Connection, trade_id: int) -> Optional[Dict[str, Any]]:
    """Yêu cầu đóng lệnh đang mở (set close_requested = 1)"""
    existing = await get_trade_by_id(db, trade_id)
    if not existing:
        return None
        
    if existing["status"] != TradeStatus.FILLED.value:
        raise ValueError("Chỉ có thể yêu cầu đóng lệnh đang ở trạng thái FILLED (đang chạy).")
        
    await db.execute("UPDATE trades SET close_requested = 1 WHERE id = ?", (trade_id,))
    await db.commit()
    return await get_trade_by_id(db, trade_id)

async def mark_trade_notified(db: aiosqlite.Connection, trade_id: int) -> bool:
    """Đánh dấu lệnh đã thông báo đóng cho Telegram Bot"""
    cursor = await db.execute("UPDATE trades SET notified = 1 WHERE id = ?", (trade_id,))
    await db.commit()
    return cursor.rowcount > 0
