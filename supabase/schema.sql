-- ChessTempo Supabase schema.
-- Run this in the Supabase SQL editor (Project -> SQL Editor -> New query).
--
-- Supabase Auth already provides `auth.users` — we don't create our own
-- users table, just a `profiles` table keyed to it (the standard Supabase
-- pattern), plus tables for game history and difficulty tracking.

-- One row per user: their difficulty/strength state (tempo.mentor.difficulty).
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text,                                -- captured at signup (auth.users.raw_user_meta_data)
  starting_difficulty text not null default 'casual'
    check (starting_difficulty in ('beginner', 'casual', 'club', 'strong')),
  strength real not null default 0.30,          -- current DifficultyController.strength
  games_played integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One row per finished game, for history + as the personalization training log.
create table if not exists public.games (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  pgn text not null,                             -- full move list, for replay + fine-tuning data
  result text not null check (result in ('user_win', 'user_loss', 'draw')),
  strength_at_start real not null,               -- difficulty snapshot when the game began
  strength_at_end real not null,                 -- difficulty snapshot after the post-game update
  created_at timestamptz not null default now()
);

-- Track when a user's personalized model was last fine-tuned, and on how
-- many games, so the backend job knows who's due for a re-tune.
create table if not exists public.personalization_state (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  last_finetuned_at timestamptz,
  games_at_last_finetune integer not null default 0,
  model_checkpoint_path text                     -- Supabase Storage path, once fine-tuning ships
);

-- Row Level Security: a user can only ever see/edit their own rows. The
-- backend talks to Supabase using the service_role key (which bypasses
-- RLS entirely) for server-side operations like fine-tuning, so this is
-- primarily what protects direct frontend access using the anon key.
alter table public.profiles enable row level security;
alter table public.games enable row level security;
alter table public.personalization_state enable row level security;

create policy "profiles: read own" on public.profiles
  for select using (auth.uid() = id);
create policy "profiles: update own" on public.profiles
  for update using (auth.uid() = id);

create policy "games: read own" on public.games
  for select using (auth.uid() = user_id);
create policy "games: insert own" on public.games
  for insert with check (auth.uid() = user_id);

create policy "personalization_state: read own" on public.personalization_state
  for select using (auth.uid() = user_id);

-- Auto-create a profile row the moment someone signs up, so the frontend
-- never has to remember to do it manually. Seeds `strength` from whichever
-- starting difficulty they picked at signup (frontend/app/signup/page.tsx),
-- keeping it in sync with DifficultyController.STARTING_DIFFICULTY_MAP —
-- update both places together if that map ever changes.
create or replace function public.handle_new_user()
returns trigger as $$
declare
  -- raw_user_meta_data is client-supplied (anyone can call the signup API
  -- directly with arbitrary metadata, not just through our own signup
  -- form) — validate against the same set profiles.starting_difficulty's
  -- CHECK constraint allows, or a bogus value here would fail the insert
  -- below and block signup entirely.
  chosen_difficulty text := case new.raw_user_meta_data->>'starting_difficulty'
    when 'beginner' then 'beginner'
    when 'casual' then 'casual'
    when 'club' then 'club'
    when 'strong' then 'strong'
    else 'casual'
  end;
  initial_strength real := case chosen_difficulty
    when 'beginner' then 0.15
    when 'casual' then 0.30
    when 'club' then 0.50
    when 'strong' then 0.70
    else 0.30
  end;
begin
  insert into public.profiles (id, full_name, starting_difficulty, strength)
    values (new.id, new.raw_user_meta_data->>'full_name', chosen_difficulty, initial_strength);
  insert into public.personalization_state (user_id) values (new.id);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
