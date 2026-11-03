create table if not exists public.scooter_settings (
 user_id uuid primary key references auth.users(id) on delete cascade,
 payload jsonb not null default '{}'::jsonb,
 updated_at timestamptz not null default now()
);
alter table public.scooter_settings enable row level security;
create policy "Owner read" on public.scooter_settings for select to authenticated using (auth.uid()=user_id);
create policy "Owner insert" on public.scooter_settings for insert to authenticated with check (auth.uid()=user_id);
create policy "Owner update" on public.scooter_settings for update to authenticated using (auth.uid()=user_id) with check (auth.uid()=user_id);
