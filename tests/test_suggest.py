"""Suggested Roth contribution tiers: hand-picked edges, not the module's own constants."""
import pytest

from core.suggest import suggest_monthly


@pytest.mark.parametrize("wants, tier, share", [
    (0.0, "light", 0.50), (199.99, "light", 0.50), (200.0, "moderate", 0.35),
    (500.0, "moderate", 0.35), (500.01, "heavy", 0.25), (5000.0, "heavy", 0.25),
])
def test_tier_edges(wants, tier, share):
    s = suggest_monthly(wants)
    assert (s.tier, s.share) == (tier, share)


def test_rounds_to_nearest_25():
    assert suggest_monthly(614.12).monthly == 150   # 25% = 153.53
    assert suggest_monthly(300.0).monthly == 100    # 35% = 105 -> 100
    assert suggest_monthly(150.0).monthly == 75     # 50% = 75
    assert suggest_monthly(125.0).monthly == 75     # 50% = 62.50, halves round up


def test_minimum_and_ira_cap():
    assert suggest_monthly(10.0).monthly == 25      # 50% = 5, floor of $25
    assert suggest_monthly(4000.0).monthly == 625   # 25% = 1,000, capped at 7,500 / 12
