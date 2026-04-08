# Legal Foundation — data uzyskania przychodu z odpłatnego zbycia papierów wartościowych

> **Ten dokument jest fundamentem całego projektu.** Każda sesja Claude Code, każdy sub-agent, każdy test — wszystko musi być zgodne z tym co tu jest napisane. W razie sprzeczności między tym dokumentem a dowolnym innym źródłem (blog, kalkulator, poradnik) — **ten dokument wygrywa**.

## Podstawa prawna

**Art. 17 ust. 1ab pkt 1 ustawy o PIT** (obowiązuje od 1 stycznia 2016 r.):

> Przychód z odpłatnego zbycia udziałów (akcji), udziałów w spółdzielni oraz papierów wartościowych **powstaje w momencie przeniesienia na nabywcę własności** udziałów (akcji), udziałów w spółdzielni oraz papierów wartościowych.

**Art. 11a ust. 1 ustawy o PIT**:

> Przychody w walutach obcych przelicza się na złote według kursu średniego walut obcych ogłaszanego przez NBP z **ostatniego dnia roboczego poprzedzającego dzień uzyskania przychodu**.

## Wniosek operacyjny

Dla papierów wartościowych w obrocie zorganizowanym **moment przeniesienia własności = data rozrachunku (settlement date)**, NIE data zawarcia transakcji (trade date). Zapis na rachunku papierów wartościowych nabywcy następuje w dacie rozrachunku w systemie depozytowym (KDPW dla GPW, DTCC dla US).

Z tego wynikają trzy reguły używane w kodzie:

1. **Rok podatkowy transakcji** = rok w którym nastąpiła data rozrachunku (settlement date), nie trade date
2. **Kurs NBP dla przychodu ze sprzedaży** = kurs średni tabeli A z ostatniego dnia roboczego przed **settlement date** sprzedaży
3. **Kurs NBP dla kosztu nabycia** = kurs średni tabeli A z ostatniego dnia roboczego przed **settlement date** zakupu

Dla dywidend i odsetek moment uzyskania przychodu = data wpływu na rachunek brokerski (pole `dateTime` w CashTransaction IBKR). Kurs NBP D−1 od tej daty.

## Cykle rozrachunkowe (stan na 2026)

| Giełda | Kod exchange_calendars | Cykl | Uwagi |
|--------|------------------------|------|-------|
| NYSE | XNYS | **T+1 od 2024-05-28**, wcześniej T+2 | US SEC Rule 15c6-1 |
| NASDAQ | XNAS | **T+1 od 2024-05-28**, wcześniej T+2 | j.w. |
| NYSE ARCA | ARCX | T+1 od 2024-05-28 | j.w. |
| GPW | XWAR | T+2 | KDPW, bez zmian |
| LSE | XLON | T+2 (do 2027-10-11) → T+1 | UK T+1 Review |
| Xetra | XETR | T+2 (do 2027-10-11) → T+1 | EU Listing Act |
| Euronext Paris | XPAR | T+2 (do 2027-10-11) → T+1 | j.w. |

Dni wolne (weekendy, święta lokalne giełdy i depozytu) **przesuwają settlement naprzód** (skip non-trading days).

## Algorytm

```python
from datetime import date
from decimal import Decimal
import exchange_calendars as xcals

def compute_settlement(trade_date: date, exchange_code: str) -> date:
    """
    Zwraca settlement date zgodnie z cyklem rozrachunkowym giełdy.
    Uwzględnia kalendarz świąt i zmianę T+2 → T+1 dla US od 2024-05-28.
    """
    calendar = xcals.get_calendar(exchange_code)
    
    # Wyznacz cykl
    if exchange_code in {"XNYS", "XNAS", "ARCX"}:
        cycle = 1 if trade_date >= date(2024, 5, 28) else 2
    elif exchange_code == "XWAR":
        cycle = 2
    elif exchange_code in {"XLON", "XETR", "XPAR"}:
        cycle = 2 if trade_date < date(2027, 10, 11) else 1
    else:
        raise ValueError(f"Nieznana giełda: {exchange_code}")
    
    # Przesuń o `cycle` dni handlowych do przodu
    settle = trade_date
    for _ in range(cycle):
        settle = calendar.next_session(settle).date()
    
    return settle


def tax_year(trade_date: date, exchange_code: str) -> int:
    """Rok podatkowy = rok daty rozrachunku."""
    return compute_settlement(trade_date, exchange_code).year


def nbp_rate_date(settle_date: date) -> date:
    """
    Zwraca datę dla której pobieramy kurs NBP — ostatni dzień roboczy
    przed settlement date. NBP publikuje tabelę A w dni robocze
    (pon-pt, z wyłączeniem polskich świąt).
    """
    # Implementacja: cofaj się dzień po dniu, pomijając weekendy i polskie święta
    # (kalendarz NBP ≈ polski kalendarz roboczy)
    ...
```

## Cutoffy dla roku podatkowego 2025 (referencyjne)

| Giełda | Pierwszy trade liczony do 2025 | Ostatni trade liczony do 2025 |
|--------|--------------------------------|-------------------------------|
| NYSE/NASDAQ (T+1) | 2025-01-02 (wt., settle 2025-01-03) | 2025-12-30 (wt., settle 2025-12-31) |
| NYSE/NASDAQ — alternatywnie trades z 2024 | 2024-12-31 (wt., settle 2025-01-02) | — |
| GPW (T+2) | 2024-12-30 (pon., settle 2025-01-02) | 2025-12-23 (pt., settle 2025-12-30) |
| GPW — alternatywnie trades z 2024 | 2024-12-29 (pon., settle 2024-12-31) → rok 2024 | 2024-12-30 → settle 2025-01-02 → rok 2025 |

**Transakcje brzegowe — pułapka**:
- Trade NYSE **2025-12-31** → settle **2026-01-02** → **rok podatkowy 2026**
- Trade GPW **2025-12-29** → settle **2025-12-31** → rok 2025 ✓
- Trade GPW **2025-12-30** → settle **2026-01-02** → **rok podatkowy 2026**

## Implikacje dla parsowania Flex Query XML

W modelu `Trade` Pydantic:

```python
class Trade(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    # Z raportu IBKR
    trade_date: date          # pole `tradeDate`, DO IDENTYFIKACJI
    settle_date: date         # pole `settleDateTarget`, AUTORYTATYWNE
    listing_exchange: str     # pole `listingExchange`
    # ... reszta pól
    
    @field_validator("settle_date")
    @classmethod
    def _settle_after_trade(cls, v: date, info: ValidationInfo) -> date:
        if "trade_date" in info.data and v < info.data["trade_date"]:
            raise ValueError("Settlement date nie może być wcześniej niż trade date")
        return v
    
    @property
    def tax_year(self) -> int:
        """Rok podatkowy transakcji — na podstawie settle_date, zgodnie z art. 17 ust. 1ab pkt 1."""
        return self.settle_date.year
    
    @property
    def nbp_rate_date(self) -> date:
        """Data dla kursu NBP — D−1 od settle_date."""
        return previous_nbp_working_day(self.settle_date)
```

## Implikacje dla FIFO engine

```python
def calculate_fifo(
    trades: list[Trade],
    corporate_actions: list[CorporateAction],
    tax_year: int,
) -> list[TaxLot]:
    """
    Oblicza FIFO dla podanego roku podatkowego.
    
    Kluczowe decyzje:
    1. Trades sortowane po (settle_date, trade_date) — settle pierwsze,
       trade jako tie-breaker dla tego samego settle date
    2. Raportowane są tylko TaxLoty gdzie sell_settle_date.year == tax_year
    3. Kurs NBP dla kosztu zakupu: D−1 od buy_settle_date
    4. Kurs NBP dla przychodu ze sprzedaży: D−1 od sell_settle_date
    """
    sorted_trades = sorted(trades, key=lambda t: (t.settle_date, t.trade_date))
    # ... reszta logiki
```

## Czego NIE robimy — red flags

- ❌ **Nie używamy `trade_date.year` jako roku podatkowego**. Nigdzie. Ani razu. Jeśli widzisz w PR `trade_date.year == tax_year` — to błąd, commit blokowany.
- ❌ **Nie pobieramy kursu NBP dla D−1 od `trade_date`** dla transakcji kupna/sprzedaży. Tylko od `settle_date`.
- ❌ **Nie sortujemy FIFO po `trade_date`**. Tylko po `settle_date` (z `trade_date` jako tie-breaker).
- ❌ **Nie cytujemy interpretacji sprzed 2016 r.** Art. 17 ust. 1ab pkt 1 został dodany nowelizacją z 2016 r. i rozstrzygnął spór.
- ❌ **Nie wierzymy przykładom z blogów** które używają trade date dla kursu NBP. Nawet renomowanym. Autorzy zwykle upraszczają dla czytelnika — my piszemy kod produkcyjny.
- ❌ **Nie oferujemy trybu „trade date"** jako opcji konfiguracyjnej. To byłoby wspieranie błędnej metody.

## Kiedy wolno użyć `trade_date`

- ✅ Debug logi („Trade executed on 2025-03-17, settled on 2025-03-18")
- ✅ Wyświetlanie w UI obok settle date (Trade | Settle columns)
- ✅ Sanity check: `assert settle_date >= trade_date`
- ✅ Identyfikacja instrumentu w kontekście giełdy (dla `compute_settlement`)
- ✅ Tie-breaker przy sortowaniu FIFO gdy dwa loty mają ten sam `settle_date`
- ✅ Historia transakcji w zakładce Transakcje frontendu

## Referencje zewnętrzne

- Ustawa o podatku dochodowym od osób fizycznych — art. 17 ust. 1ab pkt 1 (nowelizacja z 2016 r.)
- Ustawa o podatku dochodowym od osób fizycznych — art. 11a ust. 1 (przeliczanie walut obcych)
- SEC Rule 15c6-1 — Shortening the Securities Transaction Settlement Cycle (efektywna od 2024-05-28)
- `exchange_calendars` — https://github.com/gerrymanoim/exchange_calendars
- NBP tabela A — https://api.nbp.pl/api/exchangerates/rates/a/{currency}/{date}/

## Weryfikacja dokumentu

Jeśli modyfikujesz ten dokument:
1. Uruchom wszystkie testy `/validate-fifo` i `/test-year-boundary` — muszą być zielone
2. Poproś `settlement-date-guardian` o review
3. Aktualizuj `CLAUDE.md` w root jeśli zmieniasz zasady podstawowe
4. Commit message: `docs(legal): aktualizacja Legal Foundation — [uzasadnienie]`
