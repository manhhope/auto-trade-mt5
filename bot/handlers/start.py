from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import config
from bot.services.api_client import api_client

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

def get_inline_menu() -> InlineKeyboardMarkup:
    """Tạo bàn phím Inline Keyboard Menu chính"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 Trạng thái", callback_data="menu_status"),
            InlineKeyboardButton(text="💼 Vị thế mở", callback_data="menu_orders")
        ],
        [
            InlineKeyboardButton(text="⚙️ Cấu hình chung", callback_data="menu_config"),
            InlineKeyboardButton(text="📈 Trailing Stop", callback_data="menu_trailing")
        ],
        [
            InlineKeyboardButton(text="📥 Hàng đợi", callback_data="menu_queue"),
            InlineKeyboardButton(text="📅 Báo cáo P/L", callback_data="menu_report")
        ],
        [
            InlineKeyboardButton(text="📜 Lịch sử", callback_data="menu_history"),
            InlineKeyboardButton(text="💳 Tài khoản", callback_data="menu_accounts")
        ],
        [
            InlineKeyboardButton(text="🟡 Giá vàng", callback_data="menu_gold"),
            InlineKeyboardButton(text="❌ Đóng toàn bộ", callback_data="menu_closeall")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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

@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message):
        await message.reply("❌ Bạn không có quyền sử dụng Bot này.")
        return
    # Gửi tin nhắn chào mừng, xóa bàn phím Reply Keyboard cũ nếu có
    await message.reply(
        "👋 Chào mừng bạn quay trở lại!\n"
        "Sử dụng nút bấm dưới tin nhắn để điều khiển hệ thống hoặc gõ `/menu`.", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    acc_str = ""
    try:
        acc = await api_client.get_account()
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
    if not is_owner(message):
        return
    await message.reply(HELP_TEXT, parse_mode="Markdown")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if not is_owner(message):
        return
        
    acc_str = ""
    try:
        acc = await api_client.get_account()
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
