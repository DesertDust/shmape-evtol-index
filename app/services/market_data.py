from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PriceBar:
    timestamp: datetime
    symbol: str
    currency: str
    open_native: float
    high_native: float
    low_native: float
    close_native: float
    adjusted_close_native: float
    volume: int
    close_usd: float
    adjusted_close_usd: float


class MarketDataClient:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
    fundamentals_url = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries"
    allowed_intervals = {"1d", "15m"}
    allowed_ranges = {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
    # Yahoo silently downsamples `range=max` despite `interval=1d`; ten years
    # covers the sector's full public history while preserving daily bars.
    daily_history_range = "10y"

    def __init__(self, user_agent: str, timeout: int = 30) -> None:
        self.user_agent = user_agent
        self.timeout = timeout

    def chart_url(self, symbol: str, *, interval: str, range_name: str) -> str:
        if interval not in self.allowed_intervals:
            raise ValueError(f"unsupported interval: {interval}")
        if range_name not in self.allowed_ranges:
            raise ValueError(f"unsupported range: {range_name}")
        params = urlencode({"interval": interval, "range": range_name, "events": "div,splits", "includeAdjustedClose": "true"})
        return f"{self.base_url}/{quote(symbol, safe='^=.-')}?{params}"

    def fetch_chart(self, symbol: str, *, interval: str, range_name: str, fx_to_usd: float = 1.0) -> list[PriceBar]:
        payload = self._get_json(self.chart_url(symbol, interval=interval, range_name=range_name))
        return parse_chart_payload(payload, fx_to_usd=fx_to_usd)

    def fetch_metadata(self, symbol: str) -> dict:
        payload = self._get_json(self.chart_url(symbol, interval="1d", range_name="5d"))
        results = payload.get("chart", {}).get("result") or []
        if not results:
            raise ValueError(f"no market metadata for {symbol}")
        return dict(results[0].get("meta", {}))

    def fetch_fundamentals(self, symbol: str, period1: int = 1_500_000_000, period2: int = 2_000_000_000) -> list[dict]:
        metrics = ",".join((
            "quarterlyDilutedAverageShares",
            "annualDilutedAverageShares",
            "quarterlyMarketCap",
            "trailingMarketCap",
        ))
        params = urlencode({"symbol": symbol, "type": metrics, "merge": "false", "period1": period1, "period2": period2})
        payload = self._get_json(f"{self.fundamentals_url}/{quote(symbol, safe='.-')}?{params}")
        rows = []
        for series in payload.get("timeseries", {}).get("result", []):
            metric = (series.get("meta", {}).get("type") or [""])[0]
            for item in series.get(metric, []):
                reported = item.get("reportedValue", {})
                raw = reported.get("raw")
                if raw is None:
                    continue
                rows.append({
                    "symbol": symbol,
                    "metric": metric,
                    "as_of": item.get("asOfDate"),
                    "period_type": item.get("periodType"),
                    "currency": item.get("currencyCode", "USD"),
                    "value": float(raw),
                })
        return rows

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)


def parse_chart_payload(payload: dict, fx_to_usd: float = 1.0) -> list[PriceBar]:
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise ValueError(str(chart["error"]))
    results = chart.get("result") or []
    if not results:
        return []
    result = results[0]
    meta = result.get("meta", {})
    currency = meta.get("currency", "USD")
    symbol = meta.get("symbol", "")
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quote_rows = indicators.get("quote") or [{}]
    quotes = quote_rows[0]
    adjusted_rows = indicators.get("adjclose") or [{}]
    adjusted = adjusted_rows[0].get("adjclose") or quotes.get("close") or []
    native_unit = 0.01 if currency in {"GBp", "GBX"} else 1.0

    bars = []
    for index, epoch in enumerate(timestamps):
        try:
            close = quotes["close"][index]
            open_value = quotes["open"][index]
            high = quotes["high"][index]
            low = quotes["low"][index]
            volume = quotes["volume"][index]
            adjusted_close = adjusted[index]
        except (IndexError, KeyError, TypeError):
            continue
        if close is None or open_value is None or high is None or low is None or adjusted_close is None:
            continue
        bars.append(PriceBar(
            timestamp=datetime.fromtimestamp(epoch, tz=timezone.utc),
            symbol=symbol,
            currency=currency,
            open_native=float(open_value),
            high_native=float(high),
            low_native=float(low),
            close_native=float(close),
            adjusted_close_native=float(adjusted_close),
            volume=int(volume or 0),
            close_usd=float(close) * native_unit * fx_to_usd,
            adjusted_close_usd=float(adjusted_close) * native_unit * fx_to_usd,
        ))
    return bars
