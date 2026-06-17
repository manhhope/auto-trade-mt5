from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import aiosqlite
from datetime import datetime
from typing import List, Optional
import asyncio
from api.database import get_db
from api.models import (
    AccountUpdateRequest, AccountResponse, PositionsSyncRequest, 
    ManualTradeSyncRequest, TradingAccountCreate, TradingAccountResponse
)
from api.services.config_service import get_active_account_id

# Các bộ đệm lưu trữ vị thế đang chạy, tách biệt theo account_id
G_ACTIVE_POSITIONS = {}      # account_id -> list of positions
G_CLOSE_TICKETS_QUEUE = {}   # account_id -> set of tickets
G_CLOSE_ATTEMPTS = {}        # account_id -> dict of ticket -> attempts

async def notify_close_failed(account_id: int, ticket: int, db: aiosqlite.Connection):
    try:
        from bot.main import bot
        from bot.config import config
        from bot.services.background_tasks import send_telegram_safe
        
        # Lấy thông tin tài khoản giao dịch
        async with db.execute("SELECT name, account_number FROM accounts WHERE id = ?", (account_id,)) as cursor:
            row = await cursor.fetchone()
            acc_name = row["name"] if row else f"ID {account_id}"
            acc_num = row["account_number"] if row else ""
            acc_str = f" [{acc_name} - {acc_num}]" if acc_num else f" [{acc_name}]"

        symbol = "XAUUSDm"
        trade_type = ""
        lot_size = 0.0
        is_manual = True
        
        # Tìm trong G_ACTIVE_POSITIONS của tài khoản này
        for pos in G_ACTIVE_POSITIONS.get(account_id, []):
            if pos.get("ticket") == ticket:
                symbol = pos.get("symbol", "XAUUSDm")
                trade_type = pos.get("trade_type", "")
                lot_size = pos.get("lot_size", 0.0)
                break
                
        # Tìm trong database
        async with db.execute("SELECT symbol, trade_type, lot_size FROM trades WHERE account_id = ? AND ticket = ?", (account_id, ticket)) as cursor:
            row = await cursor.fetchone()
            if row:
                symbol = row["symbol"]
                trade_type = row["trade_type"]
                lot_size = row["lot_size"]
                is_manual = False
                
        type_str = " [Thủ công]" if is_manual else ""
        detail_str = f"**{trade_type} {symbol} {lot_size:.2f}** " if trade_type else ""
        
        msg = (
            f"⚠️ **Yêu cầu đóng lệnh thất bại!**{acc_str}\n\n"
            f"Lệnh{type_str} {detail_str}(Ticket: `#{ticket}`) đã thử đóng 5 lần liên tiếp qua EA nhưng không thành công.\n"
            f"👉 Yêu cầu đóng lệnh này đã bị hủy bỏ để tránh quá tải. Vui lòng tự đóng lệnh bằng tay trên terminal hoặc kiểm tra nút **Algo Trading**."
        )
        
        await send_telegram_safe(bot, config.owner_chat_id, msg)
    except Exception as e:
        import logging
        logging.getLogger("api").error(f"Lỗi khi gửi thông báo đóng lệnh thất bại: {e}")

router = APIRouter(tags=["Account & Positions"])

@router.put("/api/account", response_model=AccountResponse)
async def sync_account_info(request: Request, req: AccountUpdateRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đồng bộ thông tin tài khoản giao dịch từ EA.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    else:
        # Nếu gọi bằng admin API key, tìm tài khoản khớp với account_number
        async with db.execute("SELECT id FROM accounts WHERE account_number = ? LIMIT 1", (str(req.account_number),)) as cursor:
            row = await cursor.fetchone()
            account_id = row[0] if row else 1

    now = datetime.utcnow().isoformat()
    try:
        await db.execute(
            """
            INSERT INTO account_info (
                account_id, balance, equity, margin, free_margin, profit, 
                server, account_number, account_name, currency, leverage, 
                gold_price, gold_change_1h, gold_change_4h, gold_change_1d, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
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
                gold_price = excluded.gold_price,
                gold_change_1h = excluded.gold_change_1h,
                gold_change_4h = excluded.gold_change_4h,
                gold_change_1d = excluded.gold_change_1d,
                updated_at = excluded.updated_at
            """,
            (
                account_id, req.balance, req.equity, req.margin, req.free_margin, req.profit,
                req.server, req.account_number, req.account_name, req.currency, req.leverage,
                req.gold_price, req.gold_change_1h, req.gold_change_4h, req.gold_change_1d, now
            )
        )
        await db.commit()
        
        # Cập nhật thông tin EA Heartbeat
        await db.execute(
            """
            INSERT INTO ea_heartbeat (account_id, last_ping, mt5_connected)
            VALUES (?, ?, 1)
            ON CONFLICT(account_id) DO UPDATE SET last_ping = excluded.last_ping, mt5_connected = 1
            """,
            (account_id, now)
        )
        await db.commit()
        
        async with db.execute("SELECT * FROM account_info WHERE account_id = ?", (account_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/account", response_model=AccountResponse)
async def get_account_info(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy thông tin tài khoản hiện tại (gọi bởi Telegram Bot).
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    async with db.execute("SELECT * FROM account_info WHERE account_id = ?", (account_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chưa có thông tin tài khoản ID {account_id}")
        return dict(row)

@router.put("/api/positions")
async def sync_positions(request: Request, req: PositionsSyncRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đồng bộ các vị thế đang mở từ EA để phát hiện lệnh tự động đóng (Auto-close detection).
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    else:
        account_id = await get_active_account_id(db)

    # Đảm bảo các bộ đệm cho tài khoản này đã được khởi tạo
    if account_id not in G_ACTIVE_POSITIONS:
        G_ACTIVE_POSITIONS[account_id] = []
    if account_id not in G_CLOSE_TICKETS_QUEUE:
        G_CLOSE_TICKETS_QUEUE[account_id] = set()
    if account_id not in G_CLOSE_ATTEMPTS:
        G_CLOSE_ATTEMPTS[account_id] = {}

    try:
        now = datetime.utcnow().isoformat()
        
        # 1. Thu thập danh sách ticket đang mở từ EA
        active_tickets = {pos.ticket for pos in req.positions}
        
        # Cập nhật cache positions thực tế
        G_ACTIVE_POSITIONS[account_id] = [pos.dict() for pos in req.positions]
        
        # Tự động dọn dẹp hàng đợi đóng lệnh (xóa ticket đã đóng thành công)
        G_CLOSE_TICKETS_QUEUE[account_id] = {ticket for ticket in G_CLOSE_TICKETS_QUEUE[account_id] if ticket in active_tickets}
        
        # Theo dõi số lần thử đóng lệnh thất bại
        tickets_to_remove = []
        for ticket in G_CLOSE_TICKETS_QUEUE[account_id]:
            if ticket in active_tickets:
                G_CLOSE_ATTEMPTS[account_id][ticket] = G_CLOSE_ATTEMPTS[account_id].get(ticket, 0) + 1
                if G_CLOSE_ATTEMPTS[account_id][ticket] >= 5:
                    tickets_to_remove.append(ticket)
                    
        for ticket in tickets_to_remove:
            G_CLOSE_TICKETS_QUEUE[account_id].remove(ticket)
            if ticket in G_CLOSE_ATTEMPTS[account_id]:
                del G_CLOSE_ATTEMPTS[account_id][ticket]
            # Gửi thông báo đến Telegram
            asyncio.create_task(notify_close_failed(account_id, ticket, db))
            
        # Dọn dẹp G_CLOSE_ATTEMPTS cho các ticket đã đóng thành công
        for ticket in list(G_CLOSE_ATTEMPTS[account_id].keys()):
            if ticket not in G_CLOSE_TICKETS_QUEUE[account_id]:
                del G_CLOSE_ATTEMPTS[account_id][ticket]
        
        # 2. Lấy danh sách lệnh đang ở trạng thái FILLED trong DB cho tài khoản này
        filled_trades = []
        async with db.execute("SELECT id, ticket, symbol, trade_type, open_price, stop_loss, take_profit, lot_size FROM trades WHERE account_id = ? AND status = 'FILLED'", (account_id,)) as cursor:
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
            "active_count": len(active_tickets),
            "close_tickets": list(G_CLOSE_TICKETS_QUEUE[account_id])
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/positions")
async def list_active_positions(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ áp dụng cho Admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy danh sách các vị thế thực tế đang chạy trên MT4/MT5.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    if account_id not in G_ACTIVE_POSITIONS:
        G_ACTIVE_POSITIONS[account_id] = []
    if account_id not in G_CLOSE_TICKETS_QUEUE:
        G_CLOSE_TICKETS_QUEUE[account_id] = set()

    try:
        # Lấy các lệnh FILLED trong DB để ánh xạ ID lệnh tự động
        async with db.execute("SELECT id, ticket, close_requested FROM trades WHERE account_id = ? AND status = 'FILLED'", (account_id,)) as cursor:
            rows = await cursor.fetchall()
            db_trades = {r["ticket"]: (r["id"], bool(r["close_requested"])) for r in rows}
            
        positions_extended = []
        for pos in G_ACTIVE_POSITIONS[account_id]:
            ticket = pos.get("ticket")
            db_info = db_trades.get(ticket)
            
            pos_dict = dict(pos)
            if db_info:
                pos_dict["id"] = db_info[0]
                pos_dict["close_requested"] = db_info[1] or (ticket in G_CLOSE_TICKETS_QUEUE[account_id])
                pos_dict["is_manual"] = False
            else:
                pos_dict["id"] = None
                pos_dict["close_requested"] = (ticket in G_CLOSE_TICKETS_QUEUE[account_id])
                pos_dict["is_manual"] = True
                
            positions_extended.append(pos_dict)
            
        return positions_extended
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/api/positions/{ticket}/close")
async def request_close_position_by_ticket(
    request: Request,
    ticket: int,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ áp dụng cho Admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Yêu cầu đóng vị thế theo số ticket (áp dụng cho cả lệnh thủ công và tự động).
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    if account_id not in G_CLOSE_TICKETS_QUEUE:
        G_CLOSE_TICKETS_QUEUE[account_id] = set()

    try:
        # 1. Thêm ticket vào hàng đợi đóng
        G_CLOSE_TICKETS_QUEUE[account_id].add(ticket)
        
        # 2. Cập nhật close_requested = 1 trong DB trades cho tài khoản này
        await db.execute(
            "UPDATE trades SET close_requested = 1, updated_at = ? WHERE account_id = ? AND ticket = ? AND status = 'FILLED'",
            (datetime.utcnow().isoformat(), account_id, ticket)
        )
        await db.commit()
        
        return {"status": "success", "message": f"Đã gửi yêu cầu đóng vị thế Ticket #{ticket} cho tài khoản ID {account_id}"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/api/trades/sync-closed")
async def sync_closed_trades(request: Request, req: ManualTradeSyncRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đồng bộ thông tin các lệnh đã đóng từ EA.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    else:
        account_id = await get_active_account_id(db)

    try:
        sync_count = 0
        for trade in req.trades:
            # 1. Kiểm tra xem ticket đã tồn tại trong trades chưa
            async with db.execute("SELECT id, source FROM trades WHERE account_id = ? AND ticket = ?", (account_id, trade.ticket)) as cursor:
                row = await cursor.fetchone()
                
            opened_at_str = trade.opened_at.isoformat()
            closed_at_str = trade.closed_at.isoformat()
            now_str = datetime.utcnow().isoformat()
            
            if row:
                # Cập nhật lệnh có sẵn
                await db.execute(
                    """
                    UPDATE trades
                    SET status = 'CLOSED',
                        close_price = ?,
                        pnl = ?,
                        commission = ?,
                        swap = ?,
                        closed_at = ?,
                        close_reason = ?,
                        notified = 1,
                        updated_at = ?
                    WHERE account_id = ? AND ticket = ?
                    """,
                    (
                        trade.close_price,
                        trade.pnl,
                        trade.commission,
                        trade.swap,
                        closed_at_str,
                        trade.close_reason,
                        now_str,
                        account_id,
                        trade.ticket
                    )
                )
            else:
                # Thêm mới lệnh thủ công (MANUAL)
                await db.execute(
                    """
                    INSERT INTO trades (
                        uuid, account_id, source, symbol, trade_type, lot_size, price, open_price,
                        close_price, status, ticket, pnl, commission, swap,
                        opened_at, closed_at, close_reason, notified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        f"manual-{account_id}-{trade.ticket}",
                        account_id,
                        "MANUAL",
                        trade.symbol,
                        trade.trade_type,
                        trade.lot_size,
                        trade.open_price,
                        trade.open_price,
                        trade.close_price,
                        trade.ticket,
                        trade.pnl,
                        trade.commission,
                        trade.swap,
                        opened_at_str,
                        closed_at_str,
                        trade.close_reason,
                        now_str,
                        now_str
                    )
                )
            sync_count += 1
            
        await db.commit()
        return {"status": "success", "synced_count": sync_count}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ── Account Management Endpoints (Admin Only) ──

@router.get("/api/accounts", response_model=List[TradingAccountResponse])
async def list_trading_accounts(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    Liệt kê danh sách tất cả tài khoản giao dịch.
    """
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    if is_admin and not user_id:
        # Admin hệ thống thực sự: Xem toàn bộ tài khoản
        query = "SELECT * FROM accounts ORDER BY created_at ASC"
        params = ()
    else:
        # Người dùng thường: Chỉ xem tài khoản của chính mình
        query = "SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at ASC"
        params = (user_id,)
        
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

@router.post("/api/accounts", response_model=TradingAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_trading_account(request: Request, req: TradingAccountCreate, db: aiosqlite.Connection = Depends(get_db)):
    """
    Tạo một tài khoản giao dịch mới.
    """
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    # Nếu không phải admin và cũng không có user_id hợp lệ
    if not is_admin and not user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin hoặc thành viên đã được duyệt mới có quyền truy cập")
        
    # Nếu admin hệ thống gọi mà không chỉ định user_id, mặc định gán cho user_id = 1 (Admin)
    if not user_id:
        user_id = 1
        
    import uuid
    token = uuid.uuid4().hex
    
    try:
        # Kiểm tra xem tài khoản này có phải tài khoản đầu tiên của User này không
        async with db.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,)) as cursor:
            count_row = await cursor.fetchone()
            is_active = 1 if count_row[0] == 0 else 0
            
        cursor = await db.execute(
            """
            INSERT INTO accounts (user_id, name, platform, account_number, token, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, req.name, req.platform, req.account_number, token, is_active)
        )
        account_id = cursor.lastrowid
        await db.commit()
        
        # Seed default configs for this new account
        configs = [
            ('mode', 'queue'),
            ('default_lot', '0.01'),
            ('queue_expire_minutes', '15'),
            ('sl_buffer_pips', '0'),
            ('trailing_enabled', 'true'),
            ('trailing_be_pips', '15'),
            ('trailing_be_offset', '2'),
            ('trailing_step_pips', '10'),
            ('trailing_step_distance', '8'),
            ('partial_close_enabled', 'false'),
            ('partial_close_pips', '30'),
            ('partial_close_ratio', '0.5'),
            ('partial_close_ratios', '33/33/33'),
            ('partial_close_pips_stages', '50/100/'),
            ('trailing_manual_enabled', 'false'),
            ('default_sl_pips', '0')
        ]
        for key, value in configs:
            await db.execute(
                "INSERT OR IGNORE INTO config (account_id, key, value) VALUES (?, ?, ?)",
                (account_id, key, value)
            )
            
        # Seed default account_info and heartbeat rows
        await db.execute("INSERT OR IGNORE INTO account_info (account_id, account_number, account_name) VALUES (?, ?, ?)", (account_id, req.account_number or 0, req.name))
        await db.execute("INSERT OR IGNORE INTO ea_heartbeat (account_id) VALUES (?)", (account_id,))
        
        # Seed default Telegram signal sources from env
        import os
        group_id = os.getenv("SIGNAL_GROUP_ID")
        backup_id = os.getenv("SIGNAL_GROUP_BACKUP_ID")
        default_mode = os.getenv("DEFAULT_MODE", "queue")
        
        if group_id:
            await db.execute("""
                INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                VALUES (?, 'telegram_group', ?, 'Kênh tín hiệu chính', ?)
            """, (account_id, str(group_id), default_mode))
        if backup_id:
            await db.execute("""
                INSERT OR IGNORE INTO signal_sources (account_id, source_type, source_key, name, mode)
                VALUES (?, 'telegram_group', ?, 'Kênh tín hiệu phụ', ?)
            """, (account_id, str(backup_id), default_mode))
            
        await db.commit()
        
        async with db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)) as c:
            row = await c.fetchone()
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/api/accounts/{account_id}/active", response_model=TradingAccountResponse)
async def activate_trading_account(request: Request, account_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đặt tài khoản này làm tài khoản hoạt động mặc định.
    """
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    # Kiểm tra tài khoản tồn tại và thuộc sở hữu của người dùng (trừ hệ thống admin thực sự)
    if is_admin and not user_id:
        query = "SELECT * FROM accounts WHERE id = ?"
        params = (account_id,)
    else:
        query = "SELECT * FROM accounts WHERE id = ? AND user_id = ?"
        params = (account_id, user_id)
        
    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy tài khoản hoặc bạn không có quyền sở hữu tài khoản ID {account_id}")
            
    try:
        if is_admin and not user_id:
            await db.execute("UPDATE accounts SET is_active = 0")
            await db.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))
        else:
            await db.execute("UPDATE accounts SET is_active = 0 WHERE user_id = ?", (user_id,))
            await db.execute("UPDATE accounts SET is_active = 1 WHERE id = ? AND user_id = ?", (account_id, user_id))
        await db.commit()
        
        async with db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)) as c:
            row = await c.fetchone()
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/api/accounts/{account_id}")
async def delete_trading_account(request: Request, account_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Xóa tài khoản giao dịch.
    """
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    # Kiểm tra tài khoản tồn tại và thuộc sở hữu của người dùng (trừ hệ thống admin thực sự)
    if is_admin and not user_id:
        query = "SELECT * FROM accounts WHERE id = ?"
        params = (account_id,)
    else:
        query = "SELECT * FROM accounts WHERE id = ? AND user_id = ?"
        params = (account_id, user_id)
        
    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy tài khoản hoặc bạn không có quyền sở hữu tài khoản ID {account_id}")
            
    try:
        was_active = row["is_active"]
        
        # Delete account (cascades automatically to trades, config, account_info, ea_heartbeat, lot_overrides, action_history)
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()
        
        # Nếu tài khoản bị xóa đang là active, tự động chọn tài khoản khác làm active
        if was_active:
            if is_admin and not user_id:
                async with db.execute("SELECT id FROM accounts LIMIT 1") as c:
                    next_row = await c.fetchone()
                    if next_row:
                        await db.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (next_row[0],))
                        await db.commit()
            else:
                async with db.execute("SELECT id FROM accounts WHERE user_id = ? LIMIT 1", (user_id,)) as c:
                    next_row = await c.fetchone()
                    if next_row:
                        await db.execute("UPDATE accounts SET is_active = 1 WHERE id = ? AND user_id = ?", (next_row[0], user_id))
                        await db.commit()
                        
        return {"status": "success", "message": f"Tài khoản ID {account_id} đã được xóa thành công"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ── User Management Endpoints ──

@router.get("/api/users/{telegram_id}")
async def get_user_status(telegram_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (str(telegram_id),)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return {"exists": False, "is_approved": False}
        return {"exists": True, "is_approved": bool(row["is_approved"]), "id": row["id"], "username": row["username"]}

@router.post("/api/users", status_code=status.HTTP_201_CREATED)
async def register_user(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    telegram_id = req.get("telegram_id")
    username = req.get("username")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")
    try:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, is_approved) VALUES (?, ?, 0)",
            (str(telegram_id), username)
        )
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/users/{telegram_id}/approve")
async def approve_user(telegram_id: str, db: aiosqlite.Connection = Depends(get_db)):
    try:
        await db.execute("UPDATE users SET is_approved = 1 WHERE telegram_id = ?", (str(telegram_id),))
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/users/{telegram_id}/reject")
async def reject_user(telegram_id: str, db: aiosqlite.Connection = Depends(get_db)):
    try:
        await db.execute("DELETE FROM users WHERE telegram_id = ?", (str(telegram_id),))
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
