-- Tabelas do monitor de preços.

create table public.products (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    url text not null check (url ~ '^https?://' and char_length(url) <= 2048),
    store text not null check (store in ('mercado_livre', 'amazon_br')),
    title text not null check (title <> ''),
    image_url text,
    target_price numeric(12, 2) not null check (target_price > 0),
    -- Nulo enquanto o produto estiver esgotado.
    current_price numeric(12, 2) check (current_price > 0),
    currency text not null default 'BRL' check (currency ~ '^[A-Z]{3}$'),
    is_active boolean not null default true,
    last_checked_at timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    -- O índice desta restrição também atende às buscas por user_id.
    unique (user_id, url)
);

create table public.price_history (
    id bigint generated always as identity primary key,
    product_id uuid not null references public.products (id) on delete cascade,
    price numeric(12, 2) not null check (price > 0),
    checked_at timestamptz not null default now()
);

create table public.alerts (
    id bigint generated always as identity primary key,
    product_id uuid not null references public.products (id) on delete cascade,
    price numeric(12, 2) not null check (price > 0),
    sent_at timestamptz not null default now()
);

create index price_history_product_checked_idx
    on public.price_history (product_id, checked_at);
create index alerts_product_sent_idx on public.alerts (product_id, sent_at);
create index products_active_idx on public.products (id) where is_active;
