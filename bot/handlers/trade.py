import uuid
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import config
from bot.services.api_client import api_client
from bot.parsers.command_parser import parse_trade_command
from bot.utils.formatter import format_auto_trade

router = Router()

def is_owner(message: Message) -> bool:
    """Kiểm tra xem người gửi tin nhắn có phải chủ tài khoản không"""
    return message.from_user is not None and message.from_user.id == config.owner_chat_id

async def execute_manual_trade(message: Message, trade_type: str):
    """Xử lý tạo lệnh giao dịch thủ công"""
    if not is_owner(message):
        return
        
    try:
        # 1. Parse tin nhắn lệnh
        parsed = parse_trade_command(message.text)
        symbol = parsed["symbol"]
        
        # 2. Xác định số lot (nếu không truyền -> lấy theo config hệ thống)
        lot_size = parsed["lot_size"]
        if not lot_size:
            sys_configs = await api_client.get_config()
            # Kiểm tra override theo symbol
            overrides = sys_configs.get("lot_overrides", {})
            if symbol in overrides:
                lot_size = float(overrides[symbol])
            else:
                lot_size = float(sys_configs.get("default_lot", 0.01))
                
        # 3. Chuẩn bị request
        trade_uuid = str(uuid.uuid4())
        trade_req = {
            "uuid": trade_uuid,
            "symbol": symbol,
            "trade_type": trade_type,
            "lot_size": lot_size,
            "price": parsed["price"],
            "stop_loss": parsed["stop_loss"],
            "take_profit": parsed["take_profit"],
            "source": "MANUAL"
        }
        
        # 4. Gọi API tạo trade
        trade = await api_client.create_trade(trade_req)
        
        # 5. Thông báo kết quả lệnh đã được đưa vào hàng chờ gửi sang EA
        msg = format_auto_trade(trade)
        await message.reply(msg, parse_mode="Markdown")
        
    except ValueError as e:
        await message.reply(f"❌ Lỗi cú pháp: {str(e)}\n\nVD: `/{trade_type.lower()} XAUUSD 0.01 sl=2340 tp=2370`", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Gặp lỗi khi tạo lệnh: {str(e)}")

# Đăng ký các handler
@router.message(Command("buy"))
async def cmd_buy(message: Message):
    await execute_manual_trade(message, "BUY")

@router.message(Command("sell"))
async def cmd_sell(message: Message):
    await execute_manual_trade(message, "SELL")

@router.message(Command("buylimit"))
async def cmd_buylimit(message: Message):
    await execute_manual_trade(message, "BUY_LIMIT")

@router.message(Command("selllimit"))
async def cmd_selllimit(message: Message):
    await execute_manual_trade(message, "SELL_LIMIT")

@router.message(Command("buystop"))
async def cmd_buystop(message: Message):
    await execute_manual_trade(message, "BUY_STOP")

@router.message(Command("sellstop"))
async def cmd_sellstop(message: Message):
    await execute_manual_trade(message, "SELL_STOP")
