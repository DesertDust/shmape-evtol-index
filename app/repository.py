from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from app.services.market_data import PriceBar


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS companies (
  slug TEXT PRIMARY KEY,
  legal_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  ticker TEXT NOT NULL,
  yahoo_symbol TEXT NOT NULL UNIQUE,
  exchange TEXT NOT NULL,
  country TEXT NOT NULL,
  currency TEXT NOT NULL,
  category TEXT NOT NULL,
  listing_date TEXT NOT NULL,
  delisting_date TEXT,
  listing_status TEXT NOT NULL,
  website_url TEXT NOT NULL,
  investor_relations_url TEXT NOT NULL,
  career_url TEXT NOT NULL,
  materiality_summary TEXT NOT NULL,
  evidence_url TEXT NOT NULL,
  free_float_factor REAL NOT NULL DEFAULT 1,
  float_factor_status TEXT NOT NULL,
  discovered_at TEXT NOT NULL,
  last_verified_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_bars (
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  currency TEXT NOT NULL,
  open_native REAL NOT NULL,
  high_native REAL NOT NULL,
  low_native REAL NOT NULL,
  close_native REAL NOT NULL,
  adjusted_close_native REAL NOT NULL,
  volume INTEGER NOT NULL,
  close_usd REAL NOT NULL,
  adjusted_close_usd REAL NOT NULL,
  PRIMARY KEY(symbol, interval, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_price_bars_lookup ON price_bars(symbol, interval, timestamp);
CREATE TABLE IF NOT EXISTS fundamentals (
  symbol TEXT NOT NULL,
  metric TEXT NOT NULL,
  as_of TEXT NOT NULL,
  period_type TEXT,
  currency TEXT NOT NULL,
  value REAL NOT NULL,
  PRIMARY KEY(symbol, metric, as_of)
);
CREATE TABLE IF NOT EXISTS index_levels (
  timestamp TEXT PRIMARY KEY,
  interval TEXT NOT NULL,
  level REAL NOT NULL,
  period_return REAL NOT NULL,
  constituent_count INTEGER NOT NULL,
  weights_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
  review_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  eligible INTEGER NOT NULL,
  reason TEXT NOT NULL,
  market_cap_usd REAL NOT NULL,
  float_market_cap_usd REAL NOT NULL,
  median_daily_value_usd REAL NOT NULL,
  weight REAL NOT NULL,
  PRIMARY KEY(review_date, symbol)
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  symbols_ok INTEGER NOT NULL DEFAULT 0,
  symbols_failed INTEGER NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS discovery_audit (
  fingerprint TEXT PRIMARY KEY,
  discovered_at TEXT NOT NULL,
  name TEXT NOT NULL,
  ticker TEXT NOT NULL,
  exchange_name TEXT NOT NULL,
  score INTEGER NOT NULL,
  decision TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  evidence_json TEXT NOT NULL
);
"""


class Repository:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def seed_companies(self, seed_path: Path) -> int:
        payload = json.loads(seed_path.read_text())
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        columns = (
            "slug", "legal_name", "display_name", "ticker", "yahoo_symbol", "exchange", "country",
            "currency", "category", "listing_date", "delisting_date", "listing_status", "website_url",
            "investor_relations_url", "career_url", "materiality_summary", "evidence_url",
            "free_float_factor", "float_factor_status",
        )
        with self.connect() as connection:
            for company in payload["companies"]:
                existing = connection.execute("SELECT 1 FROM companies WHERE slug=?", (company["slug"],)).fetchone()
                values = [company.get(column) for column in columns]
                connection.execute(
                    f"""INSERT INTO companies ({','.join(columns)},discovered_at,last_verified_at)
                    VALUES ({','.join('?' for _ in columns)},?,?)
                    ON CONFLICT(slug) DO UPDATE SET
                      legal_name=excluded.legal_name, display_name=excluded.display_name,
                      ticker=excluded.ticker, yahoo_symbol=excluded.yahoo_symbol, exchange=excluded.exchange,
                      country=excluded.country, currency=excluded.currency, category=excluded.category,
                      listing_date=excluded.listing_date, delisting_date=excluded.delisting_date,
                      listing_status=excluded.listing_status, website_url=excluded.website_url,
                      investor_relations_url=excluded.investor_relations_url, career_url=excluded.career_url,
                      materiality_summary=excluded.materiality_summary, evidence_url=excluded.evidence_url,
                      free_float_factor=excluded.free_float_factor,
                      float_factor_status=excluded.float_factor_status, last_verified_at=excluded.last_verified_at""",
                    (*values, now, now),
                )
                count += 0 if existing else 1
        return count

    def list_companies(self, include_historical: bool = True) -> list[dict]:
        query = "SELECT * FROM companies"
        params: tuple = ()
        if not include_historical:
            query += " WHERE listing_status='active'"
        query += " ORDER BY listing_date, display_name"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params)]

    def upsert_discovered_company(self, company: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        fields = (
            "slug", "legal_name", "display_name", "ticker", "yahoo_symbol", "exchange", "country",
            "currency", "category", "listing_date", "delisting_date", "listing_status", "website_url",
            "investor_relations_url", "career_url", "materiality_summary", "evidence_url",
            "free_float_factor", "float_factor_status",
        )
        with self.connect() as connection:
            connection.execute(
                f"""INSERT INTO companies ({','.join(fields)},discovered_at,last_verified_at)
                VALUES ({','.join('?' for _ in fields)},?,?)
                ON CONFLICT(slug) DO UPDATE SET last_verified_at=excluded.last_verified_at,
                  materiality_summary=excluded.materiality_summary,evidence_url=excluded.evidence_url""",
                (*(company.get(field) for field in fields), now, now),
            )

    def record_discovery(
        self,
        fingerprint: str,
        candidate: dict,
        score: int,
        decision: str,
        reasons: tuple[str, ...],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO discovery_audit VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fingerprint) DO UPDATE SET score=excluded.score,decision=excluded.decision,
                  reasons_json=excluded.reasons_json,evidence_json=excluded.evidence_json""",
                (
                    fingerprint, datetime.now(timezone.utc).isoformat(), candidate["name"], candidate.get("ticker", ""),
                    candidate.get("exchange", ""), score, decision, json.dumps(reasons),
                    json.dumps(candidate.get("evidence_urls", [])),
                ),
            )

    def get_company(self, symbol: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM companies WHERE yahoo_symbol=? OR ticker=?", (symbol, symbol)).fetchone()
            return dict(row) if row else None

    def upsert_price_bars(self, symbol: str, interval: str, bars: list[PriceBar]) -> int:
        with self.connect() as connection:
            connection.executemany(
                """INSERT INTO price_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,interval,timestamp) DO UPDATE SET
                  currency=excluded.currency, open_native=excluded.open_native, high_native=excluded.high_native,
                  low_native=excluded.low_native, close_native=excluded.close_native,
                  adjusted_close_native=excluded.adjusted_close_native, volume=excluded.volume,
                  close_usd=excluded.close_usd, adjusted_close_usd=excluded.adjusted_close_usd""",
                [(
                    symbol, interval, bar.timestamp.isoformat(), bar.currency, bar.open_native, bar.high_native,
                    bar.low_native, bar.close_native, bar.adjusted_close_native, bar.volume,
                    bar.close_usd, bar.adjusted_close_usd,
                ) for bar in bars],
            )
        return len(bars)

    def upsert_fundamentals(self, rows: list[dict]) -> int:
        with self.connect() as connection:
            connection.executemany(
                """INSERT INTO fundamentals(symbol,metric,as_of,period_type,currency,value) VALUES (?,?,?,?,?,?)
                ON CONFLICT(symbol,metric,as_of) DO UPDATE SET period_type=excluded.period_type,
                currency=excluded.currency,value=excluded.value""",
                [(r["symbol"], r["metric"], r["as_of"], r.get("period_type"), r["currency"], r["value"]) for r in rows if r.get("as_of")],
            )
        return len(rows)

    def price_series(self, symbol: str, interval: str = "1d", since: str | None = None) -> list[dict]:
        query = "SELECT * FROM price_bars WHERE symbol=? AND interval=?"
        params: list = [symbol, interval]
        if since:
            query += " AND timestamp>=?"
            params.append(since)
        query += " ORDER BY timestamp"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params)]

    def latest_prices(self, interval: str = "1d") -> dict[str, dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.* FROM price_bars p JOIN (
                SELECT symbol, MAX(timestamp) timestamp FROM price_bars WHERE interval=? GROUP BY symbol
                ) latest ON latest.symbol=p.symbol AND latest.timestamp=p.timestamp WHERE p.interval=?""",
                (interval, interval),
            )
            return {row["symbol"]: dict(row) for row in rows}

    def fundamentals(self, symbol: str, metric: str | None = None) -> list[dict]:
        query = "SELECT * FROM fundamentals WHERE symbol=?"
        params: list = [symbol]
        if metric:
            query += " AND metric=?"
            params.append(metric)
        query += " ORDER BY as_of"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params)]

    def replace_index_levels(self, rows: list[dict]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM index_levels")
            connection.executemany(
                "INSERT INTO index_levels VALUES (?,?,?,?,?,?)",
                [(r["timestamp"], r["interval"], r["level"], r["period_return"], r["constituent_count"], json.dumps(r["weights"], sort_keys=True)) for r in rows],
            )

    def index_levels(self, interval: str = "1d", since: str | None = None) -> list[dict]:
        query = "SELECT * FROM index_levels WHERE interval=?"
        params: list = [interval]
        if since:
            query += " AND timestamp>=?"
            params.append(since)
        query += " ORDER BY timestamp"
        with self.connect() as connection:
            rows = []
            for row in connection.execute(query, params):
                item = dict(row)
                item["weights"] = json.loads(item.pop("weights_json"))
                rows.append(item)
            return rows

    def replace_memberships(self, review_date: str, rows: list[dict]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM memberships WHERE review_date=?", (review_date,))
            connection.executemany(
                "INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?)",
                [(review_date, r["symbol"], int(r["eligible"]), r["reason"], r["market_cap_usd"], r["float_market_cap_usd"], r["median_daily_value_usd"], r["weight"]) for r in rows],
            )

    def latest_memberships(self) -> list[dict]:
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(review_date) value FROM memberships").fetchone()
            if not row or not row["value"]:
                return []
            return [dict(item) for item in connection.execute("SELECT * FROM memberships WHERE review_date=? ORDER BY weight DESC,symbol", (row["value"],))]

    def start_sync(self, kind: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sync_runs(started_at,kind,status) VALUES (?,?,?)",
                (datetime.now(timezone.utc).isoformat(), kind, "running"),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("sync run did not receive an id")
            return int(cursor.lastrowid)

    def finish_sync(self, run_id: int, status: str, ok: int, failed: int, details: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sync_runs SET finished_at=?,status=?,symbols_ok=?,symbols_failed=?,details_json=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), status, ok, failed, json.dumps(details, sort_keys=True), run_id),
            )

    def latest_sync(self, kind: str | None = None) -> dict | None:
        query = "SELECT * FROM sync_runs"
        params: tuple = ()
        if kind:
            query += " WHERE kind=?"
            params = (kind,)
        query += " ORDER BY id DESC LIMIT 1"
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
            if not row:
                return None
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            return item
