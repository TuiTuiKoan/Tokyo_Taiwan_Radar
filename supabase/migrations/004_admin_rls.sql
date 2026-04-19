-- Allow admins to read ALL events (including inactive)
create policy "Admins read all events"
  on public.events for select
  using (public.is_admin());

-- Allow admins to insert events
create policy "Admins insert events"
  on public.events for insert
  with check (public.is_admin());

-- Allow admins to update events
create policy "Admins update events"
  on public.events for update
  using (public.is_admin());

-- Allow admins to delete events
create policy "Admins delete events"
  on public.events for delete
  using (public.is_admin());
