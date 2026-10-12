from types import SimpleNamespace as NS

from nudge.market.compose import compose_short


def _quote():
    news = [NS(title="TCS hires will need AI skills", source="Livemint", when="2 hours ago", link="https://x.test/a")]
    return NS(currency="INR", price=2125.0, change_pct=-1.44, news=news)


ITEM = NS(symbol="TCS", kind="watching")


def test_short_message_is_compact_and_has_link():
    text = compose_short(
        ITEM, _quote(), [], "TCS is at INR 2125, down 1.44%. News says AI skills are now expected for new hires."
    )
    assert len(text) < 400
    assert "https://x.test/a" in text
    assert "- " not in text
    assert "AI skills are now expected" in text


def test_short_message_falls_back_to_trigger_text():
    text = compose_short(ITEM, _quote(), [NS(detail="down 1.44% vs previous close")], None)
    assert "down 1.44% vs previous close" in text
