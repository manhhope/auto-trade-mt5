import os
import pytest
import aiosqlite
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator

# Thiết lập biến môi trường chỉ cho test và tạo thư mục data
os.environ["DATABASE_PATH"] = "data/test_trades.db"
os.environ["API_KEY"] = "testkey"
os.makedirs("data", exist_ok=True)

from api.main import create_app
from api.database import get_db, init_database

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Cung cấp database connection sạch và độc lập cho mỗi test case bằng cách tạo mới file db"""
    # 1. Đóng kết nối và xoá file database cũ để cô lập hoàn toàn các test case
    test_db_path = "data/test_trades.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except PermissionError:
            pass
            
    # 2. Khởi tạo database mới và các bảng
    await init_database()
    
    # 3. Kết nối và cung cấp cho test case
    conn = await aiosqlite.connect(test_db_path)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()

@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """Cung cấp AsyncClient kết nối tới test API server"""
    app = create_app()
    
    # Override dependency get_db để dùng database test ở trên
    async def override_get_db():
        yield db
        
    app.dependency_overrides[get_db] = override_get_db
    
    # Sử dụng header API Key và ASGITransport
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "testkey"}) as ac:
        yield ac
        
    # Xóa override sau khi xong
    app.dependency_overrides.clear()
