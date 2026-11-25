# Banco de dados

- `migrations/`: tabelas, RLS e funções, aplicadas em ordem.
- `tests/`: testes das migrations em um PostgreSQL embutido (não precisam de Docker).

## Testar

```powershell
cd supabase/tests
npm install
npm test
```

## Aplicar em um projeto Supabase

Na raiz do repositório:

```powershell
npx supabase login
npx supabase link --project-ref <ref-do-projeto>
npx supabase db push --dry-run
npx supabase db push
```

## Regras de acesso

| Tabela | Usuário | Job (`service_role`) |
|---|---|---|
| `products` | lê, cadastra e exclui os próprios; altera só `target_price` e `is_active` | total |
| `price_history` | lê o dos próprios produtos | total |
| `alerts` | lê os dos próprios produtos | total |

## Agendamento

A verificação roda a cada 6 horas. Depois do deploy da API, guarde a URL e o segredo no Vault,
pelo SQL Editor. Use o mesmo valor de `CRON_SECRET` da API:

```sql
select vault.create_secret('https://sua-api.exemplo.com', 'price_monitor_api_url');
select vault.create_secret('<CRON_SECRET>', 'price_monitor_cron_secret');
```

Sem esses segredos, o agendamento não faz nada. Para testar e acompanhar:

```sql
select private.request_price_check();
select status_code, error_msg, created from net._http_response order by created desc limit 5;
select * from cron.job_run_details order by start_time desc limit 5;
```

Para mudar a frequência, agende de novo com o mesmo nome:

```sql
select cron.schedule(
    'price-monitor-check-prices', '17 * * * *', 'select private.request_price_check()'
);
```
