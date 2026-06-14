from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_auto_trade, format_datetime

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

@router.message(Command("queue"))
async def cmd_queue(message: Message):
    """Xem hàng đợi tín hiệu đang chờ duyệt (QUEUED)"""
    if not is_owner(message):
        return
        
    try:
        signals = await api_client.get_signals(status="QUEUED")
        if not signals:
            await message.reply("📋 Hàng đợi tín hiệu trống. Không có tín hiệu nào chờ duyệt.")
            return
            
        lines = [
            f"📋 **HÀNG ĐỢI TÍN HIỆU ({len(signals)} tín hiệu)**",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        now = datetime.utcnow()
        expire_min = int(config.queue_expire_minutes)
        
        for idx, sig in enumerate(signals, 1):
            sl_str = f"{sig['parsed_sl']:.2f}" if sig.get("parsed_sl") else "Không có"
            tp_str = f"{sig['parsed_tp']:.2f}" if sig.get("parsed_tp") else "Không có"
            entry_str = f"{sig['parsed_price']:.2f}" if sig.get("parsed_price") else "Giá Thị Trường"
            
            # Tính thời gian hết hạn còn lại
            time_created = datetime.fromisoformat(sig["created_at"].replace("Z", ""))
            elapsed = now - time_created
            remaining = max(0, expire_min - int(elapsed.total_seconds() / 60))
            
            lines.append(
                f"{idx}. **{sig['queue_id']}** — **{sig['parsed_type']} {sig['parsed_symbol']}** @ {entry_str}\n"
                f"   SL: {sl_str} | TP: {tp_str}\n"
                f"   ⏱️ Còn lại: {remaining} phút | Nhận lúc: {format_datetime(sig['created_at'])}"
            )
            
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("Sử dụng `/confirm [ID] [lot=val]` hoặc `/reject [ID]` để duyệt lệnh.")
        
        await message.reply("\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(f"❌ Không thể lấy danh sách hàng đợi: {str(e)}")

@router.message(Command("confirm"))
async def cmd_confirm(message: Message):
    """Xác nhận tín hiệu từ hàng đợi. VD: /confirm SIG-0001 hoặc /confirm SIG-0001 lot=0.02"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Vui lòng nhập Queue ID. VD: `/confirm SIG-0042`", parse_mode="Markdown")
        return
        
    queue_id = parts[1].upper()
    
    # Tìm kiếm lot override nếu có (VD: lot=0.05)
    lot_override = None
    for part in parts[2:]:
        kv = part.lower().split("=", 1)
        if len(kv) == 2 and kv[0] == "lot":
            try:
                lot_override = float(kv[1])
            except ValueError:
                await message.reply("❌ Số lot override phải là số thực.")
                return
                
    try:
        # Gọi API xác nhận signal -> tạo trade
        trade = await api_client.confirm_signal(queue_id, lot_override)
        
        msg = format_auto_trade(trade)
        await message.reply(f"✅ **ĐÃ DUYỆT TÍN HIỆU {queue_id}!**\n\n{msg}", parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(f"❌ Duyệt tín hiệu thất bại: {str(e)}")

@router.message(Command("reject"))
async def cmd_reject(message: Message):
    """Từ chối tín hiệu từ hàng đợi. VD: /reject SIG-0001"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Vui lòng nhập Queue ID. VD: `/reject SIG-0042`", parse_mode="Markdown")
        return
        
    queue_id = parts[1].upper()
    
    try:
        signal = await api_client.reject_signal(queue_id)
        await message.reply(f"❌ **ĐÃ TỪ CHỐI TÍN HIỆU {queue_id}!**\nTrạng thái: {signal['status']}", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Từ chối tín hiệu thất bại: {str(e)}")

@router.message(Command("confirmall"))
async def cmd_confirmall(message: Message):
    """Xác nhận toàn bộ các tín hiệu đang ở hàng đợi"""
    if not is_owner(message):
        return
        
    try:
        res = await api_client.confirm_all_signals()
        count = res.get("confirmed_count", 0)
        await message.reply(f"✅ Đã duyệt toàn bộ **{count}** tín hiệu trong hàng đợi thành công! Lệnh đang được chuyển sang MT5...")
    except Exception as e:
        await message.reply(f"❌ Duyệt toàn bộ tín hiệu thất bại: {str(e)}")

@router.message(Command("rejectall"))
async def cmd_rejectall(message: Message):
    """Từ chối toàn bộ các tín hiệu đang ở hàng đợi"""
    if not is_owner(message):
        return
        
    try:
        res = await api_client.reject_all_signals()
        count = res.get("rejected_count", 0)
        await message.reply(f"❌ Đã từ chối toàn bộ **{count}** tín hiệu trong hàng đợi thành công.")
    except Exception as e:
        await message.reply(f"❌ Từ chối toàn bộ tín hiệu thất bại: {str(e)}")
