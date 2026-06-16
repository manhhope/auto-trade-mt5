from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from api.database import get_db
from api.models import ActionLogCreate
from api.services.config_service import get_active_account_id

router = APIRouter(prefix="/api/action-logs", tags=["Action Logs"])

@router.post("")
async def create_action_log(request: Request, req: ActionLogCreate, db: aiosqlite.Connection = Depends(get_db)):
    """
    Lưu vết hành động dời SL hoặc chốt lời từng phần từ EA và gửi thông báo Telegram thời gian thực.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    else:
        account_id = req.account_id or await get_active_account_id(db)

    try:
        # 1. Lưu vào database
        await db.execute(
            """
            INSERT INTO action_history (account_id, ticket, symbol, action_type, details, pnl)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, req.ticket, req.symbol, req.action_type, req.details, req.pnl)
        )
        await db.commit()

        # 2. Gửi thông báo qua Telegram Bot
        try:
            from bot.main import bot
            from bot.config import config
            from bot.services.background_tasks import send_telegram_safe
            
            # Lấy thông tin account để hiển thị
            async with db.execute("SELECT name, account_number FROM accounts WHERE id = ?", (account_id,)) as cursor:
                row = await cursor.fetchone()
                acc_name = row["name"] if row else f"ID {account_id}"
                acc_num = row["account_number"] if row else ""
                acc_str = f" [{acc_name} - {acc_num}]" if acc_num else f" [{acc_name}]"
            
            # Format PnL
            pnl_icon = "❇️" if req.pnl >= 0 else "❌"
            formatted_pnl = f"+${req.pnl:.2f} {pnl_icon}" if req.pnl >= 0 else f"-${abs(req.pnl):.2f} {pnl_icon}"
            trade_type = req.trade_type or "SELL" # fallback
            dir_icon = "🟢" if "BUY" in trade_type else "🔴"
            
            if req.action_type == "TRAILING_SL":
                msg = (
                    f"🔔 **[TRAILING]**{acc_str} {dir_icon} Dời SL `#{req.ticket}`: `{req.details}` | "
                    f"Giá: `{req.current_price or 'N/A'}` ({formatted_pnl})"
                )
            elif req.action_type == "PARTIAL_CLOSE":
                time_str = datetime.now().strftime("%H:%M")
                lot_closed = req.lot_size or 0.01
                msg = (
                    f"❎ **[{time_str}]**{acc_str} {dir_icon} Chốt lời {req.details} `#{req.ticket}`: "
                    f"Khớp `{lot_closed:.2f}` lot ({formatted_pnl})"
                )
            else:
                msg = (
                    f"ℹ️ **[EA Action]**{acc_str} {req.action_type} - Lệnh {dir_icon} `#{req.ticket}` ({req.symbol}):\n"
                    f"Chi tiết: {req.details}\n"
                    f"PnL: {formatted_pnl}"
                )
                
            await send_telegram_safe(bot, config.owner_chat_id, msg)
        except Exception as telegram_err:
            import logging
            logging.getLogger("api").error(f"Lỗi khi gửi thông báo Telegram action log: {telegram_err}")

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("")
async def get_action_logs(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy danh sách 10 hành động gần đây nhất từ cả bảng action_history và trades (lệnh đã đóng) của tài khoản được chọn.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        # Lấy 10 action gần nhất từ action_history
        action_list = []
        async with db.execute(
            """
            SELECT id, ticket, symbol, action_type, details, pnl, created_at
            FROM action_history
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (account_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                action_list.append({
                    "type": "action",
                    "timestamp": r["created_at"],
                    "ticket": r["ticket"],
                    "symbol": r["symbol"],
                    "action_type": r["action_type"],
                    "details": r["details"],
                    "pnl": r["pnl"]
                })

        # Lấy 10 lệnh đã đóng gần nhất từ trades (bao gồm cả lệnh tay và tự động)
        trade_list = []
        async with db.execute(
            """
            SELECT id, ticket, symbol, trade_type, lot_size, pnl, close_reason, source, closed_at
            FROM trades
            WHERE account_id = ? AND status = 'CLOSED' AND closed_at IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT 10
            """,
            (account_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                trade_list.append({
                    "type": "trade",
                    "timestamp": r["closed_at"],
                    "ticket": r["ticket"],
                    "symbol": r["symbol"],
                    "trade_type": r["trade_type"],
                    "lot_size": r["lot_size"],
                    "pnl": r["pnl"],
                    "close_reason": r["close_reason"],
                    "source": r["source"]
                })

        # Gộp cả 2 danh sách và sắp xếp theo timestamp giảm dần
        merged_list = action_list + trade_list
        def parse_timestamp(item):
            ts = item["timestamp"]
            if not ts:
                return datetime.min
            ts_str = ts.replace("Z", "").replace(" ", "T")
            try:
                if "." in ts_str:
                    return datetime.strptime(ts_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                return datetime.fromisoformat(ts_str)
            except Exception:
                return datetime.min

        merged_list.sort(key=parse_timestamp, reverse=True)
        return merged_list[:10]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
