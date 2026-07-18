from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import math
import statistics

from app.config import Settings
from app.domain.methodology import (
    ConstituentInput,
    EligibilityPolicy,
    capped_float_market_cap_weights,
    classify_outliers,
    eligible_on,
)
from app.repository import Repository
from app.services.market_data import MarketDataClient


BENCHMARKS = (
    {"symbol": "^IXIC", "name": "NASDAQ Composite", "kind": "broad benchmark"},
    {"symbol": "QQQ", "name": "NASDAQ-100 (QQQ)", "kind": "tradable proxy"},
)


class IndexService:
    def __init__(self, repository: Repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.policy = EligibilityPolicy(
            min_float_market_cap_usd=settings.min_float_market_cap_usd,
            min_median_daily_value_usd=settings.min_median_daily_value_usd,
            min_price_usd=settings.min_price_usd,
            min_trading_days=settings.min_trading_days,
        )

    def refresh_market_data(self, client: MarketDataClient) -> dict:
        run_id = self.repository.start_sync("market-data")
        companies = self.repository.list_companies()
        active_symbols = {row["yahoo_symbol"] for row in companies if row["listing_status"] == "active"}
        all_symbols = [row["yahoo_symbol"] for row in companies] + [row["symbol"] for row in BENCHMARKS]
        ok = 0
        failures = {}
        for symbol in dict.fromkeys(all_symbols):
            try:
                daily = client.fetch_chart(symbol, interval="1d", range_name=client.daily_history_range)
                if not daily:
                    raise ValueError("provider returned no daily bars")
                self.repository.upsert_price_bars(symbol, "1d", daily)
                if symbol in active_symbols or symbol in {row["symbol"] for row in BENCHMARKS}:
                    intraday = client.fetch_chart(symbol, interval="15m", range_name="5d")
                    self.repository.upsert_price_bars(symbol, "15m", intraday)
                if symbol not in {row["symbol"] for row in BENCHMARKS}:
                    self.repository.upsert_fundamentals(client.fetch_fundamentals(symbol))
                ok += 1
            except Exception as exc:  # provider failures are isolated per symbol
                failures[symbol] = f"{type(exc).__name__}: {exc}"[:300]
        status = "ok" if not failures else ("degraded" if ok else "failed")
        self.repository.finish_sync(run_id, status, ok, len(failures), {"failures": failures})
        if ok:
            self.rebuild_index()
        return {"status": status, "symbols_ok": ok, "symbols_failed": len(failures), "failures": failures}

    def rebuild_index(self) -> list[dict]:
        companies = self.repository.list_companies()
        histories = {row["yahoo_symbol"]: self.repository.price_series(row["yahoo_symbol"], "1d") for row in companies}
        by_symbol_date = {
            symbol: {bar["timestamp"][:10]: bar for bar in bars}
            for symbol, bars in histories.items()
        }
        dates = sorted({day for rows in by_symbol_date.values() for day in rows})
        if not dates:
            self.repository.replace_index_levels([])
            return []

        level = 100.0
        rows = []
        weights: dict[str, float] = {}
        prior_prices: dict[str, float] = {}
        current_quarter = None
        for day_text in dates:
            day = date.fromisoformat(day_text)
            quarter = (day.year, (day.month - 1) // 3 + 1)
            if quarter != current_quarter:
                decisions = self._review(day, companies, by_symbol_date)
                eligible_rows = [row["input"] for row in decisions if row["eligible"]]
                if len(eligible_rows) >= 4:
                    weights = capped_float_market_cap_weights(eligible_rows, cap=max(self.settings.weight_cap, 1 / len(eligible_rows)))
                else:
                    weights = {}
                membership_rows = []
                for decision in decisions:
                    item = decision["input"]
                    membership_rows.append({
                        "symbol": item.symbol,
                        "eligible": decision["eligible"] and item.symbol in weights,
                        "reason": decision["reason"] if item.symbol not in weights else "eligible",
                        "market_cap_usd": item.market_cap_usd,
                        "float_market_cap_usd": item.float_market_cap_usd,
                        "median_daily_value_usd": item.median_daily_value_usd,
                        "weight": weights.get(item.symbol, 0.0),
                    })
                self.repository.replace_memberships(day_text, membership_rows)
                prior_prices = {
                    symbol: by_symbol_date[symbol][day_text]["adjusted_close_usd"]
                    for symbol in weights if day_text in by_symbol_date[symbol]
                }
                current_quarter = quarter
                if not rows and weights:
                    rows.append({
                        "timestamp": day_text, "interval": "1d", "level": level, "period_return": 0.0,
                        "constituent_count": len(weights), "weights": weights,
                    })
                    continue
            if not weights or not rows:
                continue
            contributions = []
            for symbol, weight in weights.items():
                bar = by_symbol_date.get(symbol, {}).get(day_text)
                previous = prior_prices.get(symbol)
                if not bar or not previous:
                    contributions.append(0.0)
                    continue
                price = float(bar["adjusted_close_usd"])
                contributions.append(weight * (price / previous - 1))
                prior_prices[symbol] = price
            period_return = sum(contributions)
            level *= 1 + period_return
            rows.append({
                "timestamp": day_text,
                "interval": "1d",
                "level": round(level, 6),
                "period_return": round(period_return, 10),
                "constituent_count": len(weights),
                "weights": weights,
            })
        self.repository.replace_index_levels(rows)
        return rows

    def _review(self, day: date, companies: list[dict], prices: dict[str, dict[str, dict]]) -> list[dict]:
        decisions = []
        for company in companies:
            symbol = company["yahoo_symbol"]
            listing = date.fromisoformat(company["listing_date"])
            delisting = date.fromisoformat(company["delisting_date"]) if company["delisting_date"] else None
            history = [bar for bar_day, bar in prices.get(symbol, {}).items() if bar_day <= day.isoformat()]
            window = history[-60:]
            price = float(window[-1]["adjusted_close_usd"]) if window else 0.0
            daily_values = [float(bar["close_usd"]) * int(bar["volume"]) for bar in window if bar["volume"]]
            liquidity = statistics.median(daily_values) if daily_values else 0.0
            shares = self._shares_as_of(symbol, day)
            market_cap = price * shares
            item = ConstituentInput(
                symbol=symbol,
                market_cap_usd=market_cap,
                free_float_factor=float(company["free_float_factor"]),
                price_usd=price,
                median_daily_value_usd=liquidity,
                trading_days=len(window),
            )
            if not eligible_on(day, listing, delisting):
                eligible, reason = False, "outside public-listing period"
            else:
                result = self.policy.evaluate(item)
                eligible, reason = result.eligible, result.reason
            decisions.append({"input": item, "eligible": eligible, "reason": reason})
        return decisions

    def _shares_as_of(self, symbol: str, day: date) -> float:
        series = self.repository.fundamentals(symbol)
        allowed = {"quarterlyDilutedAverageShares", "annualDilutedAverageShares"}
        eligible = [row for row in series if row["metric"] in allowed and row["as_of"] <= day.isoformat()]
        if eligible:
            return float(max(eligible, key=lambda row: row["as_of"])["value"])
        market_caps = [row for row in series if row["metric"] in {"trailingMarketCap", "quarterlyMarketCap"} and row["as_of"] <= day.isoformat()]
        if market_caps:
            prices = self.repository.price_series(symbol, "1d")
            prior = [bar for bar in prices if bar["timestamp"][:10] <= day.isoformat()]
            if prior and float(prior[-1]["adjusted_close_usd"]):
                return float(max(market_caps, key=lambda row: row["as_of"])["value"]) / float(prior[-1]["adjusted_close_usd"])
        return 0.0

    def snapshot(self, range_name: str = "1M") -> dict:
        companies = self.repository.list_companies()
        memberships = self.repository.latest_memberships()
        membership_by_symbol = {row["symbol"]: row for row in memberships}
        latest = self.repository.latest_prices("15m") or self.repository.latest_prices("1d")
        period_days = {"1D": 2, "1W": 8, "1M": 32, "3M": 95, "YTD": 370, "1Y": 370, "MAX": 10000}.get(range_name, 32)
        since = None if range_name == "MAX" else (datetime.now(timezone.utc) - timedelta(days=period_days)).date().isoformat()
        returns = {}
        constituent_rows = []
        for company in companies:
            symbol = company["yahoo_symbol"]
            series = self.repository.price_series(symbol, "1d", since=since)
            if range_name == "YTD":
                series = [row for row in self.repository.price_series(symbol, "1d") if row["timestamp"][:4] == str(datetime.now(timezone.utc).year)]
            period_return = self._series_return(series)
            if company["listing_status"] == "active" and period_return is not None:
                returns[symbol] = period_return
            member = membership_by_symbol.get(symbol, {})
            price = latest.get(symbol, {})
            constituent_rows.append({
                **{key: company[key] for key in (
                    "slug", "display_name", "ticker", "yahoo_symbol", "exchange", "country", "category",
                    "listing_date", "delisting_date", "listing_status", "website_url", "investor_relations_url",
                    "career_url", "materiality_summary", "evidence_url", "float_factor_status",
                )},
                "price_usd": price.get("close_usd"),
                "price_timestamp": price.get("timestamp"),
                "period_return": period_return,
                "weight": member.get("weight", 0.0),
                "eligible": bool(member.get("eligible", 0)),
                "eligibility_reason": member.get("reason", "awaiting first data refresh"),
                "market_cap_usd": member.get("market_cap_usd", 0.0),
                "median_daily_value_usd": member.get("median_daily_value_usd", 0.0),
            })
        outliers = {row.symbol: row for row in classify_outliers(returns)}
        for row in constituent_rows:
            outlier = outliers.get(row["yahoo_symbol"])
            row["z_score"] = outlier.z_score if outlier else None
            row["outlier_label"] = outlier.label if outlier else "insufficient data"
            row["group_standard_deviation"] = outlier.standard_deviation if outlier else None
            row["annualized_volatility"] = self._annualized_volatility(row["yahoo_symbol"])

        index_levels = self._range_index_levels(range_name)
        latest_sync = self.repository.latest_sync("market-data")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "range": range_name,
            "index": {
                "name": "Shmape eVTOL Index",
                "symbol": "SHM-EVTOL",
                "level": index_levels[-1]["level"] if index_levels else 100.0,
                "period_return": self._level_return(index_levels),
                "constituent_count": sum(bool(row["eligible"]) for row in constituent_rows),
                "history_type": "simulated backtest before launch; live calculation from 2026-07-18",
            },
            "benchmarks": [self._benchmark_snapshot(row, range_name) for row in BENCHMARKS],
            "constituents": constituent_rows,
            "outliers": [row for row in constituent_rows if row["z_score"] is not None],
            "series": self.comparison_series(range_name),
            "methodology": self.methodology(),
            "data_freshness": latest_sync,
            "alerts": {"enabled": self.settings.alerts_enabled, "mode": "hooks-ready; notifications disabled" if not self.settings.alerts_enabled else "enabled"},
        }

    def comparison_series(self, range_name: str) -> dict:
        if range_name == "1D":
            intraday = self._intraday_comparison_series()
            if intraday["dates"]:
                return intraday
        levels = self._range_index_levels(range_name)
        if not levels:
            return {"dates": [], "series": []}
        dates = [row["timestamp"][:10] for row in levels]
        output = [{"symbol": "SHM-EVTOL", "name": "Shmape eVTOL Index", "values": [row["level"] for row in levels]}]
        for benchmark in BENCHMARKS:
            values = self._normalized_prices(benchmark["symbol"], dates)
            output.append({"symbol": benchmark["symbol"], "name": benchmark["name"], "values": values})
        membership_symbols = [row["symbol"] for row in self.repository.latest_memberships() if row["eligible"]]
        names = {row["yahoo_symbol"]: row["display_name"] for row in self.repository.list_companies()}
        for symbol in membership_symbols:
            output.append({"symbol": symbol, "name": names.get(symbol, symbol), "values": self._normalized_prices(symbol, dates)})
        return {"dates": dates, "series": output}

    def _intraday_comparison_series(self) -> dict:
        memberships = [row for row in self.repository.latest_memberships() if row["eligible"] and row["weight"] > 0]
        if not memberships:
            return {"dates": [], "series": []}
        member_weights = {row["symbol"]: float(row["weight"]) for row in memberships}
        symbols = [row["symbol"] for row in BENCHMARKS] + list(member_weights)
        histories = {symbol: self.repository.price_series(symbol, "15m") for symbol in symbols}
        all_timestamps = [bar["timestamp"] for rows in histories.values() for bar in rows]
        if not all_timestamps:
            return {"dates": [], "series": []}
        session = max(all_timestamps)[:10]
        dates = sorted({bar["timestamp"] for rows in histories.values() for bar in rows if bar["timestamp"][:10] == session})
        normalized = {}
        for symbol, rows in histories.items():
            by_timestamp = {row["timestamp"]: float(row["adjusted_close_usd"]) for row in rows if row["timestamp"][:10] == session}
            values = []
            last = None
            for timestamp in dates:
                if timestamp in by_timestamp:
                    last = by_timestamp[timestamp]
                values.append(last)
            first = next((value for value in values if value and value > 0), None)
            normalized[symbol] = [100 * value / first if value is not None and first else None for value in values]
        index_values = []
        for position in range(len(dates)):
            available = [
                (symbol, weight, normalized[symbol][position])
                for symbol, weight in member_weights.items()
                if normalized.get(symbol) and normalized[symbol][position] is not None
            ]
            total_weight = sum(weight for _, weight, _ in available)
            index_values.append(
                round(sum(weight * float(value) for _, weight, value in available) / total_weight, 6)
                if total_weight else None
            )
        names = {row["yahoo_symbol"]: row["display_name"] for row in self.repository.list_companies()}
        output = [{"symbol": "SHM-EVTOL", "name": "Shmape eVTOL Index", "values": index_values}]
        for benchmark in BENCHMARKS:
            output.append({
                "symbol": benchmark["symbol"], "name": benchmark["name"],
                "values": [round(value, 6) if value is not None else None for value in normalized.get(benchmark["symbol"], [])],
            })
        for symbol in member_weights:
            output.append({
                "symbol": symbol, "name": names.get(symbol, symbol),
                "values": [round(value, 6) if value is not None else None for value in normalized.get(symbol, [])],
            })
        return {"dates": dates, "series": output}

    def methodology(self) -> dict:
        return {
            "weighting": "free-float-adjusted market capitalization, iteratively capped",
            "weight_cap": self.settings.weight_cap,
            "review_frequency": "quarterly, using the first trading day of each calendar quarter",
            "new_listing_rule": "tracked immediately; eligible at the next review after at least 20 trading days",
            "minimum_float_market_cap_usd": self.settings.min_float_market_cap_usd,
            "minimum_median_daily_value_usd": self.settings.min_median_daily_value_usd,
            "minimum_price_usd": self.settings.min_price_usd,
            "minimum_trading_days": self.settings.min_trading_days,
            "price_series": "split- and distribution-adjusted daily closes; intraday display uses 15-minute bars",
            "base_value": 100,
            "benchmarks": ["NASDAQ Composite (^IXIC)", "NASDAQ-100 via QQQ"],
            "outlier_definition": "cross-sectional period-return z-score: company return minus group mean, divided by population standard deviation",
            "high_outlier": ">= +2 standard deviations",
            "low_outlier": "<= -2 standard deviations",
            "corporate_actions": "provider-adjusted prices; constituents enter and leave only on recorded public-listing dates and scheduled reviews",
            "backtest_label": "pre-launch levels are a simulated, point-in-time rules backtest and are not live fund performance",
        }

    def _range_index_levels(self, range_name: str) -> list[dict]:
        levels = self.repository.index_levels("1d")
        if not levels:
            return []
        today = datetime.now(timezone.utc).date()
        if range_name == "MAX":
            selected = levels
        elif range_name == "YTD":
            selected = [row for row in levels if row["timestamp"][:4] == str(today.year)]
        else:
            days = {"1D": 2, "1W": 8, "1M": 32, "3M": 95, "1Y": 370}.get(range_name, 32)
            cutoff = (today - timedelta(days=days)).isoformat()
            selected = [row for row in levels if row["timestamp"][:10] >= cutoff]
        if not selected:
            return []
        base = selected[0]["level"]
        return [{**row, "level": round(100 * row["level"] / base, 6)} for row in selected]

    def _normalized_prices(self, symbol: str, dates: list[str]) -> list[float | None]:
        raw = {row["timestamp"][:10]: float(row["adjusted_close_usd"]) for row in self.repository.price_series(symbol, "1d")}
        values = []
        last = None
        for day in dates:
            if day in raw:
                last = raw[day]
            values.append(last)
        first = next((value for value in values if value and value > 0), None)
        return [round(100 * value / first, 6) if value is not None and first else None for value in values]

    def _benchmark_snapshot(self, benchmark: dict, range_name: str) -> dict:
        series = self.repository.price_series(benchmark["symbol"], "1d")
        if range_name == "YTD":
            series = [row for row in series if row["timestamp"][:4] == str(datetime.now(timezone.utc).year)]
        elif range_name != "MAX":
            days = {"1D": 2, "1W": 8, "1M": 32, "3M": 95, "1Y": 370}.get(range_name, 32)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
            series = [row for row in series if row["timestamp"][:10] >= cutoff]
        return {**benchmark, "period_return": self._series_return(series)}

    def _annualized_volatility(self, symbol: str) -> float | None:
        rows = self.repository.price_series(symbol, "1d")[-63:]
        prices = [float(row["adjusted_close_usd"]) for row in rows if row["adjusted_close_usd"]]
        if len(prices) < 20:
            return None
        returns = [math.log(current / prior) for prior, current in zip(prices, prices[1:]) if prior > 0 and current > 0]
        return statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else None

    @staticmethod
    def _series_return(series: list[dict]) -> float | None:
        if len(series) < 2:
            return None
        first = float(series[0]["adjusted_close_usd"])
        last = float(series[-1]["adjusted_close_usd"])
        return last / first - 1 if first else None

    @staticmethod
    def _level_return(levels: list[dict]) -> float | None:
        if len(levels) < 2 or not levels[0]["level"]:
            return None
        return float(levels[-1]["level"]) / float(levels[0]["level"]) - 1
