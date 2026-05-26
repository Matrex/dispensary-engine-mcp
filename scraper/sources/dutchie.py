#!/usr/bin/env python3
"""
Dutchie Menu Scraper — pulls any dispensary's full product menu via GraphQL.

Usage:
    python dutchie_scraper.py <embedded_menu_url_or_id_or_cname> [--output FILE] [--pricing rec|med]

Examples:
    python dutchie_scraper.py https://dutchie.com/embedded-menu/67d863484420ce5c8c9897fd
    python dutchie_scraper.py best-budz-146-st
    python dutchie_scraper.py 67d863484420ce5c8c9897fd --output menu.json
    python dutchie_scraper.py dream-daze --pricing med
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

try:
    from curl_cffi import requests as cffi_requests
    SESSION_CLASS = cffi_requests.Session
    IMPERSONATE = "chrome"
except ImportError:
    print("[WARN] curl_cffi not installed. Install with: pip install curl_cffi")
    print("       Falling back to standard requests (may get blocked).")
    import requests as stdlib_requests
    SESSION_CLASS = stdlib_requests.Session
    IMPERSONATE = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GRAPHQL_URL = "https://dutchie.com/graphql"

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "apollo-require-preflight": "true",          # CSRF bypass
    "content-type": "application/json",
    "origin": "https://dutchie.com",
    "referer": "https://dutchie.com/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Persisted-query hashes (as of 2024-Q4 — may rotate; see note below)
HASH_CONSUMER_DISPENSARIES = "1a669394db4149fe474f55d0b4eba7850460f6d6e748fb27c206ab335db17f92"
HASH_FILTERED_PRODUCTS     = "98b4aaef79a84ae804b64d550f98dd64d7ba0aa6d836eb6b5d4b2ae815c95e32"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_session():
    if IMPERSONATE:
        s = SESSION_CLASS(impersonate=IMPERSONATE)
    else:
        s = SESSION_CLASS()
    s.headers.update(HEADERS)
    return s


def _warm_session(session, identifier):
    """Visit the embedded menu page to collect Cloudflare cookies before GraphQL calls."""
    try:
        session.get("https://dutchie.com/", timeout=15)
    except Exception:
        pass


def _graphql_get(session, operation_name, variables, sha256_hash):
    """Execute a persisted-query GET against Dutchie's GraphQL."""
    params = {
        "operationName": operation_name,
        "variables": json.dumps(variables, separators=(",", ":")),
        "extensions": json.dumps(
            {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}},
            separators=(",", ":"),
        ),
    }
    url = GRAPHQL_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        resp = session.get(url, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403 and attempt < 2:
            time.sleep(1 + attempt)
            # Re-warm cookies
            try:
                session.get("https://dutchie.com/", timeout=10)
            except Exception:
                pass
            continue
        resp.raise_for_status()


def parse_input(raw: str) -> str:
    """Accept a full URL, bare ID, or cName slug and return the identifier."""
    m = re.search(r"embedded-menu/([a-zA-Z0-9_-]+)", raw)
    if m:
        return m.group(1)
    m = re.search(r"dispensary/([a-zA-Z0-9_-]+)", raw)
    if m:
        return m.group(1)
    return raw.strip().rstrip("/")

# ---------------------------------------------------------------------------
# Core API wrappers
# ---------------------------------------------------------------------------

def resolve_dispensary(session, identifier: str) -> dict:
    """
    Resolve any identifier (24-char hex ID, cName slug, or URL path segment)
    into the full dispensary record with the canonical `id` and `cName`.

    This is THE fix for "slugs that don't match Dutchie's real cName values":
    always call ConsumerDispensaries first — it accepts both IDs and cNames
    via the `cNameOrID` field and returns the canonical record.
    """
    data = _graphql_get(
        session,
        "ConsumerDispensaries",
        {"dispensaryFilter": {"cNameOrID": identifier}},
        HASH_CONSUMER_DISPENSARIES,
    )
    dispensaries = data.get("data", {}).get("filteredDispensaries", [])
    if not dispensaries:
        raise ValueError(
            f"Dispensary not found for identifier '{identifier}'. "
            "Check the URL or cName and try again."
        )
    d = dispensaries[0]
    return {
        "id": d["id"],
        "cName": d.get("cName"),
        "name": d.get("name"),
        "address": d.get("address"),
        "phone": d.get("phone"),
        "status": d.get("status"),
        "timezone": d.get("timezone"),
    }


def fetch_all_products(session, dispensary_id: str, pricing_type: str = "rec") -> list:
    """
    Paginate through FilteredProducts and return every product.
    perPage is capped at 100 server-side; we paginate via 0-indexed `page`.
    """
    all_products = []
    page = 0
    total_pages = None

    while True:
        variables = {
            "includeEnterpriseSpecials": False,
            "productsFilter": {
                "dispensaryId": dispensary_id,
                "pricingType": pricing_type,
                "strainTypes": [],
                "subcategories": [],
                "Status": "Active",
                "types": [],
                "useCache": True,
                "isDefaultSort": True,
                "sortBy": "popularSortIdx",
                "sortDirection": 1,
                "bypassOnlineThresholds": False,
                "isKioskMenu": False,
                "removeProductsBelowOptionThresholds": True,
                "platformType": "ONLINE_MENU",
                "preOrderType": None,
            },
            "page": page,
            "perPage": 100,
        }
        data = _graphql_get(session, "FilteredProducts", variables, HASH_FILTERED_PRODUCTS)
        fp = data.get("data", {}).get("filteredProducts", {})
        products = fp.get("products") or []
        query_info = fp.get("queryInfo", {})

        if total_pages is None:
            total_pages = query_info.get("totalPages", 1)
            total_count = query_info.get("totalCount", 0)
            print(f"  → {total_count} products across {total_pages} page(s)")

        all_products.extend(products)
        page += 1
        if page >= total_pages:
            break
        time.sleep(0.3)  # polite delay

    return all_products


def normalize_product(p: dict) -> dict:
    """Flatten a raw GraphQL product into a clean dict."""
    thc = p.get("THCContent") or {}
    cbd = p.get("CBDContent") or {}
    thc_range = thc.get("range") or []
    cbd_range = cbd.get("range") or []

    option_labels = p.get("Options") or []
    rec_prices = p.get("recPrices") or []
    med_prices = p.get("medicalPrices") or []
    rec_specials = p.get("recSpecialPrices") or []
    med_specials = p.get("medicalSpecialPrices") or []
    weights_and_prices = []
    for i, label in enumerate(option_labels):
        weights_and_prices.append({
            "weight": label,
            "price_rec": rec_prices[i] if i < len(rec_prices) else None,
            "price_med": med_prices[i] if i < len(med_prices) else None,
            "price_rec_special": rec_specials[i] if i < len(rec_specials) else None,
            "price_med_special": med_specials[i] if i < len(med_specials) else None,
        })

    return {
        "id": p.get("_id"),
        "name": p.get("Name"),
        "brand": p.get("brandName"),
        "type": p.get("type"),
        "subcategory": p.get("subcategory"),
        "strain_type": p.get("strainType"),
        "thc_unit": thc.get("unit"),
        "thc_min": thc_range[0] if len(thc_range) > 0 else None,
        "thc_max": thc_range[1] if len(thc_range) > 1 else None,
        "cbd_unit": cbd.get("unit"),
        "cbd_min": cbd_range[0] if len(cbd_range) > 0 else None,
        "cbd_max": cbd_range[1] if len(cbd_range) > 1 else None,
        "image": p.get("Image"),
        "description": (p.get("description") or "")[:300],
        "options": weights_and_prices,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_menu(raw_input: str, pricing_type: str = "rec") -> dict:
    """
    End-to-end: accept any Dutchie URL / ID / slug, resolve the dispensary,
    pull all products, and return a clean dict.
    """
    session = _build_session()
    identifier = parse_input(raw_input)
    print(f"[1/3] Resolving dispensary: {identifier}")
    _warm_session(session, identifier)
    dispensary = resolve_dispensary(session, identifier)
    print(f"  → {dispensary['name']} (id={dispensary['id']}, cName={dispensary['cName']})")

    print(f"[2/3] Fetching products (pricing={pricing_type})...")
    raw_products = fetch_all_products(session, dispensary["id"], pricing_type)

    print("[3/3] Normalizing...")
    products = [normalize_product(p) for p in raw_products]

    return {
        "dispensary": dispensary,
        "pricing_type": pricing_type,
        "product_count": len(products),
        "products": products,
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape a Dutchie dispensary menu.")
    parser.add_argument("target", help="Embedded-menu URL, dispensary ID, or cName slug")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file (default: stdout summary)")
    parser.add_argument("--pricing", choices=["rec", "med"], default="rec", help="Pricing type")
    args = parser.parse_args()

    result = scrape_menu(args.target, args.pricing)

    out_path = args.output or f"{result['dispensary']['cName']}_menu.json"
    Path(out_path).write_text(json.dumps(result, indent=2, default=str))
    print(f"\nSaved {result['product_count']} products → {out_path}")

    # Quick summary
    types = {}
    for p in result["products"]:
        t = p.get("type") or "Unknown"
        types[t] = types.get(t, 0) + 1
    print("\nBy type:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
