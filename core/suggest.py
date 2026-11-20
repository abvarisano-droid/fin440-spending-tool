"""Suggested monthly Roth contribution, based on how much someone spends on wants.

The heavier the wants spending, the smaller the share we suggest, so the ask stays realistic:
light (under $200/month) 50%, moderate ($200 to $500) 35%, heavy (over $500) 25%. The amount is
rounded to the nearest $25, at least $25, and never above the IRA limit spread over 12 months.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import tvm

SHARES = {"light": 0.50, "moderate": 0.35, "heavy": 0.25}


@dataclass
class Suggestion:
    monthly: float
    tier: str
    share: float
    wants_monthly: float


def tier_for(wants_monthly: float) -> str:
    if wants_monthly < 200:
        return "light"
    return "moderate" if wants_monthly <= 500 else "heavy"


def suggest_monthly(wants_monthly: float) -> Suggestion:
    wants_monthly = max(float(wants_monthly), 0.0)
    tier = tier_for(wants_monthly)
    share = SHARES[tier]
    amount = max(math.floor(wants_monthly * share / 25 + 0.5) * 25, 25.0)  # nearest $25, halves up
    amount = min(amount, tvm.IRA_LIMIT_2026 / 12)
    return Suggestion(float(amount), tier, share, wants_monthly)


def starting_room(monthly: float) -> float:
    """Most of this year's IRA limit left for a lump-sum start once 12 monthly payments are in."""
    return max(tvm.IRA_LIMIT_2026 - 12 * monthly, 0.0)


def first_year_over(starting: float, monthly: float) -> bool:
    """True when a start plus 12 monthly payments exceeds this year's IRA limit (cent tolerance)."""
    return starting + 12 * monthly > tvm.IRA_LIMIT_2026 + 0.005
