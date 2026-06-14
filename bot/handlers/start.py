from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from bot.config import config

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

HELP_TEXT = (
    "🤖 **HỆ THỐNG GIAO DỊCH TELEGRAM MT5 BOT**\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Chào mừng! Đây là hệ thống điều khiển và đặt lệnh tự động trên MT5 Terminal.\n\n"
    "**Lệnh Giao dịch Thủ công:**\n"
    "• `/buy [symbol] [lot] sl=[val] tp=[val]` - Mở lệnh Buy\n"
    "• `/sell [symbol] [lot] sl=[val] tp=[val]` - Mở lệnh Sell\n"
    "• `/buylimit`/`/selllimit` - Đặt lệnh Limit (yêu cầu thêm `price=[val]`)\n"
    "• `/buystop`/`/sellstop` - Đặt lệnh Stop (yêu cầu thêm `price=[val]`)\n\n"
    "**Quản lý Vị thế & Tài khoản:**\n"
    "• `/orders` - Xem danh sách vị thế đang mở\n"
    "• `/close [ticket]` - Đóng vị thế cụ thể theo ticket\n"
    "• `/closeall` - Đóng toàn bộ các vị thế đang chạy\n"
    "• `/balance` hoặc `/status` - Xem số dư tài khoản và trạng thái EA\n\n"
    "**Quản lý Hàng đợi Tín hiệu:**\n"
    "• `/queue` - Xem danh sách tín hiệu đang chờ duyệt\n"
    "• `/confirm [queue_id] [lot=val]` - Duyệt tín hiệu\n"
    "• `/reject [queue_id]` - Từ chối tín hiệu\n"
    "• `/confirmall` - Duyệt tất cả tín hiệu đang chờ\n"
    "• `/rejectall` - Từ chối tất cả tín hiệu đang chờ\n\n"
    "**Báo cáo & Cấu hình:**\n"
    "• `/report [day|week|month]` - Báo cáo P/L kèm biểu đồ\n"
    "• `/config` - Xem và điều chỉnh cấu hình hệ thống\n"
    "• `/mode [auto|queue]` - Thay đổi chế độ hoạt động\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━"
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message):
        await message.reply("❌ Bạn không có quyền sử dụng Bot này.")
        return
    await message.reply(HELP_TEXT, parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_owner(message):
        return
    await message.reply(HELP_TEXT, parse_mode="Markdown")
