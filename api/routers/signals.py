from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
import aiosqlite
from typing import List, Optional, Any
from api.database import get_db
from api.models import SignalCreateRequest, SignalConfirmRequest, SignalResponse, TradeResponse
import api.services.signal_service as signal_service
from api.services.config_service import get_active_account_id

router = APIRouter(prefix="/api/signals", tags=["Signals"])

@router.post("", response_model=Any, status_code=status.HTTP_201_CREATED)
async def receive_new_signal(request: Request, req: SignalCreateRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Nhận tín hiệu giao dịch mới từ group Telegram.
    Nếu chế độ cài đặt là 'auto', tín hiệu sẽ được tự động khớp lệnh (tạo Trade PENDING gửi sang EA).
    """
    # 1. Xác định các tài khoản đích cần nhận tín hiệu này
    accounts = []
    
    # Nếu không phải Admin gọi (ví dụ: client thường gọi qua X-Telegram-User-Id), chỉ gán cho tài khoản của chính họ
    if not getattr(request.state, "is_admin", True):
        accounts = [request.state.account_id]
    # Nếu được chỉ định cụ thể tài khoản trong request
    elif req.account_id:
        accounts = [req.account_id]
    # Nếu không được chỉ định và được gọi từ Telethon listener (is_admin = True)
    # Nếu không phải và được gọi từ Telethon listener (is_admin = True)
    else:
        if req.group_id:
            # Kiểm tra xem nguồn này có tồn tại trong db không để tránh fallback sai
            async with db.execute(
                "SELECT COUNT(*) FROM signal_sources WHERE source_type = 'telegram_group' AND source_key = ?",
                (str(req.group_id),)
            ) as cursor:
                c_row = await cursor.fetchone()
                exists = c_row[0] > 0
                
            if exists:
                # Chỉ lấy các account của nguồn đang active
                async with db.execute(
                    "SELECT account_id FROM signal_sources WHERE source_type = 'telegram_group' AND source_key = ? AND is_active = 1",
                    (str(req.group_id),)
                ) as cursor:
                    rows = await cursor.fetchall()
                    accounts = [r[0] for r in rows]
            else:
                # Không tồn tại -> fallback về Admin active account
                fallback_acc = await get_active_account_id(db)
                if fallback_acc:
                    accounts = [fallback_acc]

    results = []
    for account_id in accounts:
        # Clone request và gán account_id tương ứng
        account_req = req.model_copy()
        account_req.account_id = account_id
        
        try:
            signal = await signal_service.create_signal(db, account_req)
            results.append(signal)
            
            # Gửi thông báo đến Telegram của chủ tài khoản sở hữu tín hiệu này
            if signal.get("parse_success"):
                telegram_id = None
                async with db.execute(
                    """
                    SELECT u.telegram_id FROM users u
                    JOIN accounts a ON a.user_id = u.id
                    WHERE a.id = ?
                    """,
                    (account_id,)
                ) as cursor:
                    user_row = await cursor.fetchone()
                    if user_row:
                        telegram_id = user_row[0]
                        
                if telegram_id:
                    try:
                        from bot.main import bot
                        from bot.services.background_tasks import send_telegram_safe
                        from bot.utils.formatter import format_auto_trade, format_queue_signal
                        import api.services.config_service as config_service
                        
                        auto_trade = signal.get("auto_executed_trade")
                        if auto_trade:
                            msg = format_auto_trade(auto_trade)
                        else:
                            expire_min_str = await config_service.get_config_value(db, "queue_expire_minutes", account_id)
                            expire_min = int(expire_min_str) if expire_min_str else 15
                            msg = format_queue_signal(signal, expire_minutes=expire_min)
                            
                        await send_telegram_safe(bot, int(telegram_id), msg)
                    except Exception as e:
                        import logging
                        logging.getLogger("api").error(f"Failed to send Telegram notification for signal: {e}")
        except Exception as e:
            import logging
            logging.getLogger("api").error(f"Failed to process signal for account {account_id}: {e}")

    # Trả về kết quả đầu tiên hoặc thông báo thành công
    return results[0] if results else {"status": "no_signals_created"}

@router.get("", response_model=List[SignalResponse])
async def list_signals(
    request: Request,
    status: Optional[str] = Query(None, description="Lọc theo trạng thái signal (QUEUED, EXECUTED, REJECTED, EXPIRED, PARSE_FAILED)"),
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    limit: int = Query(50, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy danh sách các tín hiệu từ hàng đợi.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await signal_service.get_signals(db, status, limit, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{id_or_queue_id}/confirm", response_model=TradeResponse)
async def confirm_queued_signal(
    request: Request,
    id_or_queue_id: str, 
    req: SignalConfirmRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Duyệt (xác nhận) một tín hiệu từ hàng đợi bằng ID hoặc Queue ID (VD: SIG-0042).
    Sẽ tạo lệnh giao dịch PENDING trên MT5.
    """
    # Check signal ownership
    signal = await signal_service.get_signal_by_id_or_queue_id(db, id_or_queue_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy tín hiệu với ID/QueueID: {id_or_queue_id}")

    if not getattr(request.state, "is_admin", True):
        if signal.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xác nhận tín hiệu của tài khoản khác")

    try:
        trade = await signal_service.confirm_signal(db, id_or_queue_id, req)
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{id_or_queue_id}/reject", response_model=SignalResponse)
async def reject_queued_signal(request: Request, id_or_queue_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """
    Từ chối một tín hiệu trong hàng đợi bằng ID hoặc Queue ID (VD: SIG-0042).
    """
    signal = await signal_service.get_signal_by_id_or_queue_id(db, id_or_queue_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy tín hiệu với ID/QueueID: {id_or_queue_id}")

    if not getattr(request.state, "is_admin", True):
        if signal.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền từ chối tín hiệu của tài khoản khác")

    try:
        signal_res = await signal_service.reject_signal(db, id_or_queue_id)
        return signal_res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/confirm-all")
async def confirm_all_queued(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    Xác nhận toàn bộ các tín hiệu đang đợi duyệt (QUEUED). Trả về danh sách trades được tạo ra.
    """
    if not getattr(request.state, "is_admin", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tính năng chỉ dành cho Admin")
    try:
        trades = await signal_service.confirm_all_signals(db)
        return {"confirmed_count": len(trades), "trades": trades}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/reject-all")
async def reject_all_queued(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    Từ chối toàn bộ các tín hiệu đang đợi duyệt (QUEUED). Trả về số lượng tín hiệu bị hủy.
    """
    if not getattr(request.state, "is_admin", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tính năng chỉ dành cho Admin")
    try:
        count = await signal_service.reject_all_signals(db)
        return {"rejected_count": count}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
