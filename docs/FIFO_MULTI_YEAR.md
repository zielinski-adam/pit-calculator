# FIFO Multi-Year -- Specyfikacja silnika

## Podstawy FIFO

**First In First Out**: najstarsza pozycja kupna jest dopasowywana do każdej sprzedaży.

### Klucz sortowania

```python
sorted_trades = sorted(trades, key=lambda t: (t.settle_date, t.trade_date))
```

- **Pierwszorzędny**: settle_date (obliczony z trade_date + exchange_calendars)
- **Drugorzędny**: trade_date (tie-breaker gdy settle_date identyczny)

### Koszyk FIFO

Osobny koszyk per:
1. **Instrument** (symbol + typ): "AAPL" (akcja) ≠ "AAPL 20MAR26 150 C" (opcja)
2. **Waluta** (w praktyce wynika z instrumentu)

**NIE** per konto -- jeden koszyk dla danego instrumentu niezależnie od konta.

## Multi-Year Lot Tracking

System musi przetworzyć WSZYSTKIE historyczne transakcje, nie tylko bieżący rok podatkowy.

### Przepływ danych

1. Parser wczytuje CSV z wielu lat (user uploaduje pliki od otwarcia konta)
2. Dla każdego trade: oblicz settle_date z exchange_calendars
3. Sortuj po (settle_date, trade_date)
4. BUY → dodaj lot na koniec deque
5. SELL → zabieraj loty z początku deque (FIFO)
6. Raportuj TaxLot gdy sell_settle_date.year == wybrany_rok_podatkowy

### TaxLot -- output FIFO

```python
class TaxLot:
    # Strona kupna
    buy_trade_date: date
    buy_settle_date: date
    buy_nbp_rate_date: date  # D-1 od buy_settle_date
    buy_nbp_rate: Decimal
    buy_price: Decimal        # cena per unit w walucie oryginalnej
    buy_quantity: Decimal
    buy_commission: Decimal   # proporcjonalna prowizja
    buy_cost_pln: Decimal     # (buy_price × buy_quantity + buy_commission) × buy_nbp_rate
    
    # Strona sprzedaży
    sell_trade_date: date
    sell_settle_date: date
    sell_nbp_rate_date: date  # D-1 od sell_settle_date
    sell_nbp_rate: Decimal
    sell_price: Decimal
    sell_quantity: Decimal    # = buy_quantity (lot dopasowany)
    sell_commission: Decimal
    sell_proceeds_pln: Decimal
    
    # Wynik
    profit_loss_pln: Decimal  # sell_proceeds_pln - buy_cost_pln
    
    # Identyfikacja
    instrument: str           # symbol
    isin: str
    country: str              # z prefiksu ISIN (dla PIT/ZG)
    exchange: str             # listing exchange
    tax_year: int             # sell_settle_date.year
```

## Scenariusze brzegowe

### Scenariusz 1: Klasyczny multi-year (US, przed i po reformie T+1)

```
Kupno AAPL:
  trade_date:  2023-11-15 (środa)
  exchange:    XNAS
  cycle:       T+2 (przed 2024-05-28)
  settle_date: 2023-11-17 (piątek)
  NBP rate:    z 2023-11-16 (czwartek)

Sprzedaż AAPL:
  trade_date:  2025-03-17 (poniedziałek)
  exchange:    XNAS
  cycle:       T+1 (po 2024-05-28)
  settle_date: 2025-03-18 (wtorek)
  NBP rate:    z 2025-03-17 (poniedziałek)

Raport za 2025 (sell_settle_date.year == 2025):
  koszt:     quantity × price × NBP(2023-11-16) + prowizja × NBP(2023-11-16)
  przychód:  quantity × price × NBP(2025-03-17)
```

### Scenariusz 2: Ostatnia sesja roku NYSE (KRYTYCZNE!)

```
Trade NYSE: 2025-12-31 (środa)
  cycle: T+1
  31 grudnia = ostatnia sesja, 1 stycznia = święto
  settle_date: 2026-01-02 (piątek)
  tax_year: 2026 ← NIE 2025!

Trade NYSE: 2025-12-30 (wtorek)
  cycle: T+1
  settle_date: 2025-12-31 (środa)
  tax_year: 2025 ← ostatni dzień należący do 2025
```

**Implikacja**: trade z 2025-12-31 na NYSE NIE liczy się do roku 2025. UI pokaż badge "→ rok podatkowy 2026".

### Scenariusz 3: Brzeg roku GPW (T+2)

```
Trade GPW: 2025-12-29 (poniedziałek)
  cycle: T+2
  settle_date: 2025-12-31 (środa)
  tax_year: 2025

Trade GPW: 2025-12-30 (wtorek)
  cycle: T+2
  31 grudnia = sesja, 1 stycznia = święto
  settle_date: 2026-01-02 (piątek)
  tax_year: 2026 ← ostatnia sesja 2025 na GPW to 29 grudnia!
```

### Scenariusz 4: Split + multi-year

```
2022-05-10: kupno 100 AAPL @ 400 USD (pre-split)
            settle: 2022-05-12 (T+2)
            NBP: z 2022-05-11
            lot: 100 @ 400, koszt_pln = 100 × 400 × NBP(2022-05-11)

2022-08-28: split 4:1
            deque update: 400 @ 100, koszt_pln niezmieniony
            (quantity × 4, price / 4)

2025-03-17: sprzedaż 200 AAPL @ 180 USD
            settle: 2025-03-18 (T+1)
            NBP: z 2025-03-17
            FIFO: bierze 200 z 400 split-adjusted, zostaje 200

Raport 2025:
  koszt:     200 × 100 × NBP(2022-05-11) = 20000 × NBP(2022-05-11)
  przychód:  200 × 180 × NBP(2025-03-17)
```

### Scenariusz 5: Trade/settle przechodzi przez reformę T+1 (granica 2024-05-28)

```
Trade: 2024-05-27 (poniedziałek)
  T+2 (ostatni dzień przed reformą)
  settle: 2024-05-29 (środa)

Trade: 2024-05-28 (wtorek)
  T+1 (pierwszy dzień reformy)
  settle: 2024-05-29 (środa) ← tego samego dnia!

FIFO: sort stabilny po (settle_date, trade_date)
  → najpierw trade 05-27, potem trade 05-28
```

### Scenariusz 6: Trzy loty multi-year

```
Kupno 100 AAPL: 2022-03-15, settle 2022-03-17, NBP z 2022-03-16
Kupno 100 AAPL: 2023-06-20, settle 2023-06-22, NBP z 2023-06-21
Kupno 100 AAPL: 2024-09-10, settle 2024-09-11, NBP z 2024-09-10

Sprzedaż 250 AAPL: 2025-04-15, settle 2025-04-16, NBP z 2025-04-15

FIFO: 
  lot 1: 100 z 2022 (cały)
  lot 2: 100 z 2023 (cały)
  lot 3: 50 z 2024 (częściowy, zostaje 50)

Każdy lot ma WŁASNY kurs NBP dla kosztu!
```

### Scenariusz 7: NYSE trade 2024-12-31 → rok podatkowy 2025

```
Trade NYSE: 2024-12-31 (wtorek)
  cycle: T+2 (przed reformą? NIE -- reforma była 2024-05-28, więc T+1)
  1 stycznia = święto
  settle: 2025-01-02 (czwartek)
  tax_year: 2025 ← NIE 2024!
```

## Opcje w FIFO

### Osobny koszyk

Opcja "NBIS 20MAR26 150 C" to osobny instrument od akcji "NBIS".
FIFO per symbol opcyjny.

### Wygaśnięcie bezwartościowe

```
Kupno 5 NBIS 20MAR26 150 C @ 12.90 USD
  settle: trade + 1 (OCC T+1)
  lot: 5 × 12.90 × 100 = 6450 USD koszt

Wygaśnięcie 2026-03-20 (out of the money):
  lot znika z deque
  TaxLot: buy_cost = 6450 × NBP, sell_proceeds = 0
  Strata do C.23
```

### Exercise (kupujący call)

```
Kupno 5 NBIS 20MAR26 150 C @ 12.90 USD (premia)
Cena NBIS > 150 → exercise

Opcja znika z deque opcyjnego
Nowy lot w deque akcyjnym NBIS:
  quantity: 5 × 100 = 500 akcji
  cost_basis: (150 + 12.90) × 100 × 5 = 81450 USD (strike + premia)
  
Zdarzenie podatkowe dopiero przy sprzedaży akcji NBIS
```

### Assignment (sprzedający call)

```
Sprzedaż 5 NBIS 20MAR26 150 C @ 12.90 USD (otrzymana premia)
Cena NBIS > 150 → assignment

Opcja znika z deque opcyjnego
Sprzedaż 500 akcji NBIS po strike 150:
  proceeds: (150 × 100 × 5) + (12.90 × 100 × 5) = 81450 USD
  cost: FIFO z deque akcyjnego NBIS
```

## Split handling w FIFO

Gdy CSV zawiera Corporate Action typu Split:

```python
def apply_split(deque: deque[Lot], ratio_from: int, ratio_to: int) -> None:
    """
    Aplikuje split na wszystkie otwarte loty w deque.
    Przykład: split 4:1 → ratio_from=1, ratio_to=4
    """
    for lot in deque:
        lot.quantity = lot.quantity * ratio_to / ratio_from
        lot.price_per_unit = lot.price_per_unit * ratio_from / ratio_to
        # lot.total_cost NIE zmienia się
```

## Walidacja

Przed kalkulacją engine sprawdza:

1. **Incomplete history**: najwcześniejsza transakcja powinna być "od otwarcia konta"
2. **Portfolio drift**: stan po przetworzeniu == oczekiwany (open positions)
3. **Settlement > trade**: każdy trade ma settle_date >= trade_date
4. **Year boundary flag**: transakcje z settle_date w zakresie (26 grudnia - 5 stycznia) → badge w UI

## Prowizje w FIFO

Prowizja BUY → dodana do kosztu lotu (C.23)
Prowizja SELL → odjęta od przychodu (C.22)

Prowizja przeliczana na PLN kursem NBP z D-1 od settle_date TEGO SAMEGO trade'u.

Przy częściowym dopasowaniu lotu: prowizja dzielona proporcjonalnie do quantity.
