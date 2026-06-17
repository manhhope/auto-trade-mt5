import logging
import uuid
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.config import config
from bot.services.api_client import api_client

def get_back_markup() -> InlineKeyboardMarkup:
    """Tạo bàn phím chỉ có nút quay lại Menu chính"""
    buttons = [[InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

logger = logging.getLogger("bot")
router = Router()

class RenameSourceState(StatesGroup):
    waiting_for_name = State()

def get_sources_markup(sources: list) -> InlineKeyboardMarkup:
    """Tạo bàn phím hiển thị danh sách nguồn tín hiệu"""
    buttons = []
    
    # Liệt kê các nguồn
    for src in sources:
        type_icon = "🔵" if src["source_type"] == "telegram_group" else "🟠"
        is_active = src.get("is_active", True)
        if not is_active:
            status_txt = "⚪ OFF"
        else:
            status_txt = "🤖 Auto" if src["mode"] == "auto" else "📋 Queue"
            
        buttons.append([
            InlineKeyboardButton(
                text=f"{type_icon} {src['name']} ({status_txt})", 
                callback_data=f"src_detail:{src['id']}"
            )
        ])
        
    # Nút thêm TradingView Webhook
    buttons.append([
        InlineKeyboardButton(text="➕ Thêm TradingView Webhook", callback_data="src_add_tv")
    ])
    
    # Nút quay lại
    buttons.append([
        InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_source_detail_markup(source_id: int, source_type: str, is_active: bool) -> InlineKeyboardMarkup:
    """Tạo bàn phím chi tiết nguồn tín hiệu"""
    status_btn_text = "🟢 Bật hoạt động" if not is_active else "🔴 Tạm dừng (Tắt)"
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Đổi chế độ (Auto/Queue)", callback_data=f"src_toggle:{source_id}"),
            InlineKeyboardButton(text=status_btn_text, callback_data=f"src_status_toggle:{source_id}")
        ],
        [
            InlineKeyboardButton(text="✏️ Đổi tên hiển thị", callback_data=f"src_rename:{source_id}"),
            InlineKeyboardButton(text="❌ Xóa nguồn này", callback_data=f"src_delete:{source_id}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Quay lại danh sách", callback_data="menu_sources")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# 1. Danh sách nguồn tín hiệu
@router.callback_query(F.data == "menu_sources")
async def callback_menu_sources(callback: CallbackQuery):
    await callback.answer("Đang tải nguồn tín hiệu...")
    try:
        sources = await api_client.get_signal_sources(tg_user_id=callback.from_user.id)
        msg = (
            "📡 **QUẢN LÝ NGUỒN TÍN HIỆU**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Dưới đây là danh sách các nguồn nhận tín hiệu của bạn. "
            "Bạn có thể cấu hình chế độ Auto/Queue độc lập cho từng nguồn:\n\n"
            "• 🔵: Telegram Group/Channel\n"
            "• 🟠: TradingView Webhook\n"
            "• 🤖: Tự động vào lệnh (Auto)\n"
            "• 📋: Hàng đợi duyệt bằng tay (Queue)"
        )
        await callback.message.edit_text(msg, reply_markup=get_sources_markup(sources), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể tải nguồn tín hiệu: {str(e)}", reply_markup=get_back_markup())

# 2. Thêm TradingView Webhook
@router.callback_query(F.data == "src_add_tv")
async def callback_add_tradingview(callback: CallbackQuery):
    await callback.answer("Đang tạo Webhook...")
    token = uuid.uuid4().hex[:16]
    name = f"TradingView {token[:4].upper()}"
    
    try:
        # Tạo nguồn trên API
        await api_client.create_signal_source(
            source_type="tradingview",
            source_key=token,
            name=name,
            mode="queue",
            tg_user_id=callback.from_user.id
        )
        
        # Link webhook
        webhook_url = f"{config.api_url.rstrip('/')}/api/webhooks/tradingview/{token}"
        
        msg = (
            "✅ **ĐÃ TẠO WEBHOOK TRADINGVIEW THÀNH CÔNG**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Tên nguồn:** `{name}`\n"
            f"• **Chế độ:** `Queue (Chờ duyệt)`\n\n"
            f"🔗 **URL Webhook của bạn:**\n`{webhook_url}`\n\n"
            f"👉 Hãy copy URL trên dán vào phần **Webhook URL** trong Alert Settings của TradingView.\n"
            f"Định dạng tin nhắn (Message) trên TradingView gửi sang dạng JSON:\n"
            "```json\n"
            "{\n"
            '  "symbol": "XAUUSDm",\n'
            '  "action": "BUY",\n'
            '  "price": {{close}},\n'
            '  "sl": 15.0,\n'
            '  "tp": 30.0\n'
            "}\n"
            "```"
        )
        
        buttons = [[InlineKeyboardButton(text="⬅️ Quay lại danh sách", callback_data="menu_sources")]]
        await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể tạo Webhook: {str(e)}", reply_markup=get_back_markup())

# 3. Chi tiết một nguồn
@router.callback_query(F.data.startswith("src_detail:"))
async def callback_source_detail(callback: CallbackQuery, source_id: int = None):
    if source_id is None:
        source_id = int(callback.data.split(":")[1])
    await callback.answer()
    
    try:
        sources = await api_client.get_signal_sources(tg_user_id=callback.from_user.id)
        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            await callback.message.edit_text("❌ Không tìm thấy nguồn tín hiệu này.", reply_markup=get_back_markup())
            return
            
        type_str = "Telegram Group / Channel" if source["source_type"] == "telegram_group" else "TradingView Webhook"
        mode_str = "🤖 Auto (Tự động vào lệnh)" if source["mode"] == "auto" else "📋 Queue (Hàng đợi chờ duyệt)"
        is_active = source.get("is_active", True)
        status_str = "🟢 Đang hoạt động (ON)" if is_active else "🔴 Đang tạm dừng (OFF)"
        
        msg = (
            f"📡 **CHI TIẾT NGUỒN TÍN HIỆU**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Tên hiển thị:** `{source['name']}`\n"
            f"• **Loại nguồn:** {type_str}\n"
            f"• **Mã khóa (Key):** `{source['source_key']}`\n"
            f"• **Trạng thái:** **{status_str}**\n"
            f"• **Chế độ hoạt động:** **{mode_str}**\n\n"
        )
        
        if source["source_type"] == "tradingview":
            webhook_url = f"{config.api_url.rstrip('/')}/api/webhooks/tradingview/{source['source_key']}"
            msg += f"🔗 **URL Webhook:**\n`{webhook_url}`\n\n"
            
        msg += "Chọn hành động bên dưới để cấu hình:"
        
        await callback.message.edit_text(msg, reply_markup=get_source_detail_markup(source_id, source["source_type"], is_active), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Lỗi: {str(e)}", reply_markup=get_back_markup())

# 4. Đổi chế độ Auto/Queue
@router.callback_query(F.data.startswith("src_toggle:"))
async def callback_source_toggle(callback: CallbackQuery):
    source_id = int(callback.data.split(":")[1])
    await callback.answer("Đang đổi chế độ...")
    
    try:
        sources = await api_client.get_signal_sources(tg_user_id=callback.from_user.id)
        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            await callback.message.edit_text("❌ Không tìm thấy nguồn tín hiệu.", reply_markup=get_back_markup())
            return
            
        new_mode = "queue" if source["mode"] == "auto" else "auto"
        await api_client.update_signal_source(
            source_id=source_id,
            name=source["name"],
            mode=new_mode,
            tg_user_id=callback.from_user.id
        )
        
        # Reload detail page
        await callback_source_detail(callback, source_id=source_id)
    except Exception as e:
        await callback.message.reply(f"❌ Cập nhật thất bại: {str(e)}")

# 4.5. Bật/Tắt hoạt động nguồn tín hiệu (ON/OFF)
@router.callback_query(F.data.startswith("src_status_toggle:"))
async def callback_source_status_toggle(callback: CallbackQuery):
    source_id = int(callback.data.split(":")[1])
    await callback.answer("Đang thay đổi trạng thái...")
    
    try:
        sources = await api_client.get_signal_sources(tg_user_id=callback.from_user.id)
        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            await callback.message.edit_text("❌ Không tìm thấy nguồn tín hiệu.", reply_markup=get_back_markup())
            return
            
        new_status = not source.get("is_active", True)
        await api_client.update_signal_source(
            source_id=source_id,
            name=source["name"],
            mode=source["mode"],
            is_active=new_status,
            tg_user_id=callback.from_user.id
        )
        
        # Reload detail page
        await callback_source_detail(callback, source_id=source_id)
    except Exception as e:
        await callback.message.reply(f"❌ Cập nhật thất bại: {str(e)}")

# 5. Xóa nguồn tín hiệu
@router.callback_query(F.data.startswith("src_delete:"))
async def callback_source_delete(callback: CallbackQuery):
    source_id = int(callback.data.split(":")[1])
    await callback.answer("Đang xóa nguồn...")
    
    try:
        await api_client.delete_signal_source(source_id, tg_user_id=callback.from_user.id)
        await callback.answer("Đã xóa nguồn tín hiệu", show_alert=True)
        # Quay về menu chính
        await callback_menu_sources(callback)
    except Exception as e:
        await callback.message.reply(f"❌ Xóa thất bại: {str(e)}")

# 6. Đổi tên nguồn (FSM State)
@router.callback_query(F.data.startswith("src_rename:"))
async def callback_source_rename(callback: CallbackQuery, state: FSMContext):
    source_id = int(callback.data.split(":")[1])
    await callback.answer()
    
    await state.set_state(RenameSourceState.waiting_for_name)
    await state.update_data(source_id=source_id)
    
    await callback.message.edit_text(
        "✏️ **ĐỔI TÊN NGUỒN TÍN HIỆU**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Vui lòng gửi tên hiển thị mới cho nguồn tín hiệu này (Ví dụ: `Group VIP Gold`):\n"
        "*(Hoặc gõ /cancel để hủy bỏ)*",
        parse_mode="Markdown"
    )

@router.message(RenameSourceState.waiting_for_name)
async def process_rename_source(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Đã hủy bỏ đổi tên.")
        return
        
    new_name = message.text.strip()
    if not new_name:
        await message.reply("❌ Tên không hợp lệ. Vui lòng nhập lại:")
        return
        
    data = await state.get_data()
    source_id = data["source_id"]
    await state.clear()
    
    try:
        # Lấy thông tin nguồn cũ
        sources = await api_client.get_signal_sources(tg_user_id=message.from_user.id)
        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            await message.reply("❌ Không tìm thấy nguồn tín hiệu.")
            return
            
        await api_client.update_signal_source(
            source_id=source_id,
            name=new_name,
            mode=source["mode"],
            tg_user_id=message.from_user.id
        )
        
        await message.reply(f"✅ Đã đổi tên nguồn thành: `{new_name}`", parse_mode="Markdown")
        
        # Hiển thị lại danh sách nguồn
        sources = await api_client.get_signal_sources(tg_user_id=message.from_user.id)
        msg = (
            "📡 **QUẢN LÝ NGUỒN TÍN HIỆU**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Dưới đây là danh sách các nguồn nhận tín hiệu của bạn:"
        )
        await message.reply(msg, reply_markup=get_sources_markup(sources), parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Đổi tên thất bại: {str(e)}")
