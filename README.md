# pit-calculator

Open-source kalkulator polskiego podatku giełdowego (**PIT-38 + PIT/ZG**) dla inwestorów korzystających z **Interactive Brokers**.

## Co robi

- Parsuje CSV Activity Statement z IBKR (akcje + opcje giełdowe)
- Oblicza FIFO multi-year z poprawnym settlement date (art. 17 ust. 1ab pkt 1 ustawy o PIT)
- Pobiera kursy NBP z API (D-1 od settlement date)
- Generuje gotowe wartości do wypełnienia PIT-38 (sekcje C, D, G) i PIT/ZG per kraj
- Frontend z edytowalnymi tabelami (React + TanStack Table)

## Dlaczego settlement date?

Od 2016 r. przychód z odpłatnego zbycia papierów wartościowych powstaje w momencie **przeniesienia własności** (= data rozrachunku / settlement date), nie w dniu transakcji. Większość kalkulatorów i poradników online tego nie uwzględnia.

Szczegóły: [`LEGAL_FOUNDATION.md`](LEGAL_FOUNDATION.md)

## Stack

| Warstwa | Technologia |
|---------|-------------|
| Backend | Python 3.12+, FastAPI, Pydantic v2, exchange_calendars |
| Frontend | React 18+, TypeScript, Vite, TanStack, shadcn/ui |
| Package managers | uv (backend), pnpm (frontend) |

## Dokumentacja

- [`docs/TAX_RULES.md`](docs/TAX_RULES.md) -- przepisy podatkowe, PIT-38 field mapping, WHT rates
- [`docs/FIFO_MULTI_YEAR.md`](docs/FIFO_MULTI_YEAR.md) -- specyfikacja FIFO multi-year z scenariuszami brzegowymi
- [`docs/IBKR_ACTIVITY_STATEMENT.md`](docs/IBKR_ACTIVITY_STATEMENT.md) -- format CSV, mapowanie pól
- [`docs/UX_REFERENCE.md`](docs/UX_REFERENCE.md) -- referencyjna dokumentacja UI

## Status

W trakcie budowy (Faza 0 -- dokumentacja i infrastruktura).

## Licencja

MIT
