# AI Investment Advisor — יועץ השקעות מבוסס בינה מלאכותית

מערכת ייעוץ השקעות אוטומטית: איסוף חדשות פיננסיות בזמן אמת, ניתוח דוחות SEC,
סריקת מניות small-cap, תחזיות שוק והתרעות סיכון — כל הפלט למשתמש בעברית מלאה,
בממשק RTL.

> **מצב נוכחי:** Phase 1 (תשתית) ו-Phase 2 (שירותי אחזור נתונים) מומשו במלואם.
> Phase 3 (סוכני AI) ו-Phase 4 (דשבורד Streamlit) מתוכננים במבנה הפרויקט למטה
> ויתווספו בהמשך.

## עקרונות מובילים (חוצי-פרויקט)

1. **עברית בכל פלט למשתמש** — סיכומים, אזהרות, נימוקים והודעות שגיאה.
2. **RTL** בכל רכיב ה-Frontend (Streamlit, Phase 4).
3. **UTF-8** בכל מקום: קבצים, מסד הנתונים, תגובות ה-API (`ensure_ascii=False`).
4. **טיפול שגיאות עמיד**: כל שירות חיצוני (News/Stocks/SEC) עובד מול ספק
   ראשי וספק גיבוי (fallback), עם retry עם backoff מעריכי, וזיהוי rate-limit
   (429) מול שגיאת שרת (5xx) מול "אין נתונים" (404) — ראו `app/utils/errors.py`.

## Project Structure (Full Architecture)

```
ai-investment-advisor/
├── app/
│   ├── main.py                  # FastAPI entrypoint, CORS, UTF-8 JSON, error handlers
│   ├── core/
│   │   ├── config.py             # pydantic-settings: all API keys / env config
│   │   ├── logging.py            # UTF-8 rotating file + console logging
│   │   └── database.py           # Async SQLAlchemy (SQLite/Postgres) cache tables
│   ├── models/
│   │   └── schemas.py            # Pydantic schemas: NewsArticle, StockQuote, SecFiling...
│   ├── services/                 # === Phase 2: data fetching ===
│   │   ├── news_service.py       # NewsAPI (primary) + Alpha Vantage (fallback)
│   │   ├── stock_service.py      # yfinance (primary) + Polygon.io (fallback)
│   │   └── sec_service.py        # sec-api.io (optional) + free SEC EDGAR (fallback)
│   ├── api/routes/
│   │   ├── news.py               # GET /api/news/financial
│   │   ├── stocks.py             # GET /api/stocks/quote/{ticker}, /history/{ticker}
│   │   └── sec.py                # GET /api/sec/filings/{ticker}, /company-facts/{ticker}
│   ├── agents/                   # === Phase 3 (planned): AI reasoning, Hebrew output ===
│   │   ├── prompts.py             #   Hebrew system prompts (Claude 3.5 Sonnet via LangChain)
│   │   ├── news_sentiment_agent.py#   Market-impact summaries in Hebrew
│   │   ├── report_analyzer_agent.py#  10-K/10-Q fundamental analysis in Hebrew
│   │   ├── smallcap_screener_agent.py# Small-cap/penny-stock growth screener
│   │   └── risk_assessor_agent.py #   Explicit Hebrew risk warnings per company/sector
│   ├── scheduler/                # === Phase 3 (planned): background jobs ===
│   │   └── tasks.py               #   APScheduler/Celery: news polling, daily filing scans
│   └── utils/
│       ├── errors.py              # AdvisorError hierarchy (Hebrew + English messages)
│       └── retry.py               # tenacity-based retry policy for external APIs
├── dashboard/                    # === Phase 4 (planned): Streamlit UI ===
│   └── app.py                     #   RTL + Hebrew dashboard: insights, warnings, reasoning
├── tests/
│   ├── test_stock_service.py
│   ├── test_news_service.py
│   └── test_sec_service.py
├── data/                          # SQLite DB file lives here (gitignored)
├── logs/                          # Rotating UTF-8 log files (gitignored)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Phase 1 — Setup

```bash
cd ai-investment-advisor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ערכו את .env והזינו את מפתחות ה-API הרלוונטיים (ראו טבלה למטה)
```

### API keys (all optional — every provider has a free fallback except NewsAPI)

| Variable | Provider | Required? | Notes |
|---|---|---|---|
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | Recommended | Primary news source |
| `ALPHA_VANTAGE_KEY` | [alphavantage.co](https://www.alphavantage.co) | Recommended | News fallback + sentiment scores |
| `POLYGON_API_KEY` | [polygon.io](https://polygon.io) | Optional | Stock data fallback (yfinance needs no key) |
| `SEC_API_KEY` | [sec-api.io](https://sec-api.io) | Optional | Falls back to free SEC EDGAR APIs automatically |
| `SEC_EDGAR_USER_AGENT` | — | **Required** | SEC mandates a descriptive User-Agent (`AppName email@domain.com`) for all EDGAR calls |
| `ANTHROPIC_API_KEY` | Anthropic | Needed for Phase 3 | Claude 3.5 Sonnet — Hebrew reasoning engine |

## Phase 2 — Run the data API

```bash
uvicorn app.main:app --reload --port 8000
```

- `GET /health` — health check
- `GET /api/news/financial?query=...&page_size=20`
- `GET /api/stocks/quote/{ticker}`
- `GET /api/stocks/history/{ticker}?period=1mo&interval=1d`
- `GET /api/sec/filings/{ticker}?form_type=10-K&limit=5`
- `GET /api/sec/company-facts/{ticker}` — revenue, net income, assets, liabilities, cash, EPS from the latest 10-K

Interactive docs: `http://localhost:8000/docs`.

Every error response (rate limit, provider down, no data, missing config) is
JSON with both an English `error` field (for logs/devs) and a Hebrew
`error_he` field (safe to render directly in the UI), e.g.:

```json
{
  "error": "All providers failed for resource 'מחיר מניה': ...",
  "error_he": "לא ניתן היה לאחזר נתוני 'מחיר מניה' - כל מקורות הנתונים הזמינים נכשלו. אנא נסה שוב בעוד מספר דקות."
}
```

## Phase 3 (planned) — AI reasoning agents

Each agent (`app/agents/*.py`) will wrap a LangChain chain backed by Claude
3.5 Sonnet, with a Hebrew-only system prompt enforcing: fluent professional
financial Hebrew, explicit chain-of-thought justification for every
recommendation/forecast/warning, and structured output the dashboard can
render (headline, summary, risk level, reasoning).

## Phase 4 (planned) — Streamlit dashboard

`dashboard/app.py` will be configured with `st.set_page_config` plus global
RTL CSS injection, Hebrew labels throughout, and panels for: live news
impact feed, price/forecast charts, SEC report analysis, small-cap
screener results, and risk warnings — all consuming the Phase 2 API and
Phase 3 agents.

## Testing

```bash
pytest
```

Service tests mock all outbound HTTP calls (no real API keys/network needed)
and assert both the happy path and the primary→fallback failover behavior.
