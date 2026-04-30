#!/usr/bin/env python3
"""
build_showfield_data.py

Post-processes dd_tracker.py output into one fast site bundle:
  docs/data/showfield_data.json
  data/showfield_data.json

Run after dd_tracker.py in Render:
  python dd_tracker.py && python build_showfield_data.py && git add docs/data data ...
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"


def _clean_value(value):
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = []
    for row in df.to_dict(orient="records"):
        out.append({str(k): _clean_value(v) for k, v in row.items()})
    return out


def _read_latest(name: str) -> pd.DataFrame:
    json_path = DOCS_DATA_DIR / f"{name}.json"
    csv_path = DOCS_DATA_DIR / f"{name}.csv"
    if json_path.exists() and json_path.stat().st_size > 2:
        try:
            return pd.read_json(json_path)
        except Exception:
            pass
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def _num(series, default=0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def enrich_cards(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    for col in [
        "ovr", "best_buy_price", "best_sell_price", "profit_after_tax", "speed",
        "fielding", "contact_l", "contact_r", "power_l", "power_r", "control",
        "break", "velocity", "pitch_clutch", "buy_order_count", "sell_order_count",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = _num(df[col])

    buy = df["best_buy_price"]
    sell = df["best_sell_price"]
    profit = df["profit_after_tax"]

    if "roi" not in df.columns:
        df["roi"] = 0.0
    df["roi"] = [round((p / b) * 100, 2) if b and b > 0 else 0 for p, b in zip(profit, buy)]

    df["has_market"] = buy.gt(0) | sell.gt(0)
    df["avg_contact"] = ((_num(df["contact_l"]) + _num(df["contact_r"])) / 2).round(1)
    df["avg_power"] = ((_num(df["power_l"]) + _num(df["power_r"])) / 2).round(1)
    df["hitter_fit_score"] = (df["ovr"] * 2 + df["avg_contact"] + df["avg_power"] + df["speed"] + df["fielding"]).round(1)
    df["pitcher_fit_score"] = (df["ovr"] * 3 + df["control"] + df["break"] + df["velocity"] + df["pitch_clutch"]).round(1)

    # Simple confidence score for flipping: profit matters most, ROI helps, and active order counts help a little.
    confidence = []
    for p, roi, buys, sells in zip(profit, df["roi"], df["buy_order_count"], df["sell_order_count"]):
        score = 0
        if p > 0:
            score += min(45, p / 150)
        if roi > 0:
            score += min(35, roi * 4)
        score += min(20, (buys + sells) / 50)
        confidence.append(round(max(0, min(100, score)), 1))
    df["flip_confidence"] = confidence

    tags = []
    for _, row in df.iterrows():
        card_tags = []
        if row.get("profit_after_tax", 0) > 0:
            card_tags.append("profitable")
        if row.get("flip_confidence", 0) >= 70:
            card_tags.append("high-confidence")
        if row.get("roi", 0) >= 5:
            card_tags.append("strong-roi")
        if row.get("ovr", 0) >= 90:
            card_tags.append("elite-ovr")
        if str(row.get("rarity", "")).lower() == "diamond":
            card_tags.append("diamond")
        tags.append(card_tags)
    df["tags"] = tags

    return df


def main() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    cards = _read_latest("show_dataset_latest")
    if cards.empty:
        cards = _read_latest("show_cards_latest")
    cards = enrich_cards(cards)

    profitable = cards[cards.get("profit_after_tax", pd.Series(dtype=float)).fillna(0).gt(0)].copy() if not cards.empty else pd.DataFrame()
    if not profitable.empty:
        profitable = profitable.sort_values(["flip_confidence", "profit_after_tax"], ascending=False)

    value = cards[cards.get("has_market", pd.Series(dtype=bool)) == True].copy() if not cards.empty and "has_market" in cards.columns else pd.DataFrame()
    if not value.empty:
        value["value_score_v2"] = [round((ovr / sell) * 10000, 2) if sell and sell > 0 else 0 for ovr, sell in zip(value["ovr"], value["best_sell_price"])]
        value = value.sort_values(["value_score_v2", "ovr"], ascending=False)

    meta = {}
    last_updated = {}
    for name in ["last_updated", "site_meta"]:
        p = DOCS_DATA_DIR / f"{name}.json"
        if p.exists() and p.stat().st_size > 2:
            try:
                last_updated = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass

    bundle = {
        "version": "showfield_data_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": last_updated,
        "summary": {
            "cards": int(len(cards)),
            "market_cards": int(cards["has_market"].sum()) if not cards.empty and "has_market" in cards.columns else 0,
            "profitable_cards": int(len(profitable)),
            "best_profit": int(profitable["profit_after_tax"].max()) if not profitable.empty else 0,
            "best_roi": float(profitable["roi"].max()) if not profitable.empty and "roi" in profitable.columns else 0,
        },
        "cards": _records(cards),
        "profitable": _records(profitable.head(250)),
        "value": _records(value.head(250)),
        "meta": meta,
    }

    text = json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for out in [DOCS_DATA_DIR / "showfield_data.json", DATA_DIR / "showfield_data.json"]:
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out.relative_to(ROOT)} ({len(text):,} bytes)")


if __name__ == "__main__":
    main()
