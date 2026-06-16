import pytest
from httpx import AsyncClient
import uuid

@pytest.mark.asyncio
async def test_get_report_summary_day(client: AsyncClient):
    # 1. Tạo một lệnh closed trong hôm nay
    trade_uuid = f"rep-uuid-{uuid.uuid4()}"
    payload = {
        "uuid": trade_uuid,
        "symbol": "XAUUSD",
        "trade_type": "BUY",
        "lot_size": 0.01
    }
    r_create = await client.post("/api/trades", json=payload)
    trade_id = r_create.json()["id"]
    
    # Khớp và đóng lệnh để nó được tính vào report
    await client.put(f"/api/trades/{trade_id}", json={
        "status": "FILLED",
        "ticket": 88888,
        "open_price": 2300.0
    })
    
    await client.put(f"/api/trades/{trade_id}", json={
        "status": "CLOSED",
        "close_price": 2310.0,
        "pnl": 10.0,
        "close_reason": "TP_HIT"
    })
    
    # 2. Lấy report summary ngày
    response = await client.get("/api/reports/summary?period=day")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "day"
    assert data["total_trades"] >= 1
    assert data["winning_trades"] >= 1
    assert data["total_pnl"] >= 10.0
    
    # Kiểm tra danh sách trades có chứa lệnh vừa đóng
    trades = data.get("trades", [])
    assert len(trades) >= 1
    assert any(t["ticket"] == 88888 for t in trades)
