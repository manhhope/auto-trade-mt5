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

    # ── Accounts Management ──
    async def get_accounts(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "/api/accounts")

    async def create_account(self, name: str, platform: str, account_number: Optional[str] = None) -> Dict[str, Any]:
        body = {
            "name": name,
            "platform": platform,
            "account_number": account_number
        }
        return await self._request("POST", "/api/accounts", json_body=body)

    async def activate_account(self, account_id: int) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/accounts/{account_id}/active")

    async def delete_account(self, account_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/accounts/{account_id}")

    # ── Trades ──
    async def create_trade(self, trade_req: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/trades", json_body=trade_req)

    async def get_trades(
        self, 
        status: Optional[str] = None, 
        close_requested: Optional[bool] = None, 
        notified: Optional[bool] = None,
        limit: int = 50,
        account_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit}
        if status is not None:
            params["status"] = status
        if close_requested is not None:
            params["close_requested"] = "true" if close_requested else "false"
        if notified is not None:
            params["notified"] = "true" if notified else "false"
        if account_id is not None:
            params["account_id"] = account_id
        return await self._request("GET", "/api/trades", params=params)

    async def request_close_trade(self, trade_id: int) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/trades/{trade_id}/close-request")

    async def request_close_position_by_ticket(self, ticket: int, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("PUT", f"/api/positions/{ticket}/close", params=params)

    async def mark_notified(self, trade_id: int) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/trades/{trade_id}/notify")

    # ── Signals ──
    async def create_signal(self, signal_req: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/signals", json_body=signal_req)

    async def get_signals(self, status: Optional[str] = None, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {}
        if status is not None:
            params["status"] = status
        if account_id is not None:
            params["account_id"] = account_id
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
    async def get_config(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/config", params=params)

    async def get_trailing_config(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/config/trailing", params=params)

    async def update_config(self, key: str, value: str, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("PUT", f"/api/config/{key}", json_body={"value": value}, params=params)

    async def set_lot_override(self, symbol: str, lot_size: float, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("PUT", f"/api/config/lot-overrides/{symbol}", json_body={"lot_size": lot_size}, params=params)

    async def delete_lot_override(self, symbol: str, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("DELETE", f"/api/config/lot-overrides/{symbol}", params=params)

    # ── Account & Positions ──
    async def get_account(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/account", params=params)

    async def get_positions(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/positions", params=params)

    # ── Health ──
    async def get_health(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/health", params=params)

    # ── Reports ──
    async def get_report_summary(self, period: str, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"period": period}
        if account_id is not None:
            params["account_id"] = account_id
        return await self._request("GET", "/api/reports/summary", params=params)

    async def get_report_trend(self, weeks: int = 4, account_id: Optional[int] = None) -> Dict[str, Any]:
        params = {"weeks": weeks}
        if account_id is not None:
            params["account_id"] = account_id
        return await self._request("GET", "/api/reports/trend", params=params)

    # ── Action Logs ──
    async def get_action_logs(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"account_id": account_id} if account_id is not None else None
        return await self._request("GET", "/api/action-logs", params=params)

# Khởi tạo instance API client dùng chung
api_client = ApiClient()
