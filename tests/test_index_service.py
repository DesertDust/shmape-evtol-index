from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.index_service import IndexService
from app.repository import Repository
from app.services.market_data import PriceBar


def _bar(symbol: str, minute: int, price: float) -> PriceBar:
    return PriceBar(
        timestamp=datetime(2026, 7, 17, 14, minute, tzinfo=timezone.utc),
        symbol=symbol,
        currency="USD",
        open_native=price,
        high_native=price,
        low_native=price,
        close_native=price,
        adjusted_close_native=price,
        volume=1000,
        close_usd=price,
        adjusted_close_usd=price,
    )


def test_one_day_comparison_uses_fifteen_minute_bars_and_current_weights(tmp_path) -> None:
    repository = Repository(tmp_path / "index.db")
    repository.initialize()
    repository.seed_companies(Path(__file__).parents[1] / "app" / "data" / "companies.json")
    membership = []
    for symbol, weight in (("ACHR", 0.5), ("JOBY", 0.5)):
        membership.append({
            "symbol": symbol, "eligible": True, "reason": "eligible", "market_cap_usd": 1,
            "float_market_cap_usd": 1, "median_daily_value_usd": 1, "weight": weight,
        })
    repository.replace_memberships("2026-07-01", membership)
    for symbol, first, second in (("ACHR", 10, 11), ("JOBY", 20, 20), ("^IXIC", 100, 102), ("QQQ", 200, 206)):
        repository.upsert_price_bars(symbol, "15m", [_bar(symbol, 0, first), _bar(symbol, 15, second)])
    settings = Settings("", tmp_path / "index.db", False, 0.25, 50_000_000, 250_000, 1, 20, "test")

    result = IndexService(repository, settings).comparison_series("1D")
    by_symbol = {row["symbol"]: row for row in result["series"]}

    assert len(result["dates"]) == 2
    assert by_symbol["SHM-EVTOL"]["values"] == [100.0, 105.0]
    assert by_symbol["^IXIC"]["values"] == [100.0, 102.0]
    assert by_symbol["QQQ"]["values"] == [100.0, 103.0]
