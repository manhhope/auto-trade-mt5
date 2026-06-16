import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_sync_account_info_with_gold(client: AsyncClient):
    payload = {
        "balance": 10000.50,
        "equity": 10000.50,
        "margin": 0.0,
        "free_margin": 10000.50,
        "profit": 0.0,
        "server": "Exness-Trial",
        "account_number": 8881234,
        "account_name": "Antigravity Trader",
        "currency": "USD",
        "leverage": 2000,
        "gold_price": 2330.50,
        "gold_change_1h": 2.50,
        "gold_change_4h": -5.00,
        "gold_change_1d": 12.00
    }
    
    # 1. Sync account info via PUT /api/account
    r_sync = await client.put("/api/account", json=payload)
    assert r_sync.status_code == 200
    data = r_sync.json()
    assert data["balance"] == 10000.50
    assert data["gold_price"] == 2330.50
    assert data["gold_change_1h"] == 2.50
    assert data["gold_change_4h"] == -5.00
    assert data["gold_change_1d"] == 12.00
    
    # 2. Get account info via GET /api/account
    r_get = await client.get("/api/account")
    assert r_get.status_code == 200
    get_data = r_get.json()
    assert get_data["gold_price"] == 2330.50
