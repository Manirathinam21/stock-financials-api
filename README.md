# Stock Financials API

A FastAPI backend that extracts **Annual & Quarterly Profit & Loss statements,
Balance Sheet, and Cash Flow statements** for Indian (NSE-listed) stocks.

A standalone service with a React dashboard on top, focused purely on company
fundamentals.

## Data sources

| Statement                | Source                                          | Availability          |
|---------------------------|--------------------------------------------------|------------------------|
| Profit & Loss              | NSE Corporates Financial Results API (XBRL/HTML) | Quarterly & Annual     |
| Balance Sheet              | NSE Integrated Filing API (iXBRL)                | Annual (audited) only  |
| Cash Flow Statement        | NSE Integrated Filing API (iXBRL)                | Annual (audited) only  |

Both sources are scraped directly from NSE's public web APIs (no API key
required), with cookie warmup, header spoofing, rate limiting, and
exponential-backoff retries built in, since NSE blocks naive/unauthenticated
requests.

## Project layout

```
app/
├── main.py                     FastAPI app, lifespan, CORS, error handling
├── config.py                   Settings (pydantic-settings)
├── core/
│   ├── http_session.py         Shared NSE HTTP session, warmup, rate limiting, backoff fetch
│   └── exceptions.py           Custom exceptions
├── services/
│   ├── utils.py                 Number parsing helpers
│   ├── profit_loss.py            Quarterly/Annual P&L (XBRL + legacy HTML parsers)
│   └── annual_financials.py      Balance Sheet / Cash Flow / Annual Report (iXBRL parser)
├── schemas/
│   └── financials.py             Pydantic request/response models
└── api/
    └── routes.py                 Route handlers
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

## API

Every endpoint takes the same three inputs:

- **symbol** (path) — NSE stock symbol, e.g. `RELIANCE`, `TCS`, `HDFCBANK`
- **report_type** (query, optional) —
  - `both` → both consolidated and standalone (default, also when omitted)
  - `consolidated` → consolidated only
  - `standalone` → standalone only
- **period** (query, P&L endpoints only) — `Quarterly` (default), `Annual`, or `Both`

### Combined endpoint (recommended)

```
GET /api/v1/financials/{symbol}?report_type=consolidated&period=Both
```

Always returns Profit & Loss for the requested period. Balance Sheet and
Cash Flow are attached automatically whenever `period` is `Annual` or
`Both` (they don't exist in quarterly filings), and are `null` for
`Quarterly`.

```json
{
  "symbol": "RELIANCE",
  "report_type": "consolidated",
  "period": "Both",
  "profit_and_loss": { "symbol": "RELIANCE", "company_name": "...", "total_filings": 12, "filings": [ ... ] },
  "balance_sheet": { "symbol": "RELIANCE", "total_filings": 2, "filings": [ ... ] },
  "cash_flow": { "symbol": "RELIANCE", "total_filings": 2, "filings": [ ... ] }
}
```

### Granular endpoints

```
GET /api/v1/profit-loss/{symbol}?report_type=both&period=Quarterly
GET /api/v1/balance-sheet/{symbol}?report_type=both
GET /api/v1/cash-flow/{symbol}?report_type=both
GET /api/v1/annual-report/{symbol}?report_type=both      # full filing set: P&L + BS + CF + segments
```

### Examples

```bash
# Quarterly, consolidated P&L for Reliance
curl "http://127.0.0.1:8000/api/v1/profit-loss/RELIANCE?report_type=consolidated&period=Quarterly"

# Annual standalone Balance Sheet for HDFC Bank
curl "http://127.0.0.1:8000/api/v1/balance-sheet/HDFCBANK?report_type=standalone"

# Everything (both consolidated+standalone, both periods) for TCS
curl "http://127.0.0.1:8000/api/v1/financials/TCS?period=Both"
```

## Frontend (React + Vite)

Lives in `frontend/`. Tabs map 1:1 to the API routes (Overview → `/financials`,
P&L, Balance Sheet, Cash Flow, Annual Report); statements render as
line-item × filing tables.

Local dev (two terminals):

```bash
uvicorn app.main:app --reload          # API on :8000
cd frontend && npm install && npm run dev   # UI on :5173 (proxies /api to :8000)
```

## Deploy to Render

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo (uses `render.yaml`),
   or **New → Web Service** → runtime **Docker**, health check path `/health`.
3. The `Dockerfile` builds the React app and FastAPI serves it from `/`, so
   the UI, API (`/api/v1/...`) and Swagger docs (`/docs`) share one URL.

Local Docker test: `docker build -t sf . && docker run -p 8000:8000 sf`

Note: NSE sometimes blocks cloud/datacenter IPs. If Render returns 404s for
valid symbols, check the service logs; the code is fine but NSE is refusing
the host.

## Notes

- NSE rate-limits aggressively; the service warms up and reuses a single
  cookie-authenticated session, rate-limits itself to ~3 req/s, and retries
  with backoff — but a 404 can still mean "NSE returned nothing right now"
  rather than "the symbol has no data." Retry if you get an empty result for
  a symbol you know is listed.
- Field availability varies by company/filing format (banking vs. non-banking
  IndAS, old legacy HTML vs. new XBRL) — statements are returned as flexible
  JSON objects rather than a fixed schema, so some fields will be `null` for
  some filings.
