"""User edits to the loaded transactions: ignore rows, rename categories, split them.

Every edit returns a new DataFrame (the caller stores it in session state), and keeps the
`discretionary` column right, since the Shadow and Roth pages pick wants by that column, not
by category name. Custom categories carry their own want/need flag in `wants_map`.
"""

from __future__ import annotations

import pandas as pd

from core.categorize import ALL_CATEGORIES, DISCRETIONARY, NON_SPEND

MAX_NAME = 30


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Older frames (or a fresh upload) get an all-False `ignored` column."""
    return df if "ignored" in df.columns else df.assign(ignored=False)


def is_want(category: str, wants_map: dict[str, bool]) -> bool:
    return wants_map.get(category, category in DISCRETIONARY)


def ordered_categories(df: pd.DataFrame, extra: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Built-in categories in their usual order, then custom ones A to Z. Only those present
    in `df` (plus any `extra`)."""
    present = set(df["category"]) | set(extra)
    built_in = [c for c in ALL_CATEGORIES if c in present]
    return built_in + sorted(present - set(ALL_CATEGORIES))


def want_categories(df: pd.DataFrame) -> list[str]:
    """Categories with any wants spending, in display order."""
    return ordered_categories(df[df["discretionary"]]) if not df.empty else []


def clean_name(name: str, *, existing: list[str] | None = None, allow_existing: bool = True) -> str:
    """Trimmed name, or ValueError with a message for the page."""
    name = " ".join(str(name).split())
    if not name:
        raise ValueError("Type a category name.")
    if len(name) > MAX_NAME:
        raise ValueError(f"Keep the name to {MAX_NAME} characters or fewer.")
    if name in NON_SPEND:
        raise ValueError(f"\"{name}\" is reserved for card payments and transfers.")
    if not allow_existing and existing and name.casefold() in {e.casefold() for e in existing}:
        raise ValueError(f"\"{name}\" already exists. Pick another name.")
    return name


def set_ignored(df: pd.DataFrame, ignored: pd.Series) -> pd.DataFrame:
    """Replace the ignored flags (aligned by position)."""
    out = ensure_columns(df).copy()
    out["ignored"] = pd.Series(ignored).astype(bool).values
    return out


def recategorize(df: pd.DataFrame, categories: pd.Series, wants_map: dict[str, bool]) -> pd.DataFrame:
    """Replace the categories (aligned by position) and recompute wants from them."""
    out = df.copy()
    out["category"] = pd.Series(categories).values
    out["discretionary"] = out["category"].map(lambda c: is_want(c, wants_map)).astype(bool)
    return out


def rename_category(df: pd.DataFrame, old: str, new: str,
                    wants_map: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, bool]]:
    """Every `old` row becomes `new`. A new name keeps the old want/need flag; renaming onto an
    existing category merges into it and takes that category's flag."""
    if old in NON_SPEND:
        raise ValueError(f"\"{old}\" can't be renamed: it keeps card payments out of your totals.")
    new = clean_name(new)
    if new == old:
        raise ValueError("That's the same name.")
    wants_map = dict(wants_map)
    merging = new in set(df["category"]) or new in ALL_CATEGORIES or new in wants_map
    if not merging:
        wants_map[new] = is_want(old, wants_map)
    out = df.copy()
    rows = out["category"] == old
    out.loc[rows, "category"] = new
    out.loc[rows, "discretionary"] = is_want(new, wants_map)
    wants_map.pop(old, None)
    return out, wants_map


def split_category(df: pd.DataFrame, source: str, merchants: list[str], new: str, want: bool,
                   wants_map: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, bool]]:
    """Move the `source` rows whose description is in `merchants` into a new category `new`,
    flagged as a want or a need. Shopping -> Clothing (Nike, Zara) leaves the rest in Shopping."""
    if source in NON_SPEND:
        raise ValueError(f"\"{source}\" can't be split.")
    new = clean_name(new, existing=ordered_categories(df, list(wants_map)), allow_existing=False)
    if not merchants:
        raise ValueError("Pick at least one merchant to move.")
    rows = (df["category"] == source) & df["description"].isin(merchants)
    if not rows.any():
        raise ValueError(f"None of those merchants are in {source}.")
    wants_map = dict(wants_map)
    wants_map[new] = bool(want)
    out = df.copy()
    out.loc[rows, "category"] = new
    out.loc[rows, "discretionary"] = bool(want)
    return out, wants_map
