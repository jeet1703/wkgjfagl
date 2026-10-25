# Windcast Desk

A pilot web app for a UK energy utility's **day-ahead power purchasing team**. It answers two questions for every delivery day of January 2026:

1. **What did the latest wind forecast say at the moment we had to buy?**
2. **How wrong are those forecasts, in MW, so we can size our buffer?**

Data: national GB wind from Elexon BMRS only. Actuals come from [FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) (`fuelType = WIND`) and forecasts from [WINDFOR](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream). Curtailment comes from accepted bid volumes on wind units, and prices from the system price and the APX market index (MID).

**Live app:** `<add Render URL here>`  ·  **Video walkthrough:** `<add unlisted YouTube URL here>`

## Findings in brief (January 2026, forecast at D-1 09:00)

1. **The forecast runs about 1.7 GW high against delivered wind, and 91% of that is curtailment.** On average, 1.6 GW of wind was paid to switch off by the grid operator. Against *available* wind (delivered + switched off), the bias is only +163 MW and the typical error halves (MAE 2,023 → 1,178 MW). Plan on forecast minus expected curtailment.
2. **It costs real money.** Buying against the raw forecast meant about £3.0m of net imbalance cost in January (at national scale; scale by your share). Buying against a bias-corrected *plan figure* would have cost about £1.5m.
3. **An honest buffer, tested without hindsight.** Each day's "firm" figure (forecast − P90 shortfall) was sized only from the 14 days already settled at the decision. Out of sample, it held in **87%** of hours against a 90% target, and the plan figure cut MAE from 2,023 to 1,494 MW.

Against available wind, error grows steadily with lead time: from 805 MW one hour ahead to 1,582 MW 48 hours ahead.

---

## Quick start

### Docker (recommended)

```bash
docker compose up --build
# → http://localhost:8000
```

On first start, if `backend/data/` has no snapshot, the backend downloads January-2026 data from Elexon. This takes about a minute and is cached afterwards.

### Local dev (hot reload)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m scripts.fetch_data          # one-off: download the Elexon snapshot into backend/data/
uvicorn app.main:app --reload         # http://localhost:8000/api/meta, interactive docs at /docs

# frontend (second terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173 (proxies /api → :8000)
```

### Tests and lint

```bash
cd backend && pytest -q && ruff check . && ruff format --check .
cd frontend && npm run build          # includes TypeScript type-check
```

CI (`.github/workflows/ci.yml`) runs the same commands plus a Docker build on every push.

---

## The key domain rule

A day-ahead purchase for delivery day **D** is made on **D-1**, before the auctions close mid-morning. So, for every target half-hour, the app uses:

> **the forecast with the latest `publishTime` that is ≤ the decision cutoff**, where cutoff = D-1 at a chosen UK local time (default **09:00**, adjustable in the UI).

Forecasts published after the cutoff are never used for the decision view. They appear only in the "How the forecast evolved" chart, greyed out, to show how much the picture still moved.

Scope: decisions on 1–31 Jan 2026 → delivery days **2 Jan – 1 Feb 2026**.

Implementation: `pandas.merge_asof(..., by="start_time", left_on="cutoff", right_on="publish_time", direction="backward")` in `backend/app/domain/selection.py`.

A second policy, **fixed lead time H** (cutoff = target − H hours), powers the "error grows with lead time" analysis.

### Metrics (`backend/app/domain/metrics.py`)

Error is defined as **forecast − actual**:

- **Positive error = wind shortfall.** Less wind arrived than forecast, so the team must buy more.
- **Negative error = surplus.** More wind arrived than forecast.

| Metric | Why it is there |
|---|---|
| MAE, RMSE, normalised MAE (% of mean output) | Headline accuracy |
| Bias (mean error) | Do forecasts systematically run high or low? |
| P50 / P90 / P99 / max absolute error | Size of typical and tail misses |
| **Shortfall P90 / P95** | The buffer needed to cover wind under-delivery in 90% / 95% of periods (drives the "firm wind" figure) |
| Surplus P90 | How far wind can beat the forecast (over-buying risk) |
| R² | Forecast–actual agreement |
| Breakdowns: by day, by hour of day, error histogram, by lead time | Where and when to trust the forecast |

MAPE is deliberately not used. Wind output can be near zero, which makes percentage errors explode.

### Curtailment: delivered vs available wind (`backend/app/domain/curtailment.py`)

FUELHH meters what wind farms delivered *after* the grid operator paid some of them to reduce output (accepted bids, mostly to relieve transmission constraints). WINDFOR forecasts what they could generate. Curtailed MW per half-hour is the sum of accepted bid volumes on all units registered as `WIND` (Elexon indicative volumes, MWh × 2).

Every endpoint takes `basis=metered|available`. `available` = metered + curtailed. The UI toggle is labelled *Wind delivered* / *Wind available*. Metered is the default, because it is what the buyer receives.

### Planning figures without hindsight (`backend/app/domain/planning.py`)

For delivery day D, stats come only from delivery days **D-15..D-2**. All of them are fully settled by the D-1 cutoff. December 2025 is fetched as history so that early-January days have a full window.

- **Plan** = forecast − rolling bias: the best single estimate.
- **Firm** = forecast − rolling P90 shortfall: wind you can count on 9 times out of 10.

The backtest scores both out of sample across January (firm coverage, MAE of plan vs raw forecast). An earlier version sized the band from the whole month's errors and scored it on the same month, which flatters it.

### AI desk note: Gemini (`backend/app/ai.py`)

On the day-ahead view, **AI desk note** asks Google Gemini for a three-bullet trading note:

- **Before decision:** what to plan on and what buffer to hold.
- **After delivery:** how the day went and why.

Guardrails:

- **Gemini never does the maths.** It only rewords figures this app has already computed (`ai_context` in `api.py`), and it is instructed to use no other numbers. The UI shows the exact facts sent ("Facts given to the AI").
- **No hindsight.** The before-decision note gets only what was known at the cutoff. Actuals, curtailment and later forecast runs go only to the after-delivery review. `test_ai_brief_never_sees_the_outcome` enforces this.
- **The key stays on the server.** It is sent in the `x-goog-api-key` header, never in a URL or to the browser. Without a key, the endpoint returns 503 and the UI shows a hint instead.
- **Cheap.** A note is written only when the user clicks. Identical requests are cached, and the response is constrained to a JSON schema.

To enable it, get a key from Google AI Studio, then:

```bash
export GEMINI_API_KEY=...          # Windows PowerShell: $env:GEMINI_API_KEY="..."
docker compose up --build          # compose passes it through; on Render, set it when prompted
```

`GEMINI_MODEL` defaults to `gemini-2.5-flash`.

### Cost of error (`backend/app/domain/cost.py`)

Per half-hour: `cost = (forecast − actual) MW × 0.5 h × (imbalance price − market price)`. A shortfall is bought at imbalance instead of ahead; a surplus is sold at imbalance after paying market price for it. The imbalance price is the single GB system price. The market price is the APX market index (MID), used as a proxy for buying ahead. The hourly forecast is interpolated to half-hours within each delivery day.

If WINDFOR targets are coarser than FUELHH's half-hours (for example hourly), metrics are computed on the forecast's own time grid. Coverage is reported against that grid.

---

## Architecture

```
React (Vite + TypeScript + Recharts)
        │  GET /api/meta · /api/day · /api/accuracy · /api/horizons   (JSON)
FastAPI (Python 3.12)
  ├─ api.py              HTTP layer: validation, response shaping, lru_cache per cutoff
  ├─ domain/selection.py forecast-selection rule (pure, unit-tested)
  ├─ domain/metrics.py   accuracy metrics (pure, unit-tested)
  ├─ domain/planning.py  rolling plan/firm figures (D-15..D-2) + out-of-sample backtest
  ├─ domain/curtailment.py  delivered vs available wind, bias explained by curtailment
  ├─ domain/cost.py      £ cost of error at imbalance vs market price
  ├─ ai.py               Gemini desk notes (grounded in computed figures, no hindsight)
  ├─ store.py            CSV snapshot in backend/data/, fetched once from Elexon
  └─ elexon.py           BMRS /stream client: day-sized windows, retries, de-duplication
```

**Design decisions**

- **Snapshot, not live calls.** January 2026 is historical, so the data is fetched once and served from memory. The demo never depends on Elexon's uptime or rate limits.
- **One container.** FastAPI serves the built React app and the API. This gives a single deploy on Heroku or Render and avoids CORS in production.
- **Pure domain layer.** All business logic is free of I/O, which makes it easy to review and test.
- **Times.** Stored and processed in UTC; displayed and grouped in Europe/London (the market clock). The cutoff is converted from UK local time to UTC, so BST is handled correctly.

---

## Repository layout

```
.
├── Dockerfile                 multi-stage: build React → Python runtime serving both
├── docker-compose.yml         local production-like run
├── render.yaml                Render Blueprint (free plan, health check)
├── heroku.yml                 Heroku container deploy
├── .github/workflows/ci.yml   lint, tests, frontend build, docker build
├── docs/VIDEO_SCRIPT.md       talking points for the 2-part demo video
├── backend/
│   ├── app/
│   │   ├── config.py          scope (Jan-2026 windows), default cutoff, horizons, paths
│   │   ├── elexon.py          BMRS client: FUELHH, WINDFOR, wind bid volumes, prices
│   │   ├── keepalive.py       Render free-plan self-ping
│   │   ├── store.py           snapshot fetch/load (CSV) + in-memory cache
│   │   ├── api.py             REST endpoints
│   │   ├── main.py            app factory, static SPA serving, startup warm-up
│   │   └── domain/
│   │       ├── selection.py   "latest forecast before cutoff" rule
│   │       ├── metrics.py     MAE/RMSE/bias/percentiles/breakdowns
│   │       ├── planning.py    rolling plan/firm figures, backtest
│   │       ├── curtailment.py delivered vs available wind
│   │       └── cost.py        £ cost of forecast error
│   ├── scripts/fetch_data.py  refresh the Elexon snapshot
│   ├── data/                  CSV snapshot: actuals, forecasts, curtailment, prices (Dec 2025 history + Jan 2026)
│   ├── tests/                 pytest: selection rule, metrics, planning, cost, curtailment, keep-alive, API
│   │   └── synthetic.py       synthetic data generator, used by the API tests only
│   └── requirements*.txt, pyproject.toml (pytest + ruff config)
└── frontend/
    ├── src/
    │   ├── App.tsx            layout, tabs, delivery-day & cutoff controls
    │   ├── api.ts             typed API client
    │   ├── format.ts          UK-time and number formatting
    │   ├── hooks.ts           useAsync
    │   └── components/
    │       ├── DayAheadView.tsx   decision banner, KPIs, forecast vs actual + band, forecast vintages
    │       ├── AccuracyView.tsx   KPIs, lead-time curve, daily/hourly error, histogram
    │       ├── Stat.tsx           stat card / panel primitives
    │       └── chartTheme.ts      shared chart palette
    ├── vercel.json            optional: frontend-only deploy to Vercel
    └── vite.config.ts         dev proxy to the backend
```

---

## Deployment

**Heroku (single container)**

```bash
cd backend && python -m scripts.fetch_data && cd ..   # commit the snapshot so the dyno starts instantly
git add backend/data && git commit -m "data snapshot"
heroku create <app> && heroku stack:set container
git push heroku main
```

**Render (free plan):** choose New → Blueprint and pick this repo. `render.yaml` sets up a Docker web service with `healthCheckPath: /api/health`; `$PORT` is honoured.

The free plan puts the service to sleep after 15 minutes without traffic, and waking it again takes about a minute. To avoid that, `backend/app/keepalive.py` pings the app's own `/api/health` 1 minute after start-up, then every 14 minutes. It reads the public URL from `RENDER_EXTERNAL_URL`, which Render sets automatically; set `KEEP_ALIVE_URL` to override it. When neither is set (local or Docker runs), it does nothing. A failed ping only logs a warning. Render's health check restarts a service that stops answering, but it doesn't keep it awake: that's the self-ping's job. On a paid plan, delete `keepalive.py` and its call in `main.py`, and keep the health check.

**Vercel (frontend) + Heroku/Render (API):**

1. Import `frontend/` into Vercel.
2. Set the `VITE_API_URL=https://<your-api-host>` environment variable.
3. Set `CORS_ORIGINS=https://<your-vercel-domain>` on the API.

---

## Limitations and next steps

- Curtailment uses Elexon's *indicative* bid volumes. Settled volumes can differ slightly.
- MID is a proxy for the ahead price, not the day-ahead auction clearing price. The cost model is linear and at national scale.
- The firm figure under-covered slightly (87% vs a 90% target): curtailment swings from day to day. Forecasting curtailment is the obvious next model.
- One month of data, and national wind only, as scoped. Natural next steps:
  - forecast curtailment directly (it is the dominant error term);
  - add solar and demand data to show the residual volume to buy directly;
  - add price data to value the cost of forecast error;
  - add a daily alert when the forecast at cutoff disagrees strongly with earlier runs.

## Use of AI tools

This project was built with the help of an AI assistant (Claude, by Anthropic). It was used for scaffolding, code generation, test writing and documentation. All domain decisions (cutoff rule, error sign convention, metric choice) and the code were reviewed by me.
