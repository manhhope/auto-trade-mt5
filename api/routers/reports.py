from fastapi import APIRouter, Depends, HTTPException, Query, status
import aiosqlite
from api.database import get_db
from api.models import ReportSummary, ReportTrend
import api.services.report_service as report_service

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/summary", response_model=ReportSummary)
async def get_summary(
    period: str = Query("week", regex="^(day|week|month)$", description="Chu kỳ báo cáo (day, week, hoặc month)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Lấy báo cáo tổng hợp kết quả giao dịch (P/L, tỷ lệ thắng, Drawdown, streak, biểu đồ ngày).
    """
    try:
        return await report_service.get_summary_report(db, period)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/trend", response_model=ReportTrend)
async def get_trend(
    weeks: int = Query(4, ge=1, le=12, description="Số tuần của chu kỳ so sánh"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    So sánh P/L của chu kỳ hiện tại (X tuần gần nhất) với chu kỳ trước đó để đánh giá xu hướng.
    """
    try:
        return await report_service.get_report_trend(db, weeks)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
