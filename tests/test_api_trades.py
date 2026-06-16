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
    assert data["symbol"] == "XAUUSDm"
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

@pytest.mark.asyncio
async def test_gold_price_expansion(client: AsyncClient):
    # 1. Update gold price in account_info to 4332.12 to mock the environment
    account_payload = {
        "balance": 10000.0,
        "equity": 10000.0,
        "margin": 0.0,
        "free_margin": 10000.0,
        "profit": 0.0,
        "server": "Demo",
        "account_number": 12345,
        "account_name": "Test Account",
        "currency": "USD",
        "leverage": 500,
        "gold_price": 4332.12,
        "gold_change_1h": 0.0,
        "gold_change_4h": 0.0,
        "gold_change_1d": 0.0
    }
    r_acc = await client.put("/api/account", json=account_payload)
    assert r_acc.status_code == 200

    # 2. Create a trade with 2-digit stop loss (e.g. 20.0)
    trade_uuid = f"exp-uuid-{uuid.uuid4()}"
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.03,
        "stop_loss": 20.0, # should expand to 4320.00
        "take_profit": 55.5, # should expand to 4355.50
        "source": "MANUAL"
    }
    response = await client.post("/api/trades", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["stop_loss"] == 4320.00
    assert data["take_profit"] == 4355.50

