from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite
from typing import Dict, Any
from api.database import get_db
from api.models import ConfigUpdateRequest, LotOverrideRequest
import api.services.config_service as config_service

router = APIRouter(prefix="/api/config", tags=["Configuration"])

ALLOWED_CONFIG_KEYS = {
    "mode", "default_lot", "queue_expire_minutes", 
    "sl_buffer_pips", "signal_group_id"
}

@router.get("")
async def get_configuration(db: aiosqlite.Connection = Depends(get_db)):
    """Lấy toàn bộ cấu hình hệ thống bao gồm default lot, mode và các symbol lot overrides."""
    try:
        return await config_service.get_all_configs(db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{key}")
async def update_config(
    key: str, 
    req: ConfigUpdateRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Cập nhật giá trị cấu hình theo key. Các key hợp lệ:
    mode (auto/queue), default_lot (số thực > 0), queue_expire_minutes (số nguyên > 0),
    sl_buffer_pips (số thực), signal_group_id (số nguyên/chuỗi).
    """
    if key not in ALLOWED_CONFIG_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cấu hình '{key}' không được phép chỉnh sửa hoặc không tồn tại. Các key hợp lệ: {list(ALLOWED_CONFIG_KEYS)}"
        )
        
    value = req.value.strip()
    
    # Thực hiện các validate đơn giản
    if key == "mode":
        if value not in ["auto", "queue"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode phải là 'auto' hoặc 'queue'")
    elif key == "default_lot":
        try:
            lot = float(value)
            if lot <= 0 or lot > 100:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default_lot phải là số thực lớn hơn 0 và nhỏ hơn hoặc bằng 100")
    elif key == "queue_expire_minutes":
        try:
            minutes = int(value)
            if minutes <= 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="queue_expire_minutes phải là số nguyên lớn hơn 0")
    elif key == "sl_buffer_pips":
        try:
            float(value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sl_buffer_pips phải là số thực")

    try:
        await config_service.update_config_value(db, key, value)
        return {"status": "success", "key": key, "value": value}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/lot-overrides")
async def list_lot_overrides(db: aiosqlite.Connection = Depends(get_db)):
    """Lấy danh sách ghi đè lot size cho từng cặp sản phẩm."""
    try:
        return await config_service.get_all_lot_overrides(db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/lot-overrides/{symbol}")
async def set_lot_override(
    symbol: str, 
    req: LotOverrideRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """Thiết lập số lot ghi đè cho một symbol cụ thể (VD: XAUUSD -> 0.02 lot)."""
    try:
        await config_service.update_lot_override(db, symbol, req.lot_size)
        return {"status": "success", "symbol": symbol.upper(), "lot_size": req.lot_size}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/lot-overrides/{symbol}")
async def remove_lot_override(symbol: str, db: aiosqlite.Connection = Depends(get_db)):
    """Xóa bỏ ghi đè lot size của một symbol, quay lại dùng mặc định default_lot."""
    success = await config_service.delete_lot_override(db, symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy cấu hình lot override cho symbol {symbol.upper()}"
        )
    return {"status": "success", "message": f"Lot override for {symbol.upper()} removed"}
