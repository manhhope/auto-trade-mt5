# 📊 Phân Tích Tin Nhắn Tín Hiệu (7 Ngày Gần Đây)

- **Thời gian quét:** 2026-06-08 → 2026-06-15
- **Nguồn dữ liệu:** DATABASE
- **Tổng tin nhắn:** 19
- **✅ Parse thành công:** 7
- **❌ Không nhận diện:** 12
- **Tỷ lệ nhận diện:** 36.8%

---

## ✅ Tin Nhắn Được Nhận Diện Thành Công

### 1. 📩 Message #33611 — 2026-06-15 00:35:49

**Nội dung gốc:**
```
Buy 02-99
sl 90
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `BUY` |
| Symbol | `GOLD` |
| Giá vào | `2.0` |
| Stop Loss | `90.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — BUY GOLD @ 2.0, SL=90.0, TP=None

---

### 2. 📩 Message #33613 — 2026-06-15 00:40:11

**Nội dung gốc:**
```
Buy 98-95
sl 87
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `BUY` |
| Symbol | `GOLD` |
| Giá vào | `98.0` |
| Stop Loss | `87.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — BUY GOLD @ 98.0, SL=87.0, TP=None

---

### 3. 📩 Message #33615 — 2026-06-15 01:03:05

**Nội dung gốc:**
```
Đảo sell 99-03
sl 10
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `SELL` |
| Symbol | `GOLD` |
| Giá vào | `99.0` |
| Stop Loss | `10.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — SELL GOLD @ 99.0, SL=10.0, TP=None

---

### 4. 📩 Message #33617 — 2026-06-15 01:27:22

**Nội dung gốc:**
```
Sell 00-03
sl 12
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `SELL` |
| Symbol | `GOLD` |
| Giá vào | `0.0` |
| Stop Loss | `12.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — SELL GOLD @ 0.0, SL=12.0, TP=None

---

### 5. 📩 Message #33622 — 2026-06-15 01:57:18

**Nội dung gốc:**
```
Buy 17-15
Sl 07
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `BUY` |
| Symbol | `GOLD` |
| Giá vào | `17.0` |
| Stop Loss | `7.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — BUY GOLD @ 17.0, SL=7.0, TP=None

---

### 6. 📩 Message #33625 — 2026-06-15 02:40:59

**Nội dung gốc:**
```
Buy 31-33
Sl 21
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `BUY` |
| Symbol | `GOLD` |
| Giá vào | `31.0` |
| Stop Loss | `21.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — BUY GOLD @ 31.0, SL=21.0, TP=None

---

### 7. 📩 Message #33627 — 2026-06-15 03:05:22

**Nội dung gốc:**
```
buy 27-25
sl 17
```

**Kết quả parse (signal_parser.py):**

| Trường | Giá trị |
|--------|---------|
| Loại lệnh | `BUY` |
| Symbol | `GOLD` |
| Giá vào | `27.0` |
| Stop Loss | `17.0` |
| Take Profit | `None` |
| DB Status | `PARSE_FAILED` |

**Quyết định:** 🟢 **Market/Entry Order** — BUY GOLD @ 27.0, SL=17.0, TP=None

---

## ❌ Tin Nhắn KHÔNG Nhận Diện Được

> Các tin nhắn dưới đây không match với bất kỳ pattern nào trong signal parser.
> Hãy kiểm tra xem có cần thêm pattern mới không.

### 1. 📩 Message #33610 — 2026-06-14 23:42:14

```
Hôm nay không có tin tức nào quan trọng. Chúc các trader tuần mới tràn đầy năng lượng và giao dịch thành công.
```

> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).
> DB Status: `PARSE_FAILED`

---

### 2. 📩 Message #33612 — 2026-06-15 00:37:11

```
Có 20pip hủy limit
```

> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).
> DB Status: `PARSE_FAILED`

---

### 3. 📩 Message #33614 — 2026-06-15 01:01:17

```
lệnh này bị sl mất, cả 2 entry đều có lãi mà em không kịp báo, quay xuống dịnh sl. Cả nhà chờ tín hiệu khác nhé
```

> ⚠️ **Có chứa từ khóa SL/TP** — có thể là cập nhật tín hiệu.
> DB Status: `PARSE_FAILED`

---

### 4. 📩 Message #33616 — 2026-06-15 01:04:42

```
Vàng xuống 88+110pip✅✅ hủy limit
```

> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).
> DB Status: `PARSE_FAILED`

---

### 5. 📩 Message #33618 — 2026-06-15 01:35:09

```
sell lại 13
sl 23
```

> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!
> DB Status: `PARSE_FAILED`

---

### 6. 📩 Message #33619 — 2026-06-15 01:36:00

```
ai yếu tay đứng ngoài nehs, vàng đâu tuần khó giao dịch
```

> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).
> DB Status: `PARSE_FAILED`

---

### 7. 📩 Message #33620 — 2026-06-15 01:37:32

```
Vàng xuống 09+40pip ,vàng chạy nhanh ae chủ động nhé
```

> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).
> DB Status: `PARSE_FAILED`

---

### 8. 📩 Message #33621 — 2026-06-15 01:41:11

```
🔥CÁC ĐIỀU KHOẢN DỰ KIẾN CỦA THỎA THUẬN HÒA BÌNH GIỮA MỸ VÀ IRAN:

1. Gia hạn lệnh ngừng bắn giữa Mỹ và Iran trong 60 ngày

2. Bắt đầu giai đoạn đàm phán 60 ngày để thảo luận kỹ thuật liên quan đến chương trình hạt nhân của Iran

3. Dỡ bỏ phong tỏa hải quân của Mỹ và mở lại Eo biển Hormuz 

4. Mỹ cam kết thảo luận về việc nới lỏng các biện pháp trừng phạt với Iran

5. Mỹ cam kết thảo luận về việc giải phóng các quỹ Iran bị đóng băng

6. Thỏa thuận hòa bình bao gồm việc chấm dứt vĩnh viễn chiến sự trên mọi mặt trận, bao gồm cả Lebanon

7. Thỏa thuận cuối cùng sẽ được ký vào ngày 19 tháng 6 tại Thụy Sĩ.
```

> ℹ️ **Có thể là lệnh đóng vị thế.**
> DB Status: `PARSE_FAILED`

---

### 9. 📩 Message #33623 — 2026-06-15 02:02:06

```
Vàng lên 20
Buy 15 + 50pip
Buy 17 + 30pip
```

> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!
> DB Status: `PARSE_FAILED`

---

### 10. 📩 Message #33624 — 2026-06-15 02:23:36

```
Vàng lên 28
Buy 15 + 130pip
Buy 17 + 110pip
```

> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!
> DB Status: `PARSE_FAILED`

---

### 11. 📩 Message #33626 — 2026-06-15 02:51:26

```
Buy 31 lên 34 + 30pip
```

> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!
> DB Status: `PARSE_FAILED`

---

### 12. 📩 Message #33628 — 2026-06-15 04:29:07

```
Buy 25 lên 27 + 20pip thoát giá xấu
```

> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!
> DB Status: `PARSE_FAILED`

---

## 📈 Thống Kê Tổng Hợp

### Phân bổ theo loại lệnh

| Loại lệnh | Số lượng |
|-----------|----------|
| BUY | 5 |
| SELL | 2 |

### Phân bổ theo symbol

| Symbol | Số lượng |
|--------|----------|
| GOLD | 7 |
