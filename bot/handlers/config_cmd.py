from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_config

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

@router.message(Command("config"))
async def cmd_config(message: Message):
    """Xem và điều chỉnh cấu hình hệ thống"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    
    # 1. Chỉ gõ /config -> Xem cấu hình hiện tại
    if len(parts) == 1:
        try:
            configs = await api_client.get_config()
            msg = format_config(configs)
            await message.reply(msg, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"❌ Không thể lấy cấu hình: {str(e)}")
        return
        
    # 2. Gõ /config key=value để cập nhật cấu hình hoặc thiết lập override
    param = parts[1]
    
    # Định dạng key=value (Ví dụ: default_lot=0.02 hoặc XAUUSD=0.05)
    kv = param.split("=", 1)
    if len(kv) != 2:
        await message.reply(
            "❌ Cú pháp sai. Hãy dùng:\n"
            "• <code>/config</code> — Xem cấu hình\n"
            "• <code>/config default_lot=0.02</code> — Đổi số lot mặc định\n"
            "• <code>/config queue_expire_minutes=20</code> — Đổi thời gian hết hạn hàng đợi\n"
            "• <code>/config [SYMBOL]=[LOT]</code> — Đặt ghi đè lot (VD: <code>/config XAUUSD=0.02</code>)\n"
            "• <code>/config remove [SYMBOL]</code> — Xóa ghi đè lot (VD: <code>/config remove XAUUSD</code>)",
            parse_mode="HTML"
        )
        return
        
    key, value = kv[0].strip(), kv[1].strip()
    
    try:
        # Nếu key là một trong các cấu hình chính
        if key.lower() in ["default_lot", "queue_expire_minutes", "sl_buffer_pips", "mode"]:
            await api_client.update_config(key.lower(), value)
            await message.reply(f"✅ Đã cập nhật cấu hình <b>{key.lower()}</b> thành <code>{value}</code>.")
        else:
            # Nếu không phải, mặc định coi đây là Lot Override cho Symbol (VD: XAUUSD=0.02)
            symbol = key.upper()
            try:
                lot_size = float(value)
                if lot_size <= 0:
                    raise ValueError()
            except ValueError:
                await message.reply("❌ Số lot ghi đè phải là số thực lớn hơn 0.")
                return
                
            await api_client.set_lot_override(symbol, lot_size)
            await message.reply(f"✅ Đã thiết lập lot override cho <b>{symbol}</b> là <code>{lot_size:.2f}</code> lot.")
            
    except Exception as e:
        await message.reply(f"❌ Cập nhật cấu hình thất bại: {str(e)}")

@router.message(Command("mode"))
async def cmd_mode(message: Message):
    """Thay đổi nhanh chế độ hoạt động (auto / queue)"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Vui lòng chọn chế độ: <code>/mode auto</code> hoặc <code>/mode queue</code>")
        return
        
    mode_val = parts[1].lower().strip()
    if mode_val not in ["auto", "queue"]:
        await message.reply("❌ Chế độ không hợp lệ. Chỉ chấp nhận `auto` hoặc `queue`.")
        return
        
    try:
        await api_client.update_config("mode", mode_val)
        mode_name = "Tự động đặt lệnh (Auto)" if mode_val == "auto" else "Hàng đợi duyệt (Queue)"
        await message.reply(f"✅ Đã chuyển hệ thống sang chế độ: <b>{mode_name}</b>.")
    except Exception as e:
        await message.reply(f"❌ Thay đổi chế độ thất bại: {str(e)}")

@router.message(F.text.startswith("/config remove") | F.text.startswith("/config delete"))
async def cmd_config_remove(message: Message):
    """Xóa ghi đè lot size cho symbol. VD: /config remove XAUUSD"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ Cú pháp: <code>/config remove [SYMBOL]</code>")
        return
        
    symbol = parts[2].upper()
    
    try:
        await api_client.delete_lot_override(symbol)
        await message.reply(f"✅ Đã xóa ghi đè lot size của <b>{symbol}</b>. Hệ thống sẽ sử dụng default lot cho cặp này.")
    except Exception as e:
        await message.reply(f"❌ Xóa lot override thất bại: {str(e)}")
