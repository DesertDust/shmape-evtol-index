# Shmape eVTOL Index Methodology

Version 1.0 — launch date 18 July 2026

## 1. Objective

SHM-EVTOL measures the USD-normalized equity performance of public companies for which passenger eVTOL, cargo eVTOL, or an enabling eVTOL operating platform is a material business. It is designed for understandable sector comparison, not to replicate a fund.

## 2. Universe

A company enters the tracked database when all of the following are supported by public evidence:

1. Its equity or depositary receipt is publicly traded on a recognized exchange.
2. It develops, manufactures, certifies, or operates eVTOL aircraft, or operates a platform whose economics materially depend on eVTOL deployment.
3. The exposure is material to the listed company rather than an immaterial project inside a diversified conglomerate.
4. A stable ticker and price history are available.

Passenger, cargo, piloted, autonomous, battery-electric, and hybrid-electric VTOL designs may qualify. Conventional electric takeoff and landing alone does not qualify. Large aerospace parents are excluded when their eVTOL exposure is immaterial; a separately listed eVTOL subsidiary may qualify.

Former public companies are retained with effective listing and removal dates so simulated history does not silently erase failures. A company can remain in the database while failing index eligibility.

## 3. Eligibility at each review

On the first trading day of each calendar quarter, a tracked company must have:

- float-adjusted market capitalization of at least USD 50 million;
- median daily traded value of at least USD 250,000 over the most recent 60 observations;
- adjusted closing price of at least USD 1.00;
- at least 20 daily trading observations; and
- an active public listing on the review date.

New listings are tracked immediately but wait until the next quarterly review and must have the required trading history. This avoids introducing an IPO using only a volatile opening print. Delistings and loss of material eVTOL exposure are effective on their documented dates.

## 4. Weighting

Raw weight is:

`company market capitalization × free-float factor`

Raw weights are divided by their total, then any weight over 25% is capped. Excess is redistributed pro rata to uncapped constituents, iteratively, until all weights are at or below 25% and sum to 100%.

The cap balances economic size with category breadth. It is deliberately simpler than a multi-tier modified-cap formula so a reader can reproduce it.

### Current float-factor caveat

Verified point-in-time float exclusions are not consistently available through the free automated feed. Version 1.0 stores a factor and its verification status for every company; conservative placeholders are `1.0`. The dashboard discloses this limitation. A future verified factor replaces the placeholder only with dated filing evidence—never by silently guessing.

## 5. Index calculation

- Base value: 100.
- Price input: split- and distribution-adjusted daily close.
- Daily index return: sum of each constituent's daily adjusted return multiplied by its review weight.
- Daily level: prior level multiplied by one plus daily index return.
- Missing same-day constituent price: zero return until the next valid observation; the constituent is not redistributed intraday.
- Rebalance: weights reset at the quarterly review.
- Corporate actions: adjusted prices absorb ordinary splits and distributions. Mergers, ticker changes, sales of the material eVTOL business, and delistings use documented effective dates.
- Currency: native primary-listing prices convert to USD before calculation. Current constituents happen to trade in USD; the schema and parser support foreign currencies and GBp/GBX unit conversion.

The simulated history begins only when at least four eligible constituents have point-in-time share and liquidity data. No constituent is inserted before its listing date.

## 6. Intraday view

The 1D chart uses 15-minute delayed bars. Each constituent and benchmark is rebased to 100 at the first available bar in the latest session. The intraday index is the review-weighted sum of normalized eligible constituents. It is an informational view; official stored levels are daily.

## 7. Benchmarks

- NASDAQ Composite (`^IXIC`) is the primary broad growth-equity comparison.
- Invesco QQQ (`QQQ`) is shown as a liquid proxy for NASDAQ-100.

All chart lines are normalized to 100 at the selected period start, so differences reflect relative return rather than nominal share price.

## 8. Standard deviations and outliers

For a selected period, each active tracked company's adjusted return is calculated. Let `rᵢ` be one company’s return, `μ` the group mean, and `σ` the population standard deviation.

`zᵢ = (rᵢ − μ) / σ`

Interpretation:

- `z >= +2`: high outlier;
- `+1 <= z < +2`: above group;
- `-1 < z < +1`: within group;
- `-2 < z <= -1`: below group;
- `z <= -2`: low outlier.

If dispersion is zero, every z-score is zero; the service never emits NaN. A z-score describes cross-sectional distance, not cause, valuation, or expected return.

Separate annualized volatility is the sample standard deviation of up to 62 recent daily log returns multiplied by `sqrt(252)`.

## 9. Discovery and governance

A daily discovery job searches recent SEC filings for multiple eVTOL/AAM phrases, maps filing CIKs to current exchange listings, scores materiality deterministically, and records every decision in an audit table. Automatic inclusion requires:

- verified public ticker and exchange;
- aircraft-manufacturing SIC classification plus an aviation/aircraft/aerospace identity;
- repeated matches across multiple exact eVTOL/AAM phrase searches; and
- multiple filing evidence URLs.

Lower-confidence names are recorded as observed, not promoted. This fail-closed threshold is intended to prevent a single mention by a diversified conglomerate or operator from contaminating the universe.

Seed records and automated records retain evidence URLs, discovery dates, and verification state.

## 10. Backtest and data disclosure

Levels before 18 July 2026 are labeled simulated. They are calculated with the current published rules using data available in the local point-in-time store. They may still contain availability, free-float, corporate-action, and provider biases. They are not presented as returns achieved by an actual portfolio.

Sources include company investor-relations pages, SEC filings, exchange/listing notices, Yahoo Finance chart and fundamentals endpoints, and documented corporate-action announcements. The software exposes data freshness and provider failures instead of substituting invented values.

## 11. Methodology influences

The design uses common transparent-index conventions rather than claiming affiliation:

- Solactive equity index guidelines for scheduled reviews and corporate-action treatment: https://www.solactive.com/documents/equity-index-methodology/
- Solactive Future Mobility Index guideline as an analogous thematic-index reference: https://www.solactive.com/downloads/Guideline-Solactive-SOLFMOB.pdf
- NASDAQ-100 methodology as a reference for capped market-cap weighting: https://indexes.nasdaqomx.com/docs/Methodology_NDX.pdf
- SEC EDGAR filing search and company ticker data for public-listing discovery: https://www.sec.gov/edgar/search/
- SMG Consulting AAM Reality Index as a non-equity reference for industry scope and readiness—not as a price-index methodology: https://aamrealityindex.com/

## 12. Change policy

A methodology change requires a version bump, dated changelog, code/test update, and disclosure in the dashboard before the next review. Historical results must identify the rules version used.
