import asyncio
import logging
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_trade_closed

logger = logging.getLogger("bg_tasks")

async def send_telegram_safe(bot, chat_id: int, text: str, parse_mode: str = "Markdown", max_retries: int = 2):
    """Gửi tin nhắn Telegram với retry tự động khi gặp lỗi mạng"""
    for attempt in range(1 + max_retries):
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limit, retry sau {e.retry_after}s (lần {attempt+1})")
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            logger.warning(f"Network error gửi tin nhắn (lần {attempt+1}/{1+max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(3.0 * (attempt + 1))
        except Exception as e:
            logger.error(f"Lỗi không mong đợi khi gửi tin nhắn: {e}")
            return False
    logger.error(f"Bỏ qua tin nhắn sau {1+max_retries} lần thử thất bại.")
    return False

async def get_today_pnl_summary_str() -> str:
    """Lấy tổng hợp P/L hôm nay để đính kèm thông báo"""
    try:
        summary = await api_client.get_report_summary(period="day")
        pnl = summary.get("total_pnl", 0.0)
        wins = summary.get("winning_trades", 0)
        losses = summary.get("losing_trades", 0)
        pnl_sign = "+" if pnl > 0 else ""
        indicator = "❇️" if pnl >= 0 else "❌"
        return f"📈 Hôm nay: **{pnl_sign}${pnl:.2f}** {indicator} ({wins}W / {losses}L)"
    except Exception as e:
        logger.error(f"Lỗi khi lấy P/L hôm nay: {e}")
        return ""

async def closed_trade_notification_loop(bot):
    """Vòng lặp kiểm tra và thông báo các lệnh đã đóng (mỗi 2 giây)"""
    logger.info("Starting Closed Trade Notification loop...")
    while True:
        try:
            # Lấy các lệnh đã đóng nhưng chưa thông báo
            closed_trades = await api_client.get_trades(status="CLOSED", notified=False)
            
            for trade in closed_trades:
                trade_id = trade["id"]
                logger.info(f"Phát hiện lệnh đã đóng ID {trade_id}, đang gửi thông báo...")
                
                # Lấy tổng kết P/L hôm nay
                today_summary = await get_today_pnl_summary_str()
                
                # Format tin nhắn thông báo lệnh đóng
                msg = format_trade_closed(trade, today_summary)
                
                # Gửi tin nhắn đến admin
                sent = await send_telegram_safe(bot, config.owner_chat_id, msg)
                
                # Đánh dấu đã thông báo thành công
                if sent:
                    await api_client.mark_notified(trade_id)
                
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp Closed Trade Notification: {e}")
            
        await asyncio.sleep(2.0)

async def ea_health_check_loop(bot):
    """Vòng lặp kiểm tra sức khỏe của EA và cảnh báo nếu mất kết nối (mỗi 30 giây)"""
    logger.info("Starting EA Health Check loop...")
    ea_was_offline = False  # Track state to avoid spamming alerts
    
    while True:
        try:
            health = await api_client.get_health()
            
            if not health["ea_online"]:
                if not ea_was_offline:
                    # Gửi tin nhắn cảnh báo mất kết nối (đầu tiên)
                    await send_telegram_safe(
                        bot, config.owner_chat_id,
                        "🔴 **CẢNH BÁO: EA OFFLINE!**\nKiểm tra lại MT5 Terminal trên VPS."
                    )
                    ea_was_offline = True
                    logger.warning("EA went offline! Alert sent.")
            else:
                if ea_was_offline:
                    # Gửi tin nhắn thông báo kết nối lại
                    await send_telegram_safe(
                        bot, config.owner_chat_id,
                        "🟢 **THÔNG BÁO: EA ĐÃ ONLINE TRỞ LẠI!**\nKết nối đã được khôi phục thành công."
                    )
                    ea_was_offline = False
                    logger.info("EA came back online. Recovery alert sent.")
                    
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp EA Health Check: {e}")
            
        await asyncio.sleep(30.0)
