from nudge.market.rules import WatchItem, evaluate, hours_ago
from nudge.market.serpapi import NewsItem, Quote


def _quote(price=100.0, pct=0.0, news=()):
    return Quote("ABC", "NSE", "ABC Ltd", price, "INR", pct, "now", list(news))


def test_hours_ago_parses_units():
    assert hours_ago("16 hours ago") == 16
    assert hours_ago("30 minutes ago") == 0.5
    assert hours_ago("2 days ago") == 48
    assert hours_ago("yesterday") is None


def test_target_below_fires():
    item = WatchItem("ABC", "NSE", "holding", alert_below=105)
    assert "target_below" in [t.code for t in evaluate(item, _quote(price=100))]


def test_quiet_when_nothing_fires():
    assert evaluate(WatchItem("ABC", "NSE"), _quote(pct=0.5)) == []


def test_big_move_down_reports_direction():
    triggers = evaluate(WatchItem("ABC", "NSE"), _quote(pct=-3.1))
    assert [t.code for t in triggers] == ["big_move"]
    assert "down" in triggers[0].detail


def test_stale_news_is_ignored():
    q = _quote(news=[NewsItem("old story", "X", "3 days ago", "")])
    assert evaluate(WatchItem("ABC", "NSE"), q) == []


def test_fresh_news_fires():
    q = _quote(news=[NewsItem("new story", "X", "2 hours ago", "")])
    assert [t.code for t in evaluate(WatchItem("ABC", "NSE"), q)] == ["fresh_news"]
