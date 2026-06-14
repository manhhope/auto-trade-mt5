from typing import Dict, Any, Optional

def parse_trade_command(text: str) -> Dict[str, Any]:
    """
    Phân tích cú pháp lệnh thủ công từ người dùng.
    Ví dụ: /buy XAUUSD 0.01 sl=2340 tp=2370
    Trả về: {"symbol", "lot_size", "stop_loss", "take_profit", "price"}
    """
    parts = text.split()
    if len(parts) < 2:
        raise ValueError("Thiếu symbol. Ví dụ: /buy XAUUSD 0.01 sl=2340 tp=2370")

    result = {
        "symbol": parts[1].upper(), 
        "lot_size": None, 
        "stop_loss": None,
        "take_profit": None, 
        "price": None
    }

    # Nếu phần tử thứ 3 là số lot (không chứa dấu =)
    if len(parts) >= 3 and "=" not in parts[2]:
        try:
            result["lot_size"] = float(parts[2])
        except ValueError:
            raise ValueError("Cú pháp số lot không hợp lệ. Số lot phải là số thực (VD: 0.01).")

    # Duyệt qua tất cả các tham số dạng key=value
    for part in parts:
        kv = part.lower().split("=", 1)
        if len(kv) == 2:
            key, val = kv[0], kv[1]
            try:
                if key == "sl":
                    result["stop_loss"] = float(val)
                elif key == "tp":
                    result["take_profit"] = float(val)
                elif key == "price":
                    result["price"] = float(val)
                elif key == "lot":
                    result["lot_size"] = float(val)
            except ValueError:
                raise ValueError(f"Giá trị của tham số '{key}' phải là số thực.")
                
    return result
