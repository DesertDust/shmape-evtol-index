# Implemented Features

## Product

- Rules-based SHM-EVTOL index, base 100.
- NASDAQ Composite and NASDAQ-100/QQQ comparison.
- 1D, 1W, 1M, 3M, YTD, 1Y, and MAX controls.
- 15-minute delayed intraday comparison.
- Point-in-time public-listing dates and historical constituents.
- Quarterly liquidity/size/price/history eligibility reviews.
- Free-float-factor schema and iteratively capped market-cap weights.
- Cross-sectional standard deviation, z-score outliers, and annualized volatility.
- Clear explainer, formula, methodology, backtest disclosure, and not-financial-advice language.
- Responsive Shmape/Linear-style dashboard.

## Data platform

- Versioned canonical eVTOL company API.
- SQLite WAL store for companies, prices, fundamentals, memberships, index levels, sync runs, and discovery audit.
- Yahoo daily adjusted and 15-minute chart ingestion.
- Yahoo fundamentals ingestion for historical diluted shares and market capitalization.
- GBp/GBX unit handling and USD normalization seam.
- Daily SEC EDGAR discovery across multiple eVTOL/AAM phrases.
- Deterministic, fail-closed automatic materiality scoring.
- Scheduled 15-minute refresh and daily discovery jobs.
- Data freshness and per-symbol provider failure reporting.

## Integration

- Shmape homepage live app card and navigation.
- SkyHire canonical-universe sync before hourly scans.
- Active public companies with HTTPS career sources merge without deleting private watchlist companies.
- Public and cluster-internal integration documentation.

## Delivery and security

- Standalone Git repository with GitHub Actions CI.
- Non-root, read-only-root-filesystem container.
- Capability drop, seccomp, no service-account token, resource limits, probes, PVC, and NetworkPolicy.
- Public read-only route; no mutation/admin surface.
- LDAP/OIDC-ready edge-auth model documented.
- Telegram/WhatsApp hooks disabled pending explicit identity allowlists.

Verification and live deployment status are recorded in the release/commit after deployment.
