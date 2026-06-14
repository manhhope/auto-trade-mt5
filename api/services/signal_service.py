import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import aiosqlite
from api.models import (
    SignalCreateRequest, SignalConfirmRequest, SignalStatus, 
    TradeCreateRequest, TradeSource, TradeType
)
import api.services.trade_service as trade_service
import api.services.config_service as config_service

async def dict_from_signal_row(row: aiosqlite.Row) -> Dict[str, Any]:
    """Helper to convert signal row to dict, converting boolean ints to bools"""
    d = dict(row)
    if "parse_success" in d:
        d["parse_success"] = bool(d["parse_success"])
    return d

async def create_signal(db: aiosqlite.Connection, req: SignalCreateRequest) -> Dict[str, Any]:
    """Tạo mới một tín hiệu từ group"""
    # 1. Chèn tạm thời với temp queue_id
    temp_uuid = f"TEMP-{uuid.uuid4()}"
    status = SignalStatus.QUEUED.value if req.parse_success else SignalStatus.PARSE_FAILED.value
    
    cursor = await db.execute(
        """
        INSERT INTO signals (
            queue_id, group_id, message_id, raw_message, parsed_type, 
            parsed_symbol, parsed_price, parsed_sl, parsed_tp, parse_success, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            temp_uuid, req.group_id, req.message_id, req.raw_message, req.parsed_type,
            req.parsed_symbol, req.parsed_price, req.parsed_sl, req.parsed_tp,
            1 if req.parse_success else 0, status
        )
    )
    insert_id = cursor.lastrowid
    
    # 2. Cập nhật queue_id chuẩn định dạng: SIG-0042
    queue_id = f"SIG-{insert_id:04d}"
    await db.execute("UPDATE signals SET queue_id = ? WHERE id = ?", (queue_id, insert_id))
    await db.commit()
    
    # 3. Lấy lại bản ghi đầy đủ
    async with db.execute("SELECT * FROM signals WHERE id = ?", (insert_id,)) as c:
        row = await c.fetchone()
        signal_dict = await dict_from_signal_row(row)
        
    # 4. Kiểm tra chế độ Auto Mode để tự động confirm lệnh ngay lập tức
    if req.parse_success:
        mode = await config_service.get_config_value(db, "mode")
        if mode == "auto":
            # Tự động confirm lệnh
            trade = await confirm_signal(db, insert_id, SignalConfirmRequest(lot_override=None))
            signal_dict["status"] = SignalStatus.EXECUTED.value
            signal_dict["auto_executed_trade"] = trade
            
    return signal_dict

async def get_signals(db: aiosqlite.Connection, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lấy danh sách tín hiệu"""
    query = "SELECT * FROM signals WHERE 1=1"
    params = []
    
    if status is not None:
        query += " AND status = ?"
        params.append(status)
        
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [await dict_from_signal_row(row) for row in rows]

async def get_signal_by_id_or_queue_id(db: aiosqlite.Connection, id_or_queue_id: str) -> Optional[Dict[str, Any]]:
    """Tìm kiếm signal qua ID (số) hoặc queue_id (chuỗi như SIG-0042)"""
    query = "SELECT * FROM signals WHERE "
    if id_or_queue_id.isdigit():
        query += "id = ?"
        param = int(id_or_queue_id)
    else:
        query += "queue_id = ?"
        param = id_or_queue_id
        
    async with db.execute(query, (param,)) as cursor:
        row = await cursor.fetchone()
        return await dict_from_signal_row(row) if row else None

async def confirm_signal(db: aiosqlite.Connection, signal_id_or_queue_id: Any, req: SignalConfirmRequest) -> Dict[str, Any]:
    """Xác nhận tín hiệu từ hàng đợi, tạo lệnh giao dịch PENDING gửi đi EA"""
    # 1. Lấy thông tin signal
    signal = await get_signal_by_id_or_queue_id(db, str(signal_id_or_queue_id))
    if not signal:
        raise ValueError(f"Không tìm thấy tín hiệu với ID/QueueID: {signal_id_or_queue_id}")
        
    if signal["status"] != SignalStatus.QUEUED.value:
        raise ValueError(f"Tín hiệu đang ở trạng thái {signal['status']}. Chỉ có thể xác nhận tín hiệu đang chờ duyệt (QUEUED).")
        
    # 2. Xác định volume (lot size) theo thứ tự ưu tiên:
    # lot_override (từ tham số xác nhận) > lot_overrides[symbol] (trong bảng ghi đè) > default_lot (cấu hình chung)
    lot_size = req.lot_override
    symbol = signal["parsed_symbol"]
    
    if not lot_size:
        # Kiểm tra override theo symbol
        async with db.execute("SELECT lot_size FROM lot_overrides WHERE symbol = ?", (symbol,)) as cursor:
            row = await cursor.fetchone()
            if row:
                lot_size = row[0]
                
    if not lot_size:
        # Lấy default lot từ cấu hình
        default_lot_str = await config_service.get_config_value(db, "default_lot")
        lot_size = float(default_lot_str) if default_lot_str else 0.01

    # 3. Tạo trade trên MT5 (Luôn là market order cho signal)
    trade_uuid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    # Cập nhật trạng thái signal thành CONFIRMED
    await db.execute(
        "UPDATE signals SET status = 'EXECUTED', lot_override = ?, confirmed_at = ? WHERE id = ?",
        (lot_size, now, signal["id"])
    )
    
    # Tạo trade record
    trade_req = TradeCreateRequest(
        uuid=trade_uuid,
        symbol=symbol,
        trade_type=TradeType(signal["parsed_type"]),
        lot_size=lot_size,
        price=None, # Market order
        stop_loss=signal["parsed_sl"],
        take_profit=signal["parsed_tp"],
        signal_id=signal["id"],
        source=TradeSource.SIGNAL
    )
    
    trade = await trade_service.create_trade(db, trade_req)
    await db.commit()
    
    return trade

async def reject_signal(db: aiosqlite.Connection, signal_id_or_queue_id: Any) -> Dict[str, Any]:
    """Từ chối tín hiệu trong hàng đợi"""
    signal = await get_signal_by_id_or_queue_id(db, str(signal_id_or_queue_id))
    if not signal:
        raise ValueError(f"Không tìm thấy tín hiệu với ID/QueueID: {signal_id_or_queue_id}")
        
    if signal["status"] != SignalStatus.QUEUED.value:
        raise ValueError(f"Tín hiệu đang ở trạng thái {signal['status']}. Chỉ có thể từ chối tín hiệu QUEUED.")
        
    await db.execute(
        "UPDATE signals SET status = 'REJECTED' WHERE id = ?",
        (signal["id"],)
    )
    await db.commit()
    
    async with db.execute("SELECT * FROM signals WHERE id = ?", (signal["id"],)) as cursor:
        row = await cursor.fetchone()
        return await dict_from_signal_row(row)

async def confirm_all_signals(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Duyệt tất cả tín hiệu QUEUED trong hàng đợi"""
    async with db.execute("SELECT id FROM signals WHERE status = 'QUEUED'") as cursor:
        rows = await cursor.fetchall()
        signal_ids = [r["id"] for r in rows]
        
    trades = []
    for sig_id in signal_ids:
        try:
            trade = await confirm_signal(db, sig_id, SignalConfirmRequest(lot_override=None))
            trades.append(trade)
        except Exception:
            continue
    return trades

async def reject_all_signals(db: aiosqlite.Connection) -> int:
    """Từ chối tất cả tín hiệu QUEUED trong hàng đợi"""
    cursor = await db.execute("UPDATE signals SET status = 'REJECTED' WHERE status = 'QUEUED'")
    await db.commit()
    return cursor.rowcount
