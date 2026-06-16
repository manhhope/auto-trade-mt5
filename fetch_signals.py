"""
Script lấy tin nhắn từ channel tín hiệu qua Telegram Bot API (getUpdates/getChat),
hoặc nếu bot không đọc được lịch sử channel thì lấy từ database signals.
Chạy signal_parser trên mỗi tin nhắn và xuất kết quả phân tích.
"""
import os
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Fix Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from bot.parsers.signal_parser import parse_signal

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SIGNAL_GROUP_ID = os.getenv("SIGNAL_GROUP_ID")
DB_PATH = os.getenv("DATABASE_PATH", "data/trades.db")
OUTPUT_FILE = "signal_analysis.md"
DAYS_BACK = 7

def fetch_from_bot_api():
    """Thử lấy tin nhắn qua Bot API (chỉ hoạt động nếu bot là admin của channel)"""
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    # Thử getUpdates
    try:
        resp = requests.get(f"{base_url}/getUpdates", params={"limit": 100, "offset": -100}, timeout=10)
        data = resp.json()
        if data.get("ok"):
            messages = []
            for update in data.get("result", []):
                msg = update.get("message") or update.get("channel_post")
                if msg and msg.get("text"):
                    messages.append({
                        "id": msg["message_id"],
                        "date": datetime.fromtimestamp(msg["date"]).strftime("%Y-%m-%d %H:%M"),
                        "text": msg["text"],
                        "chat_id": str(msg["chat"]["id"])
                    })
            # Filter chỉ lấy từ signal group
            signal_msgs = [m for m in messages if m["chat_id"] == SIGNAL_GROUP_ID]
            if signal_msgs:
                return signal_msgs
    except Exception as e:
        print(f"⚠️  Bot API getUpdates thất bại: {e}")
    
    return []

def fetch_from_database():
    """Lấy tin nhắn từ database signals (fallback)"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database không tồn tại: {DB_PATH}")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    min_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        SELECT id, message_id, group_id, raw_message, 
               parsed_type, parsed_symbol, parsed_price, parsed_sl, parsed_tp,
               parse_success, status, created_at
        FROM signals 
        WHERE created_at >= ?
        ORDER BY created_at ASC
    """, (min_date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for row in rows:
        messages.append({
            "db_id": row["id"],
            "id": row["message_id"],
            "date": row["created_at"],
            "text": row["raw_message"],
            "group_id": row["group_id"],
            "db_parsed_type": row["parsed_type"],
            "db_parsed_symbol": row["parsed_symbol"],
            "db_parsed_price": row["parsed_price"],
            "db_parsed_sl": row["parsed_sl"],
            "db_parsed_tp": row["parsed_tp"],
            "db_parse_success": row["parse_success"],
            "db_status": row["status"],
        })
    
    return messages

def main():
    print(f"📊 Phân tích tin nhắn tín hiệu {DAYS_BACK} ngày gần đây")
    print(f"   Signal Group: {SIGNAL_GROUP_ID}")
    print(f"   Database: {DB_PATH}")
    print()
    
    # Thử lấy từ Bot API trước
    print("🔍 Thử lấy tin nhắn từ Bot API...")
    bot_messages = fetch_from_bot_api()
    
    # Lấy từ database
    print("🔍 Lấy tin nhắn từ database...")
    db_messages = fetch_from_database()
    
    # Ưu tiên database vì có lịch sử đầy đủ hơn
    if db_messages:
        print(f"✅ Tìm thấy {len(db_messages)} tin nhắn trong database")
        messages = db_messages
        source = "DATABASE"
    elif bot_messages:
        print(f"✅ Tìm thấy {len(bot_messages)} tin nhắn từ Bot API")
        messages = bot_messages
        source = "BOT_API"
    else:
        print("❌ Không tìm thấy tin nhắn nào!")
        # Nếu không có dữ liệu, thử lấy trực tiếp từ Telegram channel
        print("\n💡 Gợi ý: Hãy đảm bảo:")
        print("   1. Bot đã được thêm vào channel tín hiệu làm admin")
        print("   2. Hoặc hệ thống đã chạy và lưu signals vào database")
        print("   3. Database path chính xác:", DB_PATH)
        return

    # Phân tích từng tin nhắn
    results = []
    for msg in messages:
        parsed = parse_signal(msg["text"])
        results.append({
            "msg": msg,
            "parsed": parsed,
            "source": source
        })

    # Thống kê
    total = len(results)
    matched = sum(1 for r in results if r["parsed"] is not None)
    unmatched = total - matched

    # Xuất file markdown
    lines = []
    lines.append("# 📊 Phân Tích Tin Nhắn Tín Hiệu (7 Ngày Gần Đây)")
    lines.append("")
    min_date_str = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    max_date_str = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"- **Thời gian quét:** {min_date_str} → {max_date_str}")
    lines.append(f"- **Nguồn dữ liệu:** {source}")
    lines.append(f"- **Tổng tin nhắn:** {total}")
    lines.append(f"- **✅ Parse thành công:** {matched}")
    lines.append(f"- **❌ Không nhận diện:** {unmatched}")
    if total > 0:
        lines.append(f"- **Tỷ lệ nhận diện:** {matched/total*100:.1f}%")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === PHẦN 1: CÁC TIN NHẮN PARSE THÀNH CÔNG ===
    lines.append("## ✅ Tin Nhắn Được Nhận Diện Thành Công")
    lines.append("")

    matched_results = [r for r in results if r["parsed"] is not None]
    if matched_results:
        for idx, r in enumerate(matched_results, 1):
            p = r["parsed"]
            msg = r["msg"]
            lines.append(f"### {idx}. 📩 Message #{msg['id']} — {msg['date']}")
            lines.append("")
            lines.append("**Nội dung gốc:**")
            lines.append("```")
            lines.append(msg["text"])
            lines.append("```")
            lines.append("")
            lines.append("**Kết quả parse (signal_parser.py):**")
            lines.append("")
            lines.append("| Trường | Giá trị |")
            lines.append("|--------|---------|")
            lines.append(f"| Loại lệnh | `{p.trade_type}` |")
            lines.append(f"| Symbol | `{p.symbol}` |")
            lines.append(f"| Giá vào | `{p.price}` |")
            lines.append(f"| Stop Loss | `{p.sl}` |")
            lines.append(f"| Take Profit | `{p.tp}` |")
            
            # Nếu nguồn là DB, hiển thị thêm trạng thái lưu
            if source == "DATABASE":
                lines.append(f"| DB Status | `{msg.get('db_status', 'N/A')}` |")
            lines.append("")

            # Quyết định hệ thống
            if p.trade_type in ("BUY", "SELL") and p.price is not None:
                decision = f"🟢 **Market/Entry Order** — {p.trade_type} {p.symbol} @ {p.price}, SL={p.sl}, TP={p.tp}"
            elif p.trade_type in ("BUY", "SELL") and p.price is None:
                decision = f"🟢 **Market Order (giá hiện tại)** — {p.trade_type} {p.symbol}, SL={p.sl}, TP={p.tp}"
            elif "LIMIT" in p.trade_type or "STOP" in p.trade_type:
                if p.price:
                    decision = f"🟡 **Pending Order** — {p.trade_type} {p.symbol} @ {p.price}, SL={p.sl}, TP={p.tp}"
                else:
                    decision = f"🔴 **Lỗi: Pending order thiếu giá!** — {p.trade_type} {p.symbol}"
            else:
                decision = f"⚪ **Unknown** — {p.trade_type}"

            lines.append(f"**Quyết định:** {decision}")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("_Không có tin nhắn nào được nhận diện._")
        lines.append("")

    # === PHẦN 2: CÁC TIN NHẮN KHÔNG NHẬN DIỆN ===
    lines.append("## ❌ Tin Nhắn KHÔNG Nhận Diện Được")
    lines.append("")
    lines.append("> Các tin nhắn dưới đây không match với bất kỳ pattern nào trong signal parser.")
    lines.append("> Hãy kiểm tra xem có cần thêm pattern mới không.")
    lines.append("")

    unmatched_results = [r for r in results if r["parsed"] is None]
    if unmatched_results:
        for idx, r in enumerate(unmatched_results, 1):
            msg = r["msg"]
            lines.append(f"### {idx}. 📩 Message #{msg['id']} — {msg['date']}")
            lines.append("")
            lines.append("```")
            lines.append(msg["text"])
            lines.append("```")
            lines.append("")
            
            # Phân loại sơ bộ nội dung
            text_lower = msg["text"].lower()
            if any(w in text_lower for w in ["buy", "sell", "mua", "bán", "long", "short"]):
                lines.append("> ⚠️ **Có vẻ là tín hiệu giao dịch** nhưng không match pattern hiện tại!")
            elif any(w in text_lower for w in ["tp", "sl", "take profit", "stop loss", "chốt lời", "cắt lỗ"]):
                lines.append("> ⚠️ **Có chứa từ khóa SL/TP** — có thể là cập nhật tín hiệu.")
            elif any(w in text_lower for w in ["close", "đóng", "chốt", "exit", "out"]):
                lines.append("> ℹ️ **Có thể là lệnh đóng vị thế.**")
            else:
                lines.append("> ℹ️ Tin nhắn thường (chat, thảo luận, không phải tín hiệu).")
            
            if source == "DATABASE":
                lines.append(f"> DB Status: `{msg.get('db_status', 'N/A')}`")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("_Tất cả tin nhắn đều được nhận diện._")
        lines.append("")

    # === PHẦN 3: THỐNG KÊ TỔNG HỢP ===
    lines.append("## 📈 Thống Kê Tổng Hợp")
    lines.append("")
    
    # Đếm theo loại lệnh
    type_counts = {}
    for r in matched_results:
        t = r["parsed"].trade_type
        type_counts[t] = type_counts.get(t, 0) + 1
    
    if type_counts:
        lines.append("### Phân bổ theo loại lệnh")
        lines.append("")
        lines.append("| Loại lệnh | Số lượng |")
        lines.append("|-----------|----------|")
        for t, c in sorted(type_counts.items()):
            lines.append(f"| {t} | {c} |")
        lines.append("")
    
    # Đếm theo symbol
    symbol_counts = {}
    for r in matched_results:
        s = r["parsed"].symbol
        symbol_counts[s] = symbol_counts.get(s, 0) + 1
    
    if symbol_counts:
        lines.append("### Phân bổ theo symbol")
        lines.append("")
        lines.append("| Symbol | Số lượng |")
        lines.append("|--------|----------|")
        for s, c in sorted(symbol_counts.items()):
            lines.append(f"| {s} | {c} |")
        lines.append("")

    # Ghi file
    content = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Đã xuất kết quả phân tích vào file: {OUTPUT_FILE}")
    print(f"   ✅ Matched: {matched}/{total}")
    print(f"   ❌ Unmatched: {unmatched}/{total}")

if __name__ == "__main__":
    main()
