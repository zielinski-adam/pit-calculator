# CLAUDE.md -- Kalkulator PIT-38 dla Interactive Brokers

## Przegląd projektu

Open-source kalkulator polskiego podatku giełdowego (PIT-38 + PIT/ZG) dla inwestorów korzystających z Interactive Brokers. Parsuje CSV Activity Statement, oblicza FIFO multi-year, generuje gotowe wartości do wypełnienia PIT-38.

**Nie-cele**: kryptowaluty, działalność gospodarcza, PIT-36, IKE/IKZE, generowanie e-Deklaracji XML.

## KRYTYCZNA ZASADA: Settlement Date (przeczytaj LEGAL_FOUNDATION.md)

Cały projekt opiera się na art. 17 ust. 1ab pkt 1 ustawy o PIT:
- **Rok podatkowy** = rok settlement date, NIE trade date
- **Kurs NBP** = z ostatniego dnia roboczego przed settlement date (D-1)
- **FIFO ordering** = po (settle_date, trade_date)
- Settlement date obliczamy z trade date + exchange_calendars (CSV nie zawiera settlement date)

**RED FLAGS -- natychmiast STOP jeśli widzisz:**
- `float` w kodzie finansowym (ZAWSZE `Decimal`)
- `trade_date.year` użyte jako rok podatkowy
- Kurs NBP pobierany dla D-1 od trade date (zamiast settle date)
- FIFO sortowane po trade date
- Hardcoded daty świąt giełdowych

## Stack techniczny

### Backend -- Python
- Python 3.12+, FastAPI, Pydantic v2 (frozen=True)
- `Decimal` -- WSZYSTKIE kwoty pieniężne, NIGDY float
- `StrEnum` -- wszystkie enumy
- `exchange_calendars` -- kalendarze świąt NYSE/NASDAQ/GPW/AEB dla settlement date
- `httpx` (async) -- klient HTTP do NBP API
- `loguru` -- logowanie
- `click` + `rich` -- CLI
- `uv` -- package manager
- `pytest`, `ruff`, `mypy --strict`

### Frontend -- React
- React 18+, TypeScript 5, Vite
- TailwindCSS + shadcn/ui
- TanStack Router, Query, Table
- Zustand, Zod + react-hook-form
- pnpm

## Format wejściowy: IBKR Activity Statement CSV

Parser czyta CSV (nie Flex Query XML, nie HTML). Kluczowe sekcje:
- `Trades` -- transakcje (trade date, symbol, quantity, price, commission)
- `Financial Instrument Information` -- ISIN, Listing Exchange per symbol
- `Corporate Actions` -- splity, inne zdarzenia korporacyjne
- `Dividends` -- dywidendy z ISIN w opisie
- `Withholding Tax` -- podatek u źródła
- `Interest` -- odsetki (dokumentowane, ale out of scope PIT-38)
- `Grant Activity` -- stock awards (out of scope PIT-38)

Settlement date obliczany z: trade date + Listing Exchange → exchange_calendars.

## Instrumenty w scope

- **Akcje** (Stocks) -- NYSE, NASDAQ, AEB (Euronext Amsterdam), GPW
- **Opcje giełdowe** (Equity & Index Options) -- CBOE, pełna obsługa: open/close, wygaśnięcie, exercise/assignment
- **ETF** (jak akcje, akumulacyjne nie generują dywidend)

## Architektura katalogów

```
pit-calculator/
├── CLAUDE.md, LEGAL_FOUNDATION.md, README.md
├── backend/src/pit38/
│   ├── models/        # Pydantic: Trade, Dividend, TaxLot, Exchange, PIT38Report
│   ├── parsers/       # CSV Activity Statement parser
│   ├── settlement/    # compute_settlement(), exchange mappings
│   ├── nbp/           # NBP API client + SQLite cache
│   ├── fifo/          # Multi-year FIFO engine
│   ├── tax/           # PIT-38 calculator, PIT/ZG mapper
│   ├── api/           # FastAPI routes
│   └── cli.py         # Click CLI
├── frontend/src/
│   ├── pages/         # 8 stron (Import, FIFO, Transakcje, Splity, Portfolio, Dywidendy, Koszty, Podsumowanie)
│   └── components/    # DataTable, YearSelector, YearBoundaryBadge, etc.
├── docs/              # TAX_RULES, FIFO_MULTI_YEAR, IBKR_ACTIVITY_STATEMENT, UX_REFERENCE
└── resources/         # Prawdziwe dane IBKR (CSV + HTML) + screenshoty
```

## Konwencje

- Komentarze w kodzie: po polsku
- Commit messages: Conventional Commits z polskimi opisami
  - Scope: `settlement`, `parser`, `fifo`, `nbp`, `tax`, `api`, `frontend`, `docs`, `tests`
- Decimal: `quantize(Decimal('0.01'))` dla PLN, `quantize(Decimal('0.000001'))` dla kursów
- Testy: każdy scenariusz FIFO musi mieć test brzegu roku (grudzień/styczeń)

## Sub-agenci

- `tax-logic-specialist` (opus) -- PIT-38, WHT, dywidendy, opcje
- `fifo-engineer` (sonnet) -- FIFO algorytm, multi-year, opcje w FIFO
- `settlement-date-guardian` (opus) -- STRAŻNIK art. 17 ust. 1ab pkt 1
- `ibkr-parser-expert` (sonnet) -- CSV parsing, Financial Instrument Information
- `frontend-engineer` (sonnet) -- React + TanStack + shadcn/ui
- `qa-reviewer` (opus) -- testy, coverage, brak floatów

## Slash commands

- `/validate-fifo` -- uruchom testy FIFO
- `/test-year-boundary` -- testy brzegów roku
- `/check-nbp [waluta] [settle_date]` -- debug NBP
- `/audit-pit38 [fixture]` -- end-to-end audit
- `/test-multiyear` -- scenariusz multi-year
