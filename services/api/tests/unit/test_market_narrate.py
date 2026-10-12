from nudge.market.narrate import is_safe
from nudge.market.serpapi import Quote


def _quote():
    return Quote("TCS", "NSE", "TCS Ltd", 2171.5, "INR", 4.6, "now", [])


def test_accepts_plain_summary_with_price():
    assert is_safe("TCS is at INR 2,171.50, up 4.6% after earnings news.", _quote())


def test_rejects_missing_price():
    assert not is_safe("TCS jumped sharply today after earnings news.", _quote())


def test_rejects_advice_words():
    assert not is_safe("TCS is at 2171.5, you should buy more.", _quote())


def test_rejects_overlong_text():
    assert not is_safe("2171.5 " + "word " * 80, _quote())


def test_rejects_empty():
    assert not is_safe("", _quote())
