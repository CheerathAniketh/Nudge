# Nudge

Calm, rule-based heads-ups for people who watch stocks, built on live SerpApi data.

**Hackathon:** SerpApi India Hackathon 2026. **Track:** Commerce & Market Intelligence (finance).
**Demo video:** (link added at submission)

## What it does

Give Nudge a watchlist (symbol, exchange, holding or watching, optional price levels). For each symbol it:

1. Fetches the live quote and recent news from SerpApi's Google Finance API.
2. Applies deterministic rules: price at or beyond your level, a move of 2 percent or more versus the previous close, or material news from the last 24 hours (results, orders, stake changes, regulator action and similar). Ordinary news only rides along when a price rule has already fired, and stock-tip clickbait ("which stock to buy", "target, stop loss") is dropped everywhere.
3. When a rule fires, asks an LLM to phrase a two-sentence plain-English heads-up from those facts. Code checks the text and falls back to a template if it fails or the provider times out:
   - the exact price must appear,
   - at most 60 words,
   - no advice words (buy, sell, should, recommend and similar),
   - every number in the text must appear in the facts given to the model.
4. Optionally sends the message to Telegram, and returns everything as JSON.

Code decides whether to alert. The LLM only phrases facts the code selected, and it never gives buy or sell advice. Every message ends with "Heads-up only, not buy or sell advice."

## How SerpApi is used

All prices, moves and headlines come from the SerpApi `google_finance` engine (`q=SYMBOL:EXCHANGE`, for example `RELIANCE:NSE`): `summary.extracted_price`, `summary.price_movement` (percentage and direction), `summary.currency` and `news_results`. One search per symbol. Responses are cached on disk for 30 minutes (`NUDGE_CACHE_TTL_S`) to conserve credits. Without SerpApi there is nothing to alert on.

## Run it

Requires Python and [uv](https://docs.astral.sh/uv/).

```bash
cd services/api
uv sync
cp ../../.env.example .env      # then fill in the keys below
uv run uvicorn nudge.market.app:app --port 8010
```

Keys in `.env`:

| Variable | Needed for |
|---|---|
| `SERPAPI_API_KEY` | required (free SerpApi account) |
| `LLM_PROVIDER`, `LLM_API_KEY` (and optionally `LLM_MODEL_*`) | LLM-written summaries; without them Nudge uses the template text |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram delivery; create a bot with @BotFather, press Start on it, then read your chat id from the `getUpdates` endpoint |

Try it (interactive docs are at `http://localhost:8010/docs`):

```bash
curl -s -X POST localhost:8010/v1/check -H 'Content-Type: application/json' -d '{
  "watchlist": [
    {"symbol": "TCS", "exchange": "NSE", "kind": "watching"},
    {"symbol": "RELIANCE", "exchange": "NSE", "kind": "holding", "alert_below": 1180}
  ],
  "use_llm": true, "send_telegram": false, "always": false
}' | python3 -m json.tool
```

Request fields: `watchlist` (1 to 10 items), `min_move_pct` (default 2.0), `use_llm`, `send_telegram`, `always` (report every symbol even when no rule fired) and `refresh` (bypass the cache and spend SerpApi credits).

Example result entry (prices are the last close when markets are shut):

```json
{
  "symbol": "RELIANCE", "price": 1157.5, "currency": "INR", "change_pct": -1.09,
  "status": "nudge",
  "triggers": [{"code": "target_below", "detail": "price 1157.5 is at or below your 1180 level"}],
  "llm_used": true, "telegram_sent": false
}
```

Tests (18): `cd services/api && uv run pytest tests/unit/test_market_rules.py tests/unit/test_market_narrate.py tests/unit/test_market_compose.py -q`

## Built before the hackathon, and built for it

| Existed before | Built for this hackathon |
|---|---|
| Supabase schema with row-level security, API foundation (config, logging, error handling, models, database client, repositories), a provider-agnostic LLM client | The whole `services/api/src/nudge/market/` package: SerpApi client with caching, alert rules, LLM summary with output checks, Telegram sender, the `/v1/check` API, sample watchlist, and 18 unit tests |

The agent graph, web app and background worker directories come from the project's planned design and are not part of this submission.

## Limitations

- Runs on demand. There is no scheduler yet, and the watchlist comes from the request, not from the database.
- "Material news" and "stock tip" detection are keyword heuristics and will misclassify some headlines.
- The LLM check verifies the price, length, advice words and numbers, not every factual claim. A summary can still mention a loosely related headline or word things imprecisely.
- No authentication or rate limiting on the API; it is meant for local use.
- Data is Google Finance via SerpApi, last close outside market hours. Only Indian NSE large caps were tested.
- Free SerpApi tier is 250 searches per month; the cache keeps reruns cheap.
