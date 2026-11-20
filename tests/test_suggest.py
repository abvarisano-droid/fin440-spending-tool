"""Suggested Roth contribution tiers: hand-picked edges, not the module's own constants."""
import pytest

from core.suggest import first_year_over, monthly_from_share, starting_room, suggest_monthly


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


def test_start_leaves_room_for_twelve_payments():
    # 2026 limit $7,500: a $300/month plan leaves $3,900 for a lump-sum start
    assert starting_room(300) == 3900
    assert starting_room(625) == 0
    assert not first_year_over(3684.72, 150)       # sample: $5,484.72
    assert first_year_over(6963.81, 300)           # every category: $10,563.81
    assert not first_year_over(3900, 300)


def test_any_share_uses_the_same_rounding():
    assert monthly_from_share(614.12, 0.50) == 300   # 307.06 -> 300
    assert monthly_from_share(614.12, 0.10) == 50    # 61.41 -> 50
    assert monthly_from_share(614.12, 1.00) == 625   # 614.12 -> 625 = 7,500 / 12, also the cap
    assert monthly_from_share(30.0, 0.05) == 25      # 1.50 -> the $25 floor
