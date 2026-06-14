import pytest
import uuid
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_trade_success(client: AsyncClient):
    trade_uuid = f"uuid-{uuid.uuid4()}"
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01,
        "stop_loss": 2340.0,
        "take_profit": 2370.0,
        "source": "MANUAL"
    }
    response = await client.post("/api/trades", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["uuid"] == trade_uuid
    assert data["symbol"] == "XAUUSD"
    assert data["status"] == "PENDING"
    assert data["close_requested"] is False
    assert data["notified"] is False

@pytest.mark.asyncio
async def test_create_trade_duplicate_uuid(client: AsyncClient):
    trade_uuid = f"dup-uuid-{uuid.uuid4()}"
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01
    }
    # Tạo lần đầu
    r1 = await client.post("/api/trades", json=payload)
    assert r1.status_code == 201
    
    # Tạo lần hai trùng UUID
    r2 = await client.post("/api/trades", json=payload)
    assert r2.status_code == 400
    assert "already exists" in r2.json()["detail"].lower() or "đã tồn tại" in r2.json()["detail"].lower()

@pytest.mark.asyncio
async def test_get_trades_filter(client: AsyncClient):
    trade_uuid = f"get-uuid-{uuid.uuid4()}"
    # Tạo lệnh
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.02
    }
    await client.post("/api/trades", json=payload)
    
    # Lấy danh sách lọc PENDING
    response = await client.get("/api/trades?status=PENDING")
    assert response.status_code == 200
    trades = response.json()
    assert len(trades) >= 1
    assert any(t["uuid"] == trade_uuid for t in trades)

@pytest.mark.asyncio
async def test_update_trade_status(client: AsyncClient):
    trade_uuid = f"update-uuid-{uuid.uuid4()}"
    # 1. Tạo lệnh PENDING
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01
    }
    r_create = await client.post("/api/trades", json=payload)
    trade_id = r_create.json()["id"]
    
    # 2. Update status sang FILLED (khớp lệnh)
    update_payload = {
        "status": "FILLED",
        "ticket": 1234567,
        "open_price": 2350.25
    }
    r_update = await client.put(f"/api/trades/{trade_id}", json=update_payload)
    assert r_update.status_code == 200
    data = r_update.json()
    assert data["status"] == "FILLED"
    assert data["ticket"] == 1234567
    assert data["open_price"] == 2350.25
    assert data["opened_at"] is not None

@pytest.mark.asyncio
async def test_request_close_filled_trade(client: AsyncClient):
    trade_uuid = f"close-uuid-{uuid.uuid4()}"
    # 1. Tạo và khớp lệnh
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01
    }
    r_create = await client.post("/api/trades", json=payload)
    trade_id = r_create.json()["id"]
    
    # Khớp lệnh
    await client.put(f"/api/trades/{trade_id}", json={"status": "FILLED", "ticket": 5555, "open_price": 2355.0})
    
    # 2. Gửi yêu cầu đóng lệnh
    r_close = await client.put(f"/api/trades/{trade_id}/close-request")
    assert r_close.status_code == 200
    assert r_close.json()["close_requested"] is True

@pytest.mark.asyncio
async def test_auth_failed_without_key(client: AsyncClient):
    # Xóa header X-API-Key tạm thời
    client.headers.clear()
    
    trade_uuid = f"auth-uuid-{uuid.uuid4()}"
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01
    }
    response = await client.post("/api/trades", json=payload)
    assert response.status_code == 401
    assert "missing" in response.json()["detail"].lower()
