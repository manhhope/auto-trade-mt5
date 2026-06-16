import os
import asyncio
import logging
import uvicorn
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("main")

from api.database import init_database, get_db_connection
from api.main import create_app
from api.services.config_service import get_config_value
from bot.main import start_bot, bot
from bot.services.signal_listener import start_listener
from bot.services.background_tasks import closed_trade_notification_loop, ea_health_check_loop

async def expire_old_signals_loop():
    """Vòng lặp chạy ngầm tự động hủy các tín hiệu quá hạn trong hàng đợi (mỗi 60s)"""
    logger.info("Starting Queue Signal Expiry loop...")
    while True:
        try:
            db = await get_db_connection()
            try:
                expire_min_str = await get_config_value(db, "queue_expire_minutes")
                expire_min = int(expire_min_str) if expire_min_str else 15
                
                cutoff = datetime.utcnow() - timedelta(minutes=expire_min)
                cursor = await db.execute(
                    "UPDATE signals SET status='EXPIRED' WHERE status='QUEUED' AND created_at < ?",
                    (cutoff.isoformat(),)
                )
                await db.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Đã hủy {cursor.rowcount} tín hiệu quá hạn (quá {expire_min} phút) khỏi hàng đợi.")
            finally:
                await db.close()
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp Queue Expiry: {e}")
        await asyncio.sleep(60.0)

async def main():
    logger.info("=== Khởi động Hệ thống Telegram MT5 Bridge ===")
    
    # 1. Đảm bảo thư mục dữ liệu tồn tại
    os.makedirs("data", exist_ok=True)
    
    # 2. Khởi tạo Database
    await init_database()
    
    # 3. Cấu hình FastAPI Web Server
    app = create_app()
    api_host = os.getenv("API_HOST", "127.0.0.1")
    api_port = int(os.getenv("API_PORT", 8000))
    
    uvicorn_config = uvicorn.Config(
        app, 
        host=api_host, 
        port=api_port, 
        log_level="warning", # Cấu hình log uvicorn gọn gàng
        loop="asyncio"
    )
    server = uvicorn.Server(uvicorn_config)
    
    # 4. Chạy đồng thời toàn bộ dịch vụ và task chạy ngầm
    logger.info(f"FastAPI API Server đang chạy tại http://{api_host}:{api_port}")
    
    await asyncio.gather(
        server.serve(),                       # FastAPI Web Server
        start_bot(),                          # Telegram Bot aiogram
        start_listener(bot),                  # Telethon Signal Listener
        closed_trade_notification_loop(bot),  # Task thông báo lệnh đóng
        ea_health_check_loop(bot),            # Task giám sát kết nối EA
        expire_old_signals_loop()             # Task dọn dẹp tín hiệu hết hạn
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Hệ thống đã dừng hoạt động.")
