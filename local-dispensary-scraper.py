"""Local stdio MCP entry point — for Claude Desktop / Cursor / Windsurf.

Run with:  python local-dispensary-scraper.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from remote_dispensary_scraper import mcp  # noqa: E402

if __name__ == "__main__":
    mcp.run()  # stdio transport for local agent clients
