from nudge.market.narrate import is_safe
from nudge.market.serpapi import Quote

FACTS = (
    "Price: INR 2171.5, +4.60% vs previous close\n"
    "<headlines>\n- Q2 earnings and $9.6B TCV wins (TradingView, 1 hour ago)\n</headlines>"
)


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


def test_rejects_number_not_in_facts():
    assert not is_safe("TCS is at INR 2171.5 after an 11.2% revenue rise.", _quote(), FACTS)


def test_accepts_numbers_found_in_facts():
    text = "TCS is at INR 2,171.50, up 4.6% after Q2 earnings and $9.6B in TCV wins."
    assert is_safe(text, _quote(), FACTS)


def test_digit_check_is_skipped_without_facts():
    assert is_safe("TCS is at INR 2171.5 after an 11.2% revenue rise.", _quote())
