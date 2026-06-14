import httpx
from typing import Dict, Any, List, Optional
from bot.config import config

class ApiClient:
    """
    HTTP Client async kết nối đến FastAPI backend, tự động đính kèm X-API-Key.
    """
    def __init__(self):
        self.base_url = config.api_url.rstrip("/")
        self.headers = {
            "X-API-Key": config.api_key,
            "Content-Type": "application/json"
        }

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        json_body: Optional[Dict[str, Any]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
            response = await client.request(method, url, json=json_body, params=params)
            response.raise_for_status()
            return response.json()

    # ── Trades ──
    async def create_trade(self, trade_req: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/trades", json_body=trade_req)

    async def get_trades(
        self, 
        status: Optional[str] = None, 
        close_requested: Optional[bool] = None, 
        notified: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit}
        if status is not None:
            params["status"] = status
        if close_requested is not None:
            params["close_requested"] = "true" if close_requested else "false"
        if notified is not None:
            params["notified"] = "true" if notified else "false"
        return await self._request("GET", "/api/trades", params=params)

    async def request_close_trade(self, trade_id: int) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/trades/{trade_id}/close-request")

    async def mark_notified(self, trade_id: int) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/trades/{trade_id}/notify")

    # ── Signals ──
    async def create_signal(self, signal_req: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/signals", json_body=signal_req)

    async def get_signals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status is not None:
            params["status"] = status
        return await self._request("GET", "/api/signals", params=params)

    async def confirm_signal(self, signal_id_or_queue: str, lot_override: Optional[float] = None) -> Dict[str, Any]:
        body = {"lot_override": lot_override} if lot_override is not None else {}
        return await self._request("PUT", f"/api/signals/{signal_id_or_queue}/confirm", json_body=body)

    async def reject_signal(self, signal_id_or_queue: str) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/signals/{signal_id_or_queue}/reject")

    async def confirm_all_signals(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/signals/confirm-all")

    async def reject_all_signals(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/signals/reject-all")

    # ── Config ──
    async def get_config(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/config")

    async def update_config(self, key: str, value: str) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/config/{key}", json_body={"value": value})

    async def set_lot_override(self, symbol: str, lot_size: float) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/config/lot-overrides/{symbol}", json_body={"lot_size": lot_size})

    async def delete_lot_override(self, symbol: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/config/lot-overrides/{symbol}")

    # ── Account & Positions ──
    async def get_account(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/account")

    async def get_positions(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "/api/positions")

    # ── Health ──
    async def get_health(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/health")

    # ── Reports ──
    async def get_report_summary(self, period: str) -> Dict[str, Any]:
        return await self._request("GET", "/api/reports/summary", params={"period": period})

    async def get_report_trend(self, weeks: int = 4) -> Dict[str, Any]:
        return await self._request("GET", "/api/reports/trend", params={"weeks": weeks})

# Khởi tạo instance API client dùng chung
api_client = ApiClient()
