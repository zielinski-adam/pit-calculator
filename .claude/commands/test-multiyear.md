---
name: test-multiyear
description: Uruchom syntetyczny scenariusz multi-year FIFO
---

Uruchom testy multi-year:

```bash
cd backend && uv run pytest -m fifo -k "multi_year" -v --tb=long
```

Jeśli testy nie istnieją, utwórz syntetyczny scenariusz:

1. **Rok 2022**: Kupno 100 AAPL @ 150 USD (T+2, settle 2022-xx-xx)
2. **Rok 2023**: Kupno 100 AAPL @ 170 USD (T+2, settle 2023-xx-xx)
3. **Rok 2024**: Split 4:1 AAPL → 800 shares @ 42.50/37.50 USD
4. **Rok 2024**: Kupno 200 AAPL @ 180 USD (T+1 po reformie, settle 2024-xx-xx)
5. **Rok 2025**: Sprzedaż 500 AAPL @ 200 USD

Weryfikuj:
- FIFO bierze loty w kolejności: 2022, 2023, 2024 (split-adjusted)
- Każdy lot ma WŁASNY kurs NBP z D-1 od SWOJEGO settle_date
- Raport za 2025 zawiera tylko tę sprzedaż (sell_settle_date.year == 2025)
- Zostaje 500 AAPL w portfolio (300 z split + 200 nowe)
