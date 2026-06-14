import os
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("API_KEY", "your-secret-api-key-here")

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware xác thực mọi HTTP request qua header X-API-Key.
    Bỏ qua kiểm tra cho các router công khai (như health check, docs).
    """
    async def dispatch(self, request: Request, call_next):
        # Bỏ qua xác thực cho Swagger docs, redoc, openapi.json và health check
        path = request.url.path
        if path in ["/docs", "/redoc", "/openapi.json", "/api/health", "/"]:
            return await call_next(request)
            
        api_key_header = request.headers.get("X-API-Key")
        if not api_key_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing X-API-Key header"}
            )
            
        if api_key_header != API_KEY:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid X-API-Key"}
            )
            
        return await call_next(request)
