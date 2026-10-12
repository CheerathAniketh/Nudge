from nudge.market.rules import WatchItem, evaluate, hours_ago
from nudge.market.serpapi import NewsItem, Quote


def _quote(price=100.0, pct=0.0, news=()):
    return Quote("ABC", "NSE", "ABC Ltd", price, "INR", pct, "now", list(news))


def _news(title, when="2 hours ago"):
    return NewsItem(title, "X", when, "")


def _codes(triggers):
    return [t.code for t in triggers]


def test_hours_ago_parses_units():
    assert hours_ago("16 hours ago") == 16
    assert hours_ago("30 minutes ago") == 0.5
    assert hours_ago("2 days ago") == 48
    assert hours_ago("yesterday") is None


def test_target_below_fires():
    item = WatchItem("ABC", "NSE", "holding", alert_below=105)
    assert "target_below" in _codes(evaluate(item, _quote(price=100)))


def test_quiet_when_nothing_fires():
    assert evaluate(WatchItem("ABC", "NSE"), _quote(pct=0.5)) == []


def test_big_move_down_reports_direction():
    triggers = evaluate(WatchItem("ABC", "NSE"), _quote(pct=-3.1))
    assert _codes(triggers) == ["big_move"]
    assert "down" in triggers[0].detail


def test_stale_news_is_ignored():
    q = _quote(news=[_news("Q2 results beat estimates", "3 days ago")])
    assert evaluate(WatchItem("ABC", "NSE"), q) == []


def test_material_news_fires_alone():
    q = _quote(news=[_news("Q2 results beat estimates")])
    assert _codes(evaluate(WatchItem("ABC", "NSE"), q)) == ["fresh_news"]


def test_ordinary_news_alone_stays_quiet():
    q = _quote(news=[_news("Company opens special window for shareholders")])
    assert evaluate(WatchItem("ABC", "NSE"), q) == []


def test_ordinary_news_rides_along_with_a_price_trigger():
    q = _quote(pct=-3.1, news=[_news("Company opens special window for shareholders")])
    assert _codes(evaluate(WatchItem("ABC", "NSE"), q)) == ["big_move", "fresh_news"]


def test_stock_tip_headline_is_not_news():
    q = _quote(news=[_news("TCS, Cipla - Which stock to buy and sell? Q2 results, target, stop loss")])
    assert evaluate(WatchItem("ABC", "NSE"), q) == []
