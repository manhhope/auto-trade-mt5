import uuid
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.services.api_client import api_client
from bot.parsers.command_parser import parse_trade_command
from bot.utils.formatter import format_auto_trade

router = Router()



async def execute_manual_trade(message: Message, trade_type: str):
    """Xử lý tạo lệnh giao dịch thủ công"""
    try:
        # 1. Parse tin nhắn lệnh
        parsed = parse_trade_command(message.text)
        symbol = parsed["symbol"]
        price = parsed["price"]
        
        # Kiểm tra nếu lệnh chờ (limit/stop) thì bắt buộc phải có giá (price)
        if trade_type in ["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"] and price is None:
            raise ValueError("Lệnh chờ (limit/stop) yêu cầu phải cấu hình tham số price (VD: price=2320).")
        
        # 2. Xác định số lot (nếu không truyền -> lấy theo config hệ thống)
        lot_size = parsed["lot_size"]
        if not lot_size:
            sys_configs = await api_client.get_config(tg_user_id=message.from_user.id)
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
            "price": price,
            "stop_loss": parsed["stop_loss"],
            "take_profit": parsed["take_profit"],
            "source": "MANUAL"
        }
        
        # 4. Gọi API tạo trade
        trade = await api_client.create_trade(trade_req, tg_user_id=message.from_user.id)
        
        # 5. Thông báo kết quả lệnh đã được đưa vào hàng chờ gửi sang EA
        msg = format_auto_trade(trade)
        await message.reply(msg, parse_mode="Markdown")
        
    except ValueError as e:
        trade_type_to_cmd = {
            "BUY": "buy",
            "SELL": "sell",
            "BUY_LIMIT": "buylimit",
            "SELL_LIMIT": "selllimit",
            "BUY_STOP": "buystop",
            "SELL_STOP": "sellstop"
        }
        cmd_name = trade_type_to_cmd.get(trade_type, trade_type.lower().replace("_", ""))
        if trade_type in ["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]:
            example = f"`/{cmd_name} XAUUSD 0.01 price=2320 sl=2310 tp=2350`"
        else:
            example = f"`/{cmd_name} XAUUSD 0.01 sl=2340 tp=2370`"
        await message.reply(f"❌ Lỗi cú pháp: {str(e)}\n\nVD: {example}", parse_mode="Markdown")
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

async def execute_quick_trade(message: Message, trade_type: str):
    """Xử lý tạo lệnh giao dịch nhanh cho Vàng (cú pháp /buynow hoặc /sellnow)"""
    try:
        parts = message.text.split()
        lot_size = None
        
        # 1. Kiểm tra lot_size nếu có truyền vào
        if len(parts) >= 2:
            try:
                lot_size = float(parts[1])
                if lot_size <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Cú pháp số lot không hợp lệ. Số lot phải là số thực lớn hơn 0 (VD: 0.03).")
                
        symbol = "GOLD" # API sẽ tự động map sang XAUUSDm
        
        # 2. Xác định số lot nếu không truyền -> lấy theo cấu hình
        if not lot_size:
            sys_configs = await api_client.get_config(tg_user_id=message.from_user.id)
            # Kiểm tra override theo symbol (kiểm tra cả XAUUSDm, GOLD)
            overrides = sys_configs.get("lot_overrides", {})
            if "XAUUSDm" in overrides:
                lot_size = float(overrides["XAUUSDm"])
            elif "GOLD" in overrides:
                lot_size = float(overrides["GOLD"])
            else:
                lot_size = float(sys_configs.get("default_lot", 0.01))
                
        # 3. Chuẩn bị request (Lệnh nhanh mặc định không truyền SL/TP, EA sẽ tự động thêm nếu cấu hình default_sl_pips > 0)
        trade_uuid = str(uuid.uuid4())
        trade_req = {
            "uuid": trade_uuid,
            "symbol": symbol,
            "trade_type": trade_type,
            "lot_size": lot_size,
            "price": None,
            "stop_loss": None,
            "take_profit": None,
            "source": "MANUAL"
        }
        
        # 4. Gọi API tạo trade
        trade = await api_client.create_trade(trade_req, tg_user_id=message.from_user.id)
        
        # 5. Thông báo kết quả
        msg = format_auto_trade(trade)
        await message.reply(msg, parse_mode="Markdown")
        
    except ValueError as e:
        cmd_name = "buynow" if trade_type == "BUY" else "sellnow"
        await message.reply(f"❌ Lỗi cú pháp: {str(e)}\n\nVD: `/{cmd_name}` hoặc `/{cmd_name} 0.03`", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Gặp lỗi khi tạo lệnh: {str(e)}")

@router.message(Command("buynow"))
async def cmd_buynow(message: Message):
    await execute_quick_trade(message, "BUY")

@router.message(Command("sellnow"))
async def cmd_sellnow(message: Message):
    await execute_quick_trade(message, "SELL")

