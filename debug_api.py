"""
Run this to inspect the raw API response and find the correct attribute field names.
Output is saved to data/debug_sample.json for you to look at.
"""

import requests, json, os

os.makedirs("data", exist_ok=True)

# Grab just the first page, first few cards
url = "https://mlb26.theshow.com/apis/items.json"
resp = requests.get(url, params={"type": "mlb_card", "page": 1}, timeout=15)
resp.raise_for_status()
data = resp.json()

# Save full first page so you can inspect every field
with open("data/debug_sample.json", "w") as f:
    json.dump(data, f, indent=2)

print("Top-level keys:", list(data.keys()))
print("Total pages:", data.get("total_pages"))
print("Items on page 1:", len(data.get("items", [])))

# Print the full structure of the first 2 cards
items = data.get("items", [])
for i, card in enumerate(items[:2]):
    print(f"\n--- Card {i+1}: {card.get('name')} ---")
    for k, v in card.items():
        print(f"  {k}: {v}")
