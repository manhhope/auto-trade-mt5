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
    # Resolve account_id
    account_id = req.account_id
    if not account_id:
        account_id = await config_service.get_active_account_id(db)

    # 1. Chèn tạm thời với temp queue_id
    temp_uuid = f"TEMP-{uuid.uuid4()}"
    status = SignalStatus.QUEUED.value if req.parse_success else SignalStatus.PARSE_FAILED.value
    
    # Tự động sửa/hoàn thiện SL và TP viết tắt đối với Vàng
    symbol = req.parsed_symbol
    parsed_sl = req.parsed_sl
    parsed_tp = req.parsed_tp
    parsed_price = req.parsed_price
    
    if symbol and ("XAU" in symbol.upper() or "GOLD" in symbol.upper() or "VÀNG" in symbol.upper()):
        ref_price = 0.0
        if parsed_price and parsed_price >= 1000:
            ref_price = parsed_price
        else:
            async with db.execute("SELECT gold_price FROM account_info WHERE account_id = ?", (account_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    ref_price = row[0]
                    
        if ref_price > 0:
            def expand_gold_val(val: Optional[float], ref: float) -> Optional[float]:
                if val is None or val >= 1000 or val <= 0:
                    return val
                mod = 1000 if val >= 100 else 100
                ref_base = ref - (ref % mod)
                c1 = ref_base + val
                c2 = ref_base - mod + val
                c3 = ref_base + mod + val
                return round(min([c1, c2, c3], key=lambda c: abs(c - ref)), 2)
                
            parsed_sl = expand_gold_val(parsed_sl, ref_price)
            parsed_tp = expand_gold_val(parsed_tp, ref_price)
            parsed_price = expand_gold_val(parsed_price, ref_price)

    cursor = await db.execute(
        """
        INSERT INTO signals (
            queue_id, account_id, group_id, message_id, raw_message, parsed_type, 
            parsed_symbol, parsed_price, parsed_sl, parsed_tp, parse_success, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            temp_uuid, account_id, req.group_id, req.message_id, req.raw_message, req.parsed_type,
            req.parsed_symbol, parsed_price, parsed_sl, parsed_tp,
            1 if req.parse_success else 0, status
        )
    )
    insert_id = cursor.lastrowid
    await db.commit()   # 2. Cập nhật queue_id chuẩn định dạng: SIG-0042
    queue_id = f"SIG-{insert_id:04d}"
    await db.execute("UPDATE signals SET queue_id = ? WHERE id = ?", (queue_id, insert_id))
    await db.commit()
    
    # 3. Lấy lại bản ghi đầy đủ
    async with db.execute("SELECT * FROM signals WHERE id = ?", (insert_id,)) as c:
        row = await c.fetchone()
        signal_dict = await dict_from_signal_row(row)
        
    # 4. Kiểm tra chế độ Auto Mode để tự động confirm lệnh ngay lập tức
    if req.parse_success:
        mode = await config_service.get_config_value(db, "mode", account_id)
        if mode == "auto":
            # Tự động confirm lệnh
            trade = await confirm_signal(db, insert_id, SignalConfirmRequest(lot_override=None))
            signal_dict["status"] = SignalStatus.EXECUTED.value
            signal_dict["auto_executed_trade"] = trade
            
    return signal_dict

async def get_signals(
    db: aiosqlite.Connection, 
    status: Optional[str] = None, 
    limit: int = 50,
    account_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Lấy danh sách tín hiệu"""
    query = "SELECT * FROM signals WHERE 1=1"
    params = []
    
    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)
        
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
        
    # 2. Xác định các tài khoản đích để giao dịch
    active_id = await config_service.get_active_account_id(db)
    
    # Đọc cấu hình chế độ chạy tín hiệu của tài khoản active
    signal_mode = await config_service.get_config_value(db, "signal_execution_mode", active_id) or "active"
    
    if signal_mode == "all":
        async with db.execute("SELECT id FROM accounts") as cursor:
            rows = await cursor.fetchall()
            account_ids = [r["id"] for r in rows]
    else:
        account_ids = [active_id]
        
    # Cập nhật trạng thái signal thành EXECUTED
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE signals SET status = 'EXECUTED', lot_override = ?, confirmed_at = ? WHERE id = ?",
        (req.lot_override, now, signal["id"])
    )
    
    main_trade = None
    for target_acc_id in account_ids:
        # Xác định volume (lot size) cho từng tài khoản:
        # lot_override (từ tham số xác nhận) > lot_overrides[symbol] (trong bảng ghi đè) > default_lot (cấu hình chung)
        lot_size = req.lot_override
        symbol = signal["parsed_symbol"]
        
        if not lot_size:
            # Kiểm tra override theo symbol cho tài khoản này
            async with db.execute("SELECT lot_size FROM lot_overrides WHERE account_id = ? AND symbol = ?", (target_acc_id, symbol)) as cursor:
                row = await cursor.fetchone()
                if row:
                    lot_size = row[0]
                    
        if not lot_size:
            # Lấy default lot từ cấu hình của tài khoản này
            default_lot_str = await config_service.get_config_value(db, "default_lot", target_acc_id)
            lot_size = float(default_lot_str) if default_lot_str else 0.01

        # Tạo trade trên từng tài khoản
        trade_uuid = str(uuid.uuid4())
        trade_req = TradeCreateRequest(
            uuid=trade_uuid,
            symbol=symbol,
            trade_type=TradeType(signal["parsed_type"]),
            lot_size=lot_size,
            price=None, # Market order
            stop_loss=signal["parsed_sl"],
            take_profit=signal["parsed_tp"],
            signal_id=signal["id"],
            source=TradeSource.SIGNAL,
            account_id=target_acc_id
        )
        
        trade = await trade_service.create_trade(db, trade_req)
        
        # Đặt main_trade là trade của tài khoản active hoặc trade đầu tiên để trả về cho API response
        if target_acc_id == active_id or main_trade is None:
            main_trade = trade
            
    await db.commit()
    return main_trade

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
