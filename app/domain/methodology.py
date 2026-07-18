from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import statistics


@dataclass(frozen=True)
class ConstituentInput:
    symbol: str
    market_cap_usd: float
    free_float_factor: float = 1.0
    price_usd: float = 0.0
    median_daily_value_usd: float = 0.0
    trading_days: int = 0

    @property
    def float_market_cap_usd(self) -> float:
        return max(0.0, self.market_cap_usd) * min(1.0, max(0.0, self.free_float_factor))


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reason: str


@dataclass(frozen=True)
class EligibilityPolicy:
    min_float_market_cap_usd: float = 50_000_000
    min_median_daily_value_usd: float = 250_000
    min_price_usd: float = 1.0
    min_trading_days: int = 20

    def evaluate(self, row: ConstituentInput) -> EligibilityDecision:
        reasons = []
        if row.float_market_cap_usd < self.min_float_market_cap_usd:
            reasons.append("float-adjusted market capitalization below threshold")
        if row.median_daily_value_usd < self.min_median_daily_value_usd:
            reasons.append("liquidity below threshold")
        if row.price_usd < self.min_price_usd:
            reasons.append("price below threshold")
        if row.trading_days < self.min_trading_days:
            reasons.append("insufficient trading history")
        return EligibilityDecision(not reasons, "; ".join(reasons) if reasons else "eligible")


@dataclass(frozen=True)
class OutlierResult:
    symbol: str
    period_return: float
    group_mean: float
    standard_deviation: float
    z_score: float
    label: str


def eligible_on(
    as_of: date,
    listing_date: date,
    delisting_date: date | None,
    *,
    listing_status: str = "active",
) -> bool:
    if listing_status not in {"active", "historical"}:
        return False
    return as_of >= listing_date and (delisting_date is None or as_of <= delisting_date)


def capped_float_market_cap_weights(rows: list[ConstituentInput], cap: float = 0.15) -> dict[str, float]:
    positive = {row.symbol: row.float_market_cap_usd for row in rows if row.float_market_cap_usd > 0}
    if not positive:
        return {}
    if not 0 < cap <= 1:
        raise ValueError("cap must be between zero and one")
    if cap * len(positive) < 1 - 1e-12:
        raise ValueError("cap is infeasible for the constituent count")

    remaining = set(positive)
    weights: dict[str, float] = {}
    available = 1.0
    while remaining:
        total = sum(positive[symbol] for symbol in remaining)
        provisional = {symbol: available * positive[symbol] / total for symbol in remaining}
        newly_capped = {symbol for symbol, weight in provisional.items() if weight > cap + 1e-12}
        if not newly_capped:
            weights.update(provisional)
            break
        for symbol in newly_capped:
            weights[symbol] = cap
            available -= cap
            remaining.remove(symbol)
    total_weight = sum(weights.values())
    if total_weight:
        weights = {symbol: weight / total_weight for symbol, weight in weights.items()}
    return dict(sorted(weights.items()))


def normalized_index_levels(
    dates: list[str],
    returns_by_symbol: dict[str, list[float]],
    weights: dict[str, float],
    base_value: float = 100.0,
) -> list[dict[str, float | str]]:
    if not dates:
        return []
    level = float(base_value)
    rows: list[dict[str, float | str]] = []
    for index, current_date in enumerate(dates):
        period_return = 0.0 if index == 0 else sum(
            weights.get(symbol, 0.0) * values[index]
            for symbol, values in returns_by_symbol.items()
            if index < len(values) and math.isfinite(values[index])
        )
        if index:
            level *= 1 + period_return
        rows.append({"date": current_date, "level": round(level, 6), "return": round(period_return, 8)})
    return rows


def classify_outliers(returns: dict[str, float]) -> list[OutlierResult]:
    clean = {symbol: value for symbol, value in returns.items() if math.isfinite(value)}
    if not clean:
        return []
    values = list(clean.values())
    mean = statistics.fmean(values)
    deviation = statistics.pstdev(values) if len(values) > 1 else 0.0
    results = []
    for symbol, value in clean.items():
        z_score = (value - mean) / deviation if deviation else 0.0
        if z_score >= 2:
            label = "high outlier"
        elif z_score >= 1:
            label = "above group"
        elif z_score <= -2:
            label = "low outlier"
        elif z_score <= -1:
            label = "below group"
        else:
            label = "within group"
        results.append(OutlierResult(symbol, value, mean, deviation, z_score, label))
    return sorted(results, key=lambda row: row.z_score, reverse=True)
