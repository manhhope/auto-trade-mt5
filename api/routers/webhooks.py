from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite
from api.database import get_db
from api.models import TradingViewWebhookRequest, SignalCreateRequest
import api.services.signal_service as signal_service
import api.services.config_service as config_service
from bot.main import bot
from bot.services.background_tasks import send_telegram_safe
from bot.utils.formatter import format_auto_trade, format_queue_signal

router = APIRouter(tags=["Webhooks"])

@router.post("/api/webhooks/tradingview/{token_key}")
async def handle_tradingview_webhook(
    token_key: str,
    payload: TradingViewWebhookRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    # 1. Tìm signal_source khớp với token_key
    async with db.execute(
        "SELECT account_id, name, is_active FROM signal_sources WHERE source_type = 'tradingview' AND source_key = ?",
        (token_key,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook source not found."
            )
        account_id, source_name, is_active = row[0], row[1], bool(row[2])
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook source is inactive/paused."
            )

    # 2. Tạo SignalCreateRequest từ payload
    raw_msg = f"TradingView Alert [{source_name}]: {payload.action} {payload.symbol}"
    if payload.price:
        raw_msg += f" @ {payload.price}"
    if payload.sl:
        raw_msg += f" SL: {payload.sl}"
    if payload.tp:
        raw_msg += f" TP: {payload.tp}"

    signal_req = SignalCreateRequest(
        group_id=token_key,
        message_id=None,
        raw_message=raw_msg,
        parsed_type=payload.action.upper(),
        parsed_symbol=payload.symbol.upper(),
        parsed_price=payload.price,
        parsed_sl=payload.sl,
        parsed_tp=payload.tp,
        parse_success=True,
        account_id=account_id
    )

    # 3. Tạo tín hiệu qua service
    try:
        response = await signal_service.create_signal(db, signal_req)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process signal: {str(e)}"
        )

    # 4. Tìm telegram_id của user sở hữu tài khoản này để gửi thông báo
    telegram_id = None
    async with db.execute(
        """
        SELECT u.telegram_id FROM users u
        JOIN accounts a ON a.user_id = u.id
        WHERE a.id = ?
        """,
        (account_id,)
    ) as cursor:
        user_row = await cursor.fetchone()
        if user_row:
            telegram_id = user_row[0]

    # 5. Gửi thông báo đến Telegram
    if telegram_id:
        try:
            auto_trade = response.get("auto_executed_trade")
            if auto_trade:
                msg = format_auto_trade(auto_trade)
            else:
                expire_min_str = await config_service.get_config_value(db, "queue_expire_minutes", account_id)
                expire_min = int(expire_min_str) if expire_min_str else 15
                msg = format_queue_signal(response, expire_minutes=expire_min)
            
            # Gửi tin nhắn
            await send_telegram_safe(bot, int(telegram_id), msg)
        except Exception as e:
            import logging
            logging.getLogger("api").error(f"Failed to send TradingView webhook notification to Telegram: {e}")

    return {"status": "success", "signal": response}
