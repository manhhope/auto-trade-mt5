import os
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telethon import TelegramClient

# Load variables from .env
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SIGNAL_GROUP_ID = os.getenv("SIGNAL_GROUP_ID")

async def main():
    print("=== CHƯƠNG TRÌNH ĐĂNG NHẬP & CÀO TÍN HIỆU TELEGRAM ===")
    
    # 1. Kiểm tra cấu hình
    if not API_ID or not API_HASH:
        print("❌ Lỗi: Thiếu TELEGRAM_API_ID hoặc TELEGRAM_API_HASH trong file .env!")
        return
        
    if not SIGNAL_GROUP_ID:
        print("❌ Lỗi: Thiếu SIGNAL_GROUP_ID trong file .env!")
        return
        
    api_id = int(API_ID)
    api_hash = API_HASH
    
    # Tạo thư mục data nếu chưa tồn tại
    os.makedirs("data", exist_ok=True)
    session_path = os.path.join("data", "anon.session")
    
    # 2. Khởi tạo Telegram Client
    client = TelegramClient(session_path, api_id, api_hash)
    
    print("\n[1] Đang kết nối tới Telegram...")
    await client.connect()
    
    # 3. Đăng nhập tương tác nếu chưa có session
    if not await client.is_user_authorized():
        print("Tài khoản chưa được xác thực. Bắt đầu đăng nhập...")
        # Nếu cấu hình có số điện thoại thì điền tự động, không thì nhập thủ công
        phone_number = PHONE if PHONE else input("Nhập số điện thoại của bạn (kèm mã quốc gia, VD: +84912345678): ")
        
        await client.send_code_request(phone_number)
        code = input("Nhập mã xác nhận (Code) gửi qua Telegram App của bạn: ")
        
        try:
            await client.sign_in(phone_number, code)
        except Exception as e:
            # Nhập mật khẩu 2FA nếu có
            if "Two-step verification" in str(e) or "password" in str(e).lower():
                pwd = input("Nhập mật khẩu xác thực 2 lớp (2FA Password) của bạn: ")
                await client.sign_in(password=pwd)
            else:
                raise e
                
    print("✅ Đăng nhập thành công!")
    
    # 4. Xác định Group ID
    # Nhóm Telegram thường có ID bắt đầu bằng -100 hoặc dạng username chuỗi.
    group_target = SIGNAL_GROUP_ID
    if group_target.startswith("-") or group_target.isdigit():
        group_target = int(group_target)
        
    print(f"\n[2] Đang kết nối tới group: {group_target}...")
    try:
        group = await client.get_entity(group_target)
        print(f"✅ Đã tìm thấy group: {group.title}")
    except Exception as e:
        print(f"❌ Không thể tìm thấy group. Lỗi: {e}")
        print("Vui lòng kiểm tra lại SIGNAL_GROUP_ID hoặc tài khoản của bạn đã tham gia group này chưa.")
        await client.disconnect()
        return
        
    # 5. Tải tin nhắn trong vòng 5 ngày qua
    print("\n[3] Đang tải toàn bộ tin nhắn trong 5 ngày qua...")
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=5)
    
    history_file_path = os.path.join("data", "signal_history.txt")
    msg_count = 0
    
    with open(history_file_path, "w", encoding="utf-8") as f:
        f.write(f"=== LỊCH SỬ TIN NHẮN TỪ GROUP '{group.title}' (5 NGÀY QUA) ===\n")
        f.write(f"Thời gian xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")
        
        async for message in client.iter_messages(group):
            # Dừng nếu tin nhắn cũ hơn 5 ngày
            if message.date < cutoff_date:
                break
                
            # Bỏ qua tin nhắn không có text
            if not message.text:
                continue
                
            msg_count += 1
            f.write(f"ID: {message.id}\n")
            f.write(f"Thời gian: {message.date.strftime('%d/%m/%Y %H:%M:%S')} UTC\n")
            f.write(f"Nội dung:\n{message.text}\n")
            f.write("--------------------------------------------------\n\n")
            
    print(f"✅ Đã cào thành công {msg_count} tin nhắn.")
    print(f"📂 Dữ liệu lịch sử đã lưu tại: {os.path.abspath(history_file_path)}")
    print("\nBạn có thể mở file này ra xem các mẫu tin nhắn để kiểm tra bộ Regex Parser.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
