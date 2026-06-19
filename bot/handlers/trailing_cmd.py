from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.services.api_client import api_client

router = Router()



def format_trailing_config(c: dict) -> str:
    """Định dạng cấu hình Trailing Stop đẹp mắt"""
    status_trail = "🟢 BẬT" if c.get("enabled") else "🔴 TẮT"
    status_manual = "🟢 BẬT" if c.get("manual_enabled") else "🔴 TẮT"
    status_partial = "🟢 BẬT" if c.get("partial_enabled") else "🔴 TẮT"
    
    msg = (
        "⚙️ **CẤU HÌNH TRAILING STOP & PARTIAL CLOSE**\n\n"
        f"• **Trạng thái Trailing:** {status_trail}\n"
        f"  - Ngưỡng kích hoạt Breakeven (`/sl_be`): `{c.get('be_pips')}` pips\n"
        f"  - Buffer Entry Breakeven (`/sl_be_offset`): `{c.get('be_offset')}` pips\n"
        f"  - Bước dời SL (`/sl_step`): `{c.get('step_pips')}` pips\n"
        f"  - Khoảng dời SL mỗi bước (`/sl_trail`): `{c.get('step_distance')}` pips\n"
        f"  - Trailing cho lệnh thủ công (`/trailing_manual`): {status_manual}\n\n"
        f"• **Stop Loss mặc định (`/default_sl`):** `{c.get('default_sl_pips', 0)}` pips (Tự động thêm SL cho lệnh chưa có SL)\n\n"
        f"• **Trạng thái Partial Close:** {status_partial}\n"
        f"  - Tỷ lệ chốt từng phần (`/partial_stages`): `{c.get('partial_ratios')}`\n"
        f"  - Pips kích hoạt từng phần (`/partial_pips_stages`): `{c.get('partial_pips_stages')}`\n\n"
        "💡 *Sử dụng các lệnh bên dưới để điều chỉnh:*\n"
        "• `/trailing on/off` — Bật/Tắt trailing stop\n"
        "• `/trailing_manual on/off` — Bật/Tắt trailing cho lệnh thủ công\n"
        "• `/default_sl 100` — Đặt Stop Loss mặc định (0 để tắt)\n"
        "• `/sl_be 15` — Ngưỡng kích hoạt breakeven\n"
        "• `/sl_be_offset 2` — Dời SL cách entry 2 pips\n"
        "• `/sl_step 10` — Mỗi 10 pips tăng thêm\n"
        "• `/sl_trail 8` — Dời SL tiến lên 8 pips\n"
        "• `/partial on/off` — Bật/Tắt chốt lời 1 phần\n"
        "• `/partial_stages 33/33/33` — Tỷ lệ chốt từng bước\n"
        "• `/partial_pips_stages 50/100/` — Số pips tương ứng từng bước"
    )
    return msg

@router.message(Command("trailing"))
async def cmd_trailing(message: Message):
    """Xem và điều chỉnh cấu hình trailing stop"""
    parts = message.text.split()
    
    # 1. Chỉ gõ /trailing -> Xem cấu hình
    if len(parts) == 1:
        try:
            cfg = await api_client.get_trailing_config(tg_user_id=message.from_user.id)
            msg = format_trailing_config(cfg)
            await message.reply(msg, parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Không thể lấy cấu hình: {str(e)}")
        return
        
    # 2. Gõ /trailing on/off
    action = parts[1].lower().strip()
    if action not in ["on", "off"]:
        await message.reply("❌ Lệnh không hợp lệ. Hãy dùng `/trailing on` hoặc `/trailing off`.")
        return
        
    val_str = "true" if action == "on" else "false"
    try:
        await api_client.update_config("trailing_enabled", val_str, tg_user_id=message.from_user.id)
        status_text = "BẬT" if action == "on" else "TẮT"
        await message.reply(f"✅ Đã **{status_text}** tính năng Trailing Stop.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("trailing_manual"))
async def cmd_trailing_manual(message: Message):
    """Bật/Tắt trailing stop cho các lệnh tự đặt bằng tay"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/trailing_manual on` hoặc `/trailing_manual off`", parse_mode="Markdown")
        return
        
    action = parts[1].lower().strip()
    if action not in ["on", "off"]:
        await message.reply("❌ Lệnh không hợp lệ. Hãy dùng `/trailing_manual on` hoặc `/trailing_manual off`.")
        return
        
    val_str = "true" if action == "on" else "false"
    try:
        await api_client.update_config("trailing_manual_enabled", val_str, tg_user_id=message.from_user.id)
        status_text = "BẬT" if action == "on" else "TẮT"
        await message.reply(f"✅ Đã **{status_text}** tính năng Trailing Stop cho lệnh tự vào (thủ công).", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("sl_be"))
async def cmd_sl_be(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/sl_be [số pips]` (VD: `/sl_be 15`)")
        return
    try:
        await api_client.update_config("trailing_be_pips", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật ngưỡng kích hoạt Breakeven là `{parts[1]}` pips.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("sl_be_offset"))
async def cmd_sl_be_offset(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/sl_be_offset [số pips]` (VD: `/sl_be_offset 2`)")
        return
    try:
        await api_client.update_config("trailing_be_offset", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật offset Breakeven là `{parts[1]}` pips.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("sl_step"))
async def cmd_sl_step(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/sl_step [số pips]` (VD: `/sl_step 10`)")
        return
    try:
        await api_client.update_config("trailing_step_pips", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật bước dời SL là `{parts[1]}` pips.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("sl_trail"))
async def cmd_sl_trail(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/sl_trail [số pips]` (VD: `/sl_trail 8`)")
        return
    try:
        await api_client.update_config("trailing_step_distance", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật khoảng dời SL mỗi bước là `{parts[1]}` pips.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("partial"))
async def cmd_partial(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Hãy chọn chế độ: `/partial on` hoặc `/partial off`", parse_mode="Markdown")
        return
    action = parts[1].lower().strip()
    if action not in ["on", "off"]:
        await message.reply("❌ Lệnh không hợp lệ. Hãy dùng `/partial on` hoặc `/partial off`.")
        return
    val_str = "true" if action == "on" else "false"
    try:
        await api_client.update_config("partial_close_enabled", val_str, tg_user_id=message.from_user.id)
        status_text = "BẬT" if action == "on" else "TẮT"
        await message.reply(f"✅ Đã **{status_text}** tính năng chốt lời một phần (Partial Close).", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("partial_pips"))
async def cmd_partial_pips(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/partial_pips [số pips]` (VD: `/partial_pips 30`)")
        return
    try:
        await api_client.update_config("partial_close_pips", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật ngưỡng chốt lời một phần là `{parts[1]}` pips.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("partial_ratio"))
async def cmd_partial_ratio(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/partial_ratio [tỉ lệ]` (VD: `/partial_ratio 0.5` cho 50%)")
        return
    try:
        await api_client.update_config("partial_close_ratio", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật tỉ lệ chốt lời một phần là `{parts[1]}` lot.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("partial_stages"))
async def cmd_partial_stages(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/partial_stages [tỷ lệ các bước]` (VD: `/partial_stages 33/33/33` hoặc `/partial_stages 25/50/25`)")
        return
    try:
        await api_client.update_config("partial_close_ratios", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật tỷ lệ các bước chốt lời là `{parts[1]}`.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("partial_pips_stages"))
async def cmd_partial_pips_stages(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/partial_pips_stages [số pips kích hoạt]` (VD: `/partial_pips_stages 50/100/` hoặc `/partial_pips_stages 50/100/150`)")
        return
    try:
        await api_client.update_config("partial_close_pips_stages", parts[1], tg_user_id=message.from_user.id)
        await message.reply(f"✅ Đã cập nhật số pips kích hoạt các bước chốt lời là `{parts[1]}`.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")

@router.message(Command("default_sl"))
async def cmd_default_sl(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Cú pháp: `/default_sl [số pips]` (VD: `/default_sl 100`). Dùng `0` để tắt.")
        return
    try:
        pips = int(parts[1])
        if pips < 0:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Số pips phải là số nguyên lớn hơn hoặc bằng 0.")
        return
        
    try:
        await api_client.update_config("default_sl_pips", str(pips), tg_user_id=message.from_user.id)
        if pips == 0:
            await message.reply("✅ Đã tắt tính năng tự động thêm Stop Loss mặc định.")
        else:
            await message.reply(f"✅ Đã cấu hình Stop Loss mặc định là `{pips}` pips cho tài khoản của bạn.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Cập nhật thất bại: {str(e)}")


