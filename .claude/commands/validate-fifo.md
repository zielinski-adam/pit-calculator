---
name: validate-fifo
description: Uruchom wszystkie testy FIFO engine
---

Uruchom testy FIFO:

```bash
cd backend && uv run pytest -m fifo -v --tb=short
```

Jeśli testy nie istnieją jeszcze, wypisz jakie testy powinny być napisane na podstawie `docs/FIFO_MULTI_YEAR.md`.

Sprawdź też:
1. Czy są testy brzegu roku (grudzień/styczeń) -- `pytest -m boundary`
2. Czy testy używają `Decimal` (grep for `float` in test files)
3. Czy FIFO sortuje po (settle_date, trade_date)
