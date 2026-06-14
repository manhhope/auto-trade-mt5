from fastapi import APIRouter, Depends, HTTPException, Query, status
import aiosqlite
from typing import List, Optional
from api.database import get_db
from api.models import TradeCreateRequest, TradeUpdateRequest, TradeResponse
import api.services.trade_service as trade_service

router = APIRouter(prefix="/api/trades", tags=["Trades"])

@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_new_trade(req: TradeCreateRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Tạo lệnh giao dịch mới ở trạng thái PENDING (chờ EA lấy về để thực hiện).
    """
    try:
        trade = await trade_service.create_trade(db, req)
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái lệnh (PENDING, FILLED, CLOSED, etc.)"),
    close_requested: Optional[bool] = Query(None, description="Lọc các lệnh có yêu cầu đóng từ phía Bot"),
    notified: Optional[bool] = Query(None, description="Lọc các lệnh đã được thông báo đóng cho Telegram Bot chưa"),
    limit: int = Query(50, ge=1, le=200, description="Giới hạn số lượng kết quả"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy danh sách các lệnh giao dịch theo bộ lọc. EA thường dùng endpoint này để poll lệnh PENDING hoặc CLOSE_REQUEST.
    """
    try:
        return await trade_service.get_trades(db, status, close_requested, notified, limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{trade_id}", response_model=TradeResponse)
async def update_trade_status(
    trade_id: int, 
    req: TradeUpdateRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Cập nhật thông tin và trạng thái lệnh. Gọi bởi EA khi lệnh được khớp (FILLED) hoặc đóng (CLOSED) hoặc thất bại (FAILED).
    """
    trade = await trade_service.update_trade(db, trade_id, req)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
    return trade

@router.delete("/{trade_id}", response_model=TradeResponse)
async def cancel_pending_trade(trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Hủy bỏ một lệnh đang chờ xử lý (PENDING). Chỉ có hiệu lực nếu EA chưa thực hiện khớp lệnh.
    """
    try:
        trade = await trade_service.cancel_pending_trade(db, trade_id)
        if not trade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{trade_id}/close-request", response_model=TradeResponse)
async def request_close(trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Yêu cầu EA đóng lệnh giao dịch đang chạy. Đánh dấu close_requested = 1.
    """
    try:
        trade = await trade_service.request_close_trade(db, trade_id)
        if not trade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
        return trade
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{trade_id}/notify")
async def mark_notified(trade_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """
    Đánh dấu lệnh đóng đã được Bot Telegram thông báo thành công cho người dùng (notified = 1).
    """
    success = await trade_service.mark_trade_notified(db, trade_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trade ID {trade_id}")
    return {"status": "success", "message": f"Trade ID {trade_id} marked as notified"}
