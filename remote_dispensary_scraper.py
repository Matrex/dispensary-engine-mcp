"""Remote MCP + FastAPI entry point.

MCP  →  POST /mcp   (SSE transport, for agents / Windsurf / Cursor remote)
REST →  GET  /health
       GET  /api/sources
       POST /api/scrape
       POST /api/ingest
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastmcp import FastMCP

from scraper.runner import run_full_pipeline, scrape_only, normalize_only, SOURCE_MAP

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("dispensary-menu-scraper")

@mcp.tool()
async def scrape_dispensary(menu_url: str, source: str = "auto") -> dict:
    """Scrape a single dispensary menu and return raw products."""
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

@mcp.tool()
def list_sources() -> dict:
    """Return all supported platform source keys."""
    return {"sources": list(SOURCE_MAP.keys())}

# ---------------------------------------------------------------------------
# FastAPI app with MCP mounted at /mcp
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Dispensary Engine MCP", lifespan=lifespan)

# Mount MCP SSE endpoint
mcp_app = mcp.get_asgi_app()
app.mount("/mcp", mcp_app)

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "sources": list(SOURCE_MAP.keys())}

@app.get("/api/sources")
def api_sources():
    return {"sources": list(SOURCE_MAP.keys())}

class ScrapeRequest(BaseModel):
    menu_url: str
    source: str = "auto"

class IngestRequest(BaseModel):
    menu_url: str
    dispensary_id: str
    source: str = "auto"

@app.post("/api/scrape")
async def api_scrape(req: ScrapeRequest):
    try:
        result = await scrape_only(menu_url=req.menu_url, source=req.source)
        return result
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/api/ingest")
async def api_ingest(req: IngestRequest):
    try:
        result = await run_full_pipeline(
            menu_url=req.menu_url,
            dispensary_id=req.dispensary_id,
            source=req.source,
        )
        return result
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# ---------------------------------------------------------------------------
# Direct run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "remote_dispensary_scraper:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=False,
    )
