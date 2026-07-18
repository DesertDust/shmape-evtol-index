from datetime import date

import pytest

from app.domain.methodology import (
    ConstituentInput,
    EligibilityPolicy,
    capped_float_market_cap_weights,
    classify_outliers,
    eligible_on,
    normalized_index_levels,
)


def test_capped_float_market_cap_weights_sum_to_one_and_enforce_cap() -> None:
    rows = [
        ConstituentInput("A", market_cap_usd=10_000, free_float_factor=0.8),
        ConstituentInput("B", market_cap_usd=2_000, free_float_factor=0.9),
        ConstituentInput("C", market_cap_usd=1_000, free_float_factor=1.0),
        ConstituentInput("D", market_cap_usd=500, free_float_factor=1.0),
    ]

    weights = capped_float_market_cap_weights(rows, cap=0.35)

    assert sum(weights.values()) == pytest.approx(1.0)
    assert max(weights.values()) <= 0.3500001
    assert weights["A"] == pytest.approx(0.35)
    assert weights["B"] > weights["C"] > weights["D"]


def test_eligibility_uses_liquidity_float_market_cap_price_and_history() -> None:
    policy = EligibilityPolicy(
        min_float_market_cap_usd=50_000_000,
        min_median_daily_value_usd=250_000,
        min_price_usd=1.0,
        min_trading_days=20,
    )
    eligible = ConstituentInput("GOOD", 120_000_000, 0.75, 3.0, 900_000, 40)
    illiquid = ConstituentInput("THIN", 120_000_000, 0.75, 3.0, 10_000, 40)

    assert policy.evaluate(eligible).eligible is True
    decision = policy.evaluate(illiquid)
    assert decision.eligible is False
    assert "liquidity" in decision.reason.lower()


def test_point_in_time_membership_respects_listing_and_delisting_dates() -> None:
    assert eligible_on(date(2024, 1, 1), date(2024, 2, 1), None) is False
    assert eligible_on(date(2024, 2, 1), date(2024, 2, 1), None) is True
    assert eligible_on(date(2025, 1, 2), date(2024, 2, 1), date(2025, 1, 1)) is False


def test_index_levels_are_total_return_like_and_start_at_100() -> None:
    levels = normalized_index_levels(
        dates=["2026-01-02", "2026-01-05", "2026-01-06"],
        returns_by_symbol={
            "A": [0.0, 0.10, -0.02],
            "B": [0.0, 0.00, 0.04],
        },
        weights={"A": 0.6, "B": 0.4},
    )

    assert levels[0]["level"] == pytest.approx(100.0)
    assert levels[1]["level"] == pytest.approx(106.0)
    assert levels[2]["level"] == pytest.approx(106.424)


def test_cross_sectional_outliers_report_standard_deviations_clearly() -> None:
    rows = classify_outliers({"A": 0.12, "B": 0.02, "C": -0.01, "D": -0.03})
    by_symbol = {row.symbol: row for row in rows}

    assert by_symbol["A"].z_score > 1.0
    assert by_symbol["A"].label in {"above group", "high outlier"}
    assert by_symbol["D"].z_score < 0
    assert all(row.standard_deviation >= 0 for row in rows)


def test_zero_dispersion_never_produces_nan() -> None:
    rows = classify_outliers({"A": 0.01, "B": 0.01})
    assert {row.z_score for row in rows} == {0.0}
