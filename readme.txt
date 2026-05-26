
dispensary-menu-mcp/
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── requirements.txt
├── README.md
├── .env.example
├── remote-dispensary-scraper.py     # FastMCP remote entrypoint (mirrors remote-seo-checker.py)
├── local-dispensary-scraper.py      # FastMCP local dev entrypoint (mirrors local-seo-checker.py)
└── scraper/
    ├── __init__.py
    ├── runner.py                    # orchestrates: scrape → normalize → upsert
    ├── sources/
    │   ├── __init__.py
    │   ├── dutchie.py
    │   ├── carrot.py
    │   ├── proteus420.py
    │   ├── aiq.py
    │   ├── blaze.py
    │   ├── weedmaps.py
    │   └── iheartjane.py
    │   ├── kushmart.py
    │   ├── goodlife.py
    ├── pek/
    │   ├── __init__.py
    │   ├── filter.py                # PEK filter (Product Equivalence Key)
    │   ├── normalize.py             # title/brand/strain/size normalizer
    │   └── tokens.py                # stopwords, unit regexes, strain aliases
    └── db/
        ├── __init__.py
        └── supabase_client.py       # upsert by pek_hash





Deploy on your Hostinger Ubuntu VPS
ssh root@your-vps-ip
git clone https://github.com/<you>/dispensary-menu-mcp.git
cd dispensary-menu-mcp
cp .env.example .env && nano .env     # fill Supabase creds
docker-compose up -d --build
ufw allow 8080/tcp
curl http://your-vps-ip:8080/mcp
MCP client config
{
  "mcpServers": {
    "dispensary-menu": {
      "url": "https://your-app.hstgr.cloud/mcp",
      "description": "Dispensary menu scraper → PEK normalizer → Supabase"
    }
  }
}
Data flow
Client (Claude/Cursor) calls ingest_menu(menu_url, dispensary_id).
scraper/sources/*.py pulls raw menu JSON/HTML (Playwright for Dutchie/Jane, httpx for APIs).
pek/normalize.py cleans title/brand/strain/size/category.
pek/filter.py computes a deterministic pek_hash from (brand|strain|size|category|thc-bucket) and additionally fuzzy-merges close titles within the same brand+size.
db/supabase_client.py upserts on (dispensary_id, pek_hash) so re-scrapes update prices/stock instead of duplicating rows.
This mirrors the Hostinger template 1:1 (Dockerfile, docker-compose, Procfile, requirements.txt, remote-*.py FastMCP entrypoint, local-*.py for stdio dev) and only swaps the SEO logic for your scraper → PEK → Supabase pipeline.


_____________________________________________________________________________________________________________________

create table if not exists menu_products (
  id uuid primary key default gen_random_uuid(),
  dispensary_id text not null,
  pek_hash text not null,
  source text,
  title text,
  brand text,
  strain text,
  category text,
  size text,
  thc_pct numeric,
  price numeric,
  url text,
  raw jsonb,
  updated_at timestamptz default now(),
  unique (dispensary_id, pek_hash)
);
create index on menu_products (brand, strain, size);
