-- ═══════════════════════════════════════════════════════════════════════════
--  REDVERSE CATHEDRAL REGISTRY — Supabase Schema
--  Run this in your Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── PROFILES TABLE ───
-- Created automatically on user signup via trigger.
-- Stores covenant rank, visit history, and Aurora card link.

create table if not exists public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text,
  title text default 'Acolyte',
  tier text default 'acolyte' check (tier in ('wanderer','acolyte','devotee','crimson_circle')),
  aurora_card_id text,
  first_visit timestamptz default now(),
  last_visit timestamptz default now(),
  visit_count integer default 1,
  created_at timestamptz default now()
);

comment on table public.profiles is 'Cathedral Registry — visitor profiles and covenant ranks';

-- RLS: users can only read/update their own profile
alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update
  using (auth.uid() = id);

-- Allow inserts from trigger (security definer)
create policy "Service can insert profiles"
  on profiles for insert
  with check (true);


-- ─── MEMORY EVENTS TABLE ───
-- Per-user session memory — mirrors MemoryBridge's event structure.
-- Stores every significant interaction for Sable's recall.

create table if not exists public.memory_events (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  session_id text not null,
  event_type text not null,
  content jsonb not null,
  emotional_state jsonb,
  created_at timestamptz default now()
);

comment on table public.memory_events is 'Per-user interaction memory for Sable relational context';

-- Indexes for fast per-user queries
create index if not exists idx_memory_user_id on memory_events(user_id);
create index if not exists idx_memory_session on memory_events(user_id, session_id);
create index if not exists idx_memory_created on memory_events(user_id, created_at desc);

-- RLS: users can only access their own memory
alter table public.memory_events enable row level security;

create policy "Users can read own memory"
  on memory_events for select
  using (auth.uid() = user_id);

create policy "Users can write own memory"
  on memory_events for insert
  with check (auth.uid() = user_id);


-- ─── SABLE CONTEXT TABLE ───
-- Sable's compressed per-user relational context.
-- What she "knows" about each visitor across all their sessions.

create table if not exists public.sable_context (
  user_id uuid references public.profiles(id) on delete cascade primary key,
  relationship_summary text,
  emotional_baseline jsonb,
  interaction_count integer default 0,
  favorite_sagas text[],
  last_topic text,
  personality_notes text,
  updated_at timestamptz default now()
);

comment on table public.sable_context is 'Sable relational memory — compressed per-visitor context';

-- RLS
alter table public.sable_context enable row level security;

create policy "Users can read own sable_context"
  on sable_context for select
  using (auth.uid() = user_id);

create policy "Users can insert own sable_context"
  on sable_context for insert
  with check (auth.uid() = user_id);

create policy "Users can update own sable_context"
  on sable_context for update
  using (auth.uid() = user_id);


-- ─── AUTO-CREATE PROFILE ON SIGNUP ───
-- Trigger function that fires after a new user signs up.
-- Creates their profile and initializes Sable's context for them.

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, tier, title)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'display_name', 'Anonymous Wanderer'),
    'acolyte',
    'Acolyte'
  );
  
  insert into public.sable_context (user_id, relationship_summary)
  values (
    new.id,
    'New soul at the Cathedral doors. Greet with curious warmth.'
  );
  
  return new;
end;
$$ language plpgsql security definer;

-- Drop existing trigger if present (safe for re-runs)
drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();


-- ─── HELPER: INCREMENT VISIT COUNT ───
-- RPC function called from the client to atomically increment visits.

create or replace function public.increment_visit(user_id_input uuid)
returns void as $$
begin
  update public.profiles
  set 
    visit_count = visit_count + 1,
    last_visit = now()
  where id = user_id_input
    and id = auth.uid();  -- RLS enforcement
end;
$$ language plpgsql security definer;


-- ═══════════════════════════════════════════════════════════════════════════
--  DONE — Your Cathedral Registry is ready.
--  
--  Next steps:
--    1. Enable Email Auth in Supabase Dashboard → Authentication → Providers
--    2. (Optional) Enable Google/GitHub/Discord OAuth providers
--    3. Copy your project URL and anon key into redverse-auth.js
--    4. Deploy and test
-- ═══════════════════════════════════════════════════════════════════════════
