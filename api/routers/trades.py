from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
import aiosqlite
from typing import List, Optional
from api.database import get_db
from api.models import TradeCreateRequest, TradeUpdateRequest, TradeResponse, TradeStatus
import api.services.trade_service as trade_service
from api.services.config_service import get_active_account_id

router = APIRouter(prefix="/api/trades", tags=["Trades"])

@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_new_trade(request: Request, req: TradeCreateRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Tạo lệnh giao dịch mới ở trạng thái PENDING (chờ EA lấy về để thực hiện).
    """
    if not getattr(request.state, "is_admin", True):
        req.account_id = request.state.account_id
    elif not req.account_id:
        req.account_id = await get_active_account_id(db)

    try:
        trade = await trade_service.create_trade(db, req)
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=List[TradeResponse])
async def list_trades(
    request: Request,
    status: Optional[str] = Query(None, description="Lọc theo trạng thái lệnh (PENDING, FILLED, CLOSED, etc.)"),
    close_requested: Optional[bool] = Query(None, description="Lọc các lệnh có yêu cầu đóng từ phía Bot"),
    notified: Optional[bool] = Query(None, description="Lọc các lệnh đã được thông báo đóng cho Telegram Bot chưa"),
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ áp dụng cho Admin)"),
    limit: int = Query(50, ge=1, le=200, description="Giới hạn số lượng kết quả"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy danh sách các lệnh giao dịch theo bộ lọc. EA thường dùng endpoint này để poll lệnh PENDING hoặc CLOSE_REQUEST.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await trade_service.get_trades(db, status, close_requested, notified, limit, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{trade_id}", response_model=TradeResponse)
async def update_trade_status(
    request: Request,
    trade_id: int, 
    req: TradeUpdateRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Cập nhật thông tin và trạng thái lệnh. Gọi bởi EA khi lệnh được khớp (FILLED) hoặc đóng (CLOSED) hoặc thất bại (FAILED).
    """
    # 1. Lấy trạng thái trước khi update và check quyền sở hữu
    existing = await trade_service.get_trade_by_id(db, trade_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")

    if not getattr(request.state, "is_admin", True):
        if existing.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền cập nhật trade của tài khoản khác")

    trade = await trade_service.update_trade(db, trade_id, req)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")

    # 2. Nếu trạng thái chuyển thành FILLED (và trước đó chưa phải FILLED), gửi thông báo lên Telegram
    if req.status == TradeStatus.FILLED and (not existing or existing.get("status") != "FILLED"):
        try:
            from bot.main import bot
            from bot.config import config
            from bot.utils.formatter import format_trade_filled
            from bot.services.background_tasks import send_telegram_safe
            
            # Gửi thông báo
            msg = format_trade_filled(trade)
            target_chat_id = int(trade.get("telegram_id")) if trade.get("telegram_id") else config.owner_chat_id
            await send_telegram_safe(bot, target_chat_id, msg)
        except Exception as telegram_err:
            import logging
            logging.getLogger("api").error(f"Lỗi khi gửi thông báo Telegram trade filled: {telegram_err}")

    return trade

@router.delete("/{trade_id}", response_model=TradeResponse)
async def cancel_pending_trade(request: Request, trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Hủy bỏ một lệnh đang chờ xử lý (PENDING). Chỉ có hiệu lực nếu EA chưa thực hiện khớp lệnh.
    """
    # Check quyền sở hữu
    existing = await trade_service.get_trade_by_id(db, trade_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")

    if not getattr(request.state, "is_admin", True):
        if existing.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền hủy trade của tài khoản khác")

    try:
        trade = await trade_service.cancel_pending_trade(db, trade_id)
        if not trade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{trade_id}/close-request", response_model=TradeResponse)
async def request_close(request: Request, trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Yêu cầu EA đóng lệnh giao dịch đang chạy. Đánh dấu close_requested = 1.
    """
    # Check quyền sở hữu
    existing = await trade_service.get_trade_by_id(db, trade_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")

    if not getattr(request.state, "is_admin", True):
        if existing.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền đóng trade của tài khoản khác")

    try:
        trade = await trade_service.request_close_trade(db, trade_id)
        if not trade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{trade_id}/notify")
async def mark_notified(request: Request, trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đánh dấu lệnh đóng đã được Bot Telegram thông báo thành công cho người dùng (notified = 1).
    """
    # Check quyền sở hữu
    existing = await trade_service.get_trade_by_id(db, trade_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")

    if not getattr(request.state, "is_admin", True):
        if existing.get("account_id") != request.state.account_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập trade của tài khoản khác")

    success = await trade_service.mark_trade_notified(db, trade_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
    return {"status": "success", "message": f"Trade ID {trade_id} marked as notified"}
