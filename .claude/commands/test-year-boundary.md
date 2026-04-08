---
name: test-year-boundary
description: Uruchom testy brzegów roku podatkowego (NYSE T+1, GPW T+2, AEB T+2)
---

Uruchom testy brzegów roku:

```bash
cd backend && uv run pytest -m boundary -v --tb=long
```

Jeśli testy nie istnieją, utwórz je z następującymi scenariuszami:

1. **NYSE trade 2025-12-31** → settle 2026-01-02 → rok podatkowy 2026
2. **NYSE trade 2025-12-30** → settle 2025-12-31 → rok podatkowy 2025
3. **NYSE trade 2024-12-31** → settle 2025-01-02 → rok podatkowy 2025
4. **GPW trade 2025-12-29** → settle 2025-12-31 → rok podatkowy 2025
5. **GPW trade 2025-12-30** → settle 2026-01-02 → rok podatkowy 2026
6. **Reforma T+1**: NYSE 2024-05-27 (T+2) vs 2024-05-28 (T+1)
7. **AEB trade** z uwzględnieniem kalendarza Euronext Amsterdam

Każdy test musi weryfikować:
- `compute_settlement()` zwraca poprawną datę
- `tax_year()` zwraca poprawny rok
- Kurs NBP jest pobierany z D-1 od settle_date (nie trade_date)
