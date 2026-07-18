# Company Universe

Researched 18 July 2026. The machine-readable source is `app/data/companies.json`; the live canonical endpoint is `/api/v1/companies`.

## Active tracked companies

| Ticker | Company | Category | Listing | Notes |
|---|---|---|---|---|
| EH | EHang | Passenger/autonomous | NASDAQ, 2019 | Pure-play autonomous eVTOL developer/operator |
| JOBY | Joby Aviation | Passenger | NYSE, 2021 | Pure-play air taxi developer/operator |
| ACHR | Archer Aviation | Passenger | NYSE, 2021 | Pure-play Midnight eVTOL developer |
| EVTL | Vertical Aerospace | Passenger | NYSE, 2021 | Pure-play VX4 developer |
| EVEX | Eve Air Mobility | Passenger/platform | NYSE, 2022 | Aircraft and UATM platform |
| HOVR | New Horizon Aircraft | Passenger/cargo | NASDAQ, 2024 | Hybrid-electric Cavorite VTOL |
| AIRO | AIRO Group | Passenger/cargo/platform | NASDAQ, 2025 | Jaunt Air Mobility is a material electric-air-mobility segment |
| BETA | BETA Technologies | Passenger/cargo/enabling | NYSE, 2025 | ALIA eVTOL/eCTOL, propulsion, and charging |

## Historical tracked companies

| Ticker | Company | Effective end | Reason |
|---|---|---|---|
| LILM | Lilium N.V. | 5 Nov 2024 | Last eligible trading day; Nasdaq suspended trading from 6 Nov. Retained against survivorship bias. |
| BLDE | Blade Air Mobility | 29 Aug 2025 | Passenger business sold to Joby; remaining public company became Strata Critical Medical and no longer had material eVTOL exposure. |

Historical data providers may represent successor/OTC symbols (`LILMF`, `SRTA`) internally. Public API/UI retain the effective historical ticker.

## Deliberate exclusions

- Boeing/Wisk, Hyundai/Supernal, Embraer parent, Textron/Pipistrel, Toyota/Joby stake, and Xpeng/AeroHT: eVTOL is not material to the listed parent or a separately listed qualifying subsidiary already represents the exposure.
- XTI Aerospace (`XTIA`): tracked as an explicit scope exclusion. Its TriFan 600 used conventional turboprop propulsion rather than an electric VTOL architecture, and the program was shelved in 2026 as the company shifted toward drones.
- Surf Air Mobility: material electric regional aviation exposure, but its current program is conventional electric takeoff and landing rather than VTOL.
- Faraday Future and Robo.ai: monitored by automated SEC discovery, but current evidence does not establish eVTOL as a sufficiently material operating business for automatic inclusion.
- Private companies such as Wisk, Volocopter, AutoFlight, SkyDrive, Pivotal, Alef, and Beta before its IPO: excluded from the equity index while private. BETA enters from its public listing date.
- General drone, defense, battery, avionics, and aerospace suppliers: excluded unless eVTOL is a material operating segment.

## Evidence highlights

- BETA final prospectus: https://www.sec.gov/Archives/edgar/data/1784570/000119312525265029/d89594d424b4.htm
- Eve NYSE listing: https://www.eveairmobility.com/eve-holding-inc-begins-trading-today-on-the-new-york-stock-exchange-under-the-symbol-evex/
- Joby acquisition of Blade passenger business: https://www.jobyaviation.com/news/joby-to-acquire-blades-passenger-business-accelerating-air-taxi-commercialization
- Blade/Strata transaction close and ticker change: https://ir.stratacritical.com/news-events/press-releases/detail/125/blade-completes-sale-of-passenger-business-and-planned-name
- Lilium delisting disclosure: https://www.sec.gov/Archives/edgar/data/1855756/000110465924113333/tm2427145d1_6k.htm

Every seed record carries its own evidence URL. Automated discoveries are retained in `discovery_audit` even when excluded.
