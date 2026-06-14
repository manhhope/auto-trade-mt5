from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import aiosqlite

def get_date_range(period: str) -> tuple[datetime, datetime]:
    """Tính toán khoảng thời gian bắt đầu và kết thúc dựa trên period (day, week, month)"""
    now = datetime.utcnow()
    # Mặc định kết thúc là thời điểm hiện tại
    date_to = now
    
    if period == "day":
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        # Thứ Hai tuần này
        date_from = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        # Ngày 1 của tháng này
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Mặc định là ngày hôm nay nếu sai period
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
    return date_from, date_to

def calculate_max_drawdown(daily_pnls: List[float]) -> float:
    """Tính toán Maximum Drawdown từ danh sách P/L hàng ngày"""
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in daily_pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)

def calculate_streak(trades: List[Dict[str, Any]]) -> int:
    """Tính chuỗi thắng/thua liên tiếp gần nhất"""
    if not trades:
        return 0
    streak = 0
    direction = None  # True: Win, False: Loss
    
    for t in trades:
        pnl = t.get("pnl") or 0.0
        is_win = pnl > 0
        if direction is None:
            direction = is_win
            streak = 1 if is_win else -1
        elif is_win == direction:
            streak += 1 if is_win else -1
        else:
            break
            
    return streak

async def get_summary_report(db: aiosqlite.Connection, period: str) -> Dict[str, Any]:
    """Tính toán báo cáo tổng hợp cho chu kỳ chỉ định"""
    date_from, date_to = get_date_range(period)
    date_from_str = date_from.isoformat()
    date_to_str = date_to.isoformat()
    
    # Query 1: Lấy số liệu tổng hợp
    summary_query = """
        SELECT
            COUNT(*) as total_trades,
            COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
            COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losing_trades,
            ROUND(COUNT(CASE WHEN pnl > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) as win_rate,
            ROUND(COALESCE(SUM(pnl), 0), 2) as total_pnl,
            ROUND(COALESCE(AVG(pnl), 0), 2) as avg_pnl,
            ROUND(COALESCE(MAX(pnl), 0), 2) as best_trade,
            ROUND(COALESCE(MIN(pnl), 0), 2) as worst_trade,
            ROUND(
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0),
            2) as profit_factor
        FROM trades
        WHERE status = 'CLOSED'
          AND closed_at >= ?
          AND closed_at < ?;
    """
    
    async with db.execute(summary_query, (date_from_str, date_to_str)) as cursor:
        row = await cursor.fetchone()
        summary = dict(row) if row else {}
        
    # Chuẩn hóa các giá trị null/None từ SQL
    summary["total_trades"] = summary.get("total_trades") or 0
    summary["winning_trades"] = summary.get("winning_trades") or 0
    summary["losing_trades"] = summary.get("losing_trades") or 0
    summary["win_rate"] = summary.get("win_rate") or 0.0
    summary["total_pnl"] = summary.get("total_pnl") or 0.0
    summary["avg_pnl"] = summary.get("avg_pnl") or 0.0
    summary["best_trade"] = summary.get("best_trade") or 0.0
    summary["worst_trade"] = summary.get("worst_trade") or 0.0
    summary["profit_factor"] = summary.get("profit_factor")
    
    # Query 2: Lấy chi tiết P/L hàng ngày cho biểu đồ breakdown và drawdown
    daily_query = """
        SELECT
            DATE(closed_at) as date,
            ROUND(SUM(pnl), 2) as pnl,
            COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
            COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losses
        FROM trades
        WHERE status = 'CLOSED'
          AND closed_at >= ?
          AND closed_at < ?
        GROUP BY DATE(closed_at)
        ORDER BY date;
    """
    
    daily_breakdown = []
    daily_pnls = []
    async with db.execute(daily_query, (date_from_str, date_to_str)) as cursor:
        rows = await cursor.fetchall()
        for r in rows:
            daily_breakdown.append({
                "date": r["date"],
                "pnl": r["pnl"],
                "wins": r["wins"],
                "losses": r["losses"]
            })
            daily_pnls.append(r["pnl"])
            
    summary["daily_breakdown"] = daily_breakdown
    summary["max_drawdown"] = calculate_max_drawdown(daily_pnls)
    
    # Query 3: Lấy các lệnh đã đóng để tính streak (sắp xếp giảm dần theo closed_at)
    async with db.execute(
        "SELECT pnl FROM trades WHERE status = 'CLOSED' AND closed_at >= ? AND closed_at < ? ORDER BY closed_at DESC",
        (date_from_str, date_to_str)
    ) as cursor:
        rows = await cursor.fetchall()
        trades_list = [dict(r) for r in rows]
        summary["current_streak"] = calculate_streak(trades_list)
        
    summary["period"] = period
    summary["date_from"] = date_from_str
    summary["date_to"] = date_to_str
    
    return summary

async def get_report_trend(db: aiosqlite.Connection, weeks: int = 4) -> Dict[str, Any]:
    """So sánh kết quả giao dịch giữa kỳ hiện tại (X tuần gần nhất) và kỳ trước đó"""
    now = datetime.utcnow()
    current_from = now - timedelta(weeks=weeks)
    previous_from = now - timedelta(weeks=weeks * 2)
    
    # Tính P/L kỳ này
    async with db.execute(
        "SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED' AND closed_at >= ? AND closed_at < ?",
        (current_from.isoformat(), now.isoformat())
    ) as cursor:
        row = await cursor.fetchone()
        current_pnl = row[0] if row and row[0] is not None else 0.0
        
    # Tính P/L kỳ trước
    async with db.execute(
        "SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED' AND closed_at >= ? AND closed_at < ?",
        (previous_from.isoformat(), current_from.isoformat())
    ) as cursor:
        row = await cursor.fetchone()
        previous_pnl = row[0] if row and row[0] is not None else 0.0
        
    change_amount = current_pnl - previous_pnl
    
    if previous_pnl == 0.0:
        change_percent = 100.0 if change_amount > 0 else (-100.0 if change_amount < 0 else 0.0)
    else:
        change_percent = round((change_amount / abs(previous_pnl)) * 100.0, 1)
        
    direction = "up" if change_amount > 0 else ("down" if change_amount < 0 else "flat")
    
    return {
        "current_period_pnl": round(current_pnl, 2),
        "previous_period_pnl": round(previous_pnl, 2),
        "change_amount": round(change_amount, 2),
        "change_percent": change_percent,
        "direction": direction
    }
