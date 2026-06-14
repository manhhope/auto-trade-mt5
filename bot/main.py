import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.config import config
from bot.handlers import start, trade, manage, signal, config_cmd, report

logger = logging.getLogger("bot")

# Khởi tạo Bot và Dispatcher
bot = Bot(
    token=config.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Đăng ký các Router handlers
dp.include_router(start.router)
dp.include_router(trade.router)
dp.include_router(manage.router)
dp.include_router(signal.router)
dp.include_router(config_cmd.router)
dp.include_router(report.router)

async def start_bot():
    """Khởi chạy Telegram Bot"""
    logger.info("Starting Telegram Bot...")
    try:
        # Xóa webhook nếu có trước khi bắt đầu polling
        await bot.delete_webhook(drop_pending_updates=True)
        # Gửi tin nhắn chào mừng cho chủ tài khoản
        await bot.send_message(
            chat_id=config.owner_chat_id,
            text="🤖 **Hệ thống Telegram Trading Bot đã ONLINE!**\nSử dụng `/start` để xem danh sách lệnh điều khiển.",
            parse_mode="Markdown"
        )
        logger.info("Telegram Bot is running and polling updates...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting Telegram Bot: {e}")
        raise e
