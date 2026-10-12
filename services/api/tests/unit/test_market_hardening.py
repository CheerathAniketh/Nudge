import pytest

from nudge.market import serpapi
from nudge.market.narrate import is_safe
from nudge.market.serpapi import Quote, SerpApiError, validate_symbol


def _quote(price):
    return Quote("A", "NSE", "A Ltd", price, "INR", 0.0, "now", [])


@pytest.mark.parametrize(
    "sym,exch", [("../../etc/x", "NSE"), ("TCS", "../NSE"), ("TCS/x", "NSE"), ("", "NSE"), ("TCS", "N SE")]
)
def test_rejects_unsafe_symbols(sym, exch):
    with pytest.raises(SerpApiError):
        validate_symbol(sym, exch)


def test_accepts_plain_symbols():
    assert validate_symbol(" tcs ", "nse") == ("TCS", "NSE")
    assert validate_symbol("m&m", "nse") == ("M&M", "NSE")


def test_price_must_be_a_whole_number_not_a_substring():
    assert not is_safe("It trades near 9100 today.", _quote(100.0))


def test_exact_price_still_accepted():
    assert is_safe("It trades at INR 100 today.", _quote(100.0))


def test_rejects_urls_in_model_text():
    assert not is_safe("TCS is at INR 2171.5, details at http://evil.example", _quote(2171.5))


def _fake_raw(percentage, movement="Up"):
    return lambda *a, **k: {
        "summary": {"extracted_price": 10, "price_movement": {"percentage": percentage, "movement": movement}},
        "news_results": [],
    }


def test_bad_percentage_becomes_serpapi_error(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    monkeypatch.setattr(serpapi, "_get_raw", _fake_raw("abc"))
    with pytest.raises(SerpApiError):
        serpapi.fetch_quote("ABC", "NSE")


def test_percent_sign_string_is_tolerated(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    monkeypatch.setattr(serpapi, "_get_raw", _fake_raw("2.5%", "Down"))
    assert serpapi.fetch_quote("ABC", "NSE").change_pct == -2.5
