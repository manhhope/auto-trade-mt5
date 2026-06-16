from datetime import datetime
from typing import Dict, Any, List

def format_datetime(dt_str: str) -> str:
    """Format ISO datetime string to HH:MM:SS DD/MM/YYYY"""
    if not dt_str:
        return "N/A"
    try:
        # Bỏ chữ Z ở cuối nếu có
        clean_str = dt_str.replace("Z", "")
        # Nếu có dấu + hoặc phần thập phân, cắt bớt để parse
        if "." in clean_str:
            clean_str = clean_str.split(".")[0]
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return dt_str

def make_bar(value: float, max_value: float, width: int = 10) -> str:
    """Tạo thanh biểu đồ ASCII"""
    if max_value <= 0:
        return "░" * width
    filled = min(int(abs(value) / max_value * width), width)
    return "█" * filled + "░" * (width - filled)

def format_auto_trade(trade: Dict[str, Any]) -> str:
    """Thông báo khi lệnh được vào tự động từ Signal"""
    pips_sl = ""
    pips_tp = ""
    entry = trade.get("price") or 0.0
    
    if trade.get("stop_loss") and entry:
        diff = abs(entry - trade["stop_loss"])
        pips = int(diff * 100) if "JPY" in trade["symbol"] else int(diff * 10000)
        # Đối với Vàng (XAUUSD), 1 pip = 0.1 giá
        if "XAU" in trade["symbol"] or "GOLD" in trade["symbol"]:
            pips = int(diff * 10)
        pips_sl = f" (-{pips} pips)"
        
    if trade.get("take_profit") and entry:
        diff = abs(entry - trade["take_profit"])
        pips = int(diff * 100) if "JPY" in trade["symbol"] else int(diff * 10000)
        if "XAU" in trade["symbol"] or "GOLD" in trade["symbol"]:
            pips = int(diff * 10)
        pips_tp = f" (+{pips} pips)"

    sl_val = f"{trade.get('stop_loss'):.2f}" if trade.get('stop_loss') else "Không có"
    tp_val = f"{trade.get('take_profit'):.2f}" if trade.get('take_profit') else "Không có"
    entry_val = f"{entry:.2f}" if entry else "Giá Thị Trường"

    trade_type = trade.get("trade_type", "BUY")
    icon = "🟢" if "BUY" in trade_type else "🔴"

    return (
        f"🤖 **AUTO — LỆNH MỚI TỪ SIGNAL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {icon} **{trade_type} {trade['symbol']}**\n"
        f"💰 Lot: {trade['lot_size']:.2f}\n"
        f"💵 Entry: {entry_val}\n"
        f"🛑 SL: {sl_val}{pips_sl}\n"
        f"🎯 TP: {tp_val}{pips_tp}\n"
        f"📢 Nguồn: Signal Group\n"
        f"⏰ {format_datetime(trade['created_at'])}\n"
        f"🔑 UUID: `{trade['uuid'][:8]}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Đang chờ EA thực thi..."
    )

def format_queue_signal(signal: Dict[str, Any], expire_minutes: int = 15) -> str:
    """Thông báo tín hiệu mới được đưa vào hàng đợi duyệt"""
    sl_val = f"{signal.get('parsed_sl'):.2f}" if signal.get('parsed_sl') else "Không có"
    tp_val = f"{signal.get('parsed_tp'):.2f}" if signal.get('parsed_tp') else "Không có"
    entry_val = f"{signal.get('parsed_price'):.2f}" if signal.get('parsed_price') else "Giá Thị Trường"

    parsed_type = signal.get("parsed_type", "BUY")
    icon = "🟢" if "BUY" in parsed_type else "🔴"

    return (
        f"📋 **TÍN HIỆU MỚI — {signal['queue_id']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {icon} **{parsed_type} {signal['parsed_symbol']}**\n"
        f"💰 Lot: (Theo cấu hình hệ thống)\n"
        f"💵 Entry: {entry_val}\n"
        f"🛑 SL: {sl_val}\n"
        f"🎯 TP: {tp_val}\n"
        f"📢 Nguồn: Signal Group\n"
        f"⏱️ Hết hạn sau: {expire_minutes} phút\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"`/confirm {signal['queue_id']}`\n"
        f"`/confirm {signal['queue_id']} lot=0.05`\n"
        f"`/reject {signal['queue_id']}`\n"
        f"`/confirmall`"
    )

def format_trade_filled(trade: Dict[str, Any]) -> str:
    """Thông báo lệnh đã khớp trên MT5"""
    sl_val = f"{trade.get('stop_loss'):.2f}" if trade.get('stop_loss') else "Không có"
    tp_val = f"{trade.get('take_profit'):.2f}" if trade.get('take_profit') else "Không có"
    
    trade_type = trade.get("trade_type", "BUY")
    icon = "🟢" if "BUY" in trade_type else "🔴"
    
    return (
        f"✅ **LỆNH ĐÃ KHỚP**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {icon} **{trade_type} {trade['symbol']} {trade['lot_size']:.2f}**\n"
        f"💵 Giá vào: {trade['open_price']:.2f}\n"
        f"🛑 SL: {sl_val}\n"
        f"🎯 TP: {tp_val}\n"
        f"🎫 Ticket: `#{trade['ticket']}`\n"
        f"⏰ {format_datetime(trade['opened_at'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def format_trade_closed(trade: Dict[str, Any], today_summary: str = "") -> str:
    """Thông báo lệnh đã đóng kèm P/L"""
    pnl = trade.get("pnl") or 0.0
    indicator = "❇️" if pnl >= 0 else "❌"
    pnl_sign = "+" if pnl > 0 else ""
    
    trade_type = trade.get("trade_type", "BUY")
    type_icon = "🟢" if "BUY" in trade_type else "🔴"
    
    # Tính thời gian giữ lệnh
    duration_str = "N/A"
    if trade.get("opened_at") and trade.get("closed_at"):
        try:
            o_time = datetime.fromisoformat(trade["opened_at"].replace("Z", ""))
            c_time = datetime.fromisoformat(trade["closed_at"].replace("Z", ""))
            diff = c_time - o_time
            hours, remainder = divmod(diff.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m"
        except Exception:
            pass

    return (
        f"❎ **LỆNH ĐÃ ĐÓNG**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {type_icon} **{trade_type} {trade['symbol']} {trade['lot_size']:.2f}**\n"
        f"💵 Vào: {trade['open_price']:.2f} → Ra: {trade['close_price']:.2f}\n"
        f"💰 P/L: **{pnl_sign}${pnl:.2f}** {indicator}\n"
        f"📢 Lý do: {trade.get('close_reason') or 'MANUAL'}\n"
        f"⏱️ Giữ lệnh: {duration_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{today_summary}"
    )

def format_positions_list(positions: List[Dict[str, Any]]) -> str:
    """Danh sách các vị thế đang mở"""
    if not positions:
        return "📋 **KHÔNG CÓ LỆNH ĐANG MỞ**"
        
    lines = [
        f"📋 **LỆNH ĐANG MỞ ({len(positions)} lệnh)**",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    
    total_pnl = 0.0
    for idx, pos in enumerate(positions, 1):
        pnl = pos.get("pnl") or 0.0
        total_pnl += pnl
        pnl_sign = "+" if pnl > 0 else ""
        
        trade_type = pos.get("trade_type", "BUY")
        icon = "🟢" if "BUY" in trade_type else "🔴"
        
        sl_str = f"{pos['stop_loss']:.2f}" if pos.get("stop_loss") else "-"
        tp_str = f"{pos['take_profit']:.2f}" if pos.get("take_profit") else "-"
        
        is_manual = pos.get("is_manual", False)
        type_tag = " ✍️" if is_manual else ""
        
        lines.append(
            f"{idx}. {icon} `#{pos['ticket']}` **{pos['symbol']} {pos['lot_size']:.2f}** @ {pos['open_price']:.2f}{type_tag} | **{pnl_sign}${pnl:.2f}** | SL: {sl_str} | TP: {tp_str}"
        )
        
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    total_sign = "+" if total_pnl > 0 else ""
    lines.append(f"💰 Tổng float P/L: **{total_sign}${total_pnl:.2f}**")
    
    return "\n".join(lines)

def format_balance(account: Dict[str, Any], health: Dict[str, Any]) -> str:
    """Thông tin tài khoản và sức khỏe kết nối EA"""
    ea_status = "Online ✅" if health["ea_online"] else "Offline 🔴"
    ea_ver = f" (v{health['ea_version']})" if health.get("ea_version") else ""
    mt5_status = "Kết nối ✅" if health["mt5_connected"] else "Mất kết nối ❌"
    
    return (
        f"💰 **THÔNG TIN TÀI KHOẢN**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Balance:     `${account['balance']:,.2f}`\n"
        f"📊 Equity:      `${account['equity']:,.2f}`\n"
        f"💳 Margin:      `${account['margin']:,.2f}`\n"
        f"🆓 Free Margin: `${account['free_margin']:,.2f}`\n"
        f"📈 Float P/L:   `{'+' if account['profit'] > 0 else ''}${account['profit']:,.2f}`\n"
        f"🏦 Server:      `{account['server']}`\n"
        f"🔑 Account:     `#{account['account_number']}` ({account['account_name']})\n"
        f"⚙️ Leverage:    `1:{account['leverage']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 EA Bridge:   **{ea_status}**{ea_ver}\n"
        f"📈 MT5 Server:  **{mt5_status}**"
    )

def format_report(summary: Dict[str, Any], trend: Dict[str, Any]) -> str:
    """Báo cáo P/L và phân tích xu hướng"""
    period_title = {
        "day": "NGÀY",
        "week": "TUẦN",
        "month": "THÁNG"
    }.get(summary["period"], "CHU KỲ")
    
    # Tính toán streak text
    streak = summary["current_streak"]
    streak_txt = f"{abs(streak)} thắng liên tiếp" if streak > 0 else (f"{abs(streak)} thua liên tiếp" if streak < 0 else "Không có")
    streak_emoji = "🔥" if streak > 0 else ("❄️" if streak < 0 else "")
    
    # Calculate win_sum and loss_sum from trades list
    trades = summary.get("trades") or []
    win_sum = sum(t.get("pnl") or 0.0 for t in trades if (t.get("pnl") or 0.0) > 0)
    loss_sum = sum(t.get("pnl") or 0.0 for t in trades if (t.get("pnl") or 0.0) < 0)
    
    # Header báo cáo
    lines = [
        f"📊 **BÁO CÁO {period_title}**",
        f"({format_datetime(summary['date_from'])} — {format_datetime(summary['date_to'])})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        f"📋 Tổng lệnh:     {summary['total_trades']}",
        f"❇️ THẮNG:         {summary['winning_trades']} ({summary['win_rate']}%) | +${win_sum:,.2f}",
        f"❌ THUA:          {summary['losing_trades']} ({round(100 - summary['win_rate'], 1) if summary['total_trades'] > 0 else 0.0}%) | -${abs(loss_sum):,.2f}",
        f"🚀 LỢI NHUẬN:     **{'+' if summary['total_pnl'] > 0 else ''}${summary['total_pnl']:,.2f}**\n",
        f"💵 Trung bình:    {'+' if summary['avg_pnl'] > 0 else ''}${summary['avg_pnl']:.2f}/lệnh",
        f"⚖️ Profit Factor: {summary['profit_factor'] if summary['profit_factor'] is not None else 'N/A'}",
        f"📉 Max Drawdown:  ${summary['max_drawdown']:.2f}",
        f"{streak_emoji} Streak:        {streak_txt}\n",
        "📅 **THEO NGÀY**",
        "━━━━━━━━━━━━"
    ]
    
    # Vẽ biểu đồ ASCII theo ngày
    breakdown = summary.get("daily_breakdown", [])
    max_pnl = max([abs(day["pnl"]) for day in breakdown]) if breakdown else 0.0
    
    for day in breakdown:
        pnl = day["pnl"]
        date_obj = datetime.fromisoformat(day["date"])
        # Format "T2 (10/06)"
        weekday_vn = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][date_obj.weekday()]
        date_str = f"{weekday_vn} ({date_obj.strftime('%d/%m')})"
        
        bar = make_bar(pnl, max_pnl, width=10)
        pnl_sign = "+" if pnl > 0 else ""
        lines.append(f"  {date_str}: {pnl_sign}${pnl:.2f}  {bar} {day['wins']}W/{day['losses']}L")
        
    lines.append("\n📈 **XU HƯỚNG**")
    lines.append("━━━━━━━━━━━")
    
    trend_amount = trend["change_amount"]
    trend_pct = trend["change_percent"]
    trend_sign = "+" if trend_amount > 0 else ""
    
    period_label = {
        "day": "Hôm qua",
        "week": "Tuần trước",
        "month": "Tháng trước"
    }.get(summary["period"], "Kỳ trước")
    
    trend_arrow = "🚀" if trend_amount > 0 else ("🔻" if trend_amount < 0 else "➡️")
    lines.append(f"  {period_label}:  ${trend['previous_period_pnl']:.2f}")
    lines.append(f"  Kỳ này:      ${trend['current_period_pnl']:.2f} ({trend_sign}{trend_pct}%) {trend_arrow}")
    
    if summary.get("period") == "day":
        if trades:
            lines.append("\n📜 **CHI TIẾT CÁC LỆNH ĐÃ ĐÓNG**")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            for t in trades:
                pnl = t.get("pnl") or 0.0
                icon = "❇️" if pnl >= 0 else "❌"
                pnl_sign = "+" if pnl > 0 else ""
                ticket_str = f" `#{t['ticket']}`" if t.get("ticket") else ""
                t_type = t.get("trade_type", "BUY")
                type_icon = "🟢" if "BUY" in t_type else "🔴"
                
                lines.append(
                    f"{icon} {type_icon}{ticket_str} **{t['symbol']} {t['lot_size']:.2f}** @ {t['open_price']:.2f} → {t['close_price']:.2f} | **{pnl_sign}${pnl:.2f}**"
                )
    
    return "\n".join(lines)

def format_config(configs: Dict[str, Any]) -> str:
    """Hiển thị cấu hình hiện tại"""
    mode_str = "📋 Queue (Chờ xác nhận)" if configs.get("mode") == "queue" else "🤖 Auto (Tự động đặt lệnh)"
    
    lines = [
        f"⚙️ <b>CẤU HÌNH HIỆN TẠI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔀 Chế độ Mode:  <b>{mode_str}</b>\n"
        f"💰 Lot mặc định: <code>{configs.get('default_lot', '0.01')}</code>\n"
        f"⏱️ Queue expire: <code>{configs.get('queue_expire_minutes', '15')} phút</code>\n"
        f"🛡️ SL buffer:    <code>{configs.get('sl_buffer_pips', '0')} pips</code>\n"
        f"📢 Listen Group: <code>{configs.get('signal_group_id', 'Chưa cấu hình')}</code>\n"
    ]
    
    overrides = configs.get("lot_overrides", {})
    if overrides:
        lines.append("   <b>Ghi đè lot size cho symbol:</b>")
        for sym, lot in overrides.items():
            lines.append(f"    └─ {sym}: <code>{lot:.2f}</code>")
        lines.append("")
            
    lines.append("💡 <b>Hướng dẫn thay đổi cấu hình:</b>")
    lines.append("• Lot mặc định: <code>/config default_lot=0.03</code>")
    lines.append("• Hạn hàng đợi: <code>/config queue_expire_minutes=15</code>")
    lines.append("• Ghi đè lot: <code>/config [CẶP]=[LOT]</code> (VD: <code>/config XAUUSD=0.02</code>)")
    lines.append("• Xoá ghi đè: <code>/config remove [CẶP]</code>")
    lines.append("• Đổi chế độ: <code>/mode auto</code> hoặc <code>/mode queue</code>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def format_gold_price(account: Dict[str, Any], health: Dict[str, Any]) -> str:
    """Định dạng thông tin giá vàng và biến động (HTML)"""
    price = account.get("gold_price") or 0.0
    if price == 0.0:
        return "⚠️ <b>Không có dữ liệu giá vàng.</b> Vui lòng đảm bảo EA đang chạy trên MT5."
        
    change_1h = account.get("gold_change_1h") or 0.0
    change_4h = account.get("gold_change_4h") or 0.0
    change_1d = account.get("gold_change_1d") or 0.0
    
    # Tính toán icon tăng giảm
    def get_trend_details(val: float) -> str:
        if val > 0:
            return f"🟢 +{val:.2f} $"
        elif val < 0:
            return f"🔴 -{abs(val):.2f} $"
        else:
            return f"⚪ 0.00 $"
            
    # Check if EA is online
    ea_status = "Online ✅" if health["ea_online"] else "Offline 🔴 (Giá có thể bị trễ)"
    
    # Tính thời gian cập nhật
    updated_at = account.get("updated_at")
    time_str = "N/A"
    if updated_at:
        try:
            time_str = format_datetime(updated_at)
        except Exception:
            time_str = str(updated_at)
            
    return (
        f"📊 <b>GIÁ VÀNG XAUUSDm</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Giá hiện tại: <b>{price:.2f} $</b>\n"
        f"⏱️ Biến động:\n"
        f"   └─ 1 giờ (H1):  {get_trend_details(change_1h)}\n"
        f"   └─ 4 giờ (H4):  {get_trend_details(change_4h)}\n"
        f"   └─ Trong ngày:  {get_trend_details(change_1d)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Trạng thái EA: <b>{ea_status}</b>\n"
        f"⏰ Cập nhật lúc: <code>{time_str}</code>"
    )
