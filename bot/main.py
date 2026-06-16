import logging
import asyncio
from aiohttp import ClientTimeout
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from bot.config import config
from bot.handlers import start, trade, manage, signal, config_cmd, report, trailing_cmd, menu_click, account_manager
from typing import Callable, Dict, Any, Awaitable

logger = logging.getLogger("bot")

class RetryMiddleware(BaseMiddleware):
    """Middleware tự động retry khi gặp lỗi mạng Telegram (timeout, connection error)"""
    
    def __init__(self, max_retries: int = 2, retry_delay: float = 3.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        last_error = None
        for attempt in range(1 + self.max_retries):
            try:
                return await handler(event, data)
            except TelegramRetryAfter as e:
                logger.warning(f"Telegram rate limit, retry sau {e.retry_after}s (lần {attempt+1})")
                await asyncio.sleep(e.retry_after)
                last_error = e
            except TelegramNetworkError as e:
                logger.warning(f"Telegram network error (lần {attempt+1}/{1+self.max_retries}): {e}")
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            except Exception:
                raise
        # Nếu hết retry, log và bỏ qua thay vì crash
        logger.error(f"Bỏ qua update sau {1+self.max_retries} lần thử thất bại: {last_error}")
        return None

# Khởi tạo Bot với custom session timeout
session = AiohttpSession(timeout=30)
bot = Bot(
    token=config.telegram_bot_token,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Đăng ký retry middleware cho tất cả update types
dp.update.outer_middleware(RetryMiddleware(max_retries=2, retry_delay=3.0))

# Đăng ký các Router handlers
dp.include_router(start.router)
dp.include_router(trade.router)
dp.include_router(manage.router)
dp.include_router(signal.router)
dp.include_router(config_cmd.router)
dp.include_router(trailing_cmd.router)
dp.include_router(menu_click.router)
dp.include_router(report.router)
dp.include_router(account_manager.router)

async def start_bot():
    """Khởi chạy Telegram Bot"""
    logger.info("Starting Telegram Bot...")
    try:
        # Xóa webhook nếu có trước khi bắt đầu polling
        await bot.delete_webhook(drop_pending_updates=True)
        # Gửi tin nhắn chào mừng cho chủ tài khoản
        try:
            await bot.send_message(
                chat_id=config.owner_chat_id,
                text="🤖 **Hệ thống Telegram Trading Bot đã ONLINE!**\nSử dụng `/start` để xem danh sách lệnh điều khiển.",
                parse_mode="Markdown"
            )
        except TelegramNetworkError as e:
            logger.warning(f"Không gửi được tin nhắn khởi động (network error): {e}")
        logger.info("Telegram Bot is running and polling updates...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting Telegram Bot: {e}")
        raise e

