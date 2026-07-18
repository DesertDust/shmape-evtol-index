from datetime import datetime, timezone

from app.services.market_data import MarketDataClient, parse_chart_payload


def test_chart_parser_skips_missing_bars_and_normalizes_currency() -> None:
    payload = {
        "chart": {
            "result": [{
                "meta": {"currency": "GBp", "symbol": "TEST.L", "exchangeTimezoneName": "Europe/London"},
                "timestamp": [100, 200, 300],
                "indicators": {
                    "quote": [{
                        "open": [100.0, None, 110.0],
                        "high": [105.0, None, 115.0],
                        "low": [99.0, None, 108.0],
                        "close": [103.0, None, 112.0],
                        "volume": [1000, None, 1200],
                    }],
                    "adjclose": [{"adjclose": [103.0, None, 112.0]}],
                },
            }],
            "error": None,
        }
    }

    bars = parse_chart_payload(payload, fx_to_usd=1.25)

    assert len(bars) == 2
    assert bars[0].close_native == 103.0
    assert bars[0].close_usd == 1.2875
    assert bars[1].timestamp == datetime.fromtimestamp(300, tz=timezone.utc)


def test_market_client_builds_daily_and_delayed_intraday_urls() -> None:
    client = MarketDataClient(user_agent="test")

    daily = client.chart_url("ACHR", interval="1d", range_name="5y")
    intraday = client.chart_url("ACHR", interval="15m", range_name="5d")

    assert "interval=1d" in daily and "range=5y" in daily
    assert "interval=15m" in intraday and "range=5d" in intraday
    assert "ACHR" in intraday


def test_daily_history_range_avoids_provider_max_range_downsampling() -> None:
    client = MarketDataClient(user_agent="test")
    assert client.daily_history_range == "10y"


def test_market_client_rejects_unsupported_intervals() -> None:
    client = MarketDataClient(user_agent="test")
    try:
        client.chart_url("ACHR", interval="1m", range_name="1d")
    except ValueError as exc:
        assert "interval" in str(exc)
    else:
        raise AssertionError("unsupported intervals must fail closed")
