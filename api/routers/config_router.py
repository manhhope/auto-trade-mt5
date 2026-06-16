from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import aiosqlite
from typing import Dict, Any, Optional
from api.database import get_db
from api.models import ConfigUpdateRequest, LotOverrideRequest
import api.services.config_service as config_service
from api.services.config_service import get_active_account_id

router = APIRouter(prefix="/api/config", tags=["Configuration"])

ALLOWED_CONFIG_KEYS = {
    "mode", "default_lot", "queue_expire_minutes", 
    "sl_buffer_pips", "signal_group_id",
    "trailing_enabled", "trailing_be_pips", "trailing_be_offset",
    "trailing_step_pips", "trailing_step_distance",
    "partial_close_enabled", "partial_close_pips", "partial_close_ratio",
    "partial_close_ratios", "partial_close_pips_stages",
    "trailing_manual_enabled", "signal_execution_mode"
}

@router.get("")
async def get_configuration(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Lấy toàn bộ cấu hình hệ thống cho tài khoản được chỉ định."""
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await config_service.get_all_configs(db, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/trailing")
async def get_trailing_configuration(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Lấy cấu hình trailing stop được gộp gọn cho EA của tài khoản tương ứng."""
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        configs = await config_service.get_all_configs(db, account_id)
        
        def to_bool(val) -> bool:
            return str(val).lower() == "true"
            
        def to_int(val, default: int = 0) -> int:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return default
                
        def to_float(val, default: float = 0.0) -> float:
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
                
        return {
            "enabled": to_bool(configs.get("trailing_enabled", "true")),
            "be_pips": to_int(configs.get("trailing_be_pips", "15")),
            "be_offset": to_int(configs.get("trailing_be_offset", "2")),
            "step_pips": to_int(configs.get("trailing_step_pips", "10")),
            "step_distance": to_int(configs.get("trailing_step_distance", "8")),
            "partial_enabled": to_bool(configs.get("partial_close_enabled", "false")),
            "partial_pips": to_int(configs.get("partial_close_pips", "30")),
            "partial_ratio": to_float(configs.get("partial_close_ratio", "0.5")),
            "partial_ratios": str(configs.get("partial_close_ratios", "33/33/33")),
            "partial_pips_stages": str(configs.get("partial_close_pips_stages", "50/100/")),
            "manual_enabled": to_bool(configs.get("trailing_manual_enabled", "false"))
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{key}")
async def update_config(
    request: Request,
    key: str, 
    req: ConfigUpdateRequest,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Cập nhật giá trị cấu hình theo key cho tài khoản được chỉ định.
    """
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

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
    elif key == "signal_execution_mode":
        if value not in ["active", "all"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="signal_execution_mode phải là 'active' hoặc 'all'")
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
    elif key in ["trailing_enabled", "partial_close_enabled", "trailing_manual_enabled"]:
        if value.lower() not in ["true", "false"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{key} phải là 'true' hoặc 'false'")
    elif key in ["trailing_be_pips", "trailing_be_offset", "trailing_step_pips", "trailing_step_distance", "partial_close_pips"]:
        try:
            val = int(value)
            if val < 0:
                raise ValueError()
            if key in ["trailing_step_pips", "trailing_step_distance", "partial_close_pips"] and val <= 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{key} phải là số nguyên lớn hơn hoặc bằng 0")
    elif key == "partial_close_ratio":
        try:
            val = float(value)
            if val <= 0 or val >= 1.0:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="partial_close_ratio phải là số thực lớn hơn 0 và nhỏ hơn 1.0")
    elif key == "partial_close_ratios":
        parts = [p for p in value.split("/") if p.strip()]
        if not parts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="partial_close_ratios không được để trống")
        try:
            ratios = [int(p) for p in parts]
            if any(r <= 0 for r in ratios):
                raise ValueError()
            if sum(ratios) > 100:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tổng các tỷ lệ không được vượt quá 100%")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tỷ lệ chốt lời phải là các số nguyên dương phân tách bằng dấu '/' (ví dụ: 33/33/33)")
    elif key == "partial_close_pips_stages":
        parts = [p for p in value.split("/") if p.strip()]
        try:
            pips = [int(p) for p in parts]
            if any(p <= 0 for p in pips):
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số pips kích hoạt phải là các số nguyên dương phân tách bằng dấu '/' (ví dụ: 50/100/)")

    try:
        await config_service.update_config_value(db, key, value, account_id)
        return {"status": "success", "key": key, "value": value}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/lot-overrides")
async def list_lot_overrides(
    request: Request,
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Lấy danh sách ghi đè lot size cho từng cặp sản phẩm của tài khoản."""
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        return await config_service.get_all_lot_overrides(db, account_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/lot-overrides/{symbol}")
async def set_lot_override(
    request: Request,
    symbol: str, 
    req: LotOverrideRequest, 
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Thiết lập số lot ghi đè cho một symbol cụ thể cho tài khoản chỉ định."""
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    try:
        await config_service.update_lot_override(db, symbol, req.lot_size, account_id)
        return {"status": "success", "symbol": symbol.upper(), "lot_size": req.lot_size}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/lot-overrides/{symbol}")
async def remove_lot_override(
    request: Request,
    symbol: str, 
    account_id: Optional[int] = Query(None, description="Lọc theo account ID (chỉ admin)"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Xóa bỏ ghi đè lot size của một symbol cho tài khoản chỉ định."""
    if not getattr(request.state, "is_admin", True):
        account_id = request.state.account_id
    elif account_id is None:
        account_id = await get_active_account_id(db)

    success = await config_service.delete_lot_override(db, symbol, account_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy cấu hình lot override cho symbol {symbol.upper()} của tài khoản ID {account_id}"
        )
    return {"status": "success", "message": f"Lot override for {symbol.upper()} removed"}
