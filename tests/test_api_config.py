import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_trailing_config(client: AsyncClient):
    response = await client.get("/api/config/trailing")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["be_pips"] == 15
    assert data["be_offset"] == 2
    assert data["step_pips"] == 10
    assert data["step_distance"] == 8
    assert data["partial_enabled"] is False
    assert data["partial_pips"] == 30
    assert data["partial_ratio"] == 0.5

@pytest.mark.asyncio
async def test_update_trailing_config_success(client: AsyncClient):
    # Cập nhật trailing_enabled sang false
    response = await client.put("/api/config/trailing_enabled", json={"value": "false"})
    assert response.status_code == 200
    assert response.json()["value"] == "false"
    
    # Đọc lại config gộp
    response = await client.get("/api/config/trailing")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    
    # Cập nhật trailing_be_pips sang 20
    response = await client.put("/api/config/trailing_be_pips", json={"value": "20"})
    assert response.status_code == 200
    
    # Đọc lại config gộp
    response = await client.get("/api/config/trailing")
    assert response.json()["be_pips"] == 20

    # Cập nhật partial_close_ratios và partial_close_pips_stages thành công
    response = await client.put("/api/config/partial_close_ratios", json={"value": "25/50/25"})
    assert response.status_code == 200
    response = await client.put("/api/config/partial_close_pips_stages", json={"value": "50/100/150"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_update_trailing_config_validation_fail(client: AsyncClient):
    # trailing_enabled sai định dạng
    response = await client.put("/api/config/trailing_enabled", json={"value": "not-bool"})
    assert response.status_code == 400
    
    # trailing_be_pips sai định dạng
    response = await client.put("/api/config/trailing_be_pips", json={"value": "-5"})
    assert response.status_code == 400
    
    # partial_close_ratio sai định dạng (>= 1.0)
    response = await client.put("/api/config/partial_close_ratio", json={"value": "1.2"})
    assert response.status_code == 400

    # partial_close_ratios sai định dạng (> 100%)
    response = await client.put("/api/config/partial_close_ratios", json={"value": "50/60"})
    assert response.status_code == 400

    # partial_close_ratios giá trị âm
    response = await client.put("/api/config/partial_close_ratios", json={"value": "50/-10"})
    assert response.status_code == 400

    # partial_close_pips_stages sai định dạng
    response = await client.put("/api/config/partial_close_pips_stages", json={"value": "50/abc"})
    assert response.status_code == 400
    
    # key không được phép chỉnh sửa
    response = await client.put("/api/config/non_existent_key", json={"value": "test"})
    assert response.status_code == 400
