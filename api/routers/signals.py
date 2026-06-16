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
    if not getattr(request.state, "is_admin", True):
        req.account_id = request.state.account_id
    elif not req.account_id:
        req.account_id = await get_active_account_id(db)

    try:
        signal = await signal_service.create_signal(db, req)
        return signal
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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
