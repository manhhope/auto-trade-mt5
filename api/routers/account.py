from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite
from datetime import datetime
from typing import List
from api.database import get_db
from api.models import AccountUpdateRequest, AccountResponse, PositionsSyncRequest
import api.services.trade_service as trade_service

router = APIRouter(tags=["Account & Positions"])

@router.put("/api/account", response_model=AccountResponse)
async def sync_account_info(req: AccountUpdateRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đồng bộ thông tin tài khoản giao dịch từ EA trên MT5.
    """
    now = datetime.utcnow().isoformat()
    try:
        await db.execute(
            """
            INSERT INTO account_info (
                id, balance, equity, margin, free_margin, profit, 
                server, account_number, account_name, currency, leverage, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                balance = excluded.balance,
                equity = excluded.equity,
                margin = excluded.margin,
                free_margin = excluded.free_margin,
                profit = excluded.profit,
                server = excluded.server,
                account_number = excluded.account_number,
                account_name = excluded.account_name,
                currency = excluded.currency,
                leverage = excluded.leverage,
                updated_at = excluded.updated_at
            """,
            (
                req.balance, req.equity, req.margin, req.free_margin, req.profit,
                req.server, req.account_number, req.account_name, req.currency, req.leverage, now
            )
        )
        await db.commit()
        
        # Cập nhật ping của EA để báo hiệu EA hoạt động bình thường (Heartbeat)
        await db.execute(
            "UPDATE ea_heartbeat SET last_ping = ?, mt5_connected = 1 WHERE id = 1",
            (now,)
        )
        await db.commit()
        
        async with db.execute("SELECT * FROM account_info WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/account", response_model=AccountResponse)
async def get_account_info(db: aiosqlite.Connection = Depends(get_db)):
    """
    Lấy thông tin tài khoản hiện tại (gọi bởi Telegram Bot).
    """
    async with db.execute("SELECT * FROM account_info WHERE id = 1") as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có thông tin tài khoản")
        return dict(row)

@router.put("/api/positions")
async def sync_positions(req: PositionsSyncRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đồng bộ các vị thế đang mở từ EA để phát hiện lệnh tự động đóng (Auto-close detection).
    """
    try:
        now = datetime.utcnow().isoformat()
        
        # 1. Thu thập danh sách ticket đang mở từ EA
        active_tickets = {pos.ticket for pos in req.positions}
        
        # 2. Lấy danh sách lệnh đang ở trạng thái FILLED trong DB
        filled_trades = []
        async with db.execute("SELECT id, ticket, symbol, trade_type, open_price, stop_loss, take_profit, lot_size FROM trades WHERE status = 'FILLED'") as cursor:
            rows = await cursor.fetchall()
            filled_trades = [dict(r) for r in rows]
            
        closed_trade_ids = []
        
        # 3. Duyệt và so sánh để tìm lệnh đã đóng
        for trade in filled_trades:
            ticket = trade.get("ticket")
            if not ticket:
                continue
                
            # Nếu ticket của lệnh trong DB không nằm trong danh sách đang mở của EA => Lệnh đã đóng!
            if ticket not in active_tickets:
                trade_id = trade["id"]
                
                # Xác định P/L ước tính hoặc dựa trên giá hiện tại
                # EA sẽ cập nhật giá đóng chính xác qua PUT /api/trades/{id} sau đó.
                # Ở bước này chúng ta xác định lý do đóng cơ bản
                close_reason = "MANUAL"
                close_price = trade["open_price"]
                
                # Cập nhật trạng thái lệnh trong DB thành CLOSED
                await db.execute(
                    """
                    UPDATE trades 
                    SET status = 'CLOSED', closed_at = ?, close_reason = ?, close_price = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, close_reason, close_price, now, trade_id)
                )
                closed_trade_ids.append(trade_id)
                
        if closed_trade_ids:
            await db.commit()
            
        return {
            "status": "success",
            "closed_trade_ids": closed_trade_ids,
            "active_count": len(active_tickets)
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/positions")
async def list_active_positions(db: aiosqlite.Connection = Depends(get_db)):
    """
    Lấy danh sách các lệnh đang chạy (FILLED) trong DB (gọi bởi Telegram Bot).
    """
    try:
        async with db.execute("SELECT * FROM trades WHERE status = 'FILLED' ORDER BY opened_at DESC") as cursor:
            rows = await cursor.fetchall()
            # Convert rows to dicts
            trades = []
            for r in rows:
                d = dict(r)
                d["close_requested"] = bool(d["close_requested"])
                d["notified"] = bool(d["notified"])
                trades.append(d)
            return trades
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
