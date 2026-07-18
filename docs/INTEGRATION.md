# Shmape Integration Contract

The eVTOL Index is the canonical public-company universe for other Shmape products.

## Endpoint

Cluster-internal:

`http://evtol-index-web.shmape.svc.cluster.local:8000/api/v1/companies`

Public:

`https://cloud.tomgiro.com/Shmape-Homepage/evtol-index/api/v1/companies`

Consumers must verify:

- HTTP status is 200;
- `canonical_source == "shmape-evtol-index"`; and
- the supported `schema_version` major is `1`.

Consumers should cache the last good response and fail closed on malformed payloads. They must not interpret a network failure as an empty universe.

## Fields

Each company includes stable `slug`, display/legal names, public and provider symbols, exchange, country/currency, category, listing dates/status, website, investor-relations page, career page, materiality summary, evidence URL, and float-factor verification status.

`listing_status=historical` records are included by default. Pass `include_historical=false` to request active records only.

## SkyHire integration

SkyHire Radar sets:

`SKYHIRE_EVTOL_UNIVERSE_URL=http://evtol-index-web.shmape.svc.cluster.local:8000/api/v1/companies`

Before each hourly scan, it merges active canonical public companies that have an HTTPS career source. Private SkyHire watchlist companies are preserved. The sync does not accept arbitrary sources and never deletes local companies on API failure.

## Schema evolution

- additive fields: minor version;
- removals or semantic changes: major version;
- consumers ignore unknown fields;
- the source never exposes secrets or administrative mutation routes.
