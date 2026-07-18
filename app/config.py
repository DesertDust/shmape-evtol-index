from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_path: str
    database_path: Path
    alerts_enabled: bool
    weight_cap: float
    min_float_market_cap_usd: float
    min_median_daily_value_usd: float
    min_price_usd: float
    min_trading_days: int
    market_data_user_agent: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        base_path=os.getenv("EVTOL_INDEX_BASE_PATH", "/Shmape-Homepage/evtol-index").rstrip("/"),
        database_path=Path(os.getenv("EVTOL_INDEX_DATABASE_PATH", "./var/evtol-index.db")),
        alerts_enabled=os.getenv("EVTOL_INDEX_ALERTS_ENABLED", "false").lower() in {"1", "true", "yes"},
        weight_cap=float(os.getenv("EVTOL_INDEX_WEIGHT_CAP", "0.15")),
        min_float_market_cap_usd=float(os.getenv("EVTOL_INDEX_MIN_FLOAT_MARKET_CAP_USD", "50000000")),
        min_median_daily_value_usd=float(os.getenv("EVTOL_INDEX_MIN_MEDIAN_DAILY_VALUE_USD", "250000")),
        min_price_usd=float(os.getenv("EVTOL_INDEX_MIN_PRICE_USD", "1.0")),
        min_trading_days=int(os.getenv("EVTOL_INDEX_MIN_TRADING_DAYS", "20")),
        market_data_user_agent=os.getenv(
            "EVTOL_INDEX_USER_AGENT",
            "ShmapeEVTOLIndex/0.1 (+https://cloud.tomgiro.com/Shmape-Homepage/evtol-index)",
        ),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
