from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class BotConfig(BaseSettings):
    """
    Cấu hình chạy Telegram Bot và Telethon Client, đọc tự động từ file .env.
    """
    # Telegram Bot
    telegram_bot_token: str
    owner_chat_id: int
    signal_group_id: str  # Có thể là chuỗi số -1001234 hoặc username nhóm @group_name
    
    # Telethon (Telegram User Client)
    telegram_api_id: int
    telegram_api_hash: str
    
    # FastAPI Backend
    api_url: str = "http://127.0.0.1:8000"
    api_key: str = "testkey"

    # Cho phép đọc từ file .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Khởi tạo instance cấu hình duy nhất
config = BotConfig()
