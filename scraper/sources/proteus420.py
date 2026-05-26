Setup & run:


pip install curl_cffi beautifulsoup4
python proteus420_scraper.py
Output — creates ./inventory_output/ with:


tcsbflo_<timestamp>.json — 311 products, 9 categories
honeykenmore_<timestamp>.json — 503 products, 9 categories
tokelane_<timestamp>.json — 710 products across 3 locations (Trenton Medical, Trenton Adult Use, Buffalo NY)
all_stores_<timestamp>.json — everything combined (~1.2 MB)
Each product includes: id, name, brand, price, inventory_qty, lab_data (THC/CBD/Terpenes when available), short_description, on_sale, image_url, full_url, strain_id.


#!/usr/bin/env python3
"""
Proteus420 Dispensary Inventory Scraper
Scrapes product inventory from three Proteus420-powered dispensary stores:
  - The Cannabis Store (tcsbflo.com)
  - Honey Kenmore (cart.honeykenmore.com)
  - Toke Lane (cart.tokelane.com)


Uses curl_cffi to bypass CDN/Cloudflare protection.
Exports inventory organized by category to JSON files.
"""


import json
import re
import time
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup


try:
    from curl_cffi import requests as cffi_requests
    USE_CURL_CFFI = True
    print("[INFO] Using curl_cffi for CDN bypass")
except ImportError:
    import requests as cffi_requests
    USE_CURL_CFFI = False
    print("[WARN] curl_cffi not found, falling back to standard requests")




# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────


STORES = [
    {
        "name": "The Cannabis Store",
        "slug": "tcsbflo",
        "base_url": "https://tcsbflo.com",
        "cart_path": "/cart",
        "products_endpoint": "/cart/cart/ajax_getproducts.cfm",
        "filters_endpoint": "/cart/cart/ajax_getfilters.cfm",
        "session_params": {},
    },
    {
        "name": "Honey Kenmore",
        "slug": "honeykenmore",
        "base_url": "https://cart.honeykenmore.com",
        "cart_path": "/",
        "products_endpoint": "/cart/ajax_getproducts.cfm",
        "filters_endpoint": "/cart/ajax_getfilters.cfm",
        "session_params": {},
    },
    {
        "name": "Toke Lane",
        "slug": "tokelane",
        "base_url": "https://cart.tokelane.com",
        "cart_path": "/",
        "products_endpoint": "/cart/ajax_getproducts.cfm",
        "filters_endpoint": "/cart/ajax_getfilters.cfm",
        "session_params": {},
        # Toke Lane has multiple locations - we scrape all of them
        "locations": [
            {"acc": "1140", "loc": "1", "shoptype": "Pickup", "label": "Trenton - Medical NJ"},
            {"acc": "1140", "loc": "2", "shoptype": "Pickup", "label": "Trenton - Adult Use NJ"},
            {"acc": "1153", "loc": "1", "shoptype": "Pickup", "label": "Buffalo NY"},
        ],
    },
]


OUTPUT_DIR = Path("./inventory_output")
OUTPUT_DIR.mkdir(exist_ok=True)


REQUEST_DELAY = 0.5   # seconds between requests to be polite
TIMEOUT = 30          # request timeout in seconds




# ─────────────────────────────────────────────
#  HTTP SESSION
# ─────────────────────────────────────────────


def make_session():
    """Create a curl_cffi or requests session that mimics a real browser."""
    if USE_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome120")
    else:
        session = cffi_requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
    return session




# ─────────────────────────────────────────────
#  PARSING HELPERS
# ─────────────────────────────────────────────


def parse_product_card(card_div) -> dict:
    """Extract all available data from a Proteus420 product card <div>."""
    product = {}


    product["id"] = card_div.get("data-id", "").strip()


    link = card_div.select_one("a.item_view[data-id]")
    if link:
        product["url_path"] = link.get("href", "").strip()
        product["name"] = link.get("title", "").strip() or link.get("alt", "").strip()
        product["brand"] = link.get("data-brandname", "").strip()
        product["slug"] = link.get("data-prodname", "").strip()


    # Name fallback
    name_el = card_div.select_one(".product_name")
    if name_el and not product.get("name"):
        product["name"] = name_el.get_text(strip=True)


    # Short description
    desc_el = card_div.select_one(".product_short_description")
    if desc_el:
        product["short_description"] = desc_el.get_text(strip=True)


    # Price — regular and sale
    price_el = card_div.select_one(".price span")
    if price_el:
        raw_price = price_el.get_text(strip=True)
        product["price"] = raw_price.replace("\xa0", "").strip()


    # Sale price (if present)
    sale_el = card_div.select_one(".product_sale_price")
    if sale_el:
        product["sale_price"] = sale_el.get_text(strip=True)


    old_el = card_div.select_one(".product_regular_price")
    if old_el:
        product["regular_price"] = old_el.get_text(strip=True)


    # Inventory — stored in an HTML comment: <!--<small><small>Inv: N</small></small>-->
    card_str = str(card_div)
    inv_match = re.search(r"Inv:\s*(\d+)", card_str)
    if inv_match:
        product["inventory_qty"] = int(inv_match.group(1))
    else:
        product["inventory_qty"] = None


    # Lab data (THC, CBD, terpenes) — rendered as .labinfo spans
    lab_spans = card_div.select(".labinfo")
    lab_data = {}
    for span in lab_spans:
        text = span.get_text(strip=True)
        kv = text.split(":", 1)
        if len(kv) == 2:
            lab_data[kv[0].strip()] = kv[1].strip()
    if lab_data:
        product["lab_data"] = lab_data


    # Image URL (CloudFront CDN)
    img = card_div.select_one("img.product-image")
    if img:
        product["image_url"] = img.get("data-src", img.get("src", "")).strip()


    # On-sale flag
    product["on_sale"] = bool(card_div.select_one(".salebanner, #forsalebanner"))


    # Strain class (products_strain_N)
    for cls in card_div.get("class", []):
        m = re.match(r"products_strain_(\d+)", cls)
        if m:
            product["strain_id"] = m.group(1)


    return product




def extract_categories_from_html(html: str) -> list[dict]:
    """Return list of {id, name} category dicts from a Proteus420 cart page."""
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    cats = []
    for a in soup.select("a.getproducts[data-id][data-catname]"):
        cat_id = a.get("data-id", "").strip()
        cat_name = a.get("data-catname", "").strip()
        if cat_name and cat_name not in ("featured", "onsale", "onsalepage") and cat_id not in seen:
            seen.add(cat_id)
            cats.append({"id": cat_id, "name": cat_name})
    return cats




# ─────────────────────────────────────────────
#  CORE SCRAPE FUNCTIONS
# ─────────────────────────────────────────────


def fetch_html(session, url: str, params: dict = None, referer: str = None) -> str | None:
    """GET a URL and return HTML text, or None on failure."""
    headers = {"Referer": referer} if referer else {}
    try:
        r = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        print(f"  [ERROR] GET {url} — {exc}")
        return None




def scrape_store_products(session, store: dict, location: dict = None) -> dict:
    """
    Scrape all products from a single store (and optionally a specific location).
    Returns {category_name: [product, ...], ...}
    """
    base = store["base_url"]
    cart_path = store["cart_path"]
    products_ep = store["products_endpoint"]


    if location:
        cart_url = (
            f"{base}{cart_path}"
            f"?acc={location['acc']}&loc={location['loc']}"
            f"&shoptype={location['shoptype']}"
        )
        if USE_CURL_CFFI:
            session.cookies.set("acc", location["acc"], domain=base.split("//")[1])
            session.cookies.set("loc", location["loc"], domain=base.split("//")[1])
            session.cookies.set("shoptype", location["shoptype"], domain=base.split("//")[1])
    else:
        cart_url = f"{base}{cart_path}"


    print(f"\n  Fetching main page: {cart_url}")
    main_html = fetch_html(session, cart_url)
    if not main_html:
        return {}


    categories = extract_categories_from_html(main_html)
    print(f"  Found {len(categories)} categories: {[c['name'] for c in categories]}")


    inventory_by_category = {}
    categories_with_featured = [{"id": "", "name": "Featured"}] + categories


    for cat in categories_with_featured:
        cat_id = cat["id"]
        cat_name = cat["name"]


        products_url = f"{base}{products_ep}"
        params = {"cat": cat_id, "sel_soldout": "n", "page": "all"}


        print(f"    Fetching category [{cat_name}] (id={cat_id or 'all'}) ... ", end="", flush=True)
        time.sleep(REQUEST_DELAY)


        cat_html = fetch_html(session, products_url, params=params, referer=cart_url)
        if not cat_html:
            print("FAILED")
            continue


        soup = BeautifulSoup(cat_html, "html.parser")
        cards = soup.select(".product-card-wrapper")


        products = []
        for card in cards:
            try:
                p = parse_product_card(card)
                if p.get("id") and p.get("name"):
                    url_path = p.get("url_path", "")
                    if url_path and not url_path.startswith("/"):
                        url_path = "/" + url_path
                    p["full_url"] = base + url_path
                    products.append(p)
            except Exception as exc:
                print(f"\n      [WARN] parse error: {exc}")


        print(f"{len(products)} products")
        if products:
            inventory_by_category[cat_name] = products


    return inventory_by_category




# ─────────────────────────────────────────────
#  DEDUPLICATION
# ─────────────────────────────────────────────


def dedupe_category(products: list[dict]) -> list[dict]:
    """Remove duplicate product IDs within a category."""
    seen_ids = set()
    unique = []
    for p in products:
        pid = p.get("id", "")
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique.append(p)
    return unique




# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = {}


    for store in STORES:
        print(f"\n{'='*60}")
        print(f"  Store: {store['name']} ({store['base_url']})")
        print(f"{'='*60}")


        session = make_session()


        if "locations" in store:
            store_data = {"store_name": store["name"], "locations": {}}
            for location in store["locations"]:
                print(f"\n  --- Location: {location['label']} ---")
                loc_session = make_session()
                loc_inventory = scrape_store_products(loc_session, store, location)


                for cat_name in loc_inventory:
                    loc_inventory[cat_name] = dedupe_category(loc_inventory[cat_name])


                store_data["locations"][location["label"]] = {
                    "location_info": location,
                    "scraped_at": datetime.now().isoformat(),
                    "categories": loc_inventory,
                    "total_products": sum(len(v) for v in loc_inventory.values()),
                }
                print(f"    => Total unique products: {store_data['locations'][location['label']]['total_products']}")


            all_results[store["slug"]] = store_data


        else:
            inventory = scrape_store_products(session, store)


            for cat_name in inventory:
                inventory[cat_name] = dedupe_category(inventory[cat_name])


            store_data = {
                "store_name": store["name"],
                "scraped_at": datetime.now().isoformat(),
                "categories": inventory,
                "total_products": sum(len(v) for v in inventory.values()),
            }
            print(f"  => Total unique products: {store_data['total_products']}")
            all_results[store["slug"]] = store_data


        store_file = OUTPUT_DIR / f"{store['slug']}_{timestamp}.json"
        store_file.write_text(json.dumps(store_data, indent=2, ensure_ascii=False))
        print(f"  Saved: {store_file}")


    combined_file = OUTPUT_DIR / f"all_stores_{timestamp}.json"
    combined_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"\n{'='*60}")
    print(f"  Combined output saved: {combined_file}")
    print(f"{'='*60}\n")


    for slug, data in all_results.items():
        if "locations" in data:
            total = sum(loc["total_products"] for loc in data["locations"].values())
            print(f"  {data['store_name']}: {total} products across {len(data['locations'])} locations")
        else:
            print(f"  {data['store_name']}: {data.get('total_products', 0)} products")




if __name__ == "__main__":
    main()
