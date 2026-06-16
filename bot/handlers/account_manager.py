from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.config import config
from bot.services.api_client import api_client

router = Router()

class AccountForm(StatesGroup):
    name = State()
    platform = State()
    account_number = State()

def get_back_markup() -> InlineKeyboardMarkup:
    """Nút quay lại Menu chính"""
    buttons = [[InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def display_accounts_list(message_or_callback, state: FSMContext = None):
    # Xoá trạng thái FSM hiện tại nếu có để tránh kẹt trạng thái
    if state:
        await state.clear()
        
    try:
        accounts = await api_client.get_accounts()
    except Exception as e:
        text = f"❌ Lỗi khi lấy danh sách tài khoản: {e}"
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=get_back_markup())
        else:
            await message_or_callback.reply(text, reply_markup=get_back_markup())
        return

    lines = [
        "💳 **DANH SÁCH TÀI KHOẢN GIAO DỊCH**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    buttons = []
    for acc in accounts:
        status_str = "🔴 Offline"
        balance_str = "N/A"
        
        # Lấy trạng thái hoạt động (online/offline) của EA tài khoản này
        try:
            health = await api_client.get_health(account_id=acc["id"])
            if health.get("ea_online"):
                status_str = "🟢 Online"
            else:
                status_str = "🔴 Offline"
        except Exception:
            pass

        # Lấy số dư hiện tại của tài khoản
        try:
            acc_detail = await api_client.get_account(account_id=acc["id"])
            balance_str = f"${acc_detail.get('balance', 0.0):,.2f}"
        except Exception:
            pass

        active_tag = " [Mặc định]" if acc["is_active"] else ""
        active_icon = "🔹" if acc["is_active"] else "🔸"
        platform = acc["platform"]
        acc_num = acc["account_number"] or "Chưa đồng bộ"

        lines.append(
            f"{active_icon} **{acc['name']}**{active_tag}\n"
            f"   • Nền tảng: `{platform}` | Số TK: `{acc_num}`\n"
            f"   • Số dư: `{balance_str}`\n"
            f"   • Trạng thái EA: {status_str}\n"
        )

        acc_buttons = []
        if not acc["is_active"]:
            acc_buttons.append(InlineKeyboardButton(text="✅ Chọn", callback_data=f"acc_select:{acc['id']}"))
        
        acc_buttons.append(InlineKeyboardButton(text="🔑 Token", callback_data=f"acc_token:{acc['id']}"))
        acc_buttons.append(InlineKeyboardButton(text="🗑️ Xóa", callback_data=f"acc_confirm_del:{acc['id']}"))
        buttons.append(acc_buttons)

    # Thêm nút thêm tài khoản mới và nút quay lại menu chính
    buttons.append([InlineKeyboardButton(text="➕ Thêm tài khoản mới", callback_data="acc_add")])
    buttons.append([InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "\n".join(lines)
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_callback.reply(text, reply_markup=markup, parse_mode="Markdown")

@router.message(Command("accounts"))
async def cmd_accounts(message: Message, state: FSMContext):
    if message.from_user.id != config.owner_chat_id:
        return
    await display_accounts_list(message, state)

@router.callback_query(F.data == "menu_accounts")
async def cb_menu_accounts(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.owner_chat_id:
        await callback.answer("❌ Bạn không có quyền.")
        return
    await callback.answer()
    await display_accounts_list(callback, state)

@router.callback_query(F.data.startswith("acc_select:"))
async def cb_acc_select(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.owner_chat_id:
        return
    account_id = int(callback.data.split(":")[1])
    try:
        acc = await api_client.activate_account(account_id)
        await callback.answer(f"✅ Đã chọn làm mặc định: {acc['name']}")
    except Exception as e:
        await callback.answer(f"❌ Lỗi: {e}", show_alert=True)
    await display_accounts_list(callback, state)

@router.callback_query(F.data.startswith("acc_token:"))
async def cb_acc_token(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        return
    account_id = int(callback.data.split(":")[1])
    try:
        accounts = await api_client.get_accounts()
        acc = next((a for a in accounts if a["id"] == account_id), None)
        if acc:
            text = (
                f"🔑 **TOKEN KẾT NỐI TÀI KHOẢN**\n\n"
                f"Tên tài khoản: **{acc['name']}**\n"
                f"Nền tảng: `{acc['platform']}`\n"
                f"Token: `{acc['token']}`\n\n"
                f"👉 Hãy copy chuỗi Token trên và dán vào tham số đầu vào **Account Token** của EA trên MT4/MT5."
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu_accounts")]])
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await callback.answer("❌ Không tìm thấy tài khoản.", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Lỗi: {e}", show_alert=True)

@router.callback_query(F.data.startswith("acc_confirm_del:"))
async def cb_acc_confirm_del(callback: CallbackQuery):
    if callback.from_user.id != config.owner_chat_id:
        return
    account_id = int(callback.data.split(":")[1])
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Đồng ý xóa", callback_data=f"acc_delete:{account_id}"),
            InlineKeyboardButton(text="🔙 Hủy bỏ", callback_data="menu_accounts")
        ]
    ])
    await callback.message.edit_text(
        "⚠️ **CẢNH BÁO XÓA TÀI KHOẢN**\n\n"
        "Việc xóa tài khoản sẽ xóa toàn bộ cấu hình, lịch sử giao dịch và vết hoạt động của tài khoản này trong hệ thống.\n"
        "Bạn có chắc chắn muốn xóa không?",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("acc_delete:"))
async def cb_acc_delete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.owner_chat_id:
        return
    account_id = int(callback.data.split(":")[1])
    try:
        res = await api_client.delete_account(account_id)
        await callback.answer(res.get("message", "Đã xóa tài khoản."), show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Lỗi khi xóa: {e}", show_alert=True)
    await display_accounts_list(callback, state)

@router.callback_query(F.data == "acc_add")
async def cb_acc_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.owner_chat_id:
        return
    await callback.answer()
    await state.set_state(AccountForm.name)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Hủy bỏ", callback_data="menu_accounts")]])
    await callback.message.edit_text(
        "➕ **THÊM TÀI KHOẢN MỚI**\n\n"
        "Nhập tên gợi nhớ cho tài khoản này (Ví dụ: Exness Real 1):",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@router.message(AccountForm.name)
async def process_name(message: Message, state: FSMContext):
    if message.from_user.id != config.owner_chat_id:
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AccountForm.platform)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="MT4", callback_data="platform_select:MT4"),
            InlineKeyboardButton(text="MT5", callback_data="platform_select:MT5")
        ],
        [
            InlineKeyboardButton(text="❌ Hủy bỏ", callback_data="menu_accounts")
        ]
    ])
    await message.reply(
        "Chọn nền tảng giao dịch cho tài khoản này:",
        reply_markup=markup
    )

@router.callback_query(AccountForm.platform, F.data.startswith("platform_select:"))
async def cb_platform_select(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.owner_chat_id:
        return
    platform = callback.data.split(":")[1]
    await state.update_data(platform=platform)
    await state.set_state(AccountForm.account_number)
    await callback.answer()
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Hủy bỏ", callback_data="menu_accounts")]])
    await callback.message.edit_text(
        f"Bạn đã chọn **{platform}**.\n\n"
        "Nhập số tài khoản giao dịch (Ví dụ: 123456) để đồng bộ hoặc nhập `0` nếu chưa rõ:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@router.message(AccountForm.account_number)
async def process_account_number(message: Message, state: FSMContext):
    if message.from_user.id != config.owner_chat_id:
        return
    account_number = message.text.strip()
    user_data = await state.get_data()
    await state.clear()
    
    try:
        acc = await api_client.create_account(
            name=user_data["name"],
            platform=user_data["platform"],
            account_number=account_number if account_number != "0" else None
        )
        
        text = (
            f"🎉 **TÀI KHOẢN ĐÃ ĐƯỢC TẠO THÀNH CÔNG!**\n\n"
            f"• Tên tài khoản: **{acc['name']}**\n"
            f"• Nền tảng: `{acc['platform']}`\n"
            f"• Số tài khoản: `{acc['account_number'] or 'Chưa đồng bộ'}`\n\n"
            f"🔑 **Token kết nối:**\n"
            f"`{acc['token']}`\n\n"
            f"👉 Hãy sao chép Token này và dán vào Input **Account Token** trong EA trên {acc['platform']} để bắt đầu kết nối."
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Danh sách tài khoản", callback_data="menu_accounts"),
                InlineKeyboardButton(text="⬅️ Quay lại Menu", callback_data="menu_main")
            ]
        ])
        await message.reply(text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Lỗi khi tạo tài khoản: {e}", reply_markup=get_back_markup())
