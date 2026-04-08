---
name: check-nbp
description: Debug NBP client -- sprawdź kurs dla danej waluty i settlement date
---

Użycie: `/check-nbp [waluta] [settle_date]`

Przykład: `/check-nbp USD 2025-03-18`

Dla podanej waluty i settlement date:
1. Oblicz datę D-1 (ostatni dzień roboczy przed settle_date, pomijając weekendy i polskie święta)
2. Pobierz kurs średni NBP tabeli A z API: `https://api.nbp.pl/api/exchangerates/rates/a/{waluta}/{data_d1}/`
3. Wyświetl:
   - Settlement date: podana data
   - Data D-1: obliczona data
   - Kurs NBP: wartość z API
   - Źródło: link do tabeli NBP

Jeśli waluta = PLN, wyświetl: `Decimal("1")` (bez zapytania do API).

Jeśli API zwraca 404 (brak tabeli na ten dzień), cofnij się o kolejny dzień roboczy.
