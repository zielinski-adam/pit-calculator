---
name: audit-pit38
description: End-to-end audit kalkulacji PIT-38 na podanym fixture CSV
---

Użycie: `/audit-pit38 [ścieżka_do_csv]`

Wykonaj pełny pipeline:
1. **Parsuj CSV** -- wyciągnij Trades, Financial Instrument Information, Dividends, WHT, Corporate Actions
2. **Oblicz settlement dates** -- dla każdego trade z exchange_calendars
3. **Pobierz kursy NBP** -- dla każdego settlement date D-1
4. **Oblicz FIFO** -- multi-year, po settle_date
5. **Wygeneruj podsumowanie PIT-38**:
   - C.22: Suma przychodów ze sprzedaży w PLN
   - C.23: Suma kosztów FIFO w PLN + prowizje
   - C.28/C.29: Dochód / Strata
   - D.31: Podstawa (zaokrąglona)
   - D.33: Podatek 19%
   - D.35: Podatek należny (zaokrąglony)
   - G.47: 19% × dywidendy brutto PLN
   - G.48: WHT w PLN
   - G.49: Różnica
   - PIT/ZG per kraj
6. **Wypisz wyniki** w formacie tabelarycznym
7. **Oflaguj transakcje brzegowe** (settle date w zakresie 26.12 - 05.01)
