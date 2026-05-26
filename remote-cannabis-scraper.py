# remote-cannabis-scrapers.py
from mcp.server.fastmcp import FastMCP
import json
import traceback

# Import your existing scraper scripts as modules
# Ensure your scraper files are named accordingly (e.g., dispenses_scraper.py)
import dispenses_scraper
import dutchie_scraper
from curl_cffi import requests as cffi_requests

# Initialize the MCP Server
mcp = FastMCP("Cannabis Menu Scraper API")

@mcp.tool()
def scrape_dispense_app(venue_id: str, dispensary_name: str) -> str:
    """
    Scrapes live cannabis inventory from a Dispense App dispensary.
    
    Args:
        venue_id: The unique venue ID (e.g., '390243df4f0ee7fa' for 82-J Cannabis).
        dispensary_name: The name of the dispensary.
        
    Returns:
        JSON string containing the live inventory data.
    """
    try:
        session = cffi_requests.Session()
        dispensary_config = {"venue_id": venue_id, "name": dispensary_name}
        
        # Call the core function from your uploaded Dispenses-Scraper
        products = dispenses_scraper.scrape_dispensary(session, dispensary_config)
        
        return json.dumps({
            "status": "success",
            "dispensary": dispensary_name,
            "total_products": len(products),
            "data": products
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e), "trace": traceback.format_exc()})

@mcp.tool()
def scrape_dutchie_menu(identifier: str) -> str:
    """
    Scrapes live cannabis inventory from a Dutchie platform dispensary.
    
    Args:
        identifier: The Dutchie URL, ID, or cName (e.g., 'best-budz-146-st').
        
    Returns:
        JSON string containing the live inventory data.
    """
    try:
        # Call the core function from your uploaded Dutchie-Scraper
        results = dutchie_scraper.scrape_menu(identifier, pricing_type="rec")
        
        return json.dumps({
            "status": "success",
            "total_products": results.get("total_products", 0),
            "data": results
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

# Add additional @mcp.tool() wrappers for Jane, Proteus420, Tymber, etc.

if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run()
