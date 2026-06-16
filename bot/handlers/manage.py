from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_positions_list, format_balance

router = Router()

def is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

@router.message(Command("orders"))
async def cmd_orders(message: Message):
    """Xem danh sách các lệnh đang mở (FILLED)"""
    if not is_owner(message):
        return
        
    try:
        positions = await api_client.get_positions()
        msg = format_positions_list(positions)
        await message.reply(msg, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Không thể lấy danh sách lệnh: {str(e)}")

@router.message(Command("balance"))
@router.message(Command("status"))
async def cmd_balance(message: Message):
    """Xem thông tin tài khoản và kết nối EA"""
    if not is_owner(message):
        return
        
    try:
        account = await api_client.get_account()
        health = await api_client.get_health()
        msg = format_balance(account, health)
        await message.reply(msg, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Không thể lấy thông tin tài khoản: {str(e)}")

@router.message(Command("close"))
async def cmd_close(message: Message):
    """Yêu cầu đóng một lệnh cụ thể theo ticket. VD: /close 12345"""
    if not is_owner(message):
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Vui lòng nhập số Ticket. VD: `/close 12345`", parse_mode="Markdown")
        return
        
    ticket_str = parts[1].lstrip("#")
    if not ticket_str.isdigit():
        await message.reply("❌ Ticket phải là số nguyên.")
        return
        
    ticket = int(ticket_str)
    
    try:
        # 1. Tìm lệnh có số ticket tương ứng trong các positions đang chạy
        positions = await api_client.get_positions()
        target_pos = None
        for pos in positions:
            if pos.get("ticket") == ticket:
                target_pos = pos
                break
                
        if not target_pos:
            await message.reply(f"❌ Không tìm thấy vị thế đang mở nào có ticket #{ticket}.")
            return
            
        # 2. Gửi yêu cầu đóng lệnh lên API theo ticket
        await api_client.request_close_position_by_ticket(ticket)
        type_str = f" [Thủ công]" if target_pos.get("is_manual") else ""
        await message.reply(f"⏳ Đã gửi yêu cầu đóng lệnh{type_str} **{target_pos['trade_type']} {target_pos['symbol']} {target_pos['lot_size']:.2f}** (Ticket: `#{ticket}`). EA đang thực thi...", parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(f"❌ Yêu cầu đóng lệnh thất bại: {str(e)}")

@router.message(Command("closeall"))
async def cmd_closeall(message: Message):
    """Yêu cầu đóng toàn bộ các lệnh đang chạy"""
    if not is_owner(message):
        return
        
    try:
        positions = await api_client.get_positions()
        if not positions:
            await message.reply("📋 Không có vị thế nào đang mở để đóng.")
            return
            
        closed_count = 0
        for pos in positions:
            await api_client.request_close_position_by_ticket(pos["ticket"])
            closed_count += 1
            
        await message.reply(f"⏳ Đã gửi yêu cầu đóng **{closed_count}** vị thế đang chạy. Vui lòng chờ EA thực thi...")
    except Exception as e:
        await message.reply(f"❌ Lỗi khi gửi yêu cầu đóng toàn bộ lệnh: {str(e)}")

@router.message(Command("gold"))
@router.message(Command("price"))
@router.message(Command("xauusd"))
async def cmd_gold_price(message: Message):
    """Xem giá vàng hiện tại và biến động"""
    if not is_owner(message):
        return
        
    try:
        from bot.utils.formatter import format_gold_price
        account = await api_client.get_account()
        health = await api_client.get_health()
        msg = format_gold_price(account, health)
        await message.reply(msg)
    except Exception as e:
        await message.reply(f"❌ Không thể lấy giá vàng: {str(e)}")
