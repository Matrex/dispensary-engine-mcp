How it works:

It uses a two-method fallback strategy:


curl_cffi (impersonate="chrome124") — tries a direct call to the dispensary REST API with a Chrome TLS fingerprint to bypass Cloudflare. Fast (~2s).
Playwright (headless Chromium) — if the API returns a 403 (auth required), the browser renders the full JS app and reads the product inventory from sessionStorage — exactly how the site itself loads it.
pip install curl_cffi playwright
playwright install chromium
python goodlife_scraper.py


Each product record contains: id, title, desc, category, brand, price, priceAfterTax, rawPrice, quantity, weight, unit, strainType, thc, cbd, image, terpenes, totalTerpenes, potency (totalThc, thc, thca, cbd, cbda, totalCbd), weightTierInformation, and productUpdatedAt.


____________________________________________________________


#!/usr/bin/env python3
"""
Good Life Collective - Buffalo, NY
Cannabis Dispensary Product Inventory Scraper
URL: https://goodlifeweed.com/location/cannabis-dispensary-buffalo-ny/shop


Uses curl_cffi to bypass Cloudflare and Playwright to render the JS app
and extract inventory from the dispensary-api backend.


Usage:
    pip install curl_cffi playwright
    playwright install chromium
    python scraper.py
"""


import json
import time
from datetime import datetime
from collections import defaultdict
from pathlib import Path




# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
SHOP_URL       = "https://goodlifeweed.com/location/cannabis-dispensary-buffalo-ny/shop"
LOCATION_ID    = "f65352d5-0fd4-4fdf-96c3-0045c318bbbd"
SESSION_KEY    = f"products_{LOCATION_ID}"
API_BASE       = "https://dispensary-api-ac9613fa4c11.herokuapp.com/api"
INVENTORY_URL  = (
    f"{API_BASE}/flowhub/inventoryByLocation"
    f"?location_id={LOCATION_ID}&toggleVape=false"
)
OUTPUT_FILE    = "goodlife_buffalo_inventory.json"




# ──────────────────────────────────────────────────────────────────────────────
# METHOD 1 — Playwright (renders the JS app and reads sessionStorage)
# ──────────────────────────────────────────────────────────────────────────────
def scrape_via_playwright() -> list[dict]:
    """
    Launches a headless Chromium browser, navigates to the shop page,
    waits for the JS app to fetch and cache inventory into sessionStorage,
    then reads and returns the full product list.
    """
    from playwright.sync_api import sync_playwright


    print("[playwright] Launching browser …")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()


        print(f"[playwright] Navigating to {SHOP_URL}")
        page.goto(SHOP_URL, wait_until="networkidle", timeout=60_000)


        # Wait until the app has written products to sessionStorage
        print("[playwright] Waiting for inventory data in sessionStorage …")
        for attempt in range(30):
            raw = page.evaluate(f"sessionStorage.getItem('{SESSION_KEY}')")
            if raw:
                print(f"[playwright] Data ready after ~{attempt * 2}s")
                break
            time.sleep(2)
        else:
            raise RuntimeError(
                "Inventory never appeared in sessionStorage. "
                "The site may have changed its caching mechanism."
            )


        products = json.loads(raw)
        print(f"[playwright] Extracted {len(products)} products")
        browser.close()
        return products




# ──────────────────────────────────────────────────────────────────────────────
# METHOD 2 — curl_cffi (direct API call with Cloudflare-bypass TLS fingerprint)
#            Note: the API currently requires an auth token that the browser
#            app obtains automatically. If this method returns a 403 you must
#            use Method 1 (Playwright) instead.
# ──────────────────────────────────────────────────────────────────────────────
def scrape_via_curl_cffi() -> list[dict]:
    """
    Attempts a direct HTTPS request to the inventory API using curl_cffi
    (Chrome TLS fingerprint) to bypass Cloudflare bot detection.
    Falls back to Playwright on 401/403.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        raise ImportError("Install with: pip install curl_cffi")


    print(f"[curl_cffi] GET {INVENTORY_URL}")
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://goodlifeweed.com",
        "Referer": SHOP_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }


    resp = cffi_requests.get(
        INVENTORY_URL,
        headers=headers,
        impersonate="chrome124",
        timeout=30,
    )
    print(f"[curl_cffi] Status: {resp.status_code}")


    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            return data
        raise ValueError(f"Unexpected response shape: {list(data.keys())}")


    print(f"[curl_cffi] Got {resp.status_code} — falling back to Playwright …")
    return scrape_via_playwright()




# ──────────────────────────────────────────────────────────────────────────────
# ORGANISE & EXPORT
# ──────────────────────────────────────────────────────────────────────────────
def organise(products: list[dict]) -> dict:
    """Groups products by category and builds the final export structure."""
    by_category: dict[str, list[dict]] = defaultdict(list)
    for product in products:
        cat = product.get("category") or "Unknown"
        by_category[cat].append(product)


    category_summary = {cat: len(items) for cat, items in by_category.items()}


    return {
        "store":        "Good Life Collective - Buffalo, NY",
        "location_id":  LOCATION_ID,
        "shop_url":     SHOP_URL,
        "scraped_at":   datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_products": len(products),
        "category_summary": category_summary,
        "inventory": dict(by_category),
    }




def save(data: dict, path: str = OUTPUT_FILE) -> None:
    out = Path(path)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[output] Saved {data['total_products']} products → {out.resolve()}")




# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    # Try the fast direct-API path first; fall back to browser rendering
    try:
        products = scrape_via_curl_cffi()
    except Exception as exc:
        print(f"[curl_cffi] Failed ({exc}); using Playwright …")
        products = scrape_via_playwright()


    data = organise(products)


    print("\n── Category Summary ──────────────────────────────────")
    for cat, count in data["category_summary"].items():
        print(f"  {cat:<20} {count:>5} products")
    print(f"  {'TOTAL':<20} {data['total_products']:>5} products")
    print()


    save(data)




if __name__ == "__main__":
    main()
