import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_action_log_success(client: AsyncClient):
    payload = {
        "ticket": 623566161,
        "symbol": "XAUUSDm",
        "action_type": "TRAILING_SL",
        "details": "4331.496 -> 4331.196",
        "pnl": 10.50,
        "current_price": 4330.12,
        "lot_size": 0.02,
        "trade_type": "SELL"
    }
    response = await client.post("/api/action-logs", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@pytest.mark.asyncio
async def test_get_action_logs(client: AsyncClient):
    # Tạo trước một log hành động
    action_payload = {
        "ticket": 623566161,
        "symbol": "XAUUSDm",
        "action_type": "PARTIAL_CLOSE",
        "details": "1/3",
        "pnl": 20.0,
        "current_price": 4330.12,
        "lot_size": 0.01,
        "trade_type": "SELL"
    }
    r_action = await client.post("/api/action-logs", json=action_payload)
    assert r_action.status_code == 200

    # Gọi GET /api/action-logs
    response = await client.get("/api/action-logs")
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) > 0
    assert logs[0]["type"] == "action"
    assert logs[0]["ticket"] == 623566161
    assert logs[0]["pnl"] == 20.0
    assert logs[0]["details"] == "1/3"

@pytest.mark.asyncio
async def test_sync_closed_trades(client: AsyncClient):
    payload = {
        "trades": [
            {
                "ticket": 999999999,
                "symbol": "XAUUSDm",
                "trade_type": "BUY",
                "lot_size": 0.02,
                "open_price": 2330.50,
                "close_price": 2335.50,
                "pnl": 10.0,
                "commission": -0.04,
                "swap": -0.01,
                "opened_at": "2026-06-16T12:00:00",
                "closed_at": "2026-06-16T12:05:00",
                "close_reason": "TP_HIT"
            }
        ]
    }
    response = await client.post("/api/trades/sync-closed", json=payload)
    assert response.status_code == 200
    assert response.json()["synced_count"] == 1

    # Kiểm tra xem có lấy ra được từ lịch sử logs không
    response_logs = await client.get("/api/action-logs")
    assert response_logs.status_code == 200
    logs = response_logs.json()
    # Tìm trade có ticket là 999999999
    synced_trade = None
    for item in logs:
        if item.get("ticket") == 999999999:
            synced_trade = item
            break
            
    assert synced_trade is not None
    assert synced_trade["type"] == "trade"
    assert synced_trade["symbol"] == "XAUUSDm"
    assert synced_trade["pnl"] == 10.0
    assert synced_trade["close_reason"] == "TP_HIT"
