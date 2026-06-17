import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_signal_routing_modes(client: AsyncClient):
    # 1. Register a test user and approve
    tg_user_id = 999999999
    reg_res = await client.post("/api/users", json={"telegram_id": str(tg_user_id), "username": "test_routing_user"})
    assert reg_res.status_code == 201
    
    app_res = await client.put(f"/api/users/{tg_user_id}/approve")
    assert app_res.status_code == 200
    
    # 2. Create an account for the user
    acc_res = await client.post(
        "/api/accounts", 
        json={"name": "Test Account 1", "platform": "MT5", "account_number": "99991111"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert acc_res.status_code == 201
    acc_data = acc_res.json()
    account_id = acc_data["id"]
    
    # Set as active
    act_res = await client.put(f"/api/accounts/{account_id}/active", headers={"X-Telegram-User-Id": str(tg_user_id)})
    assert act_res.status_code == 200
    
    # 3. Create signal sources
    # Group A: mode = auto
    source_a = await client.post(
        "/api/signal-sources",
        json={"source_type": "telegram_group", "source_key": "-100222222", "name": "Group Auto A", "mode": "auto"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert source_a.status_code == 201
    
    # Group B: mode = queue
    source_b = await client.post(
        "/api/signal-sources",
        json={"source_type": "telegram_group", "source_key": "-100333333", "name": "Group Queue B", "mode": "queue"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert source_b.status_code == 201

    # Add symbol mapping for GOLD in db for testing (GOLD maps to XAUUSDm in default mapping if exists, but let's send GOLD)
    
    # 4. Post signal to Group A (auto)
    payload_a = {
        "group_id": "-100222222",
        "message_id": 1001,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    res_sig_a = await client.post("/api/signals", json=payload_a)
    assert res_sig_a.status_code == 201
    data_a = res_sig_a.json()
    assert data_a["status"] == "EXECUTED"
    assert "auto_executed_trade" in data_a
    assert data_a["auto_executed_trade"]["status"] == "PENDING"
    assert data_a["auto_executed_trade"]["account_id"] == account_id
    
    # 5. Post signal to Group B (queue)
    payload_b = {
        "group_id": "-100333333",
        "message_id": 1002,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    res_sig_b = await client.post("/api/signals", json=payload_b)
    assert res_sig_b.status_code == 201
    data_b = res_sig_b.json()
    assert data_b["status"] == "QUEUED"
    assert "auto_executed_trade" not in data_b

@pytest.mark.asyncio
async def test_tradingview_webhook_routing(client: AsyncClient):
    # 1. Register a test user and approve
    tg_user_id = 888888888
    reg_res = await client.post("/api/users", json={"telegram_id": str(tg_user_id), "username": "test_tv_user"})
    assert reg_res.status_code == 201
    await client.put(f"/api/users/{tg_user_id}/approve")
    
    # 2. Create account for the user
    acc_res = await client.post(
        "/api/accounts", 
        json={"name": "Test Account 2", "platform": "MT5", "account_number": "88882222"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["id"]
    
    # Set active
    await client.put(f"/api/accounts/{account_id}/active", headers={"X-Telegram-User-Id": str(tg_user_id)})
    
    # 3. Create TradingView source with token key
    token = "testtoken123"
    source_tv = await client.post(
        "/api/signal-sources",
        json={"source_type": "tradingview", "source_key": token, "name": "TV Alert A", "mode": "auto"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert source_tv.status_code == 201
    
    # 4. Trigger TradingView Webhook
    payload = {
        "symbol": "GOLD",
        "action": "BUY",
        "price": 2350.0,
        "sl": 2340.0,
        "tp": 2370.0
    }
    tv_res = await client.post(f"/api/webhooks/tradingview/{token}", json=payload)
    assert tv_res.status_code == 200
    data = tv_res.json()
    assert data["status"] == "success"
    assert data["signal"]["status"] == "EXECUTED"
    assert data["signal"]["auto_executed_trade"]["account_id"] == account_id

@pytest.mark.asyncio
async def test_signal_source_active_toggle(client: AsyncClient):
    # 1. Register user & account
    tg_user_id = 777777777
    await client.post("/api/users", json={"telegram_id": str(tg_user_id), "username": "test_toggle_user"})
    await client.put(f"/api/users/{tg_user_id}/approve")
    
    acc_res = await client.post(
        "/api/accounts", 
        json={"name": "Test Account 3", "platform": "MT5", "account_number": "77773333"},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["id"]
    await client.put(f"/api/accounts/{account_id}/active", headers={"X-Telegram-User-Id": str(tg_user_id)})

    # 2. Create Telegram group source
    source_res = await client.post(
        "/api/signal-sources",
        json={"source_type": "telegram_group", "source_key": "-100777777", "name": "Group Toggle", "mode": "auto", "is_active": True},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert source_res.status_code == 201
    source_id = source_res.json()["id"]

    # 3. Post signal when active -> should be processed (executed)
    payload_active = {
        "group_id": "-100777777",
        "message_id": 2001,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    res_sig_active = await client.post("/api/signals", json=payload_active)
    assert res_sig_active.status_code == 201
    assert res_sig_active.json()["status"] == "EXECUTED"

    # 4. Toggle source to inactive
    update_res = await client.put(
        f"/api/signal-sources/{source_id}",
        json={"name": "Group Toggle", "mode": "auto", "is_active": False},
        headers={"X-Telegram-User-Id": str(tg_user_id)}
    )
    assert update_res.status_code == 200
    assert update_res.json()["is_active"] is False

    # 5. Post signal when inactive -> should NOT be processed (no fallback, no signals created)
    payload_inactive = {
        "group_id": "-100777777",
        "message_id": 2002,
        "raw_message": "BUY GOLD 2350.00 SL 2340 TP 2370",
        "parsed_type": "BUY",
        "parsed_symbol": "GOLD",
        "parsed_price": 2350.0,
        "parsed_sl": 2340.0,
        "parsed_tp": 2370.0,
        "parse_success": True
    }
    res_sig_inactive = await client.post("/api/signals", json=payload_inactive)
    assert res_sig_inactive.status_code == 201
    assert res_sig_inactive.json() == {"status": "no_signals_created"}
