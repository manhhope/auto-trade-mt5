import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.config import config
from bot.services.api_client import api_client
from bot.handlers.menu_click import get_inline_menu

logger = logging.getLogger("bot")
router = Router()

def is_owner(telegram_id: int) -> bool:
    return telegram_id == config.owner_chat_id

async def check_user_approved(telegram_id: int, username: str = None) -> bool:
    """Kiểm tra và tự động đăng ký/phê duyệt người dùng"""
    if is_owner(telegram_id):
        # Admin luôn tự động được duyệt
        return True
        
    try:
        status = await api_client.get_user_status(telegram_id)
        if status.get("exists"):
            return status.get("is_approved", False)
            
        # Chưa tồn tại: Tự động gửi yêu cầu đăng ký
        await api_client.register_user(telegram_id, username)
        return False
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra trạng thái phê duyệt của user {telegram_id}: {e}")
        return False

HELP_TEXT = (
    "🤖 **HỆ THỐNG GIAO DỊCH TELEGRAM MT5 BOT**\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Chào mừng! Đây là hệ thống điều khiển và đặt lệnh tự động trên MT5 Terminal.\n\n"
    "**Các lệnh nhanh:**\n"
    "• `/menu` - Mở Menu nút bấm điều khiển chính\n"
    "• `/help` - Xem hướng dẫn sử dụng hệ thống\n\n"
    "**Lệnh Giao dịch Thủ công:**\n"
    "• `/buy [symbol] [lot] sl=[val] tp=[val]` - Mở lệnh Buy\n"
    "• `/sell [symbol] [lot] sl=[val] tp=[val]` - Mở lệnh Sell\n"
    "• `/buylimit`/`/selllimit` - Đặt lệnh Limit\n"
    "• `/buystop`/`/sellstop` - Đặt lệnh Stop\n\n"
    "**Quản lý Vị thế & Tài khoản:**\n"
    "• `/orders` - Xem danh sách vị thế đang mở\n"
    "• `/gold` hoặc `/price` - Xem giá vàng và biến động\n"
    "• `/close [ticket]` - Đóng vị thế cụ thể\n"
    "• `/closeall` - Đóng toàn bộ vị thế\n"
    "• `/balance` hoặc `/status` - Xem số dư và trạng thái\n\n"
    "**Quản lý Hàng đợi Tín hiệu:**\n"
    "• `/queue` - Xem danh sách tín hiệu chờ duyệt\n"
    "• `/confirm [queue_id] [lot=val]` - Duyệt tín hiệu\n"
    "• `/reject [queue_id]` - Từ chối tín hiệu\n\n"
    "**Báo cáo & Cấu hình:**\n"
    "• `/report [day|week|month]` - Báo cáo P/L\n"
    "• `/config` - Xem/điều chỉnh cấu hình hệ thống\n"
    "• `/mode [auto|queue]` - Thay đổi chế độ hoạt động\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━"
)

async def notify_admin_request(message: Message, bot):
    """Gửi yêu cầu phê duyệt tới Admin"""
    telegram_id = message.from_user.id
    username = message.from_user.username or "Không rõ"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    name_str = f"{first_name} {last_name}".strip() or username
    
    msg = (
        f"🔔 **YÊU CẦU PHÊ DUYỆT THÀNH VIÊN MỚI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Họ tên:** {name_str}\n"
        f"• **Username:** @{username}\n"
        f"• **Telegram ID:** `{telegram_id}`\n\n"
        f"Bạn có phê duyệt cho người dùng này sử dụng hệ thống không?"
    )
    
    buttons = [
        [
            InlineKeyboardButton(text="✅ Phê duyệt", callback_data=f"admin_approve:{telegram_id}"),
            InlineKeyboardButton(text="❌ Từ chối", callback_data=f"admin_reject:{telegram_id}")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(chat_id=config.owner_chat_id, text=msg, reply_markup=markup, parse_mode="Markdown")

@router.message(CommandStart())
async def cmd_start(message: Message):
    approved = await check_user_approved(message.from_user.id, message.from_user.username)
    if not approved:
        # Nếu chưa được duyệt, thông báo và xin duyệt
        await message.reply(
            "👋 Chào mừng bạn! Yêu cầu đăng ký sử dụng bot đã được gửi tới Quản trị viên.\n"
            "Vui lòng chờ phê duyệt hoặc liên hệ Admin để được cấp quyền.",
            reply_markup=ReplyKeyboardRemove()
        )
        await notify_admin_request(message, message.bot)
        return
        
    await message.reply(
        "👋 Chào mừng bạn quay trở lại!\n"
        "Sử dụng nút bấm dưới tin nhắn để điều khiển hệ thống hoặc gõ `/menu`.", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    acc_str = ""
    try:
        acc = await api_client.get_account(tg_user_id=message.from_user.id)
        acc_str = f"\n🎮 *Đang thao tác trên:* **{acc['account_name']}** (`{acc['account_number']}`)"
    except Exception:
        pass

    await message.reply(
        "🤖 **MENU ĐIỀU KHIỂN HỆ THỐNG**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        f"{acc_str}\n\n"
        "Chọn một tính năng bên dưới để quản lý hoặc thiết lập cấu hình:", 
        reply_markup=get_inline_menu(), 
        parse_mode="Markdown"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    approved = await check_user_approved(message.from_user.id, message.from_user.username)
    if not approved:
        return
    await message.reply(HELP_TEXT, parse_mode="Markdown")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    approved = await check_user_approved(message.from_user.id, message.from_user.username)
    if not approved:
        return
        
    acc_str = ""
    try:
        acc = await api_client.get_account(tg_user_id=message.from_user.id)
        acc_str = f"\n🎮 *Đang thao tác trên:* **{acc['account_name']}** (`{acc['account_number']}`)"
    except Exception:
        pass

    await message.reply(
        "🤖 **MENU ĐIỀU KHIỂN HỆ THỐNG**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        f"{acc_str}\n\n"
        "Chọn một tính năng bên dưới để quản lý hoặc thiết lập cấu hình:", 
        reply_markup=get_inline_menu(), 
        parse_mode="Markdown"
    )

# ── HÀNH ĐỘNG CỦA ADMIN DUYỆT / TỪ CHỐI THÀNH VIÊN ──

@router.callback_query(F.data.startswith("admin_approve:"))
async def callback_admin_approve(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Bạn không có quyền Admin.", show_alert=True)
        return
        
    user_id = callback.data.split(":")[1]
    await callback.answer("Đang phê duyệt...")
    try:
        await api_client.approve_user(int(user_id))
        await callback.message.edit_text(
            f"✅ **ĐÃ DUYỆT THÀNH VIÊN**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"User ID: `{user_id}` đã được kích hoạt thành công.",
            parse_mode="Markdown"
        )
        # Thông báo cho user đó
        await callback.bot.send_message(
            chat_id=int(user_id),
            text="🎉 **Tài khoản của bạn đã được phê duyệt!**\nSử dụng `/start` hoặc `/menu` để bắt đầu quản lý tài khoản.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.reply(f"❌ Duyệt người dùng thất bại: {str(e)}")

@router.callback_query(F.data.startswith("admin_reject:"))
async def callback_admin_reject(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Bạn không có quyền Admin.", show_alert=True)
        return
        
    user_id = callback.data.split(":")[1]
    await callback.answer("Đang từ chối...")
    try:
        await api_client.reject_user(int(user_id))
        await callback.message.edit_text(
            f"❌ **ĐÃ TỪ CHỐI THÀNH VIÊN**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"User ID: `{user_id}` đã bị từ chối và xóa khỏi hàng đợi đăng ký.",
            parse_mode="Markdown"
        )
        # Thông báo cho user đó
        await callback.bot.send_message(
            chat_id=int(user_id),
            text="❌ Yêu cầu đăng ký sử dụng của bạn đã bị từ chối bởi Admin.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.reply(f"❌ Từ chối người dùng thất bại: {str(e)}")

# Lệnh duyệt trực tiếp bằng text dành cho Admin
@router.message(Command("approve"))
async def cmd_approve_user(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/approve [telegram_id]`")
        return
    user_id = parts[1]
    try:
        await api_client.approve_user(int(user_id))
        await message.reply(f"✅ Đã phê duyệt người dùng `{user_id}`.")
        await message.bot.send_message(
            chat_id=int(user_id),
            text="🎉 **Tài khoản của bạn đã được phê duyệt!**\nSử dụng `/start` hoặc `/menu` để bắt đầu quản lý tài khoản.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply(f"❌ Thất bại: {e}")

@router.message(Command("reject"))
async def cmd_reject_user(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/reject [telegram_id]`")
        return
    user_id = parts[1]
    try:
        await api_client.reject_user(int(user_id))
        await message.reply(f"❌ Đã từ chối/xóa người dùng `{user_id}`.")
        await message.bot.send_message(
            chat_id=int(user_id),
            text="❌ Yêu cầu đăng ký sử dụng của bạn đã bị từ chối bởi Admin.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply(f"❌ Thất bại: {e}")
