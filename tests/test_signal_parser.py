from bot.parsers.signal_parser import parse_signal

def test_parse_en_inline_gold():
    text = "BUY GOLD 2350.50 SL 2340 TP 2370"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "BUY"
    assert signal.symbol == "GOLD"
    assert signal.price == 2350.50
    assert signal.sl == 2340.0
    assert signal.tp == 2370.0

def test_parse_multiline_gold():
    text = "BUY GOLD\nEntry: 2350\nSL: 2340\nTP: 2370"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "BUY"
    assert signal.symbol == "GOLD"
    assert signal.price == 2350.0
    assert signal.sl == 2340.0
    assert signal.tp == 2370.0

def test_parse_vietnamese_gold():
    text = "Mua vàng giá 2350 cắt lỗ 2340 chốt lời 2370"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "BUY"
    assert signal.symbol == "VÀNG"
    assert signal.price == 2350.0
    assert signal.sl == 2340.0
    assert signal.tp == 2370.0

def test_parse_no_tp_gold():
    text = "BUY GOLD 2350 SL 2340"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "BUY"
    assert signal.symbol == "GOLD"
    assert signal.price == 2350.0
    assert signal.sl == 2340.0
    assert signal.tp is None

def test_parse_sell_stop_gold():
    text = "SELL STOP GOLD 2320 SL 2330 TP 2300"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "SELL_STOP"
    assert signal.symbol == "GOLD"
    assert signal.price == 2320.0
    assert signal.sl == 2330.0
    assert signal.tp == 2300.0

def test_parse_invalid_text():
    text = "Hôm nay thời tiết đẹp quá đi trade vàng thôi"
    signal = parse_signal(text)
    assert signal is None

def test_parse_implicit_gold_multiline():
    text = "Buy 87-85\nSl 77"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "BUY"
    assert signal.symbol == "GOLD"
    assert signal.price == 87.0
    assert signal.sl == 77.0
    assert signal.tp is None

def test_parse_implicit_gold_sell_range():
    text = "Sell 95-97\nSl 05"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "SELL"
    assert signal.symbol == "GOLD"
    assert signal.price == 95.0
    assert signal.sl == 5.0
    assert signal.tp is None

def test_parse_implicit_gold_with_context():
    text = "Vàng xuống 72 được 80 pip lại quay lên\nsell 82-85\nsl 94"
    signal = parse_signal(text)
    assert signal is not None
    assert signal.trade_type == "SELL"
    assert signal.symbol == "GOLD"
    assert signal.price == 82.0
    assert signal.sl == 94.0
    assert signal.tp is None

def test_vietnamese_fillers_and_dao():
    # sell lại 13\nsl 23
    sig1 = parse_signal("sell lại 13\nsl 23")
    assert sig1 is not None
    assert sig1.trade_type == "SELL"
    assert sig1.symbol == "GOLD"
    assert sig1.price == 13.0
    assert sig1.sl == 23.0

    # Đảo sell 99-03\nsl 10
    sig2 = parse_signal("Đảo sell 99-03\nsl 10")
    assert sig2 is not None
    assert sig2.trade_type == "SELL"
    assert sig2.symbol == "GOLD"
    assert sig2.price == 99.0
    assert sig2.sl == 10.0

    # Buy thêm 25-27\nSl 17
    sig3 = parse_signal("Buy thêm 25-27\nSl 17")
    assert sig3 is not None
    assert sig3.trade_type == "BUY"
    assert sig3.symbol == "GOLD"
    assert sig3.price == 25.0
    assert sig3.sl == 17.0

def test_profit_updates():
    # Buy 15 + 50pip
    assert parse_signal("Buy 15 + 50pip") is None
    # Buy 31 lên 34 + 30pip
    assert parse_signal("Buy 31 lên 34 + 30pip") is None
    # Buy 25 lên 27 + 20pip thoát giá xấu
    assert parse_signal("Buy 25 lên 27 + 20pip thoát giá xấu") is None
    # Vàng lên 20\nBuy 15 + 50pip
    assert parse_signal("Vàng lên 20\nBuy 15 + 50pip") is None
    # Có 20pip hủy limit
    assert parse_signal("Có 20pip hủy limit") is None

