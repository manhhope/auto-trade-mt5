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
        # Bỏ qua xác thực cho Swagger docs, redoc, openapi.json và health check
        path = request.url.path
        if path in ["/docs", "/redoc", "/openapi.json", "/api/health", "/"]:
            return await call_next(request)
            
        # 1. Kiểm tra Admin X-API-Key
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            if api_key_header != API_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid X-API-Key"}
                )
            request.state.is_admin = True
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
