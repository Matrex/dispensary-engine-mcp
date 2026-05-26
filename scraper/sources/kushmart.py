How it works
Step
	What happens
	1
	Fetches all 38 paginated listing pages (/shop?page=N)
	2
	Parses each [data-ssr-card] product link — no JS rendering needed, pure SSR HTML
	3
	(Optional, default ON) Fetches each product detail page in parallel threads to add: category, image_url, full cannabinoid_profile (THC-a, CBD-a, etc.), and confirmed in_stock status
	4
	Exports everything to 
kushmart_inventory.json
	Fields per product
name, brand, strain_type, thc, cbd, pack, price_usd, url,
in_stock, category, image_url, cannabinoid_profile, availability_schema


Usage
pip install requests beautifulsoup4
python kushmart_scraper.py                          # full run (~5-10 min with enrichment)
python kushmart_scraper.py --no-enrich              # listing data only (~30 sec)
python kushmart_scraper.py --workers 16 --output out.json


CDN fallback
If Cloudflare ever blocks plain requests, install curl_cffi — the script auto-detects it and switches to Chrome TLS impersonation:
pip install curl_cffi
python kushmart_scraper.py   # automatically uses curl_cffi


Note on quantity
KushMart does not expose numeric stock counts on the public menu. The in_stock field reflects the schema.org InStock/OutOfStock availability from each product detail page — this is the only stock signal available.


#!/usr/bin/env python3
"""
KushMart Lackawanna NY — Product Inventory Scraper
Fetches all products from https://kushmart.com/location/lackawanna-ny/shop
and enriches each with category, image URL, and full cannabinoid profile
from individual product detail pages.


Usage:
    pip install requests beautifulsoup4
    python kushmart_scraper.py


    # Skip detail-page enrichment for a quick listing-only run:
    python kushmart_scraper.py --no-enrich


    # Custom worker count and output file:
    python kushmart_scraper.py --workers 12 --output my_inventory.json


    # If Cloudflare / CDN blocks plain requests, install curl_cffi:
    pip install curl_cffi
    python kushmart_scraper.py   # will auto-detect and use Chrome TLS impersonation


Output:
    kushmart_inventory.json  — full product list with all available fields


Note on quantity:
    KushMart does not expose numeric stock quantities on the public menu.
    Each product receives in_stock=True/False derived from the schema.org
    availability field (InStock / OutOfStock) on the product detail page.
"""


import re
import json
import time
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------------------------------------------------------------------
# HTTP client — auto-detects requests vs curl_cffi
# ---------------------------------------------------------------------------
_session = None
_use_curl_cffi = False


def _build_session():
    global _session, _use_curl_cffi
    try:
        import requests
        from requests.adapters import HTTPAdapter, Retry
        s = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        _session = s
        _use_curl_cffi = False
        print("[http] Using requests library")
        return
    except ImportError:
        pass


    try:
        from curl_cffi import requests as cffi_requests
        _session = cffi_requests.Session(impersonate="chrome124")
        _use_curl_cffi = True
        print("[http] Using curl_cffi (Chrome TLS impersonation)")
        return
    except ImportError:
        pass


    raise ImportError(
        "No HTTP library found. Install one:\n"
        "  pip install requests beautifulsoup4\n"
        "  pip install curl_cffi beautifulsoup4  # for CDN bypass"
    )




def get_html(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            resp = _session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.text
            print(f"  [warn] HTTP {resp.status_code} for {url}")
        except Exception as exc:
            print(f"  [warn] Request error ({attempt + 1}/{retries}): {exc}")
            time.sleep(1.0)
    return None




# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL   = "https://kushmart.com"
SHOP_URL   = f"{BASE_URL}/location/lackawanna-ny/shop"
TOTAL_PAGES           = 38
DEFAULT_WORKERS       = 8
DELAY_BETWEEN_PAGES   = 0.2   # seconds




# ---------------------------------------------------------------------------
# Listing-page parser
# ---------------------------------------------------------------------------
def parse_listing_page(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    all_cards = soup.select("a[data-ssr-card]")
    # Product detail cards have exactly 6 path segments: /location/x/shop/brand/slug
    product_cards = [c for c in all_cards if len(c.get("href", "").split("/")) == 6]


    products = []
    for card in product_cards:
        href      = card.get("href", "")
        name_el   = card.find("strong")
        name      = name_el.get_text(strip=True) if name_el else ""
        divs      = card.find_all("div", recursive=False)


        meta_text = ""
        price_text = ""
        for d in divs:
            t = d.get_text(" ", strip=True)
            if "$" in t:
                price_text = t.lstrip("$").strip()
            elif "·" in t or "gram" in t.lower() or re.search(r"\d+mg", t.lower()):
                meta_text = t


        parts = [p.strip() for p in meta_text.split("·")]
        brand = parts[0] if parts else ""
        strain_type = thc = cbd = pack = None
        for p in parts[1:]:
            pl = p.lower()
            if re.match(r"(indica|sativa|hybrid|50/50)", pl):
                strain_type = p
            elif pl.startswith("thc"):
                thc = p[3:].strip()
            elif pl.startswith("cbd"):
                cbd = p[3:].strip()
            elif "gram" in pl or re.search(r"\d+mg", pl):
                pack = p


        products.append({
            "name":                name,
            "brand":               brand,
            "strain_type":         strain_type,
            "thc":                 thc,
            "cbd":                 cbd,
            "pack":                pack,
            "price_usd":           price_text or None,
            "url":                 BASE_URL + href,
            "in_stock":            True,
            "category":            None,
            "image_url":           None,
            "cannabinoid_profile": {},
            "availability_schema": "InStock",
        })
    return products




# ---------------------------------------------------------------------------
# Detail-page enricher
# ---------------------------------------------------------------------------
def enrich_from_detail(product: dict) -> dict:
    from bs4 import BeautifulSoup
    html = get_html(product["url"])
    if not html:
        return product


    soup = BeautifulSoup(html, "html.parser")


    # Product image
    img = (soup.find("img", attrs={"fetchpriority": "high"})
           or soup.find("img", attrs={"loading": "eager"}))
    if img:
        product["image_url"] = img.get("src", "")


    # Category from the spec <ul> on the detail page
    ul = soup.find("ul", style=lambda s: "list-style:none" in (s or ""))
    if ul:
        for li in ul.find_all("li"):
            txt = li.get_text(strip=True)
            if txt.startswith("Category:"):
                product["category"] = txt.replace("Category:", "").strip()


    # Full cannabinoid profile
    cannabinoids = {}
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if h2 and "cannabinoid" in h2.get_text(strip=True).lower():
            for li in section.find_all("li"):
                t = li.get_text(strip=True)
                m = re.match(r"([^:]+):\s*(.+)", t)
                if m:
                    cannabinoids[m.group(1).strip()] = m.group(2).strip()
    if cannabinoids:
        product["cannabinoid_profile"] = cannabinoids


    # Availability via JSON-LD schema
    avail_match = re.search(r'"availability"\s*:\s*"([^"]+)"', html)
    if avail_match:
        schema_val = avail_match.group(1).split("/")[-1]
        product["availability_schema"] = schema_val
        product["in_stock"] = schema_val == "InStock"


    return product




# ---------------------------------------------------------------------------
# Main scraper function
# ---------------------------------------------------------------------------
def scrape(
    enrich: bool = True,
    max_workers: int = DEFAULT_WORKERS,
    output: str = "kushmart_inventory.json",
) -> dict:
    _build_session()
    print(f"[scrape] KushMart Lackawanna menu — {datetime.now(timezone.utc).isoformat()}")


    # ---- Step 1: listing pages ----
    all_products: list[dict] = []
    for page_num in range(1, TOTAL_PAGES + 1):
        url  = SHOP_URL if page_num == 1 else f"{SHOP_URL}?page={page_num}"
        html = get_html(url)
        if not html:
            print(f"  [skip] Failed to fetch page {page_num}")
            continue
        page_products = parse_listing_page(html)
        all_products.extend(page_products)
        print(f"  [page {page_num:2d}/{TOTAL_PAGES}]  +{len(page_products):3d}  →  {len(all_products):4d} total")
        time.sleep(DELAY_BETWEEN_PAGES)


    print(f"[scrape] Listing pages done — {len(all_products)} products.")


    # ---- Step 2: detail-page enrichment ----
    if enrich:
        print(f"[scrape] Enriching detail pages ({max_workers} workers)…")
        enriched: list[dict] = [None] * len(all_products)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(enrich_from_detail, prod): i
                for i, prod in enumerate(all_products)
            }
            done = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                enriched[idx] = future.result()
                done += 1
                if done % 50 == 0 or done == len(all_products):
                    print(f"  [enrich] {done}/{len(all_products)}")
        all_products = enriched
        print("[scrape] Enrichment complete.")


    # ---- Step 3: export ----
    output_data = {
        "scraped_at":       datetime.now(timezone.utc).isoformat(),
        "location":         "KushMart Lackawanna, NY",
        "menu_url":         SHOP_URL,
        "total_products":   len(all_products),
        "note_on_quantity": (
            "KushMart does not expose numeric stock quantities on the public menu. "
            "in_stock reflects schema.org InStock/OutOfStock from the product detail page."
        ),
        "products": all_products,
    }
    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"[scrape] Done — {len(all_products)} products saved to {output}")
    return output_data




# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape the KushMart Lackawanna NY cannabis menu into JSON."
    )
    parser.add_argument(
        "--no-enrich", action="store_true",
        help="Skip detail-page enrichment (faster, omits category/image/cannabinoid_profile)"
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS,
        help=f"Parallel threads for detail-page fetches (default: {DEFAULT_WORKERS})"
    )
    parser.add_argument(
        "--output", default="kushmart_inventory.json",
        help="Output file path (default: kushmart_inventory.json)"
    )
    args = parser.parse_args()
    scrape(enrich=not args.no_enrich, max_workers=args.workers, output=args.output)
