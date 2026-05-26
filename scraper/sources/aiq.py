How the scraper works


The three menus run on Dispense's API (api.dispenseapp.com) which is publicly accessible once you pass the correct headers. curl_cffi with impersonate="chrome124" bypasses Cloudflare on both the CDN and API layers.


Flow:


Fetches all product categories per venue (/v1/venues/{venue_id}/product-categories)
Paginates through all products per category with skip/limit=200 (/v1/venues/{venue_id}/product-categories/{cat_id}/products)
De-duplicates products that appear in multiple categories (e.g. "Offers/Specials")
Enriches each product with flattened lab values (THC, THCA, CBD, CBG, CBN), pricing tiers, full inventory quantities, images, effects, terpenes, and POS data
Each product record includes
name, brand, sku, slug, product_url
cannabis_type (SATIVA/INDICA/HYBRID/CBD), cannabis_strain, sub_type
weight, weight_unit, weight_formatted
price, price_gross, price_net, price_with_discounts, discount fields
quantity, quantity_total, quantity_sold, quantity_threshold
Lab values: thc, thca, cbd, cbda, cbg, cbn
effects, terpenes, images, created, modified
Full raw API payload for any additional fields
Usage
pip install curl_cffi
python dispense_scraper.py
# Outputs: dispense_menus_YYYYMMDD_HHMMSS.json
