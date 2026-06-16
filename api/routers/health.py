import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import aiosqlite
from datetime import datetime
from typing import Optional
from api.database import get_db, DATABASE_PATH
from api.models import HealthResponse, HeartbeatRequest
from api.services.config_service import get_active_account_id

router = APIRouter(tags=["Health & Heartbeat"])

@router.get("/api/health", response_model=HealthResponse)
async def check_health(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Kiểm tra trạng thái hệ thống cho tài khoản giao dịch tương ứng.
    """
    if not hasattr(request.state, "is_admin"):
        # Trường hợp đi qua bypass list và không có authentication headers
        account_id = await get_active_account_id(db)
    elif not request.state.is_admin:
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        # Lấy thông tin nhịp đập của EA của tài khoản tương ứng
        async with db.execute("SELECT last_ping, ea_version, mt5_connected FROM ea_heartbeat WHERE account_id = ?", (account_id,)) as cursor:
            row = await cursor.fetchone()
            
        ea_last_ping = None
        ea_version = None
        mt5_connected = False
        ea_online = False
        
        if row:
            last_ping_str = row["last_ping"]
            ea_version = row["ea_version"]
            mt5_connected = bool(row["mt5_connected"])
            
            if last_ping_str:
                ea_last_ping = datetime.fromisoformat(last_ping_str)
                delta = datetime.utcnow() - ea_last_ping
                ea_online = delta.total_seconds() < 30.0
                
        db_size_mb = 0.0
        if os.path.exists(DATABASE_PATH):
            db_size_mb = round(os.path.getsize(DATABASE_PATH) / (1024 * 1024), 3)
            
        return HealthResponse(
            api_status="ok",
            ea_online=ea_online,
            ea_last_ping=ea_last_ping,
            ea_version=ea_version,
            mt5_connected=mt5_connected,
            db_size_mb=db_size_mb
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/api/heartbeat")
async def update_heartbeat(
    request: Request,
    req: HeartbeatRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Cập nhật nhịp đập từ EA của tài khoản tương ứng để báo hiệu EA vẫn đang hoạt động tốt.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    else:
        account_id = await get_active_account_id(db)

    now = datetime.utcnow().isoformat()
    try:
        await db.execute(
            """
            INSERT INTO ea_heartbeat (account_id, last_ping, ea_version, mt5_connected) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET 
                last_ping = excluded.last_ping,
                ea_version = excluded.ea_version,
                mt5_connected = excluded.mt5_connected
            """,
            (account_id, now, req.ea_version, 1 if req.mt5_connected else 0)
        )
        await db.commit()
        return {"status": "success", "message": f"Heartbeat updated for account {account_id}", "time": now}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
