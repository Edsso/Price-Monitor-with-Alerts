-- Segurança: cada usuário só acessa os próprios dados; o job usa service_role, que ignora RLS.

alter table public.products enable row level security;
alter table public.price_history enable row level security;
alter table public.alerts enable row level security;

-- Privilégios explícitos, sem depender dos padrões do projeto.
revoke all on public.products, public.price_history, public.alerts from anon, authenticated;
grant select, insert, update, delete
    on public.products, public.price_history, public.alerts to service_role;

grant select, delete on public.products to authenticated;
grant insert (
    user_id, url, store, title, image_url, target_price, current_price, currency, last_checked_at
) on public.products to authenticated;
-- Preço atual e dados da coleta só mudam pelo job.
grant update (target_price, is_active) on public.products to authenticated;

-- Histórico e alertas são registros do sistema: o usuário apenas lê.
grant select on public.price_history, public.alerts to authenticated;

create policy "Usuário lê os próprios produtos"
    on public.products for select to authenticated
    using (user_id = (select auth.uid()));

create policy "Usuário cadastra os próprios produtos"
    on public.products for insert to authenticated
    with check (user_id = (select auth.uid()));

create policy "Usuário altera os próprios produtos"
    on public.products for update to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));

create policy "Usuário exclui os próprios produtos"
    on public.products for delete to authenticated
    using (user_id = (select auth.uid()));

create policy "Usuário lê o histórico dos próprios produtos"
    on public.price_history for select to authenticated
    using (exists (
        select 1 from public.products p
        where p.id = product_id and p.user_id = (select auth.uid())
    ));

create policy "Usuário lê os alertas dos próprios produtos"
    on public.alerts for select to authenticated
    using (exists (
        select 1 from public.products p
        where p.id = product_id and p.user_id = (select auth.uid())
    ));
