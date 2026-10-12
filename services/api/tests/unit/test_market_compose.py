from nudge.market.compose import pick_news
from nudge.market.serpapi import NewsItem, Quote


def test_pick_news_drops_tips_and_puts_material_first():
    q = Quote("A", "NSE", "A Ltd", 1.0, "INR", 0.0, "now", [
        NewsItem("Which stock to buy today? Target, stop loss", "X", "1 hour ago", ""),
        NewsItem("Company opens special window", "X", "2 hours ago", ""),
        NewsItem("Q2 results beat estimates", "X", "3 hours ago", ""),
    ])
    assert [n.title for n in pick_news(q)] == ["Q2 results beat estimates", "Company opens special window"]
