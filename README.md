# Diamond Dynasty vs Real Life Tracker

Pulls MLB The Show 26 Live series card ratings and compares them to
current season MLB stats — finding who's overrated or underrated in the game.

---

## Setup

```bash
cd dd_tracker
pip install -r requirements.txt --break-system-packages
```

---

## Usage

```bash
python dd_tracker.py
```

Run it daily (or weekly) during the season. Results are saved to the `data/`
folder with today's date so you can track changes over time.

---

## How it works

### Step 1 — The Show card data
Hits the official MLB The Show 26 API (`mlb26.theshow.com/apis/items.json`)
and pulls all **Live series** cards. These are the cards that reflect current
player performance — the ones that get updated with roster updates throughout
the season. Grabs attributes like contact, power, speed, plate vision, velocity,
control, K/9, BB/9, etc.

### Step 2 — Real MLB stats
Pulls current season stats from the **MLB Stats API** (free, no key needed).
Batters: AVG, OBP, SLG, OPS, ISO, K%, BB%, SB, HR.
Pitchers: ERA, WHIP, K/9, BB/9, HR/9, FIP.

### Step 3 — Player matching
Fuzzy-matches names between the two datasets using token sort ratio (handles
"Ronald Acuña Jr." vs "Ronald Acuna Jr." type mismatches). Match threshold
is 85 by default — lower it if you're missing players, raise it if you're
getting bad matches.

### Step 4 — Gap score
Builds a weighted real-life performance score (scaled to the ~OVR range)
and subtracts the in-game OVR. Positive gap = underrated. Negative = overrated.

**Batter weights:**
- OPS: 35%
- K%:  20% (inverted — lower is better)
- BB%: 15%
- ISO: 20%
- SB:  10%

**Pitcher weights:**
- K/9:  25%
- BB/9: 20% (inverted)
- FIP:  20% (inverted)
- ERA:  20% (inverted)
- WHIP: 15% (inverted)

You can tune these weights in the `calc_batter_gap()` and `calc_pitcher_gap()`
functions to match your own theory of player value.

---

## Output files (saved to `data/`)

| File | Contents |
|---|---|
| `show_cards_YYYY-MM-DD.csv` | Raw Show card attributes |
| `mlb_batting_YYYY-MM-DD.csv` | Raw MLB batting stats |
| `mlb_pitching_YYYY-MM-DD.csv` | Raw MLB pitching stats |
| `batter_gaps_YYYY-MM-DD.csv` | Full merged batter comparison |
| `pitcher_gaps_YYYY-MM-DD.csv` | Full merged pitcher comparison |

---

## Tips

- **Run it after roster updates** — The Show typically updates Live cards
  on Fridays. Running right after gives you the freshest delta.
- **Watch the gap trend over time** — A player whose gap grows week over week
  is likely due for a rating bump soon.
- **Adjust min PA/IP filters** — Edit the `.query("pa >= 30")` and
  `.query("ip >= 10")` lines in the fetch functions if you want to include
  players earlier in the season.
- **Series filter** — The script defaults to `series_type="Live"`. You can
  pass `series_type=""` to `fetch_show_cards()` to include all card types
  (though non-Live cards won't change with player performance).
# show-dashboard
