# Shmape eVTOL Index

A transparent public-equity index and canonical company database for the eVTOL sector.

Live route: `https://cloud.tomgiro.com/Shmape-Homepage/evtol-index`

## What it does

- Tracks active and historical public companies with material passenger, cargo, or enabling-platform eVTOL exposure.
- Calculates a quarterly reviewed, free-float-adjusted market-cap basket with a 25% constituent cap.
- Compares the index and every eligible constituent with NASDAQ Composite (`^IXIC`) and NASDAQ-100 (`QQQ`).
- Shows normalized performance, cross-sectional z-scores, population standard deviation, and rolling annualized volatility.
- Serves 15-minute delayed intraday views and adjusted daily history.
- Preserves delisted/former constituents to reduce survivorship bias.
- Exposes a versioned, read-only company-universe API for all Shmape products.
- Runs a daily SEC filing discovery scan and a 15-minute market-data refresh.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
EVTOL_INDEX_DATABASE_PATH=./var/index.db .venv/bin/python -m app.worker refresh
EVTOL_INDEX_DATABASE_PATH=./var/index.db .venv/bin/uvicorn app.main:app --port 8000
```

Open `http://127.0.0.1:8000/`.

## Tests

```bash
.venv/bin/pytest -q
```

## Public API

- `GET /api/v1/health`
- `GET /api/v1/companies`
- `GET /api/v1/snapshot?range=1M`
- `GET /api/v1/series?range=YTD`
- `GET /api/v1/methodology`

Supported ranges: `1D`, `1W`, `1M`, `3M`, `YTD`, `1Y`, `MAX`.

The canonical company payload identifies itself with:

```json
{"schema_version":"1.0","canonical_source":"shmape-evtol-index"}
```

See `docs/INTEGRATION.md` for downstream use.

## Operations

```bash
python -m app.worker bootstrap  # initialize schema and seed universe
python -m app.worker refresh    # daily + 15-minute market data, fundamentals, index rebuild
python -m app.worker rebuild    # rebuild index from stored point-in-time data
python -m app.worker discover   # scan SEC filings for newly public candidates
```

Deploy to the single-node MicroK8s environment with:

```bash
deploy/deploy_to_giro_k8s.sh
```

The deployment is public read-only, non-root, capability-free, read-only-root-filesystem, resource-limited, and protected by explicit network policy. Notifications are disabled by default. Authentication is designed to remain at the shared edge so LDAP/OIDC can be introduced centrally without embedding directory credentials here.

## Important limitations

- This is an independent research index, not a licensed benchmark or investable product.
- Pre-launch levels are a simulated rules backtest, not fund performance.
- Current free-float factors remain conservatively set to `1.0` until verified point-in-time share-class exclusions are available from filings. The UI and API disclose this state.
- Free Yahoo Finance endpoints can be delayed, revised, rate-limited, or unavailable.
- A z-score identifies unusual relative movement; it does not explain causality or constitute a trade recommendation.

Not financial advice.
