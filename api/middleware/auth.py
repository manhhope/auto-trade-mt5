import os
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from api.database import get_db_connection

API_KEY = os.getenv("API_KEY", "your-secret-api-key-here")

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware xác thực mọi HTTP request qua header X-API-Key hoặc X-Account-Token.
    Bỏ qua kiểm tra cho các router công khai (như health check, docs).
    """
    async def dispatch(self, request: Request, call_next):
        # Bỏ qua xác thực cho Swagger docs, redoc, openapi.json, health check và webhooks TradingView
        path = request.url.path
        if path.startswith("/api/webhooks/tradingview/") or path in ["/docs", "/redoc", "/openapi.json", "/api/health", "/"]:
            return await call_next(request)
            
        # 1. Kiểm tra Admin X-API-Key
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            if api_key_header != API_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid X-API-Key"}
                )
            
            # Thêm hỗ trợ định danh Telegram User khi Bot gọi API
            telegram_user_id = request.headers.get("X-Telegram-User-Id")
            if telegram_user_id:
                db = await get_db_connection()
                try:
                    # Tra cứu user_id và kiểm tra phê duyệt
                    async with db.execute(
                        "SELECT id, is_approved FROM users WHERE telegram_id = ?",
                        (str(telegram_user_id),)
                    ) as cursor:
                        user_row = await cursor.fetchone()
                        if not user_row:
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "User not registered."}
                            )
                        if not user_row["is_approved"]:
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "User not approved by Admin."}
                            )
                        
                        user_id = user_row["id"]
                        
                    # Tra cứu tài khoản active của user
                    async with db.execute(
                        "SELECT id FROM accounts WHERE user_id = ? AND is_active = 1 LIMIT 1",
                        (user_id,)
                    ) as cursor:
                        acc_row = await cursor.fetchone()
                        active_account_id = acc_row["id"] if acc_row else None
                        
                    request.state.is_admin = False  # Đánh dấu không phải admin thực sự để lọc dữ liệu
                    request.state.user_id = user_id
                    request.state.account_id = active_account_id
                finally:
                    await db.close()
            else:
                request.state.is_admin = True
                request.state.user_id = None
                request.state.account_id = None
                
            return await call_next(request)
            
        # 2. Kiểm tra Account Token (dành cho EA)
        account_token_header = request.headers.get("X-Account-Token")
        if account_token_header:
            db = await get_db_connection()
            try:
                async with db.execute("SELECT id FROM accounts WHERE token = ?", (account_token_header,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={"detail": "Invalid X-Account-Token"}
                        )
                    request.state.is_admin = False
                    request.state.account_id = row["id"]
            finally:
                await db.close()
            return await call_next(request)
            
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing authorization headers (X-API-Key or X-Account-Token)"}
        )
