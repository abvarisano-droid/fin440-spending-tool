"""Read any bank or card CSV and normalize it to one schema.

Output schema (one row per spending transaction):
    date (datetime64, day precision), description (str), amount (float, positive = money spent),
    category (str)

Nothing here touches disk except reading the file object it is given.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

DATE_HINTS = ("transaction date", "trans date", "date", "posted", "post date", "posting date")
DESC_HINTS = ("description", "merchant", "payee", "name", "details", "memo", "narrative")
AMOUNT_HINTS = ("amount", "amt", "value", "transaction amount")
DEBIT_HINTS = ("debit", "withdrawal", "withdrawals", "money out", "spent")
CREDIT_HINTS = ("credit", "deposit", "deposits", "money in")
CATEGORY_HINTS = ("category", "type of spend", "spend category")


@dataclass
class ColumnMap:
    date: str | None = None
    description: str | None = None
    amount: str | None = None  # single signed column
    debit: str | None = None  # or a debit/credit pair
    credit: str | None = None
    category: str | None = None

    def is_complete(self) -> bool:
        has_money = self.amount is not None or self.debit is not None
        return self.date is not None and self.description is not None and has_money


def read_csv(file) -> pd.DataFrame:
    """Read an uploaded file object or path. Tries UTF-8 first, then Latin-1."""
    raw = file.read() if hasattr(file, "read") else open(file, "rb").read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=enc, skip_blank_lines=True)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def _match(columns: list[str], hints: tuple[str, ...], taken: set[str]) -> str | None:
    lowered = {c: c.lower().strip() for c in columns if c not in taken}
    # exact match in hint priority order, then substring match
    for hint in hints:
        for col, low in lowered.items():
            if low == hint:
                return col
    for hint in hints:
        for col, low in lowered.items():
            if hint in low:
                return col
    return None


def _mostly_dates(s: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s):  # floats would parse as epoch timestamps
        return False
    parsed = pd.to_datetime(s, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() > 0.8)


def detect_columns(df: pd.DataFrame) -> ColumnMap:
    cols = list(df.columns)
    taken: set[str] = set()
    m = ColumnMap()

    m.date = _match(cols, DATE_HINTS, taken)
    if m.date is None:
        for c in cols:
            if _mostly_dates(df[c]):
                m.date = c
                break
    if m.date:
        taken.add(m.date)

    m.debit = _match(cols, DEBIT_HINTS, taken)
    if m.debit:
        taken.add(m.debit)
        m.credit = _match(cols, CREDIT_HINTS, taken)
        if m.credit:
            taken.add(m.credit)

    if m.debit is None:
        m.amount = _match(cols, AMOUNT_HINTS, taken)
        if m.amount is None:
            for c in cols:
                if (c not in taken and not _mostly_dates(df[c])
                        and to_number(df[c]).notna().mean() > 0.8):
                    m.amount = c
                    break
        if m.amount:
            taken.add(m.amount)

    m.description = _match(cols, DESC_HINTS, taken)
    if m.description:
        taken.add(m.description)
    else:
        text_cols = [c for c in cols if c not in taken and not pd.api.types.is_numeric_dtype(df[c])]
        if text_cols:
            m.description = max(text_cols, key=lambda c: df[c].astype(str).str.len().mean())
            taken.add(m.description)

    m.category = _match(cols, CATEGORY_HINTS, taken)
    return m


def to_number(s: pd.Series) -> pd.Series:
    """Parse '$1,234.56', '(12.00)', '-12', '12.00 CR' style strings to floats."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    txt = s.astype(str).str.strip()
    negative = txt.str.startswith("(") & txt.str.endswith(")")
    negative |= txt.str.upper().str.endswith("CR")
    cleaned = txt.str.replace(r"[^\d.\-]", "", regex=True)
    nums = pd.to_numeric(cleaned, errors="coerce")
    return nums.where(~negative, -nums.abs())


def guess_purchases_negative(df: pd.DataFrame, m: ColumnMap) -> bool:
    """True if purchases are stored as negative numbers (Chase, most banks).
    False if purchases are positive (Amex, Discover)."""
    if m.amount is None:
        return False
    vals = to_number(df[m.amount]).dropna()
    return bool((vals < 0).sum() > (vals > 0).sum())


def normalize(df: pd.DataFrame, m: ColumnMap, purchases_negative: bool) -> pd.DataFrame:
    """Return only spending rows in the standard schema. Refunds, deposits and
    card payments received are dropped (they are not spending)."""
    if not m.is_complete():
        raise ValueError("Column mapping needs a date, a description and an amount (or debit) column.")

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[m.date], errors="coerce", format="mixed").dt.normalize()
    out["description"] = df[m.description].astype(str).str.strip()

    if m.debit is not None:
        spend = to_number(df[m.debit]).fillna(0).abs()
        if m.credit is not None:
            # a row with only a credit is income or a refund; zero it out
            spend = spend.where(to_number(df[m.credit]).fillna(0) == 0, 0.0)
    else:
        raw = to_number(df[m.amount])
        spend = -raw if purchases_negative else raw

    out["amount"] = spend.round(2)
    out["bank_category"] = df[m.category].astype(str).str.strip() if m.category else ""

    out = out.dropna(subset=["date", "amount"])
    out = out[out["amount"] > 0]
    return out.sort_values("date").reset_index(drop=True)


