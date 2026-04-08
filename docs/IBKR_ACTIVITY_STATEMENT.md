# IBKR Activity Statement -- Instrukcja i format danych

## Dlaczego CSV (nie HTML, nie Flex Query XML)

### CSV Activity Statement

Wybrany format, bo:
- Ma sekcję `Financial Instrument Information` z **ISIN** i **Listing Exchange** per symbol
- Strukturalny format łatwy do parsowania
- Zawiera wszystkie potrzebne sekcje w jednym pliku

### HTML Activity Statement

Odrzucony jako format wejściowy, bo:
- Brak sekcji Financial Instrument Information
- Brak ISIN i Listing Exchange w tabeli Trades
- Trudniejszy do parsowania (HTML parsing vs CSV)
- Zachowany w `resources/` jako referencja

### Flex Query XML

Nie wymagamy -- user nie musi konfigurować Flex Query w IBKR.
CSV Activity Statement jest prostszy do wygenerowania i zawiera wystarczające dane.

## Jak wygenerować CSV Activity Statement

1. Zaloguj się do IBKR → Performance & Reports → Statements
2. Wybierz konto (uwaga: IBKR migrował konta między krajami -- sprawdź zamknięte konta)
3. Activity Statement → Annual → wybierz rok
4. **Format: CSV** (nie HTML, nie PDF)
5. Pobierz plik

**WAŻNE**: Pobierz raporty za WSZYSTKIE lata od otwarcia konta. FIFO wymaga pełnej historii.

## Struktura CSV

CSV jest podzielony na sekcje. Każda linia zaczyna się od nazwy sekcji.

### Sekcja: Trades

```csv
Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,C. Price,Proceeds,Comm/Fee,Basis,Realized P/L,MTM P/L,Code
Trades,Data,Order,Stocks,USD,AAPL,"2025-03-18, 10:30:00",100,178.50,,17850,-1.00,,,O
Trades,Data,Order,Stocks,USD,AAPL,"2025-04-15, 14:22:11",-100,185.00,,18500,-1.00,,650,,C
```

**Kluczowe pola:**
| Pole | Użycie |
|------|--------|
| Asset Category | "Stocks" lub "Equity and Index Options" |
| Currency | Waluta transakcji (USD, EUR) |
| Symbol | Identyfikator instrumentu |
| Date/Time | Trade date + czas (format: "YYYY-MM-DD, HH:MM:SS") |
| Quantity | Dodatnia = kupno, ujemna = sprzedaż |
| T. Price | Cena transakcji per unit |
| Proceeds | Kwota transakcji (ujemna = kupno, dodatnia = sprzedaż) |
| Comm/Fee | Prowizja (zazwyczaj ujemna) |
| Code | O = Open, C = Close, P = Partial, IA = inne |

**Brak settlement date!** → obliczamy z exchange_calendars.

### Sekcja: Financial Instrument Information

```csv
Financial Instrument Information,Header,Asset Category,Symbol,Description,Conid,Security ID,Underlying,Listing Exch,Multiplier,Type,Code
Financial Instrument Information,Data,Stocks,AAPL,APPLE INC,265598,US0378331005,AAPL,NASDAQ,1,COMMON,
Financial Instrument Information,Data,Stocks,IWDA,ISHARES CORE MSCI WORLD,100292038,IE00B4L5Y983,IWDA,AEB,1,ETF,
```

**Kluczowe pola:**
| Pole | Użycie |
|------|--------|
| Security ID | **ISIN** -- identyfikator międzynarodowy, prefix = kraj dla PIT/ZG |
| Listing Exch | **Giełda** -- mapowanie na exchange_calendars dla settlement date |
| Multiplier | 1 dla akcji, 100 dla opcji |
| Type | COMMON, ETF, itp. |

**Dla opcji -- osobny header:**
```csv
Financial Instrument Information,Header,Asset Category,Symbol,Description,Conid,Underlying,Listing Exch,Multiplier,Expiry,Delivery Month,Type,Strike,Code
Financial Instrument Information,Data,Equity and Index Options,NBIS 20MAR26 150 C,NBIS 20MAR26 150 C,813139361,NBIS,CBOE,100,2026-03-20,2026-03,C,150,
```

### Sekcja: Corporate Actions

```csv
Corporate Actions,Header,Asset Category,Currency,Report Date,Date/Time,Description,Quantity,Proceeds,Value,Realized P/L,Code
Corporate Actions,Data,Stocks,USD,2025-06-18,"2025-06-17, 20:25:00","IBKR(US45841N1072) Split 4 for 1 (IBKR, INTERACTIVE BROKERS GRO-CL A, US45841N1072)",4.9668,0,0,0,
```

**Parsowanie opisu splitu**: regex `(\w+)\((\w+)\) Split (\d+) for (\d+)`
- Group 1: Symbol
- Group 2: ISIN
- Group 3: ratio_to (nowa ilość)
- Group 4: ratio_from (stara ilość)

### Sekcja: Dividends

```csv
Dividends,Header,Currency,Date,Description,Amount
Dividends,Data,USD,2025-03-14,IBKR(US45841N1072) Payment in Lieu of Dividend (Ordinary Dividend),0.41
Dividends,Data,USD,2025-12-12,IBKR(US45841N1072) Cash Dividend USD 0.08 per Share (Ordinary Dividend),0.53
```

**Parsowanie opisu**: regex `(\w+)\((\w+)\) (Payment in Lieu of Dividend|Cash Dividend)`
- ISIN w nawiasie → kraj dla PIT/ZG
- Date = data wpływu na rachunek → kurs NBP D-1 od tej daty

### Sekcja: Withholding Tax

```csv
Withholding Tax,Header,Currency,Date,Description,Amount,Code
Withholding Tax,Data,USD,2025-03-14,IBKR(US45841N1072) Payment in Lieu of Dividend - US Tax,-0.06,
Withholding Tax,Data,USD,2025-06-04,Withholding @ 20% on Credit Interest for May-2025,-2.14,
```

**Dwa typy WHT:**
1. Dividend WHT (np. "- US Tax") → odliczenie w sekcji G PIT-38
2. Interest WHT (np. "Withholding @ 20% on Credit Interest") → PIT-36 (out of scope)

### Sekcja: Interest

```csv
Interest,Header,Currency,Date,Description,Amount
Interest,Data,EUR,2025-04-03,EUR Credit Interest for Mar-2025,0.46
```

Out of scope PIT-38 (to jest PIT-36). Parsujemy ale nie włączamy do kalkulacji.

### Sekcja: Grant Activity

```csv
Grant Activity,Header,Symbol,Report Date,Description,Award Date,Vesting Date,Quantity,Price,Value
Grant Activity,Data,IBKR,2025-09-19,Stock Award Vesting,2024-09-20,2025-09-19,1.1796,65.03,76.7094
```

Cost basis dla przyszłych sprzedaży = Price (FMV at vest). 
Zdarzenie dochodowe na PIT-36 (out of scope).

## Mapowanie Listing Exchange → exchange_calendars

| CSV Listing Exch | exchange_calendars code | Cykl | Uwagi |
|-----------------|------------------------|------|-------|
| NASDAQ | XNAS | T+1 od 2024-05-28, wcześniej T+2 | US SEC Rule |
| NYSE | XNYS | T+1 od 2024-05-28, wcześniej T+2 | j.w. |
| AEB | XAMS | T+2 (do 2027-10-11), potem T+1 | Euronext Amsterdam |
| CBOE | (używaj XNYS) | T+1 | OCC settlement |
| LSE | XLON | T+2 (do 2027-10-11), potem T+1 | London |
| ARCA | ARCX | T+1 od 2024-05-28 | NYSE ARCA |

## Wiersze SubTotal i Total

CSV zawiera wiersze podsumowań:
```csv
Trades,SubTotal,,Stocks,USD,AAPL,,0,,,-355,-12.21,0,-367.21,-355,
Trades,Total,,Stocks,USD,,,,,,-355,-12.21,0,-367.21,-355,
Trades,Total,,Stocks,PLN,,,,,,-1420,-48.84,0,-1468.84,-1420,
```

**Ignoruj** wiersze SubTotal i Total -- parsuj tylko wiersze `Data`.
Wiersz "Total in PLN" jest przeliczony po kursie IBKR (nie NBP!) -- nie używać.
