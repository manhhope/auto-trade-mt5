from fastapi import APIRouter, Depends, HTTPException, status, Request
import aiosqlite
from api.database import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/api/signal-sources", tags=["Signal Sources"])

class SignalSourceCreate(BaseModel):
    source_type: str
    source_key: str
    name: str
    mode: str = "queue"
    is_active: bool = True

class SignalSourceUpdate(BaseModel):
    name: str
    mode: str
    is_active: bool = True

def format_source_row(row) -> dict:
    d = dict(row)
    if "is_active" in d:
        d["is_active"] = bool(d["is_active"])
    return d

@router.get("")
async def list_signal_sources(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    if is_admin and not user_id:
        # Hệ thống admin thực sự: xem toàn bộ
        query = "SELECT * FROM signal_sources ORDER BY created_at ASC"
        params = ()
    else:
        # User: chỉ xem các nguồn liên kết với tài khoản của mình
        query = """
            SELECT s.* FROM signal_sources s
            JOIN accounts a ON s.account_id = a.id
            WHERE a.user_id = ?
            ORDER BY s.created_at ASC
        """
        params = (user_id,)
        
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [format_source_row(r) for r in rows]

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_signal_source(request: Request, req: SignalSourceCreate, db: aiosqlite.Connection = Depends(get_db)):
    account_id = getattr(request.state, "account_id", None)
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Tài khoản hoạt động chưa được thiết lập. Vui lòng tạo tài khoản trước."
        )
        
    try:
        cursor = await db.execute(
            """
            INSERT INTO signal_sources (account_id, source_type, source_key, name, mode, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, req.source_type, req.source_key, req.name, req.mode, 1 if req.is_active else 0)
        )
        await db.commit()
        insert_id = cursor.lastrowid
        
        async with db.execute("SELECT * FROM signal_sources WHERE id = ?", (insert_id,)) as c:
            row = await c.fetchone()
            return format_source_row(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{source_id}")
async def update_signal_source(request: Request, source_id: int, req: SignalSourceUpdate, db: aiosqlite.Connection = Depends(get_db)):
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    # Check ownership
    if is_admin and not user_id:
        query = "SELECT * FROM signal_sources WHERE id = ?"
        params = (source_id,)
    else:
        query = """
            SELECT s.* FROM signal_sources s
            JOIN accounts a ON s.account_id = a.id
            WHERE s.id = ? AND a.user_id = ?
        """
        params = (source_id, user_id)
        
    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nguồn tín hiệu hoặc bạn không có quyền chỉnh sửa")
            
    try:
        await db.execute(
            "UPDATE signal_sources SET name = ?, mode = ?, is_active = ? WHERE id = ?",
            (req.name, req.mode, 1 if req.is_active else 0, source_id)
        )
        await db.commit()
        
        async with db.execute("SELECT * FROM signal_sources WHERE id = ?", (source_id,)) as c:
            row = await c.fetchone()
            return format_source_row(row)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{source_id}")
async def delete_signal_source(request: Request, source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", True)
    
    # Check ownership
    if is_admin and not user_id:
        query = "SELECT * FROM signal_sources WHERE id = ?"
        params = (source_id,)
    else:
        query = """
            SELECT s.* FROM signal_sources s
            JOIN accounts a ON s.account_id = a.id
            WHERE s.id = ? AND a.user_id = ?
        """
        params = (source_id, user_id)
        
    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nguồn tín hiệu hoặc bạn không có quyền xóa")
            
    try:
        await db.execute("DELETE FROM signal_sources WHERE id = ?", (source_id,))
        await db.commit()
        return {"status": "success", "message": f"Đã xóa nguồn tín hiệu ID {source_id}"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
