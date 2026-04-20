#!/usr/bin/env python3
"""
dd_tracker.py — MLB The Show 26 Diamond Dynasty card + market snapshot
Fetches cards, listings, and roster-update data from the public Show API,
then writes CSVs for the GitHub Pages dashboard.
"""

import os
import json
import time
import argparse
from datetime import date
from statistics import mean

import requests
import pandas as pd

SHOW_BASE = "https://mlb26.theshow.com"
DATA_DIR = "data"
DOCS_DATA_DIR = os.path.join("docs", "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DATA_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
})

CARD_NUMERIC_COLS = [
    "ovr", "age", "series_year",
    "contact_l", "contact_r", "power_l", "power_r", "vision",
    "discipline", "clutch_h", "bunt", "drag_bunt",
    "hitting_durability", "fielding_durability",
    "fielding", "arm_strength", "arm_accuracy", "reaction", "blocking",
    "speed", "stealing", "baserunning_ability", "br_aggr",
    "stamina", "hits_per_bf", "k_per_bf", "bb9", "hr9",
    "pitch_clutch", "control", "velocity", "break",
    "best_buy_price", "best_sell_price",
    "buy_order_count", "sell_order_count", "completed_orders",
    "market_spread", "profit_after_tax",
]

SERIES_IDS = {
    "live":            1337,
    "rookie":         10001,
    "breakout":       10002,
    "veteran":        10003,
    "allstar":        10004,
    "awards":         10005,
    "postseason":     10006,
    "signature":      10009,
    "prime":          10013,
    "toppsnow":       10017,
    "2ndhalf":        10020,
    "milestone":      10022,
    "wbc":            10028,
    "standout":       10034,
    "negroleagues":   10035,
    "springbreakout": 10039,
    "contributor":    10044,
    "lastride":       10045,
    "jolt":           10046,
    "cornerstone":    10049,
    "newthreads":     10050,
    "ranked1000":     10052,
    "stpatricks":     10062,
}


def _to_int(v, default=0):
    try:
        if v is None or v == "" or v == "-":
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


def _parse_pitches(raw_pitches):
    result = {}
    if not isinstance(raw_pitches, list):
        for i in range(1, 6):
            result[f"pitch_{i}"] = ""
            result[f"pitch_{i}_speed"] = 0
            result[f"pitch_{i}_control"] = 0
            result[f"pitch_{i}_movement"] = 0
        return result

    for i in range(1, 6):
        if i - 1 < len(raw_pitches):
            p = raw_pitches[i - 1]
            result[f"pitch_{i}"] = p.get("name", "")
            result[f"pitch_{i}_speed"] = _to_int(p.get("speed"))
            result[f"pitch_{i}_control"] = _to_int(p.get("control"))
            result[f"pitch_{i}_movement"] = _to_int(p.get("movement"))
        else:
            result[f"pitch_{i}"] = ""
            result[f"pitch_{i}_speed"] = 0
            result[f"pitch_{i}_control"] = 0
            result[f"pitch_{i}_movement"] = 0
    return result


def fetch_paginated_json(
    path: str,
    params: dict | None = None,
    pause: float = 0.2,
    items_key: str = "items",
) -> list[dict]:
    params = dict(params or {})
    page = 1
    rows: list[dict] = []

    while True:
        req_params = {**params, "page": page}
        url = f"{SHOW_BASE}{path}"
        resp = SESSION.get(url, params=req_params, timeout=25)
        resp.raise_for_status()
        data = resp.json()

        items = data.get(items_key) if isinstance(data, dict) else None
        if items is None:
            if page == 1:
                return data if isinstance(data, list) else [data]
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


def fetch_metadata() -> dict:
    print("Fetching metadata (series, brands, sets)...")
    resp = SESSION.get(f"{SHOW_BASE}/apis/meta_data.json", timeout=20)
    resp.raise_for_status()
    data = resp.json()

    series_list = data.get("series", [])
    brands_list = data.get("brands", [])
    sets_list = data.get("sets", [])

    series_by_id = {
        s["series_id"]: s["name"]
        for s in series_list
        if isinstance(s, dict) and s.get("series_id", -1) != -1
    }
    brand_by_id = {
        b["brand_id"]: b["name"]
        for b in brands_list
        if isinstance(b, dict) and b.get("brand_id", -1) != -1
    }

    print(f"  {len(series_by_id)} series, {len(brand_by_id)} brands, {len(sets_list)} sets")
    return {
        "series": series_list,
        "brands": brands_list,
        "sets": sets_list,
        "series_by_id": series_by_id,
        "brand_by_id": brand_by_id,
    }


def save_metadata(meta: dict):
    for key, label in [("series", "series"), ("brands", "brands")]:
        rows = meta.get(key, [])
        if rows:
            df = pd.DataFrame(rows)
            for subdir in [DATA_DIR, DOCS_DATA_DIR]:
                df.to_csv(os.path.join(subdir, f"meta_{label}.csv"), index=False)
            print(f"  Saved metadata → meta_{label}.csv")

    sets_list = meta.get("sets", [])
    if sets_list:
        df_sets = pd.DataFrame({"set_name": sets_list})
        for subdir in [DATA_DIR, DOCS_DATA_DIR]:
            df_sets.to_csv(os.path.join(subdir, "meta_sets.csv"), index=False)
        print(f"  Saved metadata → meta_sets.csv ({len(sets_list)} sets)")


def fetch_roster_updates() -> pd.DataFrame:
    print("Fetching roster updates...")
    resp = SESSION.get(f"{SHOW_BASE}/apis/roster_updates.json", timeout=20)
    resp.raise_for_status()
    updates = resp.json().get("roster_updates", [])

    if not updates:
        print("  No roster updates found.")
        return pd.DataFrame()

    df_list = pd.DataFrame(updates)
    for subdir in [DATA_DIR, DOCS_DATA_DIR]:
        df_list.to_csv(os.path.join(subdir, "roster_updates_list.csv"), index=False)
    print(f"  {len(updates)} roster updates found. Fetching the latest...")

    latest = updates[-1]
    update_id = latest["id"]
    update_name = latest["name"]

    resp2 = SESSION.get(
        f"{SHOW_BASE}/apis/roster_update.json",
        params={"id": update_id},
        timeout=20,
    )
    resp2.raise_for_status()
    data = resp2.json()

    changes = data.get("attribute_changes", [])
    new_items = data.get("new_items", [])

    rows = []
    for change in changes:
        item = change.get("item", {}) if isinstance(change.get("item"), dict) else {}
        rows.append({
            "update_id": update_id,
            "update_name": update_name,
            "uuid": item.get("uuid") or change.get("uuid", ""),
            "name": item.get("name") or change.get("name", ""),
            "team": item.get("team", ""),
            "position": item.get("display_position", ""),
            "ovr_before": _to_int(change.get("old_ovr") or change.get("before_ovr")),
            "ovr_after": _to_int(change.get("new_ovr") or change.get("after_ovr") or item.get("ovr")),
            "ovr_change": (
                _to_int(change.get("new_ovr") or change.get("after_ovr") or item.get("ovr"))
                - _to_int(change.get("old_ovr") or change.get("before_ovr"))
            ),
            "change_type": "attribute_change",
        })

    for ni in new_items:
        item = ni if isinstance(ni, dict) else {}
        rows.append({
            "update_id": update_id,
            "update_name": update_name,
            "uuid": item.get("uuid", ""),
            "name": item.get("name", ""),
            "team": item.get("team", ""),
            "position": item.get("display_position", ""),
            "ovr_before": 0,
            "ovr_after": _to_int(item.get("ovr")),
            "ovr_change": 0,
            "change_type": "new_item",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        for subdir in [DATA_DIR, DOCS_DATA_DIR]:
            df.to_csv(os.path.join(subdir, "roster_update_latest.csv"), index=False)
        upgrades = df[df["ovr_change"] > 0]
        downgrades = df[df["ovr_change"] < 0]
        print(
            f"  Latest update ({update_name}): "
            f"{len(upgrades)} upgrades, {len(downgrades)} downgrades, "
            f"{len(new_items)} new items"
        )

    return df


def fetch_show_cards(
    series_filter: str | None = None,
    type_filter: str = "mlb_card",
) -> pd.DataFrame:
    print("Fetching MLB The Show item/card data...")
    raw = fetch_paginated_json("/apis/items.json", {"type": type_filter})

    rows = []
    scanned_at = date.today().isoformat()

    for card in raw:
        series = card.get("series", "")
        if series_filter and series_filter.lower() not in str(series).lower():
            continue

        pitch_cols = _parse_pitches(card.get("pitches", []))
        trend_val = card.get("trend", "")

        rows.append({
            "item_id": card.get("id"),
            "uuid": card.get("uuid"),
            "name": card.get("name") or card.get("item_name") or card.get("short_name") or "",
            "series": series,
            "series_year": _to_int(card.get("series_year"), default=0),
            "rarity": card.get("rarity", ""),
            "team": card.get("team", ""),
            "team_short": card.get("team_short_name") or card.get("team_abbrev") or "",
            "display_position": card.get("display_position", ""),
            "secondary_positions": _list_to_text(card.get("secondary_positions", [])),
            "location": _list_to_text(card.get("locations") or card.get("location") or []),
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
            "hitting_durability": _to_int(card.get("hitting_durability")),
            "fielding_durability": _to_int(card.get("fielding_durability")),
            "fielding": _to_int(card.get("fielding_ability")),
            "arm_strength": _to_int(card.get("arm_strength")),
            "arm_accuracy": _to_int(card.get("arm_accuracy")),
            "reaction": _to_int(card.get("reaction_time")),
            "blocking": _to_int(card.get("blocking")),
            "speed": _to_int(card.get("speed")),
            # API field is "stealing" not "stealing_ability"
            "stealing": _to_int(card.get("stealing")),
            # "baserunning_ability" is not exposed by the API — br_aggr works via "baserunning_aggression"
            "baserunning_ability": _to_int(card.get("baserunning_ability")),
            "br_aggr": _to_int(card.get("baserunning_aggression")),
            "stamina": _to_int(card.get("stamina")),
            # NOTE: k_per_bf and hits_per_bf return 0 for all cards — the API may use
            # different keys (e.g. "strikeouts_per_bf", "h_per_bf"). To debug, add:
            #   if not any(card.get(k) for k in ("k_per_bf","strikeouts_per_bf","so_per_bf")): print(card.keys())
            "hits_per_bf": _to_int(card.get("hits_per_bf") or card.get("h_per_bf")),
            "k_per_bf": _to_int(card.get("k_per_bf") or card.get("strikeouts_per_bf") or card.get("so_per_bf")),
            "bb9": _to_int(card.get("bb_per_bf")),
            "hr9": _to_int(card.get("hr_per_bf")),
            "pitch_clutch": _to_int(card.get("pitching_clutch")),
            "control": _to_int(card.get("pitch_control")),
            "velocity": _to_int(card.get("pitch_velocity")),
            "break": _to_int(card.get("pitch_movement")),
            "quirks": _list_to_text(card.get("quirks", [])),
            "has_augments": bool(card.get("has_augments", False)),
            "trend": "" if pd.isna(trend_val) else trend_val,
            "new_rank": card.get("new_rank", ""),
            "scanned_at": scanned_at,
            **pitch_cols,
        })

    df = pd.DataFrame(rows)

    pitch_num_cols = [
        f"pitch_{i}_{stat}"
        for i in range(1, 6)
        for stat in ("speed", "control", "movement")
    ]
    for col in CARD_NUMERIC_COLS + pitch_num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    return df


def fetch_bulk_listings(
    rarity: str | None = None,
    position: str | None = None,
    series_id: int | None = None,
    min_buy_price: int | None = None,
    max_buy_price: int | None = None,
) -> pd.DataFrame:
    print("Fetching marketplace listings (bulk)...")
    params: dict = {"type": "mlb_card", "sort": "best_buy_price", "order": "desc"}
    if rarity:
        params["rarity"] = rarity
    if position:
        params["display_position"] = position
    if series_id:
        params["series_id"] = series_id
    if min_buy_price:
        params["min_best_buy_price"] = min_buy_price
    if max_buy_price:
        params["max_best_buy_price"] = max_buy_price

    try:
        raw = fetch_paginated_json("/apis/listings.json", params, items_key="listings")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            print(f"  Bulk listings fetch failed: {e}")
            raise  # propagate 403 so caller skips per-item crawl
        print(f"  Bulk listings fetch failed: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  Bulk listings fetch failed: {e}")
        return pd.DataFrame()

    rows = []
    scanned_at = date.today().isoformat()
    for x in raw:
        item = x.get("item") if isinstance(x.get("item"), dict) else {}
        rows.append({
            "uuid": x.get("uuid") or item.get("uuid"),
            "item_id": item.get("id"),
            "best_buy_price": _to_int(x.get("best_buy_price")),
            "best_sell_price": _to_int(x.get("best_sell_price")),
            "buy_order_count": _to_int(x.get("buy_order_count") or x.get("num_buy_orders")),
            "sell_order_count": _to_int(x.get("sell_order_count") or x.get("num_sell_orders")),
            "completed_orders": _to_int(x.get("completed_orders")),
            "market_name": x.get("listing_name") or item.get("name") or "",
            "scanned_at": scanned_at,
        })

    df = pd.DataFrame(rows)
    for col in ["best_buy_price", "best_sell_price", "buy_order_count", "sell_order_count", "completed_orders"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    print(f"  Bulk listings: {len(df)} rows")
    return df


def fetch_listing_for_item(
    uuid: str | None = None,
    item_id=None,
    capture_price_history: bool = True,
    pause: float = 0.05,
) -> dict | None:
    candidates = []
    if uuid:
        candidates.append({"uuid": uuid})
    if item_id not in (None, "", 0):
        candidates.extend([{"item_id": item_id}, {"id": item_id}])

    for params in candidates:
        try:
            resp = SESSION.get(f"{SHOW_BASE}/apis/listing.json", params=params, timeout=20)
            if resp.status_code != 200:
                continue
            data = resp.json()

            if isinstance(data, dict) and data.get("listing"):
                payload = data["listing"]
            elif isinstance(data, dict) and any(
                k in data for k in ("best_buy_price", "best_sell_price", "listing_name")
            ):
                payload = data
            elif isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
                payload = data["items"][0]
            else:
                continue

            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}

            price_trend = None
            avg_recent_price = None
            if capture_price_history:
                history = payload.get("price_history") or payload.get("completed_orders") or []
                if isinstance(history, list) and history:
                    recent_prices = []
                    for entry in history[:10]:
                        if isinstance(entry, dict):
                            p = _to_int(
                                entry.get("price")
                                or entry.get("sell_price")
                                or entry.get("best_sell_price")
                            )
                            if p > 0:
                                recent_prices.append(p)
                    if len(recent_prices) >= 2:
                        avg_recent_price = int(mean(recent_prices))
                        sell_now = _to_int(payload.get("best_sell_price") or payload.get("sell_price"))
                        if sell_now > 0 and avg_recent_price > 0:
                            pct = (sell_now - avg_recent_price) / avg_recent_price * 100
                            if pct > 5:
                                price_trend = "up"
                            elif pct < -5:
                                price_trend = "down"
                            else:
                                price_trend = "stable"

            row = {
                "uuid": payload.get("uuid") or item.get("uuid") or uuid,
                "item_id": payload.get("item_id") or item.get("id") or item_id,
                "best_buy_price": _to_int(payload.get("best_buy_price") or payload.get("buy_price")),
                "best_sell_price": _to_int(payload.get("best_sell_price") or payload.get("sell_price")),
                "buy_order_count": _to_int(payload.get("buy_order_count") or payload.get("num_buy_orders")),
                "sell_order_count": _to_int(payload.get("sell_order_count") or payload.get("num_sell_orders")),
                "completed_orders": _to_int(payload.get("completed_orders")),
                "avg_recent_price": avg_recent_price,
                "price_trend": price_trend,
                "market_name": payload.get("listing_name") or item.get("name") or "",
                "listing_source": "per_item",
                "scanned_at": date.today().isoformat(),
            }
            time.sleep(pause)
            return row
        except Exception:
            continue

    return None


def fetch_listings_for_cards(
    cards: pd.DataFrame,
    mode: str = "auto",
    limit: int | None = None,
    rarity: str | None = None,
    position: str | None = None,
    series_id: int | None = None,
    min_buy_price: int | None = None,
) -> pd.DataFrame:
    if mode == "none":
        return pd.DataFrame()

    if mode in {"auto", "bulk"}:
        bulk = fetch_bulk_listings(
            rarity=rarity,
            position=position,
            series_id=series_id,
            min_buy_price=min_buy_price,
        )
        if mode == "bulk":
            return bulk
        if len(bulk) >= max(50, int(len(cards) * 0.10)):
            print(f"  Bulk listings usable ({len(bulk)} rows).")
            return bulk
        print(f"  Bulk listings too sparse ({len(bulk)} rows) — falling back to per-item crawl...")

    rows = []
    subset = cards.head(limit) if limit else cards
    total = len(subset)
    for idx, row in enumerate(subset.itertuples(index=False), start=1):
        if idx % 50 == 0 or idx == 1 or idx == total:
            print(f"  Listing crawl {idx}/{total}")
        listing = fetch_listing_for_item(
            uuid=getattr(row, "uuid", None),
            item_id=getattr(row, "item_id", None),
            capture_price_history=True,
        )
        if listing:
            rows.append(listing)

    df = pd.DataFrame(rows)
    for col in ["best_buy_price", "best_sell_price", "buy_order_count", "sell_order_count", "completed_orders", "avg_recent_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")
    return df


def combine_cards_and_market(
    cards: pd.DataFrame,
    listings: pd.DataFrame,
    roster_updates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df = cards.copy()

    if not listings.empty:
        use_uuid = (
            "uuid" in df.columns
            and "uuid" in listings.columns
            and listings["uuid"].notna().any()
        )
        key = "uuid" if use_uuid else "item_id"
        deduped = listings.drop_duplicates(subset=[key], keep="first")
        df = df.merge(deduped, on=key, how="left", suffixes=("", "_market"))

        df["best_buy_price"] = pd.to_numeric(df.get("best_buy_price"), errors="coerce").fillna(0)
        df["best_sell_price"] = pd.to_numeric(df.get("best_sell_price"), errors="coerce").fillna(0)

        df["market_spread"] = (df["best_sell_price"] - df["best_buy_price"]).astype("Int64")
        df["profit_after_tax"] = ((df["best_sell_price"] * 0.9) - df["best_buy_price"]).round(0).astype("Int64")
        df["is_profitable"] = df["profit_after_tax"].fillna(0) > 0

    if roster_updates is not None and not roster_updates.empty and "uuid" in df.columns:
        recently_upgraded = set(
            roster_updates.loc[roster_updates["ovr_change"] > 0, "uuid"].dropna()
        )
        recently_downgraded = set(
            roster_updates.loc[roster_updates["ovr_change"] < 0, "uuid"].dropna()
        )
        df["recently_upgraded"] = df["uuid"].isin(recently_upgraded)
        df["recently_downgraded"] = df["uuid"].isin(recently_downgraded)
        n_up = df["recently_upgraded"].sum()
        n_down = df["recently_downgraded"].sum()
        print(f"  Roster update flags: {n_up} upgraded, {n_down} downgraded cards marked")

    pitch_num_cols = [
        f"pitch_{i}_{stat}"
        for i in range(1, 6)
        for stat in ("speed", "control", "movement")
    ]
    for col in CARD_NUMERIC_COLS + pitch_num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    return df


def prep_for_json(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []

    records = df.to_dict(orient="records")

    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and (v != v):
                row[k] = None

    return records


def write_json(df: pd.DataFrame, path: str):
    records = prep_for_json(df)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, allow_nan=False)


def save_outputs(
    cards: pd.DataFrame,
    combined: pd.DataFrame,
    listings: pd.DataFrame,
):
    today = date.today().isoformat()

    for subdir in [DATA_DIR, DOCS_DATA_DIR]:
        csv_path = os.path.join(subdir, "show_cards_latest.csv")
        json_path = os.path.join(subdir, "show_cards_latest.json")
        cards.to_csv(csv_path, index=False)
        write_json(cards, json_path)

    cards.to_csv(os.path.join(DATA_DIR, f"show_cards_{today}.csv"), index=False)
    write_json(cards, os.path.join(DATA_DIR, f"show_cards_{today}.json"))
    print(f"Saved cards → show_cards_latest.csv + show_cards_latest.json ({len(cards):,} rows)")

    if not listings.empty:
        for subdir in [DATA_DIR, DOCS_DATA_DIR]:
            csv_path = os.path.join(subdir, "show_listings_latest.csv")
            json_path = os.path.join(subdir, "show_listings_latest.json")
            listings.to_csv(csv_path, index=False)
            write_json(listings, json_path)

        listings.to_csv(os.path.join(DATA_DIR, f"show_listings_{today}.csv"), index=False)
        write_json(listings, os.path.join(DATA_DIR, f"show_listings_{today}.json"))
        print(f"Saved listings → show_listings_latest.csv + show_listings_latest.json ({len(listings):,} rows)")

    for subdir in [DATA_DIR, DOCS_DATA_DIR]:
        csv_path = os.path.join(subdir, "show_dataset_latest.csv")
        json_path = os.path.join(subdir, "show_dataset_latest.json")
        combined.to_csv(csv_path, index=False)
        write_json(combined, json_path)

    combined.to_csv(os.path.join(DATA_DIR, f"show_dataset_{today}.csv"), index=False)
    write_json(combined, os.path.join(DATA_DIR, f"show_dataset_{today}.json"))
    print(f"Saved combined → show_dataset_latest.csv + show_dataset_latest.json ({len(combined):,} rows)")

    if "ovr" in combined.columns and "best_buy_price" in combined.columns:
        value_df = combined.copy()
        buy_nonzero = pd.to_numeric(value_df["best_buy_price"], errors="coerce").fillna(0)
        ovr_vals = pd.to_numeric(value_df["ovr"], errors="coerce").fillna(0)

        value_df["value_score"] = [
            round((ovr / buy), 6) if buy and buy > 0 else None
            for ovr, buy in zip(ovr_vals, buy_nonzero)
        ]

        if "best_sell_price" in value_df.columns:
            sell_vals = pd.to_numeric(value_df["best_sell_price"], errors="coerce").fillna(0)
            value_df["market_value_score"] = [
                round((ovr / sell), 6) if sell and sell > 0 else None
                for ovr, sell in zip(ovr_vals, sell_vals)
            ]

        for col in ["contact_r", "speed", "power_r", "fielding", "bunt", "control", "break", "k_per_bf", "pitch_clutch"]:
            if col not in value_df.columns:
                value_df[col] = 0

        value_df["contact_speed_score"] = pd.to_numeric(value_df["contact_r"], errors="coerce").fillna(0) + pd.to_numeric(value_df["speed"], errors="coerce").fillna(0)
        value_df["power_defense_score"] = pd.to_numeric(value_df["power_r"], errors="coerce").fillna(0) + pd.to_numeric(value_df["fielding"], errors="coerce").fillna(0)
        value_df["bunt_speed_score"] = pd.to_numeric(value_df["bunt"], errors="coerce").fillna(0) + pd.to_numeric(value_df["speed"], errors="coerce").fillna(0)
        value_df["pitching_command_score"] = pd.to_numeric(value_df["control"], errors="coerce").fillna(0) + pd.to_numeric(value_df["break"], errors="coerce").fillna(0)
        value_df["pitching_dominance_score"] = pd.to_numeric(value_df["k_per_bf"], errors="coerce").fillna(0) + pd.to_numeric(value_df["pitch_clutch"], errors="coerce").fillna(0)

        profitable_df = value_df.copy()
        if "profit_after_tax" in profitable_df.columns:
            profitable_df = profitable_df[
                pd.to_numeric(profitable_df["profit_after_tax"], errors="coerce").fillna(0) > 0
            ].copy()

        combo_cols = [
            c for c in [
                "uuid", "name", "team", "display_position", "ovr",
                "contact_speed_score", "power_defense_score", "bunt_speed_score",
                "pitching_command_score", "pitching_dominance_score",
                "best_buy_price", "best_sell_price", "profit_after_tax", "img"
            ] if c in value_df.columns
        ]
        combo_df = value_df[combo_cols].copy()

        for subdir in [DATA_DIR, DOCS_DATA_DIR]:
            value_df.to_csv(os.path.join(subdir, "show_value_latest.csv"), index=False)
            write_json(value_df, os.path.join(subdir, "show_value_latest.json"))

            profitable_df.to_csv(os.path.join(subdir, "show_profitable_latest.csv"), index=False)
            write_json(profitable_df, os.path.join(subdir, "show_profitable_latest.json"))

            combo_df.to_csv(os.path.join(subdir, "show_combo_leaders_latest.csv"), index=False)
            write_json(combo_df, os.path.join(subdir, "show_combo_leaders_latest.json"))

        print("Saved extras → show_value_latest.(csv/json), show_profitable_latest.(csv/json), show_combo_leaders_latest.(csv/json)")


def print_summary(
    cards: pd.DataFrame,
    combined: pd.DataFrame,
    listings: pd.DataFrame,
    meta: dict | None = None,
):
    print("\n" + "=" * 80)
    print(f"MLB THE SHOW 26 SNAPSHOT — {date.today()}")
    print("=" * 80)

    if meta:
        print(
            f"Metadata: {len(meta.get('series_by_id', {}))} series | "
            f"{len(meta.get('brand_by_id', {}))} brands | "
            f"{len(meta.get('sets', []))} sets"
        )

    print(f"Cards fetched: {len(cards):,}")

    if "best_buy_price" in combined.columns:
        with_market = combined["best_buy_price"].fillna(0).gt(0).sum()
        print(f"Cards with market data: {with_market:,}")

    if "series" in cards.columns:
        print("\nTop 10 series by card count:")
        print(cards["series"].fillna("Unknown").value_counts().head(10).to_string())

    if "best_buy_price" in combined.columns:
        market = combined[combined["best_buy_price"].fillna(0) > 0].copy()
        if not market.empty:
            cols = [
                c for c in [
                    "name", "series", "rarity", "ovr", "best_buy_price",
                    "best_sell_price", "profit_after_tax", "price_trend",
                    "recently_upgraded"
                ] if c in market.columns
            ]
            print("\nTop 15 by buy price:")
            print(
                market.sort_values("best_buy_price", ascending=False)[cols]
                .head(15)
                .to_string(index=False)
            )
            profitable = market[market["profit_after_tax"].fillna(0) > 0]
            if not profitable.empty:
                print("\nTop 10 profitable flips:")
                print(
                    profitable.sort_values("profit_after_tax", ascending=False)[cols]
                    .head(10)
                    .to_string(index=False)
                )

    if "recently_upgraded" in combined.columns:
        upgrades = combined[combined["recently_upgraded"] == True]
        if not upgrades.empty:
            up_cols = [c for c in ["name", "team", "ovr", "series", "best_buy_price"] if c in upgrades.columns]
            print(f"\nRecently upgraded cards ({len(upgrades)}):")
            print(upgrades[up_cols].head(15).to_string(index=False))

    ts_path = os.path.join(DOCS_DATA_DIR, "last_updated.json")
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump({"updated": date.today().isoformat() + "T00:00:00Z"}, f)
    print(f"Wrote last_updated.json → {ts_path}")

    print("\nStatic site data written to docs/data/. Refresh the dashboard to see updated data.")


def run():
    parser = argparse.ArgumentParser(
        description="MLB The Show 26 DD card + market snapshot for GitHub Pages"
    )
    parser.add_argument("--series", "-s", default=None,
                        help="Filter cards by series name substring")
    parser.add_argument("--type", "-t", default="mlb_card",
                        help="Item type: mlb_card | stadium | equipment | sponsorship | unlockable")
    parser.add_argument("--market-mode",
                        choices=["auto", "bulk", "per_item", "none"], default="auto",
                        help="How to fetch market data (default: auto)")
    parser.add_argument("--market-limit", type=int, default=None,
                        help="Cap per-item market crawl (useful for testing)")
    parser.add_argument("--skip-metadata", action="store_true",
                        help="Skip fetching metadata (series/brands/sets)")
    parser.add_argument("--rarity",
                        choices=["diamond", "gold", "silver", "bronze", "common"],
                        default=None,
                        help="Filter bulk listings by rarity")
    parser.add_argument("--position",
                        choices=["SP", "RP", "CP", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"],
                        default=None,
                        help="Filter bulk listings by position")
    parser.add_argument("--series-id", type=int, default=None,
                        help=("Filter bulk listings by series_id. "
                              "Known IDs: live=1337, awards=10005, toppsnow=10017, etc. "
                              "See SERIES_IDS dict in source."))
    parser.add_argument("--min-buy-price", type=int, default=None,
                        help="Filter bulk listings to cards with buy price >= N stubs")
    parser.add_argument("--fetch-roster-updates", action="store_true",
                        help="Fetch and save latest roster update; flags upgraded cards in output")
    args = parser.parse_args()

    if args.series_id is None and args.series:
        alias = args.series.lower().replace(" ", "").replace("-", "")
        if alias in SERIES_IDS:
            print(f"  Resolved series alias '{args.series}' → series_id={SERIES_IDS[alias]}")
            args.series_id = SERIES_IDS[alias]

    meta = {}
    if not args.skip_metadata:
        try:
            meta = fetch_metadata()
            save_metadata(meta)
        except Exception as e:
            print(f"  Warning: metadata fetch failed ({e}). Continuing without it.")

    try:
        cards = fetch_show_cards(series_filter=args.series, type_filter=args.type)
    except Exception as e:
        status = ""
        if hasattr(e, "response") and e.response is not None:
            status = f" (HTTP {e.response.status_code})"
        if "403" in str(e) or "Forbidden" in str(e):
            print(
                f"\n  ✗ API blocked{status} — MLB The Show is returning 403 Forbidden.\n"
                f"  This usually means Replit's server IP has been rate-limited or blocked.\n"
                f"  Options:\n"
                f"    1. Wait a few hours and try again.\n"
                f"    2. Run dd_tracker.py on your local machine instead.\n"
                f"    3. Your existing data in docs/data/ is still valid and being served.\n"
            )
        else:
            print(f"  ✗ Card fetch failed{status}: {e}")

        cached = os.path.join(DOCS_DATA_DIR, "show_dataset_latest.json")
        if os.path.exists(cached):
            print(f"  Loading cached data from {cached} …")
            with open(cached, encoding="utf-8") as f:
                records = json.load(f)
            cards = pd.DataFrame(records)
            print(f"  Loaded {len(cards):,} cached cards. Dashboard data unchanged.")
        else:
            print("  No cached data found. Exiting.")
            return

    series_by_id = meta.get("series_by_id", {})
    if series_by_id and "series" in cards.columns:
        def resolve_series(val):
            try:
                return series_by_id.get(int(float(val)), val)
            except (TypeError, ValueError):
                return val
        cards["series"] = cards["series"].apply(resolve_series)

    roster_updates = None
    if args.fetch_roster_updates:
        try:
            roster_updates = fetch_roster_updates()
        except Exception as e:
            print(f"  Warning: roster update fetch failed ({e}). Skipping.")

    try:
        listings = fetch_listings_for_cards(
            cards,
            mode=args.market_mode,
            limit=args.market_limit,
            rarity=args.rarity,
            position=args.position,
            series_id=args.series_id,
            min_buy_price=args.min_buy_price,
        )
    except Exception as e:
        print(f"  Warning: listings fetch failed ({e}). Continuing without market data.")
        listings = pd.DataFrame()

    combined = combine_cards_and_market(cards, listings, roster_updates=roster_updates)
    save_outputs(cards, combined, listings)
    print_summary(cards, combined, listings, meta=meta)


if __name__ == "__main__":
    run()
