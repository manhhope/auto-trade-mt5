from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable
from bot.config import config
from bot.services.api_client import api_client

class AuthMiddleware(BaseMiddleware):
    """
    Middleware xác thực người dùng Telegram.
    Chỉ cho phép Admin hệ thống hoặc người dùng đã phê duyệt truy cập.
    Yêu cầu đăng ký tự động nếu người dùng chưa tồn tại trong hệ thống.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Lấy thông tin user từ event
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)
            
        user_id = from_user.id
        
        # 1. Bỏ qua kiểm tra cho Admin hệ thống
        if user_id == config.owner_chat_id:
            return await handler(event, data)
            
        # 2. Kiểm tra nếu là tin nhắn lệnh /start
        is_start_cmd = False
        if isinstance(event, Message) and event.text:
            if event.text.startswith("/start"):
                is_start_cmd = True
                
        # 3. Tra cứu trạng thái phê duyệt từ API
        try:
            status = await api_client.get_user_status(user_id)
            if status.get("exists") and status.get("is_approved"):
                # Thành viên đã phê duyệt: Cho phép đi tiếp
                return await handler(event, data)
        except Exception as e:
            import logging
            logging.getLogger("bot").error(f"AuthMiddleware error checking user {user_id}: {e}")
            
        # 4. Cho phép lệnh /start đi tiếp để gửi yêu cầu duyệt
        if is_start_cmd:
            return await handler(event, data)
            
        # 5. Cho phép các callback duyệt của admin đi tiếp
        if isinstance(event, CallbackQuery) and event.data:
            if event.data.startswith("admin_approve:") or event.data.startswith("admin_reject:"):
                return await handler(event, data)
                
        # 6. Chặn toàn bộ các trường hợp còn lại
        if isinstance(event, Message):
            await event.reply("❌ Bạn chưa được phê duyệt sử dụng hệ thống. Vui lòng gõ `/start` để đăng ký.")
        elif isinstance(event, CallbackQuery):
            await event.answer("❌ Bạn chưa được phê duyệt sử dụng hệ thống. Vui lòng gõ /start.", show_alert=True)
            
        return None
