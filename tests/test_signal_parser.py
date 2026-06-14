import pytest
from bot.parsers.signal_parser import parse_signal, ParsedSignal

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
