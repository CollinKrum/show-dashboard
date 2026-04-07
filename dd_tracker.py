#!/usr/bin/env python3
import os
import time
import argparse
from datetime import date
from urllib.parse import urljoin

import requests
import pandas as pd

SHOW_BASE = "https://mlb26.theshow.com"
DATA_DIR = "data"
DOCS_DATA_DIR = os.path.join("docs", "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DATA_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36"
})

CARD_NUMERIC_COLS = [
    "ovr", "age", "contact_l", "contact_r", "power_l", "power_r", "vision",
    "discipline", "clutch_h", "bunt", "drag_bunt", "durability", "fielding",
    "arm_strength", "arm_accuracy", "reaction", "blocking", "speed", "stealing",
    "br_aggr", "stamina", "h9_l", "h9_r", "k9_l", "k9_r", "bb9", "hr9",
    "pitch_clutch", "control", "velocity", "break", "best_buy_price",
    "best_sell_price", "buy_order_count", "sell_order_count", "completed_orders",
    "market_spread", "profit_after_tax"
]


def _to_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _list_to_text(value):
    if value is None:
        return ""
    if not isinstance(value, list):
        return str(value)

    cleaned = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = (
                item.get("name")
                or item.get("desc")
                or item.get("description")
                or item.get("value")
                or item.get("short_name")
                or item.get("display_name")
                or str(item)
            )
        else:
            text = str(item)
        if text:
            cleaned.append(text)
    return ", ".join(cleaned)


def fetch_paginated_json(path: str, params: dict | None = None, pause: float = 0.2) -> list[dict]:
    params = dict(params or {})
    page = 1
    rows: list[dict] = []

    while True:
        req_params = dict(params)
        req_params["page"] = page
        url = f"{SHOW_BASE}{path}"
        resp = SESSION.get(url, params=req_params, timeout=25)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items") if isinstance(data, dict) else None
        if items is None:
            if page == 1:
                if isinstance(data, list):
                    return data
                return [data]
            break

        if not items:
            break

        rows.extend(items)
        total_pages = _to_int(data.get("total_pages"), 1)
        print(f"  Page {page}/{total_pages} — {len(rows)} rows so far")
        if page >= total_pages:
            break
        page += 1
        time.sleep(pause)

    return rows


def fetch_show_cards(series_filter: str | None = None, type_filter: str = "mlb_card") -> pd.DataFrame:
    print("Fetching MLB The Show item/card data...")
    raw = fetch_paginated_json("/apis/items.json", {"type": type_filter})

    rows = []
    scanned_at = date.today().isoformat()

    for card in raw:
        series = card.get("series", "")
        if series_filter and series_filter.lower() not in str(series).lower():
            continue

        rows.append({
            "item_id": card.get("id"),
            "uuid": card.get("uuid"),
            "name": card.get("name") or card.get("item_name") or card.get("short_name") or "",
            "series": series,
            "rarity": card.get("rarity", ""),
            "team": card.get("team", ""),
            "team_short": card.get("team_short_name") or card.get("team_abbrev") or "",
            "display_position": card.get("display_position", ""),
            "secondary_positions": _list_to_text(card.get("secondary_positions", [])),
            "is_hitter": bool(card.get("is_hitter", False)),
            "is_pitcher": bool(card.get("is_pitcher", False)) or not bool(card.get("is_hitter", False)),
            "ovr": _to_int(card.get("ovr")),
            "bat_hand": card.get("bat_hand", ""),
            "throw_hand": card.get("throw_hand", ""),
            "age": _to_int(card.get("age"), default=-1),
            "born": card.get("born", ""),
            "height": card.get("height", ""),
            "weight": card.get("weight", ""),
            "img": card.get("img") or card.get("image") or "",
            "contact_l": _to_int(card.get("contact_left")),
            "contact_r": _to_int(card.get("contact_right")),
            "power_l": _to_int(card.get("power_left")),
            "power_r": _to_int(card.get("power_right")),
            "vision": _to_int(card.get("plate_vision")),
            "discipline": _to_int(card.get("plate_discipline")),
            "clutch_h": _to_int(card.get("batting_clutch")),
            "bunt": _to_int(card.get("bunting_ability")),
            "drag_bunt": _to_int(card.get("drag_bunting_ability")),
            "durability": _to_int(card.get("durability")),
            "fielding": _to_int(card.get("fielding_ability")),
            "arm_strength": _to_int(card.get("arm_strength")),
            "arm_accuracy": _to_int(card.get("arm_accuracy")),
            "reaction": _to_int(card.get("reaction_time")),
            "blocking": _to_int(card.get("blocking")),
            "speed": _to_int(card.get("speed")),
            "stealing": _to_int(card.get("stealing_ability")),
            "br_aggr": _to_int(card.get("base_running_aggression")),
            "stamina": _to_int(card.get("stamina")),
            "h9_l": _to_int(card.get("hits_per_bf_left")),
            "h9_r": _to_int(card.get("hits_per_bf_right")),
            "k9_l": _to_int(card.get("k_per_bf_left")),
            "k9_r": _to_int(card.get("k_per_bf_right")),
            "bb9": _to_int(card.get("bb_per_bf")),
            "hr9": _to_int(card.get("hr_per_bf")),
            "pitch_clutch": _to_int(card.get("pitching_clutch")),
            "control": _to_int(card.get("pitch_control")),
            "velocity": _to_int(card.get("pitch_velocity")),
            "break": _to_int(card.get("pitch_movement")),
            "pitch_1": card.get("pitch_1", ""),
            "pitch_2": card.get("pitch_2", ""),
            "pitch_3": card.get("pitch_3", ""),
            "pitch_4": card.get("pitch_4", ""),
            "pitch_5": card.get("pitch_5", ""),
            "quirks": _list_to_text(card.get("quirks", [])),
            "location": card.get("location") or card.get("set_name") or "",
            "has_augments": bool(card.get("has_augments", False)),
            "trend": card.get("trend", ""),
            "new_rank": card.get("new_rank", ""),
            "scanned_at": scanned_at,
        })

    df = pd.DataFrame(rows)
    for col in CARD_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")
    return df


def fetch_bulk_listings() -> pd.DataFrame:
    print("Fetching bulk marketplace listings...")
    try:
        raw = fetch_paginated_json("/apis/listings.json")
    except Exception as e:
        print(f"  Bulk listings endpoint failed: {e}")
        return pd.DataFrame()

    rows = []
    scanned_at = date.today().isoformat()
    for x in raw:
        item = x.get("item") if isinstance(x.get("item"), dict) else {}
        rows.append({
            "item_id": x.get("item_id") or item.get("id") or x.get("id"),
            "uuid": x.get("uuid") or item.get("uuid"),
            "best_buy_price": _to_int(x.get("best_buy_price") or x.get("buy_price") or x.get("best_buy")),
            "best_sell_price": _to_int(x.get("best_sell_price") or x.get("sell_price") or x.get("best_sell")),
            "buy_order_count": _to_int(x.get("buy_order_count") or x.get("num_buy_orders")),
            "sell_order_count": _to_int(x.get("sell_order_count") or x.get("num_sell_orders")),
            "completed_orders": _to_int(x.get("completed_orders")),
            "market_name": x.get("name") or item.get("name") or item.get("item_name") or "",
            "scanned_at": scanned_at,
        })
    df = pd.DataFrame(rows)
    for col in ["best_buy_price", "best_sell_price", "buy_order_count", "sell_order_count", "completed_orders"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")
    return df


def fetch_listing_for_item(item_id=None, uuid=None, pause: float = 0.05):
    """
    Best-effort single-item listing fetch.
    The Show endpoints can vary, so this tries several common parameter names
    and accepts either a dict or the first row from an items array.
    """
    candidates = []
    if item_id not in (None, "", 0):
        candidates.extend([
            {"item_id": item_id},
            {"id": item_id},
            {"item": item_id},
        ])
    if uuid:
        candidates.extend([
            {"uuid": uuid},
            {"item_uuid": uuid},
        ])

    for params in candidates:
        try:
            resp = SESSION.get(f"{SHOW_BASE}/apis/listing.json", params=params, timeout=20)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if isinstance(data, dict) and data.get("listing"):
                payload = data["listing"]
            elif isinstance(data, dict) and data.get("item"):
                payload = data
            elif isinstance(data, dict) and any(k in data for k in ("best_buy_price", "best_sell_price", "buy_price", "sell_price")):
                payload = data
            elif isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
                payload = data["items"][0]
            else:
                continue

            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
            row = {
                "item_id": payload.get("item_id") or item.get("id") or item_id,
                "uuid": payload.get("uuid") or item.get("uuid") or uuid,
                "best_buy_price": _to_int(payload.get("best_buy_price") or payload.get("buy_price") or payload.get("best_buy")),
                "best_sell_price": _to_int(payload.get("best_sell_price") or payload.get("sell_price") or payload.get("best_sell")),
                "buy_order_count": _to_int(payload.get("buy_order_count") or payload.get("num_buy_orders")),
                "sell_order_count": _to_int(payload.get("sell_order_count") or payload.get("num_sell_orders")),
                "completed_orders": _to_int(payload.get("completed_orders")),
                "market_name": payload.get("name") or item.get("name") or "",
                "listing_source": "per_item",
                "scanned_at": date.today().isoformat(),
            }
            time.sleep(pause)
            return row
        except Exception:
            continue
    return None


def fetch_listings_for_cards(cards: pd.DataFrame, mode: str = "auto", limit: int | None = None) -> pd.DataFrame:
    """
    Modes:
      - auto: try bulk first; if it returns too few rows, crawl item-by-item
      - bulk: only bulk listings.json
      - per_item: iterate each card through listing.json
      - none: skip market data
    """
    if mode == "none":
        return pd.DataFrame()

    if mode in {"auto", "bulk"}:
        bulk = fetch_bulk_listings()
        if mode == "bulk":
            return bulk
        if len(bulk) >= max(50, int(len(cards) * 0.10)):
            print(f"Bulk listings look usable ({len(bulk)} rows).")
            return bulk
        print(f"Bulk listings look too small ({len(bulk)} rows). Falling back to item-by-item crawl...")

    rows = []
    subset = cards.head(limit) if limit else cards
    total = len(subset)
    for idx, row in enumerate(subset.itertuples(index=False), start=1):
        if idx % 50 == 0 or idx == 1 or idx == total:
            print(f"  Listing crawl {idx}/{total}")
        listing = fetch_listing_for_item(
            item_id=getattr(row, "item_id", None),
            uuid=getattr(row, "uuid", None),
        )
        if listing:
            rows.append(listing)

    df = pd.DataFrame(rows)
    for col in ["best_buy_price", "best_sell_price", "buy_order_count", "sell_order_count", "completed_orders"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")
    return df


def combine_cards_and_market(cards: pd.DataFrame, listings: pd.DataFrame) -> pd.DataFrame:
    df = cards.copy()

    if not listings.empty:
        use_uuid = "uuid" in df.columns and "uuid" in listings.columns and listings["uuid"].notna().any()
        key = "uuid" if use_uuid else "item_id"

        deduped = listings.drop_duplicates(subset=[key], keep="first")
        df = df.merge(deduped, on=key, how="left", suffixes=("", "_market"))

        if "best_buy_price" not in df.columns:
            df["best_buy_price"] = 0
        if "best_sell_price" not in df.columns:
            df["best_sell_price"] = 0

        df["market_spread"] = (
            pd.to_numeric(df["best_sell_price"], errors="coerce").fillna(0) -
            pd.to_numeric(df["best_buy_price"], errors="coerce").fillna(0)
        ).astype("Int64")

        df["profit_after_tax"] = (
            pd.to_numeric(df["best_sell_price"], errors="coerce").fillna(0) * 0.9 -
            pd.to_numeric(df["best_buy_price"], errors="coerce").fillna(0)
        ).round(0).astype("Int64")

        df["is_profitable"] = df["profit_after_tax"].fillna(0) > 0

    for col in CARD_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    return df


def save_outputs(cards: pd.DataFrame, combined: pd.DataFrame, listings: pd.DataFrame):
    today = date.today().isoformat()

    dated_cards = os.path.join(DATA_DIR, f"show_cards_{today}.csv")
    latest_cards = os.path.join(DATA_DIR, "show_cards_latest.csv")
    docs_cards = os.path.join(DOCS_DATA_DIR, "show_cards_latest.csv")

    cards.to_csv(dated_cards, index=False)
    cards.to_csv(latest_cards, index=False)
    cards.to_csv(docs_cards, index=False)

    print(f"Saved cards → {dated_cards}")
    print(f"Saved cards → {latest_cards}")
    print(f"Saved cards → {docs_cards}")

    if not listings.empty:
        dated_listings = os.path.join(DATA_DIR, f"show_listings_{today}.csv")
        latest_listings = os.path.join(DATA_DIR, "show_listings_latest.csv")
        docs_listings = os.path.join(DOCS_DATA_DIR, "show_listings_latest.csv")
        listings.to_csv(dated_listings, index=False)
        listings.to_csv(latest_listings, index=False)
        listings.to_csv(docs_listings, index=False)
        print(f"Saved listings → {dated_listings}")
        print(f"Saved listings → {latest_listings}")
        print(f"Saved listings → {docs_listings}")

    combined_path = os.path.join(DATA_DIR, "show_dataset_latest.csv")
    combined_docs_path = os.path.join(DOCS_DATA_DIR, "show_dataset_latest.csv")
    combined.to_csv(combined_path, index=False)
    combined.to_csv(combined_docs_path, index=False)
    print(f"Saved combined dataset → {combined_path}")
    print(f"Saved combined dataset → {combined_docs_path}")


def print_summary(cards: pd.DataFrame, combined: pd.DataFrame, listings: pd.DataFrame):
    print("\n" + "=" * 80)
    print(f"MLB THE SHOW 26 SNAPSHOT — {date.today()}")
    print("=" * 80)
    print(f"Cards: {len(cards):,}")
    print(f"Cards with market rows: {combined['best_buy_price'].fillna(0).gt(0).sum():,}" if "best_buy_price" in combined.columns else "Cards with market rows: 0")
    if "series" in cards.columns:
        print("\nTop series:")
        print(cards["series"].fillna("Unknown").value_counts().head(10).to_string())
    if "best_buy_price" in combined.columns:
        market = combined[combined["best_buy_price"].fillna(0) > 0].copy()
        if not market.empty:
            cols = [c for c in ["name", "series", "rarity", "ovr", "best_buy_price", "best_sell_price", "profit_after_tax"] if c in market.columns]
            print("\nTop 15 by buy price:")
            print(market.sort_values("best_buy_price", ascending=False)[cols].head(15).to_string(index=False))
    print("\nStatic site data refreshed in docs/data/.")
    print("Commit the repo, then GitHub Pages can serve docs/index.html from the docs folder.")


def run():
    parser = argparse.ArgumentParser(description="MLB The Show 26 cards + marketplace snapshot for GitHub Pages")
    parser.add_argument("--series", "-s", default=None, help="Filter cards by series name")
    parser.add_argument("--type", "-t", default="mlb_card", help="Item type, default mlb_card")
    parser.add_argument("--market-mode", choices=["auto", "bulk", "per_item", "none"], default="auto")
    parser.add_argument("--market-limit", type=int, default=None, help="Limit per-item market crawl for testing")
    args = parser.parse_args()

    cards = fetch_show_cards(series_filter=args.series, type_filter=args.type)
    listings = fetch_listings_for_cards(cards, mode=args.market_mode, limit=args.market_limit)
    combined = combine_cards_and_market(cards, listings)

    save_outputs(cards, combined, listings)
    print_summary(cards, combined, listings)


if __name__ == "__main__":
    run()
