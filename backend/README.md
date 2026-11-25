# Back-end

## Preparação (Windows / PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
```

No Linux/macOS, use `python3 -m venv .venv` e `source .venv/bin/activate`.

## Qualidade

```powershell
ruff check .
ruff format --check .
mypy app tests
pytest
```

## Consultar um preço

```powershell
python -m app.cli "https://www.amazon.com.br/dp/B09B8VGCR8"
```

Erros (loja não suportada, bloqueio, página inválida) saem em `stderr` com código 1.

## API

Preencha o `.env` (veja `.env.example`) e rode:

```powershell
uvicorn app.main:create_app --factory --reload
```

Documentação interativa: <http://localhost:8000/docs>. Todas as rotas, exceto `/health`,
exigem o token do Supabase Auth no header `Authorization: Bearer <token>`.

| Rota | Descrição |
|---|---|
| `POST /products` | cadastra e faz a primeira coleta |
| `GET /products` | lista os produtos do usuário |
| `GET /products/{id}` | detalha um produto |
| `PATCH /products/{id}` | altera `target_price` e/ou `is_active` |
| `DELETE /products/{id}` | exclui o produto e o histórico |
| `GET /products/{id}/history?days=30` | histórico de preços (1 a 365 dias) |
| `GET /health` | verifica se a API está no ar |

Erros seguem o formato `{"detail": "..."}`: 401 (login), 404 (produto inexistente ou de outro
usuário), 409 (já cadastrado), 422 (dados inválidos ou loja não suportada), 502 (falha da loja)
e 503 (Supabase indisponível). Nos erros de validação, `detail` é uma lista. Preços são enviados
como texto (`"100.55"`), para não perder precisão.
