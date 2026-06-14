# 🤖 Telegram MT5 Bridge Trading Bot

Hệ thống giao dịch tự động và bán tự động trên MetaTrader 5 (MT5) thông qua điều khiển từ Telegram Bot, tích hợp lắng nghe và phân tích tín hiệu (chủ yếu XAUUSD/Vàng) từ nhóm Telegram bất kỳ bằng tài khoản cá nhân.

---

## 📋 Mục lục
1. [Tính năng nổi bật](#-tính-năng-nổi-bật)
2. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
3. [Cấu trúc dự án](#-cấu-trúc-dự-án)
4. [Hướng dẫn cài đặt](#-hướng-dẫn-cài-đặt)
5. [Cấu hình hệ thống](#-cấu-hình-hệ-thống)
6. [Thiết lập trên MetaTrader 5](#-thiết-lập-trên-metatrader-5)
7. [Danh sách lệnh Telegram Bot](#-danh-sách-lệnh-telegram-bot)
8. [Kiểm thử (Tests)](#-kiểm-thử-tests)

---

## ✨ Tính năng nổi bật
* **2 Chế độ Giao dịch:**
  1. `Auto` (Tự động): Khớp lệnh trực tiếp lên MT5 ngay khi nhận tín hiệu từ nhóm.
  2. `Queue` (Hàng đợi): Tín hiệu từ nhóm được đưa vào hàng đợi với ID duy nhất (VD: `SIG-0001`). Người dùng có thể duyệt (`/confirm`) hoặc từ chối (`/reject`) trên Bot Telegram trước khi lệnh được đặt.
* **Lắng nghe Tín hiệu bằng tài khoản Cá nhân:** Sử dụng thư viện `Telethon` đăng nhập bằng tài khoản Telegram cá nhân giúp lắng nghe bất kỳ nhóm tín hiệu nào (kể cả nhóm của bên thứ ba không có quyền Admin).
* **Quản lý Vốn An toàn:** Bỏ qua số lot có sẵn trong tin nhắn của nhóm tín hiệu. Chỉ sử dụng số lot được cấu hình trực tiếp trên hệ thống (lot mặc định hoặc lot ghi đè riêng cho từng cặp sản phẩm).
* **Báo cáo và Biểu đồ Trực quan:** Xem báo cáo P/L theo ngày, tuần, tháng kèm biểu đồ ASCII thể hiện xu hướng và các thông số chuyên sâu (Win Rate, Profit Factor, Drawdown, Streak thắng/thua liên tiếp).
* **Đồng bộ trạng thái EA:** EA liên tục gửi nhịp đập heartbeat và trạng thái tài khoản. Bot sẽ tự động cảnh báo đỏ nếu EA mất kết nối quá 30 giây.
* **Auto-close Detection:** Phát hiện lệnh đóng tự động (do chạm SL/TP hoặc đóng tay trên MT5) để gửi thông báo P/L và lý do đóng về Telegram Bot ngay lập tức.

---

## 💻 Yêu cầu hệ thống
* Python 3.10+ (Đã thử nghiệm tốt trên Python 3.10)
* MetaTrader 5 Terminal chạy trên Windows VPS hoặc máy tính cá nhân
* Tài khoản Telegram Bot (tạo qua `@BotFather`)
* Tài khoản Telegram cá nhân lấy `API_ID` và `API_HASH` từ [my.telegram.org](https://my.telegram.org)

---

## 📁 Cấu trúc dự án
* `api/`: REST API (FastAPI) đóng vai trò trung gian giữa Bot Telegram và EA.
* `bot/`: Telegram Bot (`aiogram 3`) điều khiển thủ công và lắng nghe nhóm tín hiệu (`Telethon`).
* `ea/`: Các tệp nguồn Expert Advisor viết bằng ngôn ngữ MQL5.
* `tests/`: Bộ kiểm thử tự động (unit tests và integration tests).

---

## 🚀 Hướng dẫn cài đặt

### Bước 1: Clone dự án và cài đặt Thư viện
Mở Command Prompt/PowerShell tại thư mục dự án và thực hiện:
```bash
# Tạo môi trường ảo python
py -3.10 -m venv venv

# Kích hoạt môi trường ảo (Windows)
.\venv\Scripts\activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### Bước 2: Cấu hình biến môi trường
1. Copy file `.env.example` thành `.env`:
   ```bash
   copy .env.example .env
   ```
2. Mở file `.env` và điền đầy đủ các thông tin:
   * `TELEGRAM_BOT_TOKEN`: Token của bot giao dịch.
   * `OWNER_CHAT_ID`: ID chat Telegram của bạn (Chỉ chat ID này mới có quyền điều khiển bot).
   * `SIGNAL_GROUP_ID`: ID nhóm hoặc username nhóm cần lắng nghe tín hiệu (VD: `-100123456789` hoặc `@signal_gold_group`).
   * `TELEGRAM_API_ID` và `TELEGRAM_API_HASH`: Lấy từ trang [my.telegram.org](https://my.telegram.org).
   * `API_KEY`: Đặt một khóa bảo mật tùy ý để EA và Bot xác thực với API (VD: `my-super-secret-key`).

### Bước 3: Đăng nhập tài khoản cá nhân & Phân tích lịch sử tín hiệu
Chạy script đăng nhập tương tác một lần duy nhất trước khi chạy hệ thống chính:
```bash
python login_telethon.py
```
* Nhập số điện thoại tài khoản Telegram cá nhân của bạn (VD: `+84912345678`).
* Nhập mã xác nhận (Code) gửi qua app Telegram.
* Nhập mật khẩu 2 lớp (nếu có).
* **Kết quả:** Session sẽ được lưu tại `data/anon.session`. Đồng thời script tự động cào tin nhắn 5 ngày qua từ group mục tiêu và lưu tại `data/signal_history.txt` để bạn xem định dạng tin nhắn mẫu.

---

## ⚙️ Cấu hình hệ thống
Hệ thống sử dụng các thông số mặc định trong `.env`. Bạn có thể thay đổi cấu hình này trực tiếp từ Telegram Bot thông qua các lệnh điều khiển.
Các thông số cấu hình chính:
* `mode`: `auto` hoặc `queue` (mặc định là `queue`).
* `default_lot`: Số lot mặc định cho các lệnh giao dịch (mặc định là `0.01`).
* `queue_expire_minutes`: Thời gian hết hạn của tín hiệu trong hàng đợi xác nhận (mặc định là `15` phút).

---

## 📊 Thiết lập trên MetaTrader 5

1. Mở phần mềm MT5 Terminal trên Windows.
2. Cho phép WebRequest kết nối tới API:
   * Vào `Tools` → `Options` → chọn thẻ `Expert Advisors`.
   * Tích chọn `Allow WebRequest for listed URL:`.
   * Thêm địa chỉ API của bạn vào danh sách: `http://127.0.0.1:8000` (hoặc IP VPS của bạn).
3. Đưa các file EA vào MT5:
   * Vào `File` → `Open Data Folder`.
   * Tìm đường dẫn: `MQL5/Experts/` và copy toàn bộ các file trong thư mục `ea/` của dự án vào đây (bao gồm `TelegramBridge.mq5`, `HttpClient.mqh`, và `JsonParser.mqh`).
4. Biên dịch và gắn EA:
   * Mở trình soạn thảo MetaEditor (phím tắt `F4`), mở file `TelegramBridge.mq5` và nhấn **Compile**.
   * Trở lại MT5, mở bảng Navigator, tìm `TelegramBridge` trong mục Expert Advisors và kéo vào biểu đồ (khuyến nghị chạy trên chart XAUUSD).
   * Thiết lập tham số đầu vào:
     * `InpApiUrl`: `http://127.0.0.1:8000`
     * `InpApiKey`: Khớp với `API_KEY` bạn đã thiết lập trong file `.env`.

---

## 🎮 Danh sách lệnh Telegram Bot

Gửi các lệnh sau trực tiếp cho Bot Telegram của bạn (chỉ hoạt động với `OWNER_CHAT_ID`):

### 1. Đặt lệnh thủ công
* `/buy XAUUSD 0.01 sl=2340 tp=2370` — Mở vị thế Mua vàng
* `/sell XAUUSD 0.02 sl=2360 tp=2330` — Mở vị thế Bán vàng
* `/buylimit XAUUSD price=2320 sl=2310 tp=2350` — Đặt lệnh chờ Buy Limit
* `/selllimit XAUUSD price=2350 sl=2360 tp=2320` — Đặt lệnh chờ Sell Limit

### 2. Quản lý lệnh đang chạy
* `/orders` — Hiển thị danh sách các lệnh đang chạy kèm float P/L thực tế.
* `/close [TICKET]` — Đóng vị thế cụ thể (VD: `/close 12345678`).
* `/closeall` — Yêu cầu đóng toàn bộ các vị thế đang chạy ngay lập tức.
* `/balance` hoặc `/status` — Xem số dư tài khoản MT5 và trạng thái kết nối của EA.

### 3. Duyệt hàng đợi tín hiệu (Queue Mode)
* `/queue` — Xem danh sách các tín hiệu đang đợi duyệt trong hàng đợi.
* `/confirm [QUEUE_ID] [lot=val]` — Duyệt tín hiệu vào lệnh (VD: `/confirm SIG-0001` hoặc `/confirm SIG-0001 lot=0.03`).
* `/reject [QUEUE_ID]` — Từ chối tín hiệu, lệnh sẽ bị hủy khỏi hàng đợi.
* `/confirmall` — Duyệt toàn bộ các tín hiệu đang có trong hàng đợi.
* `/rejectall` — Hủy bỏ toàn bộ hàng đợi tín hiệu.

### 4. Báo cáo & Cấu hình
* `/report day` / `/report week` / `/report month` — Báo cáo kết quả giao dịch kèm biểu đồ ASCII.
* `/config` — Xem cấu hình hệ thống hiện tại.
* `/mode auto` hoặc `/mode queue` — Đổi nhanh chế độ hoạt động của Bot.
* `/config default_lot=0.02` — Đổi số lot mặc định của hệ thống.
* `/config XAUUSD=0.03` — Đặt lot ghi đè riêng cho symbol XAUUSD.
* `/config remove XAUUSD` — Xóa lot ghi đè của symbol XAUUSD.

---

## 🧪 Kiểm thử (Tests)

Bộ kiểm thử tự động kiểm tra tính chính xác của bộ parser tín hiệu và các API giao dịch:
```bash
# Chạy bộ test
.\venv\Scripts\python -m pytest
```
