from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import config
from bot.services.api_client import api_client
from bot.utils.formatter import format_balance, format_positions_list, format_config, format_report, format_datetime
from bot.handlers.trailing_cmd import format_trailing_config

router = Router()

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

def get_back_markup() -> InlineKeyboardMarkup:
    """Tạo bàn phím chỉ có nút quay lại Menu chính"""
    buttons = [[InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_queue_list(signals: list) -> str:
    """Định dạng danh sách tín hiệu hàng đợi"""
    if not signals:
        return "📋 Hàng đợi tín hiệu trống. Không có tín hiệu nào chờ duyệt."
        
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
    lines.append("💡 *Mẹo:* Sử dụng lệnh `/confirm [ID] [lot=val]` ngoài khung chat để duyệt lệnh.")
    return "\n".join(lines)

# 1. Quay lại Menu chính
@router.callback_query(F.data == "menu_main")
async def callback_menu_main(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer()
    
    acc_str = ""
    try:
        acc = await api_client.get_account()
        acc_str = f"\n🎮 *Đang thao tác trên:* **{acc['account_name']}** (`{acc['account_number']}`)"
    except Exception:
        pass
        
    await callback.message.edit_text(
        "🤖 **MENU ĐIỀU KHIỂN HỆ THỐNG**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        f"{acc_str}\n\n"
        "Chọn một tính năng bên dưới để quản lý hoặc thiết lập cấu hình:",
        reply_markup=get_inline_menu(),
        parse_mode="Markdown"
    )

# 2. Xem trạng thái hệ thống
@router.callback_query(F.data == "menu_status")
async def callback_menu_status(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang lấy trạng thái...")
    try:
        account = await api_client.get_account()
        health = await api_client.get_health()
        msg = format_balance(account, health)
        
        # Thêm nút Quay lại Menu
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy thông tin tài khoản: {str(e)}", reply_markup=get_back_markup())

# Xem giá vàng và biến động
@router.callback_query(F.data == "menu_gold")
async def callback_menu_gold(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang lấy giá vàng...")
    try:
        account = await api_client.get_account()
        health = await api_client.get_health()
        
        from bot.utils.formatter import format_gold_price
        msg = format_gold_price(account, health)
        
        # Thêm nút Quay lại Menu
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy giá vàng: {str(e)}", reply_markup=get_back_markup())

# 3. Xem danh sách lệnh mở
@router.callback_query(F.data == "menu_orders")
async def callback_menu_orders(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang tải danh sách vị thế...")
    try:
        positions = await api_client.get_positions()
        msg = format_positions_list(positions)
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy danh sách lệnh: {str(e)}", reply_markup=get_back_markup())

# 4. Xem cấu hình chung
@router.callback_query(F.data == "menu_config")
async def callback_menu_config(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang tải cấu hình...")
    try:
        configs = await api_client.get_config()
        msg = format_config(configs)
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy cấu hình: {str(e)}", reply_markup=get_back_markup())

# 5. Xem cấu hình trailing stop
@router.callback_query(F.data == "menu_trailing")
async def callback_menu_trailing(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang tải cấu hình trailing...")
    try:
        cfg = await api_client.get_trailing_config()
        msg = format_trailing_config(cfg)
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy cấu hình trailing: {str(e)}", reply_markup=get_back_markup())

# 6. Xem hàng đợi tín hiệu
@router.callback_query(F.data == "menu_queue")
async def callback_menu_queue(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang tải hàng đợi...")
    try:
        signals = await api_client.get_signals(status="QUEUED")
        msg = format_queue_list(signals)
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy danh sách hàng đợi: {str(e)}", reply_markup=get_back_markup())

# 7. Menu chọn báo cáo
@router.callback_query(F.data == "menu_report")
async def callback_menu_report(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer()
    buttons = [
        [
            InlineKeyboardButton(text="📅 Ngày", callback_data="report_day"),
            InlineKeyboardButton(text="📅 Tuần", callback_data="report_week"),
            InlineKeyboardButton(text="📅 Tháng", callback_data="report_month")
        ],
        [
            InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "📅 **BÁO CÁO KẾT QUẢ GIAO DỊCH (P/L)**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Chọn khoảng thời gian báo cáo bạn muốn hiển thị:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# 8. Màn hình xác nhận đóng toàn bộ lệnh
@router.callback_query(F.data == "menu_closeall")
async def callback_menu_closeall(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer()
    try:
        positions = await api_client.get_positions()
        if not positions:
            await callback.message.edit_text(
                "📋 Không có vị thế nào đang mở để đóng.",
                reply_markup=get_back_markup(),
                parse_mode="Markdown"
            )
            return
            
        buttons = [
            [
                InlineKeyboardButton(text="🔥 Xác nhận đóng hết", callback_data="confirm_close_all"),
                InlineKeyboardButton(text="❌ Hủy bỏ", callback_data="cancel_close_all")
            ]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            "⚠️ **CẢNH BÁO:** Bạn đang yêu cầu đóng TOÀN BỘ vị thế đang chạy trên tài khoản.\n"
            "Bạn có chắc chắn muốn thực hiện hành động này không?",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể kiểm tra vị thế: {str(e)}", reply_markup=get_back_markup())

# ── XỬ LÝ CLICK NÚT TRÊN MENU PHỤ (BÁO CÁO & XÁC NHẬN ĐÓNG LỆNH) ──

@router.callback_query(F.data.startswith("report_"))
async def callback_report_generate(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    period = callback.data.split("_")[1] # day, week, month
    await callback.answer(f"Đang tạo báo cáo {period}...")
    
    try:
        summary = await api_client.get_report_summary(period)
        weeks_to_compare = 8 if period == "month" else 4
        trend = await api_client.get_report_trend(weeks_to_compare)
        
        msg = format_report(summary, trend)
        
        # Báo cáo được gửi và đính kèm nút Quay lại Menu ở cuối tin nhắn
        await callback.message.edit_text(msg, reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Không thể lấy báo cáo: {str(e)}", reply_markup=get_back_markup())

@router.callback_query(F.data == "confirm_close_all")
async def callback_confirm_close_all(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang gửi yêu cầu đóng toàn bộ lệnh...")
    try:
        positions = await api_client.get_positions()
        if not positions:
            await callback.message.edit_text("📋 Không có vị thế nào đang mở để đóng.", reply_markup=get_back_markup())
            return
            
        closed_count = 0
        for pos in positions:
            await api_client.request_close_position_by_ticket(pos["ticket"])
            closed_count += 1
            
        await callback.message.edit_text(
            f"⏳ Đã gửi yêu cầu đóng **{closed_count}** vị thế đang chạy.\n"
            "Vui lòng chờ EA thực thi và đồng bộ...",
            reply_markup=get_back_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Lỗi khi gửi yêu cầu đóng toàn bộ lệnh: {str(e)}", reply_markup=get_back_markup())

@router.callback_query(F.data == "menu_history")
async def callback_menu_history(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đang tải lịch sử...")
    try:
        logs = await api_client.get_action_logs()
        if not logs:
            await callback.message.edit_text(
                "📋 Lịch sử hoạt động trống.",
                reply_markup=get_back_markup(),
                parse_mode="Markdown"
            )
            return
            
        lines = [
            "📜 **LỊCH SỬ HOẠT ĐỘNG GẦN ĐÂY**\n"
            "*(Sắp xếp từ mới đến cũ, tối đa 10 thao tác)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for idx, item in enumerate(logs, 1):
            ts_parsed = item.get("timestamp")
            # format timestamp
            time_part = "N/A"
            if ts_parsed:
                ts_str = ts_parsed.replace("Z", "").replace("T", " ")
                try:
                    dt = datetime.fromisoformat(ts_str.split(".")[0])
                    time_part = dt.strftime("%H:%M:%S %d/%m")
                except Exception:
                    time_part = ts_str
            
            pnl_val = item.get("pnl", 0.0)
            pnl_icon = "❇️" if pnl_val > 0 else "❌"
            formatted_pnl = f"+${pnl_val:.2f} {pnl_icon}" if pnl_val >= 0 else f"-${abs(pnl_val):.2f} {pnl_icon}"
            
            if item.get("type") == "action":
                action_type = item["action_type"]
                ticket = item["ticket"]
                symbol = item["symbol"]
                details = item["details"]
                
                if action_type == "TRAILING_SL":
                    lines.append(
                        f"{idx}. 🔔 **[Dời SL]** #{ticket} ({symbol})\n"
                        f"   - Chi tiết: `{details}`\n"
                        f"   - Lãi/lỗ: `{formatted_pnl}` | 🕒 `{time_part}`"
                    )
                elif action_type == "PARTIAL_CLOSE":
                    lines.append(
                        f"{idx}. ❎ **[Chốt lời]** #{ticket} ({symbol})\n"
                        f"   - Chi tiết: Chốt `{details}`\n"
                        f"   - Lãi: `{formatted_pnl}` | 🕒 `{time_part}`"
                    )
                else:
                    lines.append(
                        f"{idx}. ℹ️ **[{action_type}]** #{ticket} ({symbol})\n"
                        f"   - Chi tiết: `{details}`\n"
                        f"   - Lãi/lỗ: `{formatted_pnl}` | 🕒 `{time_part}`"
                    )
            elif item.get("type") == "trade":
                ticket = item["ticket"]
                symbol = item["symbol"]
                trade_type = item["trade_type"]
                lot_size = item["lot_size"]
                close_reason = item["close_reason"]
                source = item["source"]
                
                source_str = "✍️ Tay" if source == "MANUAL" else "🤖 Bot"
                dir_icon = "🟢" if "BUY" in trade_type else "🔴"
                
                # Mapped reason
                reason_map = {
                    "SL_HIT": "Khớp SL ❌",
                    "TP_HIT": "Khớp TP ❇️",
                    "MANUAL": "Đóng tay ✍️",
                    "TRAILING_STOP": "Trailing SL 🔔"
                }
                reason_str = reason_map.get(close_reason, close_reason)
                
                lines.append(
                    f"{idx}. ❎ **[Đóng lệnh]** #{ticket} ({symbol})\n"
                    f"   - Loại: `{source_str} {dir_icon} {trade_type} {lot_size:.2f} lot`\n"
                    f"   - PnL: `{formatted_pnl}` | Lý do: `{reason_str}`\n"
                    f"   - 🕒 `{time_part}`"
                )
                
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        await callback.message.edit_text("\n".join(lines), reply_markup=get_back_markup(), parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ Lỗi khi lấy lịch sử hoạt động: {str(e)}", reply_markup=get_back_markup())

@router.callback_query(F.data == "cancel_close_all")
async def callback_cancel_close_all(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
        
    await callback.answer("Đã hủy bỏ yêu cầu.")
    await callback.message.edit_text(
        "❌ Đã hủy yêu cầu đóng toàn bộ lệnh.",
        reply_markup=get_back_markup(),
        parse_mode="Markdown"
    )

# 9. Lắng nghe và dọn dẹp các nút bấm từ bàn phím Reply Keyboard cũ
@router.message(F.text.in_({
    "📊 Trạng thái", "💼 Vị thế mở", "📥 Hàng đợi", 
    "⚙️ Cấu hình", "📈 Trailing Stop", "📅 Báo cáo", 
    "💰 Số dư", "❌ Đóng toàn bộ"
}))
async def handle_old_reply_keyboard(message: Message):
    if not is_owner(message): return
    
    # Gửi menu inline mới và gỡ bỏ bàn phím cũ
    await message.reply(
        "🔄 **Hệ thống đã chuyển sang sử dụng Inline Menu (Nút bấm dưới tin nhắn).**\n"
        "Bàn phím cũ đã được gỡ bỏ. Bạn có thể sử dụng menu bên dưới hoặc gõ `/menu` để mở lại bất kỳ lúc nào:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await message.answer(
        "🤖 **MENU ĐIỀU KHIỂN HỆ THỐNG**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Chọn một tính năng bên dưới để quản lý hoặc thiết lập cấu hình:",
        reply_markup=get_inline_menu(),
        parse_mode="Markdown"
    )
