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
