create extension if not exists pgcrypto;

-- =========================
-- Tables
-- =========================

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  telegram_chat_id bigint unique,
  telegram_link_code text unique,
  timezone text not null default 'Asia/Kolkata',
  daily_alert_cap int not null default 5,
  created_at timestamptz not null default now()
);

create table public.instruments (
  id bigint generated always as identity primary key,
  symbol text not null,
  exchange text not null check (exchange in ('NSE','BSE','AMFI')),
  name text,
  instrument_type text not null default 'equity'
    check (instrument_type in ('equity','mutual_fund')),
  unique (symbol, exchange)
);

create table public.quotes (
  instrument_id bigint primary key references public.instruments(id) on delete cascade,
  price numeric not null,
  prev_close numeric,
  volume bigint,
  updated_at timestamptz not null default now()
);

create table public.news_items (
  id uuid primary key default gen_random_uuid(),
  instrument_id bigint not null references public.instruments(id) on delete cascade,
  title text not null,
  url text not null,
  source text,
  published_at timestamptz,
  summary text,
  relevance smallint,
  created_at timestamptz not null default now(),
  unique (instrument_id, url)
);

create table public.positions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  instrument_id bigint not null references public.instruments(id),
  intent text not null
    check (intent in ('holding','considering_buy','considering_sell')),
  quantity numeric check (quantity >= 0),
  avg_price numeric check (avg_price >= 0),
  thesis text,
  source text not null default 'chat' check (source in ('chat','manual','csv')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, instrument_id)
);

create table public.alert_rules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  position_id uuid not null references public.positions(id) on delete cascade,
  rule_type text not null
    check (rule_type in ('price_above','price_below','day_drop_pct','day_gain_pct')),
  threshold numeric not null,
  active boolean not null default true,
  last_triggered_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  instrument_id bigint not null references public.instruments(id),
  run_id uuid,                                  -- ties an alert to one monitoring cycle
  trigger_type text not null,
  importance smallint not null check (importance between 1 and 10),
  message text not null,
  why text,
  dedup_key text not null,
  status text not null default 'queued'
    check (status in ('queued','sent','suppressed','failed')),
  sent_at timestamptz,
  feedback smallint check (feedback in (-1, 1)),
  created_at timestamptz not null default now(),
  unique (user_id, dedup_key)                   -- idempotency: no double alerts
);
create index alerts_user_created_idx on public.alerts (user_id, created_at desc);

create table public.chat_messages (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null check (role in ('user','assistant','tool')),
  content text not null,
  created_at timestamptz not null default now()
);
create index chat_messages_user_created_idx on public.chat_messages (user_id, created_at);

-- =========================
-- Triggers
-- =========================

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end $$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

create trigger positions_set_updated_at
before update on public.positions
for each row execute function public.set_updated_at();

-- =========================
-- Row-level security
-- =========================

alter table public.profiles      enable row level security;
alter table public.instruments   enable row level security;
alter table public.quotes        enable row level security;
alter table public.news_items    enable row level security;
alter table public.positions     enable row level security;
alter table public.alert_rules   enable row level security;
alter table public.alerts        enable row level security;
alter table public.chat_messages enable row level security;

create policy "own profile read" on public.profiles
  for select to authenticated using (id = auth.uid());
create policy "own profile update" on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy "own positions" on public.positions
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own rules" on public.alert_rules
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "own alerts read" on public.alerts
  for select to authenticated using (user_id = auth.uid());
create policy "own alerts rate" on public.alerts
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "own chat read" on public.chat_messages
  for select to authenticated using (user_id = auth.uid());

create policy "read instruments" on public.instruments
  for select to authenticated using (true);
create policy "read quotes" on public.quotes
  for select to authenticated using (true);
create policy "read news" on public.news_items
  for select to authenticated using (true);

-- =========================
-- Grants (auto-expose is OFF, so nothing is reachable until granted)
-- =========================

grant usage on schema public to anon, authenticated, service_role;

grant select on public.instruments, public.quotes, public.news_items to authenticated;
grant select, insert, update, delete on public.positions, public.alert_rules to authenticated;
grant select on public.alerts, public.chat_messages to authenticated;
grant update (feedback) on public.alerts to authenticated;       -- users can only rate alerts
grant select on public.profiles to authenticated;
grant update (display_name, timezone, daily_alert_cap) on public.profiles to authenticated;

-- backend uses the service role
grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;
