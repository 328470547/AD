# AI Investment Advisor — יועץ השקעות מבוסס בינה מלאכותית

מערכת ייעוץ השקעות אוטומטית: איסוף חדשות פיננסיות בזמן אמת, ניתוח דוחות SEC,
סריקת מניות small-cap, תחזיות שוק והתרעות סיכון — כל הפלט למשתמש בעברית מלאה,
בממשק RTL.

> **מצב נוכחי:** כל 4 השלבים מומשו, בתוספת תזמון רקע אוטומטי: תשתית
> (Phase 1), שירותי אחזור נתונים (Phase 2), סוכני AI מבוססי Claude בעברית
> (Phase 3), דשבורד Streamlit RTL בסגנון חדר בקרה (Phase 4), ותזמון משימות
> רקע (`app/scheduler/`) שמריץ את סוכני ה-AI על בסיס קבוע ושומר את
> התוצאות - הדשבורד קורא נתונים שחושבו מראש במקום להריץ קריאות API/LLM
> כבדות בכל טעינת עמוד.

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
│   │   ├── sec.py                # GET /api/sec/filings/{ticker}, /company-facts/{ticker}
│   │   ├── analysis.py           # GET /api/dashboard/snapshot, /api/analysis/*
│   │   └── scheduler.py          # GET /api/scheduler/status - background job monitoring
│   ├── agents/                   # === Phase 3: AI reasoning, Hebrew output ===
│   │   ├── llm.py                 #   LLM client factory - Gemini (default, free) or Claude, by config
│   │   ├── prompts.py             #   Hebrew-only system prompts, one per agent
│   │   ├── schemas.py             #   Structured Hebrew output schemas (with_structured_output)
│   │   ├── news_sentiment_agent.py#   Market-impact summaries + sentiment, in Hebrew
│   │   ├── report_analyzer_agent.py#  10-K/10-Q fundamental analysis, in Hebrew
│   │   ├── risk_assessor_agent.py #   Explicit Hebrew risk warnings, red-flag detection
│   │   ├── smallcap_screener_agent.py# Small-cap/penny-stock growth screener
│   │   └── orchestrator.py        #   Shared fetch_*/build_* building blocks + live snapshot compute
│   ├── scheduler/                # === background jobs (in-process APScheduler) ===
│   │   ├── scheduler.py           #   AsyncIOScheduler start/shutdown, wired into FastAPI's lifespan
│   │   ├── jobs.py                #   news_polling_job (15-30 min), daily_report_scan_job (once/day)
│   │   ├── store.py               #   Persists last-known-good sections, job run history, seen filings
│   │   └── schemas.py             #   API-facing scheduler status schemas
│   └── utils/
│       ├── errors.py              # AdvisorError hierarchy (Hebrew + English messages)
│       └── retry.py               # tenacity-based retry policy for external APIs
├── dashboard/                    # === Phase 4: Streamlit UI ===
│   ├── app.py                     #   Control-room dashboard: RTL, Hebrew, alerts/news/reports/small-cap
│   ├── api_client.py              #   Cached, error-safe HTTP client for the FastAPI backend
│   └── styles.py                  #   Custom CSS: RTL forcing + dark control-room theme
├── .streamlit/config.toml        # Dark theme base (matches the control-room palette)
├── tests/
│   ├── test_stock_service.py
│   ├── test_news_service.py
│   ├── test_sec_service.py
│   ├── test_news_sentiment_agent.py
│   ├── test_risk_assessor_agent.py
│   ├── test_report_analyzer_agent.py
│   ├── test_smallcap_screener_agent.py
│   ├── test_orchestrator.py
│   ├── test_scheduler_store.py    #   Persistence round-trips, upsert-not-duplicate, new-filing detection
│   ├── test_scheduler_jobs.py     #   Job success/failure logging, partial-failure handling
│   ├── test_scheduler_scheduler.py#   Regression test for the next_run_time=None "paused" pitfall
│   ├── test_analysis_routes.py    #   Snapshot endpoint's cache-vs-live branching
│   ├── test_dashboard_smoke.py    #   Streamlit AppTest: renders the dashboard headlessly
│   └── conftest.py                #   Isolated temp-file test DB; scheduler disabled during tests
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
| `GOOGLE_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | **Required** (default provider) | Gemini — free tier, no billing/subscription needed. Powers all 4 agents + the scheduler. Without it, background jobs still run on schedule and log clearly-labeled failures (`GET /api/scheduler/status`), they just have nothing to save. |
| `ANTHROPIC_API_KEY` | Anthropic | Only if `LLM_PROVIDER=anthropic` | Optional paid alternative to Gemini (Claude, no free tier) — see below |

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

## Phase 3 — AI reasoning agents

Each agent (`app/agents/*.py`) wraps an LLM via LangChain's `with_structured_output`
(returns a validated Pydantic object instead of free-form text). The
provider is a config switch (`app/agents/llm.py`, `LLM_PROVIDER` in `.env`):

- **`google`** (default) — Gemini via `langchain-google-genai`. Free tier,
  no billing required: get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
  *(Note: a paid Gemini/Google One subscription does not itself grant free
  API access — the API's free tier is separate and automatic for any key,
  subscription or not.)*
- **`anthropic`** — Claude via `langchain-anthropic`, if you'd rather pay
  for it (no free tier on the Anthropic API).

Nothing in the agent code depends on which provider is active — both
implement the same LangChain `with_structured_output` interface, so
swapping is a `.env` change, not a code change. Every system prompt
(`app/agents/prompts.py`) enforces: fluent professional financial Hebrew
only, reasoning strictly from the data provided (no hallucinated figures),
an explicit `reasoning_he` chain-of-thought field on every output, and
language making clear this is analysis, not licensed investment advice.

| Agent | Product requirement | Output |
|---|---|---|
| `news_sentiment_agent.py` | News aggregation + market sentiment/forecast | Sentiment, headline, impact summary, key drivers, affected sectors |
| `risk_assessor_agent.py` | Risk management & warnings | Risk level, `is_flagged`, warning headline/detail, concrete red flags |
| `report_analyzer_agent.py` | Daily SEC report analysis | Financial health, summary, key-metrics commentary, cautious recommendation |
| `smallcap_screener_agent.py` | Small-cap/penny-stock screener | Ranked opportunities with growth thesis, risks, 1-10 score |

`orchestrator.py` ties Phase 2 services + all four agents into one
`DashboardSnapshot` (`GET /api/dashboard/snapshot`) - the single call the
Streamlit dashboard needs. Each of the four sections is fetched
independently with `asyncio.gather`; a failure in one (missing API key,
provider outage, no data for the watchlist) degrades that section
gracefully with a Hebrew `*_error_he` message instead of breaking the
whole page. Per-ticker endpoints are also exposed for on-demand lookups:
`GET /api/analysis/risk/{ticker}`, `GET /api/analysis/report/{ticker}`,
`GET /api/analysis/news-sentiment`.

Agent calls are bounded per snapshot (`MAX_RISK_ASSESSMENTS`,
`MAX_COMPANY_REPORTS` in `orchestrator.py`) to keep latency/cost sane on a
dashboard auto-refresh; the demo watchlist and small-cap market-cap
threshold are configurable via `WATCHLIST_TICKERS` / `SMALLCAP_MARKET_CAP_USD`.

## Background scheduler — continuous news polling + daily SEC scans

`app/scheduler/` runs two jobs in-process via APScheduler's `AsyncIOScheduler`
(started/stopped from `app/main.py`'s FastAPI lifespan - no separate worker
process or broker like Redis/Celery needed for a single-process deployment):

| Job | Cadence | What it does |
|---|---|---|
| `news_polling_job` | Every `NEWS_POLLING_INTERVAL_MINUTES` (default 20, product spec: 15-30 min) | Fetches breaking financial news and refreshes the Hebrew market-sentiment analysis |
| `daily_report_scan_job` | Once a day at `DAILY_SCAN_HOUR_UTC:DAILY_SCAN_MINUTE_UTC` (default 07:00 UTC) | Scans the watchlist's 10-K/10-Q filings for genuinely *new* ones (tracked in a `SeenFiling` table, not just re-fetched blindly), then refreshes risk alerts, company report analyses, and the small-cap screener - all fundamentals-driven, so a daily cadence matches how often the underlying data actually changes |

Both jobs also get an immediate first run on a fresh database, so the
dashboard isn't empty while waiting for the first scheduled tick.

**Persistence, not just live compute.** Every successful job run is saved
to a DB table (`AgentSnapshotSection`) as the "last-known-good" result for
that section. `GET /api/dashboard/snapshot` reads from there by default -
a fast DB read, not a live API/LLM call triggered by loading the page. A
failed run does *not* wipe the previous good result (the dashboard keeps
serving it, visibly stale via its `*_updated_at` timestamp) - only the job's
own success/failure is recorded separately, so a transient provider outage
never blanks the UI. An explicit `?tickers=` override on the snapshot
endpoint (used by the dashboard's watchlist text box) still falls back to
a live compute, since the scheduler only maintains data for the server's
configured watchlist.

**Robust, timestamped logging.** Every job run logs `[JOB START]` /
`[JOB SUCCESS]` / `[JOB FAILURE]` through the app's normal UTF-8 logger
(timestamped by `app/core/logging.py`'s format), including duration and a
Hebrew summary; individual API failures within a job (e.g. one ticker's
quote fetch failing) log separately at their own level. Every run is also
recorded to a `JobRunLog` DB table, queryable via **`GET
/api/scheduler/status`** (next run time per job, per-section data
freshness, recent run history) - this is what the dashboard's sidebar
"🩺 בריאות משימות רקע" panel renders, so job health is visible in the UI
without grepping log files.

Config: `SCHEDULER_ENABLED` (set `false` to disable entirely, e.g. for a
one-off script that imports the app), `NEWS_POLLING_INTERVAL_MINUTES`,
`DAILY_SCAN_HOUR_UTC`, `DAILY_SCAN_MINUTE_UTC`.

> **Known limitation for a single-process deployment:** APScheduler's
> in-memory job store means job *definitions* are re-registered fresh on
> every process restart (cheap and intentional - not designed to survive
> restarts as a durable queue). If this ever needs multiple worker
> processes/machines sharing a job queue, Celery+Redis would be the right
> upgrade; not needed for the current single-process architecture.

## Phase 4 — Streamlit dashboard (control room, RTL, Hebrew)

```bash
# in one terminal:
uvicorn app.main:app --reload --port 8000
# in another terminal:
streamlit run dashboard/app.py
```

By default the dashboard talks to `http://localhost:8000`; override with
`API_BASE_URL=http://your-backend:8000 streamlit run dashboard/app.py`.

Layout, top to bottom:

1. **Header + status KPI row** - server connection LED, watchlist size,
   alert/opportunity/report counts, last-updated time, and the data
   **source** for this load (🗄️ background job vs. ⚡ live compute).
2. **🚨 התרעות וסיכונים (Risk Alerts)** - always the first content zone.
   Every flagged/high-risk name is rendered as a red `st.error` card with
   its Hebrew warning, concrete red flags, and an expandable chain-of-thought;
   a small Plotly bar chart summarizes the risk-level distribution across
   the watchlist. If risk assessment fails outright (e.g. no Claude API
   key), that is surfaced as a warning - it never silently renders as "no
   risk found".
3. **Three-column main content**: 📰 news + sentiment, 📄 SEC report
   analysis / financial health, 🌱 small-cap opportunities (green
   `st.success` cards with an opportunity-score progress bar). Each zone
   shows a relative-time freshness caption (e.g. "עודכן לפני 4 דקות") from
   the section's last successful background-job run.
4. **🔍 On-demand ticker deep-dive** - type any ticker to run the risk +
   report agents live against it (the one part of the dashboard that's
   always a live call, by design - it's not part of the watchlist the
   scheduler maintains).

The sidebar also has a **🩺 בריאות משימות רקע** panel (background job
health): each job's next scheduled run and a log of recent runs with
success/failure status and Hebrew summaries, reading `GET
/api/scheduler/status`.

RTL/Hebrew is enforced via injected CSS (`dashboard/styles.py`) targeting
Streamlit's own component `data-testid` attributes (sidebar, metrics,
dataframes, alerts, inputs) plus a Hebrew webfont (Assistant). The one
deliberate exception is the Plotly chart container, which is kept
LTR-internal (see the comment in `styles.py`) - forcing `direction: rtl`
on Plotly's own SVG clips its axis labels; the chart's RTL-appropriate
layout (title alignment, Hebrew tick labels, colors) is instead set
per-figure in `app.py`. The dark "control room" palette
(`.streamlit/config.toml` + `styles.py`) matches the rest of this
account's Hebrew tech content.

Every response the dashboard renders is `error_he`/Hebrew end-to-end, and
every network call to the backend goes through `dashboard/api_client.py`,
which turns connection errors, timeouts, and backend error payloads into a
single `BackendError` with a Hebrew message safe to show directly.

## Testing

```bash
pytest
```

- Service tests (`test_*_service.py`) mock all outbound HTTP calls and
  assert both the happy path and primary→fallback failover behavior.
- Agent tests (`test_*_agent.py`) mock the Claude client itself (no API
  key/network needed) and assert correct prompting/error-wrapping.
- `test_orchestrator.py` is a regression test for a real bug found during
  manual QA: if every risk assessment in a batch fails, the section must
  raise/report an error rather than silently looking like "no risk
  detected".
- `test_scheduler_store.py` / `test_scheduler_jobs.py` cover the
  persistence round-trip (including upsert-not-duplicate and new-filing
  detection) and job success/partial-failure/total-failure logging - e.g.
  a failed job run must never wipe a section's previous good result.
- `test_scheduler_scheduler.py` is a regression test for an APScheduler
  pitfall caught during development: `add_job(next_run_time=None)` means
  "add the job as paused", not "use the trigger's own schedule" - a naive
  bootstrap-on-empty-database implementation could accidentally pass that
  for every non-bootstrapped job and permanently pause it.
- `test_analysis_routes.py` covers the snapshot endpoint's cache-vs-live
  branching (default read from the store, live compute for an explicit
  ticker override or a not-yet-populated store).
- `tests/conftest.py` points `DATABASE_URL` at an isolated temp-file
  SQLite DB and disables the scheduler for the whole test session, so
  tests never share state with (or write to) the real dev database and
  never trigger a real background job on a timer.
- `test_dashboard_smoke.py` uses Streamlit's own `AppTest` harness to run
  `dashboard/app.py` headlessly end-to-end (happy path, backend offline,
  partial section failures) with the backend mocked, and asserts the
  script never raises. This caught two real bugs during development: a
  `sys.path` import error when launched via `streamlit run`, and the
  silent-risk-section bug above.
