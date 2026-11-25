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
