-- Agenda a verificação de preços: pg_cron chama a API por meio do pg_net.
-- A URL e o segredo ficam no Vault (veja supabase/README.md), nunca neste arquivo.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

-- Esquema não exposto pela API do Supabase.
create schema if not exists private;

create function private.request_price_check() returns void
language plpgsql security invoker set search_path = ''
as $$
declare
    api_url text;
    cron_secret text;
begin
    select decrypted_secret into api_url
        from vault.decrypted_secrets where name = 'price_monitor_api_url';
    select decrypted_secret into cron_secret
        from vault.decrypted_secrets where name = 'price_monitor_cron_secret';

    if api_url is null or cron_secret is null then
        raise warning 'Monitor de preços: configure os segredos no Vault';
        return;
    end if;

    perform net.http_post(
        url := rtrim(api_url, '/') || '/jobs/check-prices',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'X-Cron-Secret', cron_secret
        ),
        body := '{}'::jsonb,
        -- Margem para a API acordar em hospedagens gratuitas.
        timeout_milliseconds := 60000
    );
end;
$$;

revoke execute on function private.request_price_check() from public;

-- A cada 6 horas, no minuto 17 (UTC). Reagendar com o mesmo nome substitui o anterior.
select cron.schedule(
    'price-monitor-check-prices', '17 */6 * * *', 'select private.request_price_check()'
);
