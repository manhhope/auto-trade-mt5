import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedSignal:
    trade_type: str      # "BUY" or "SELL" (hoặc BUY_LIMIT, etc.)
    symbol: str          # Raw symbol trước mapping
    price: Optional[float]
    sl: Optional[float]
    tp: Optional[float]

# Định nghĩa các biểu thức chính quy (Regex) để trích xuất tín hiệu
PATTERNS = [
    # Pattern 1: Inline EN — "BUY GOLD 2350.50 SL 2340 TP 2370"
    re.compile(
        r'(BUY|SELL|BUY\s+LIMIT|SELL\s+LIMIT|BUY\s+STOP|SELL\s+STOP)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*[@:]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|stoploss|stop\s*loss|cắt\s*lỗ)\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:TP|takeprofit|take\s*profit|chốt\s*lời)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
    # Pattern 2: Multiline — BUY GOLD\nEntry: 2350\nSL: 2340\nTP: 2370
    re.compile(
        r'(BUY|SELL|BUY\s+LIMIT|SELL\s+LIMIT|BUY\s+STOP|SELL\s+STOP)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*\n'
        r'.*?(?:entry|price|giá)\s*[:=]?\s*(\d+\.?\d*)\s*\n'
        r'.*?(?:SL|stoploss|stop\s*loss|cắt\s*lỗ)\s*[:=]?\s*(\d+\.?\d*)\s*\n'
        r'.*?(?:TP|takeprofit|take\s*profit|chốt\s*lời)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE | re.DOTALL
    ),
    # Pattern 3: Vietnamese — "Mua vàng giá 2350 cắt lỗ 2340 chốt lời 2370"
    re.compile(
        r'(Mua|Bán)\s+(GOLD|XAU(?:USD[T]?)?|[Vv]àng|VÀNG)\s*'
        r'(?:giá|entry|price)?\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|cắt\s*lỗ|stoploss)\s*[:=]?\s*(\d+\.?\d*)\s*'
        r'(?:TP|chốt\s*lời|takeprofit)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
    # Pattern 4: Không có TP — "BUY GOLD 2350 SL 2340"
    re.compile(
        r'(BUY|SELL|BUY\s+LIMIT|SELL\s+LIMIT|BUY\s+STOP|SELL\s+STOP)\s+(GOLD|XAU(?:USD[T]?)?|VÀNG)\s*[@:]?\s*(\d+\.?\d*)\s*'
        r'(?:SL|stoploss|stop\s*loss|cắt\s*lỗ)\s*[:=]?\s*(\d+\.?\d*)',
        re.IGNORECASE
    ),
]

VIET_TYPE_MAP = {
    "mua": "BUY", 
    "bán": "SELL"
}

def clean_type(t: str) -> str:
    """Chuẩn hóa loại lệnh giao dịch"""
    t_clean = re.sub(r'\s+', '_', t.strip().upper())
    return VIET_TYPE_MAP.get(t_clean.lower(), t_clean)

def parse_signal(text: str) -> Optional[ParsedSignal]:
    """
    Phân tích cú pháp tin nhắn group tín hiệu.
    Trả về ParsedSignal nếu khớp mẫu, ngược lại trả về None.
    """
    for pattern in PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            trade_type = clean_type(groups[0])
            symbol = groups[1].upper()
            price = float(groups[2]) if groups[2] else None
            
            # SL và TP có thể không có ở một số pattern
            sl = float(groups[3]) if len(groups) > 3 and groups[3] else None
            tp = float(groups[4]) if len(groups) > 4 and groups[4] else None
            
            return ParsedSignal(
                trade_type=trade_type,
                symbol=symbol,
                price=price,
                sl=sl,
                tp=tp
            )
            
    return None
