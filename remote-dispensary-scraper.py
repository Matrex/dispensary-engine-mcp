import os
from fastmcp import FastMCP
from scraper.runner import run_full_pipeline, scrape_only, normalize_only

mcp = FastMCP("dispensary-menu-scraper")

@mcp.tool()
async def scrape_dispensary(menu_url: str, source: str = "auto") -> dict:
    """Scrape a single dispensary menu page and return raw products."""
    return await scrape_only(menu_url=menu_url, source=source)

@mcp.tool()
async def normalize_products(products: list[dict]) -> dict:
    """Run PEK filter + normalizer on raw products (no DB write)."""
    return normalize_only(products)

@mcp.tool()
async def ingest_menu(menu_url: str, dispensary_id: str, source: str = "auto") -> dict:
    """Full pipeline: scrape → PEK normalize → Supabase upsert."""
    return await run_full_pipeline(
        menu_url=menu_url,
        dispensary_id=dispensary_id,
        source=source,
    )

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        path="/mcp",
    )
