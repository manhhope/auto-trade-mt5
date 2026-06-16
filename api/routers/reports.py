from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
import aiosqlite
from typing import Optional
from api.database import get_db
from api.models import ReportSummary, ReportTrend
import api.services.report_service as report_service
from api.services.config_service import get_active_account_id

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/summary", response_model=ReportSummary)
async def get_summary(
    request: Request,
    period: str = Query("week", pattern="^(day|week|month)$", description="Chu kỳ báo cáo (day, week, hoặc month)"),
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy báo cáo tổng hợp kết quả giao dịch (P/L, tỷ lệ thắng, Drawdown, streak, biểu đồ ngày).
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await report_service.get_summary_report(db, period, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/trend", response_model=ReportTrend)
async def get_trend(
    request: Request,
    weeks: int = Query(4, ge=1, le=12, description="Số tuần của chu kỳ so sánh"),
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    So sánh P/L của chu kỳ hiện tại (X tuần gần nhất) với chu kỳ trước đó để đánh giá xu hướng.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await report_service.get_report_trend(db, weeks, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
