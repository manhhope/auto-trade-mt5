import os
import logging
from telethon import TelegramClient, events
from bot.config import config
from bot.services.api_client import api_client
from bot.parsers.signal_parser import parse_signal

logger = logging.getLogger("listener")

# Đường dẫn session file dùng chung
session_path = os.path.join("data", "anon.session")
client = TelegramClient(session_path, config.telegram_api_id, config.telegram_api_hash)

async def handle_new_message(event, bot):
    """Xử lý tin nhắn mới từ group tín hiệu"""
    # Chỉ xử lý tin nhắn dạng text
    if not event.message or not event.message.text:
        return
        
    raw_text = event.message.text
    message_id = event.message.id
    group_id = str(event.chat_id)
    
    logger.info(f"Received message ID {message_id} from group {group_id}: {raw_text[:50]}...")
    
    # 1. Parse tin nhắn
    parsed = parse_signal(raw_text)
    
    signal_req = {
        "group_id": group_id,
        "message_id": message_id,
        "raw_message": raw_text,
        "parse_success": False,
        "parsed_type": None,
        "parsed_symbol": None,
        "parsed_price": None,
        "parsed_sl": None,
        "parsed_tp": None
    }
    
    if parsed:
        signal_req.update({
            "parse_success": True,
            "parsed_type": parsed.trade_type,
            "parsed_symbol": parsed.symbol,
            "parsed_price": parsed.price,
            "parsed_sl": parsed.sl,
            "parsed_tp": parsed.tp
        })
        
    try:
        # 2. Gửi tín hiệu lên API (API tự động định tuyến và gửi thông báo Telegram cho chủ sở hữu tài khoản tương ứng)
        response = await api_client.create_signal(signal_req)
        
        if not parsed:
            logger.warning(f"Phân tích tín hiệu thất bại cho tin nhắn ID {message_id}")
            return
            
        logger.info(f"Signal processed successfully via API: {response.get('queue_id')}")
    except Exception as e:
        logger.error(f"Lỗi khi xử lý tin nhắn tín hiệu: {e}")

async def start_listener(bot):
    """Khởi chạy Telethon listener lắng nghe group tin nhắn"""
    logger.info("Starting Telethon Signal Listener...")
    
    # 1. Khởi động Telethon Client (Sử dụng session đã lưu từ login_telethon.py)
    await client.start()
    
    if not await client.is_user_authorized():
        logger.error("Telethon Client chưa được xác thực! Vui lòng chạy 'python login_telethon.py' trước.")
        await client.disconnect()
        return
        
    # 2. Xác định các Group/Channel Target để filter
    chats_to_listen = []
    
    # Kênh chính
    group_target = config.signal_group_id
    if group_target:
        if group_target.startswith("-") or group_target.isdigit():
            group_target = int(group_target)
        chats_to_listen.append(group_target)
        
    # Kênh phụ (Backup)
    backup_target = config.signal_group_backup_id
    if backup_target:
        if backup_target.startswith("-") or backup_target.isdigit():
            backup_target = int(backup_target)
        chats_to_listen.append(backup_target)
        
    logger.info(f"Listening for messages in groups/channels: {chats_to_listen}")
    
    # 3. Đăng ký event handler lắng nghe tin nhắn mới từ các group chỉ định
    @client.on(events.NewMessage(chats=chats_to_listen))
    async def message_handler(event):
        await handle_new_message(event, bot)
        
    # Chạy vòng lặp lắng nghe bất đồng bộ
    try:
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Telethon Client disconnected with error: {e}")
