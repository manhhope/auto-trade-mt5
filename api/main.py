from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.database import init_database
from api.middleware.auth import APIKeyMiddleware
from api.routers import trades, signals, account, config_router, reports, health, action_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động: Tự động khởi tạo database SQLite và các bảng nếu chưa có
    await init_database()
    yield
    # Giải phóng tài nguyên (nếu có)
    pass

def create_app() -> FastAPI:
    app = FastAPI(
        title="Telegram MT5 Bridge API",
        description="Middleware REST API kết nối giữa Telegram Bot và Expert Advisor (EA) trên MetaTrader 5.",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # 1. Thêm API Key Authentication Middleware để bảo mật
    app.add_middleware(APIKeyMiddleware)
    
    # 2. Đăng ký các router
    app.include_router(health.router) # Đăng ký health đầu tiên vì có các đường dẫn không cần middleware
    app.include_router(trades.router)
    app.include_router(signals.router)
    app.include_router(account.router)
    app.include_router(config_router.router)
    app.include_router(reports.router)
    app.include_router(action_router.router)
    
    @app.get("/", tags=["General"])
    async def index():
        return {
            "message": "Welcome to Telegram MT5 Bridge API",
            "docs_url": "/docs",
            "status": "running"
        }
        
    return app

# Bản app chính dùng cho ASGI server chạy
app = create_app()
