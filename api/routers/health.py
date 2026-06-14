import os
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite
from datetime import datetime
from typing import Optional
from api.database import get_db, DATABASE_PATH
from api.models import HealthResponse, HeartbeatRequest

router = APIRouter(tags=["Health & Heartbeat"])

@router.get("/api/health", response_model=HealthResponse)
async def check_health(db: aiosqlite.Connection = Depends(get_db)):
    """
    Kiểm tra trạng thái hệ thống: trạng thái hoạt động của REST API, kết nối của EA và kích thước Database.
    """
    try:
        # Lấy thông tin nhịp đập của EA
        async with db.execute("SELECT last_ping, ea_version, mt5_connected FROM ea_heartbeat WHERE id = 1") as cursor:
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
                # SQLite stores datetime as ISO format string
                ea_last_ping = datetime.fromisoformat(last_ping_str)
                # Nếu ping cuối cách đây dưới 30 giây -> EA online
                delta = datetime.utcnow() - ea_last_ping
                ea_online = delta.total_seconds() < 30.0
                
        # Tính kích thước DB
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
async def update_heartbeat(req: HeartbeatRequest, db: aiosqlite.Connection = Depends(get_db)):
    """
    Cập nhật nhịp đập từ EA trên MT5 để báo hiệu EA vẫn đang hoạt động tốt.
    """
    now = datetime.utcnow().isoformat()
    try:
        await db.execute(
            """
            INSERT INTO ea_heartbeat (id, last_ping, ea_version, mt5_connected) 
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET 
                last_ping = excluded.last_ping,
                ea_version = excluded.ea_version,
                mt5_connected = excluded.mt5_connected
            """,
            (now, req.ea_version, 1 if req.mt5_connected else 0)
        )
        await db.commit()
        return {"status": "success", "message": "Heartbeat updated", "time": now}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
