import pytest
from bot.parsers.command_parser import parse_trade_command

def test_parse_buy_command_with_lot_positional():
    text = "/buy XAUUSD 0.01 sl=2340 tp=2370"
    res = parse_trade_command(text)
    assert res["symbol"] == "XAUUSD"
    assert res["lot_size"] == 0.01
    assert res["stop_loss"] == 2340.0
    assert res["take_profit"] == 2370.0
    assert res["price"] is None

def test_parse_sell_command_with_lot_keyword():
    text = "/sell XAUUSD lot=0.05 sl=2360"
    res = parse_trade_command(text)
    assert res["symbol"] == "XAUUSD"
    assert res["lot_size"] == 0.05
    assert res["stop_loss"] == 2360.0
    assert res["take_profit"] is None
    assert res["price"] is None

def test_parse_buylimit_command():
    text = "/buylimit XAUUSD price=2320 sl=2310 tp=2350"
    res = parse_trade_command(text)
    assert res["symbol"] == "XAUUSD"
    assert res["lot_size"] is None
    assert res["price"] == 2320.0
    assert res["stop_loss"] == 2310.0
    assert res["take_profit"] == 2350.0

def test_parse_command_invalid():
    text = "/buy"
    with pytest.raises(ValueError, match="Thiếu symbol"):
        parse_trade_command(text)

def test_parse_command_invalid_float():
    text = "/buy XAUUSD 0.01 sl=abc"
    with pytest.raises(ValueError, match="phải là số thực"):
        parse_trade_command(text)
