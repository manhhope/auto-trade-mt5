import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_receive_and_queue_signal(client: AsyncClient):
    payload = {
        "group_id": "-1001234567890",
        "message_id": 991,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    
    # Tạo signal (ở mode mặc định: queue)
    response = await client.post("/api/signals", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["queue_id"].startswith("SIG-")
    assert data["status"] == "QUEUED"
    assert data["parsed_symbol"] == "GOLD"
    assert data["parse_success"] is True

@pytest.mark.asyncio
async def test_confirm_queued_signal(client: AsyncClient):
    # 1. Tạo signal
    payload = {
        "group_id": "-1001234567890",
        "message_id": 992,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    r_create = await client.post("/api/signals", json=payload)
    sig_data = r_create.json()
    queue_id = sig_data["queue_id"]
    
    # 2. Xác nhận signal
    r_confirm = await client.put(f"/api/signals/{queue_id}/confirm", json={"lot_override": 0.05})
    assert r_confirm.status_code == 200
    trade = r_confirm.json()
    
    # Lệnh sinh ra từ signal phải ở trạng thái PENDING trên MT5
    assert trade["source"] == "SIGNAL"
    assert trade["symbol"] == "XAUUSD" # Đã được map từ GOLD -> XAUUSD trong DB
    assert trade["trade_type"] == "BUY"
    assert trade["lot_size"] == 0.05
    assert trade["stop_loss"] == 2340.0
    assert trade["take_profit"] == 2370.0
    assert trade["status"] == "PENDING"
    
    # Kiểm tra trạng thái signal đã được cập nhật thành EXECUTED
    r_signals = await client.get("/api/signals")
    sig_check = next(s for s in r_signals.json() if s["queue_id"] == queue_id)
    assert sig_check["status"] == "EXECUTED"

@pytest.mark.asyncio
async def test_reject_queued_signal(client: AsyncClient):
    # 1. Tạo signal
    payload = {
        "group_id": "-1001234567890",
        "message_id": 993,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    r_create = await client.post("/api/signals", json=payload)
    queue_id = r_create.json()["queue_id"]
    
    # 2. Từ chối signal
    r_reject = await client.put(f"/api/signals/{queue_id}/reject")
    assert r_reject.status_code == 200
    assert r_reject.json()["status"] == "REJECTED"
