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
