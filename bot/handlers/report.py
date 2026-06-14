from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_report

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

@router.message(Command("report"))
async def cmd_report(message: Message):
    """
    Xem báo cáo kết quả giao dịch và xu hướng P/L.
    Cú pháp: /report [day|week|month] (Mặc định: week)
    """
    if not is_owner(message):
        return
        
    parts = message.text.split()
    period = "week"
    if len(parts) >= 2:
        val = parts[1].lower().strip()
        if val in ["day", "week", "month"]:
            period = val
        else:
            await message.reply("❌ Cú pháp sai. Hãy dùng: `/report day`, `/report week` hoặc `/report month`.", parse_mode="Markdown")
            return
            
    try:
        # 1. Gọi API lấy báo cáo tổng hợp
        summary = await api_client.get_report_summary(period)
        
        # 2. Gọi API lấy xu hướng
        # Với period là day -> so sánh tuần (4 tuần), week -> 4 tuần, month -> 8 tuần để có ý nghĩa thống kê
        weeks_to_compare = 8 if period == "month" else 4
        trend = await api_client.get_report_trend(weeks_to_compare)
        
        # 3. Format báo cáo
        msg = format_report(summary, trend)
        
        await message.reply(msg, parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(f"❌ Lỗi khi tải báo cáo: {str(e)}")
