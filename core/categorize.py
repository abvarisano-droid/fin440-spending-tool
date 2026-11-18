"""Keyword categorizer. First matching rule wins, so order matters
(e.g. 'UBER EATS' must hit Dining before 'UBER' hits Transport)."""

from __future__ import annotations

import pandas as pd

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Transfers & Payments", ("payment thank you", "autopay", "transfer", "venmo cashout",
                              "credit card payment", "online payment", "epay", "zelle to self")),
    ("Dining", ("uber eats", "doordash", "grubhub", "postmates", "restaurant", "grill", "pizza",
                "chipotle", "mcdonald", "taco bell", "chick-fil-a", "wendy", "burger", "sushi",
                "cafe", "diner", "kitchen", "panera", "subway", "wingstop", "raising cane")),
    ("Coffee", ("starbucks", "dunkin", "coffee", "espresso", "dutch bros", "peet")),
    ("Groceries", ("kroger", "walmart grocery", "whole foods", "trader joe", "aldi", "publix",
                   "safeway", "h-e-b", "wegmans", "costco", "sam's club", "grocery", "supermarket")),
    ("Gas", ("shell", "exxon", "chevron", "bp ", "speedway", "marathon", "circle k", "wawa",
             "sunoco", "valero", "fuel", "gas station")),
    ("Transport", ("uber", "lyft", "transit", "parking", "metro", "toll", "amtrak", "bird", "lime")),
    ("Subscriptions", ("netflix", "spotify", "hulu", "disney+", "disney plus", "apple.com/bill",
                       "youtube premium", "hbo", "max.com", "paramount", "peacock", "chatgpt",
                       "openai", "adobe", "amazon prime", "patreon", "icloud", "subscription")),
    ("Entertainment", ("ticketmaster", "stubhub", "cinema", "amc ", "regal", "steam", "playstation",
                       "xbox", "nintendo", "concert", "bowling", "bar ", "brewery", "tavern")),
    ("Travel", ("airline", "delta air", "united air", "american air", "southwest", "spirit air",
                "hotel", "marriott", "hilton", "airbnb", "expedia", "booking.com")),
    ("Shopping", ("amazon", "amzn", "target", "walmart", "best buy", "nike", "apple store",
                  "etsy", "ebay", "shein", "zara", "h&m", "ulta", "sephora", "tj maxx", "marshalls")),
    ("Health", ("cvs", "walgreens", "pharmacy", "doctor", "dental", "clinic", "gym",
                "planet fitness", "hospital")),
    ("Housing & Utilities", (" rent ", "rent payment", "electric", "water", "utility", "comcast", "xfinity",
                             "spectrum", "at&t", "verizon", "t-mobile", "internet", "insurance")),
    ("Education", ("tuition", "bookstore", "chegg", "pearson", "mcgraw", "university", "college")),
]

# Wants, not needs. The Roth page can redirect a share of these. Transport (rides, transit,
# parking, tolls) counts as a need, the same as Gas, because most of it is getting to work/class.
DISCRETIONARY = frozenset({"Dining", "Coffee", "Entertainment", "Shopping", "Subscriptions",
                           "Travel"})

# Not real spending, excluded from totals by default
NON_SPEND = frozenset({"Transfers & Payments"})

ALL_CATEGORIES = [name for name, _ in RULES] + ["Other"]


def categorize_one(description: str) -> str:
    d = f" {description.lower()} "
    for name, keywords in RULES:
        if any(k in d for k in keywords):
            return name
    return "Other"


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """Adds 'category' and 'discretionary' columns. Our rules decide; the bank's own
    category is kept in 'bank_category' for reference only, so categories are consistent
    across banks."""
    out = df.copy()
    out["category"] = out["description"].map(categorize_one)
    out["discretionary"] = out["category"].isin(DISCRETIONARY)
    return out
