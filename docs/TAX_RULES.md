# Zasady podatkowe -- Kalkulator PIT-38

> **UWAGA**: Przed przeczytaniem tego dokumentu, przeczytaj `LEGAL_FOUNDATION.md` w root repo.
> Legal Foundation definiuje fundamentalną zasadę: rok podatkowy = rok settlement date.
> Ten dokument rozszerza Legal Foundation o szczegóły PIT-38, WHT, dywidendy i opcje.

## 1. Struktura formularza PIT-38

### Sekcja C -- Przychody z odpłatnego zbycia papierów wartościowych

| Pozycja | Nazwa | Źródło danych |
|---------|-------|---------------|
| C.20 | Przychody wykazane w części D informacji PIT-8C | 0 (IBKR nie wysyła PIT-8C) |
| C.21 | Koszty wykazane w części D informacji PIT-8C | 0 |
| C.22 | Inne przychody / Przychód | Suma proceeds sprzedaży w PLN (kurs NBP D-1 od settle date sprzedaży) |
| C.23 | Inne przychody / Koszty uzyskania przychodów | Koszty FIFO w PLN (kurs NBP D-1 od settle date zakupu) + prowizje kupna i sprzedaży w PLN |
| C.26 | Razem Przychód (wiersz 1 + wiersz 2) | = C.22 (bo C.20 = 0) |
| C.27 | Razem Koszty (wiersz 1 + wiersz 2) | = C.23 (bo C.21 = 0) |
| C.28 | Dochód (C.26 - C.27) | Gdy przychód > koszty |
| C.29 | Strata (C.27 - C.26) | Gdy koszty > przychód |

**Uwaga**: C.22 i C.23 obejmują zarówno akcje, ETF-y jak i opcje giełdowe.

### Sekcja D -- Obliczenie podatku od dochodów z odpłatnego zbycia

| Pozycja | Nazwa | Wartość |
|---------|-------|--------|
| D.30 | Strata z lat ubiegłych do odliczenia | Input od użytkownika (max 50%/rok przez 5 lat lub jednorazowo do 5 mln PLN) |
| D.31 | Podstawa obliczenia podatku | C.28 - D.30, zaokrąglona do pełnych PLN (w dół) |
| D.32 | Stawka podatku | 19% |
| D.33 | Podatek od dochodów (art. 30b ust. 1) | D.31 × 19% |
| D.34 | Podatek zapłacony za granicą (art. 30b ust. 5a i 5b) | 0 dla IBKR (broker nie pobiera podatku od zysków kapitałowych) |
| D.35 | Podatek należny | D.33 - D.34, zaokrąglony do pełnych PLN |

### Sekcja G -- Zryczałtowany podatek od przychodów uzyskanych poza granicami RP

| Pozycja | Nazwa | Wartość |
|---------|-------|--------|
| — | Suma dywidend zagranicznych brutto w PLN (wiersz pomocniczy) | Suma kwot z sekcji Dividends × kurs NBP D-1 |
| G.47 | Zryczałtowany podatek obliczony | 19% × suma dywidend brutto w PLN |
| G.48 | Podatek zapłacony za granicą | Suma WHT w PLN (kurs NBP D-1 od daty WHT), max = G.47 |
| — | Dokładna wartość do dopłacenia (wiersz pomocniczy) | G.47 - G.48 (przed zaokrągleniem) |
| G.49 | Różnica | G.47 - G.48, zaokrąglona do pełnych PLN |

**WAŻNE**: Dywidendy NIE idą do PIT/ZG -- tylko do sekcji G PIT-38.

### PIT/ZG -- Załącznik per kraj

Wypełniany osobno dla każdego kraju, z którego uzyskano zyski kapitałowe (sekcja C).
Kraj identyfikowany z giełdy (listing_exchange), np. NYSE/NASDAQ = US, AEB = NL, LSE = GB.

| Pozycja | Nazwa |
|---------|-------|
| poz. 6 | Dochód z zysków kapitałowych w danym kraju |
| poz. 29 | Inne przychody - Dochód |
| poz. 30 | Podatek od innych przychodów zapłacony za granicą |

**Uwaga o ISIN vs giełda**: JOBY (KYG651631007) jest zarejestrowany na Kajmanach (KY) ale notowany na NYSE.
Kraj PIT/ZG = kraj giełdy (US), NIE prefiks ISIN (KY). Źródło: inwestomat.eu -- "jeden PIT/ZG dla kraju każdej giełdy".

## 2. Stawki WHT (Withholding Tax) na dywidendy

| Kraj | ISIN prefix | WHT bez umowy | WHT z umową / W-8BEN | Dopłata PL (19% - WHT) |
|------|-------------|---------------|----------------------|------------------------|
| USA | US | 30% | 15% (W-8BEN) | 4% |
| Wielka Brytania | GB | 0% | 0% | 19% |
| Irlandia | IE | 25% | 15% | 4% |
| Niemcy | DE | 26.375% | 15% | 4% |
| Holandia | NL | 15% | 15% | 4% |
| Francja | FR | 25% | 15% | 4% |
| Szwajcaria | CH | 35% | 15% | 4% |

**Zasada**: WHT zapłacony za granicą odlicza się od 19% polskiego podatku, ale **nie więcej niż stawka z umowy**.
Jeśli WHT > 19% (np. Szwajcaria 35% bez umowy) -- nadwyżka przepada (nie ma zwrotu z PL).

### Payment in Lieu of Dividend

IBKR może wypłacić "Payment in Lieu of Dividend" zamiast zwykłej dywidendy (gdy akcje są pożyczone w programie Stock Yield Enhancement). Traktowane identycznie jak zwykła dywidenda dla celów PIT-38.

### ETF akumulacyjne

ETF-y akumulacyjne (np. VWCE IE00BK5BQT80, IWDA IE00B4L5Y983) nie generują dywidend -- reinwestują automatycznie. Zdarzenie podatkowe tylko przy sprzedaży (sekcja C, nie G).

## 3. Straty z lat ubiegłych (art. 9 ust. 3 ustawy o PIT)

Dwa warianty (od 2022 r.):
1. **Standardowy**: do 50% straty rocznie, przez maksymalnie 5 lat
2. **Jednorazowy**: całość straty w jednym roku, max 5 000 000 PLN

Straty z zysków kapitałowych (sekcja C) mogą kompensować TYLKO dochody z zysków kapitałowych.
Straty z dywidend (sekcja G) -- **NIE MA** carryforward dla dywidend.

## 4. Opcje giełdowe (Equity & Index Options)

### Traktowanie podatkowe

Opcje traktowane identycznie jak akcje dla celów PIT-38 -- zyski/straty idą do sekcji C.

### Scenariusze

| Scenariusz | Zdarzenie podatkowe | Sekcja PIT-38 |
|------------|---------------------|---------------|
| Kupno + sprzedaż opcji | Zamknięcie pozycji, FIFO | C.22 (przychód), C.23 (koszt) |
| Wygaśnięcie bezwartościowe (kupujący) | Strata = koszt premii | C.23 (koszt), C.22 = 0 |
| Wygaśnięcie bezwartościowe (sprzedający) | Zysk = premia otrzymana | C.22 (przychód z premii) |
| Exercise (kupujący call) | Opcja → pozycja akcyjna, cost basis = strike × 100 + premia | Brak zdarzenia w momencie exercise, dopiero przy sprzedaży akcji |
| Assignment (sprzedający call) | Opcja → sprzedaż akcji po strike, proceeds = strike × 100 + premia | C.22 (strike × 100 + premia), C.23 (koszt akcji z FIFO) |

### FIFO dla opcji

- **Osobny koszyk FIFO** per symbol opcyjny (np. "NBIS 20MAR26 150 C" to osobny instrument od "NBIS" akcji)
- Multiplier = 100 (1 kontrakt opcyjny = 100 akcji underlying)
- Settlement: OCC T+1 (jak akcje US)

## 5. Corporate Actions

### Split

- Korekta ilości i ceny per share w FIFO deque
- Przykład: IBKR split 4:1 (2025-06-17): 1.6556 shares → 6.6224 shares, cena/4
- Łączny koszt lotu NIE zmienia się, zmienia się quantity × 4 i price / 4
- NIE jest zdarzeniem podatkowym

### Grant Activity / Stock Awards

- Vesting = zdarzenie dochodowe na PIT-36 (NIE PIT-38)
- Cost basis dla przyszłej sprzedaży = FMV (Fair Market Value) w dniu vesting
- W naszym kalkulatorze: dokumentujemy, ale obliczenie PIT-36 jest out of scope

## 6. Odsetki od gotówki (Interest)

- Credit/debit interest na koncie IBKR
- Opodatkowane na PIT-36 (nie PIT-38) -- out of scope
- WHT na odsetki (20% w Irlandii) -- również PIT-36
- CSV zawiera te dane, parsujemy ale nie włączamy do kalkulacji PIT-38

## 7. Kurs walutowy NBP

Szczegóły w `LEGAL_FOUNDATION.md`. Skrót:
- Tabela A NBP (kursy średnie)
- Dzień: ostatni dzień roboczy **przed settlement date** (D-1)
- API: `https://api.nbp.pl/api/exchangerates/rates/a/{currency}/{date}/`
- PLN → `Decimal("1")` bez zapytania do API
- Fallback: tabela B dla walut egzotycznych (rzadko potrzebne)

## Źródła

- Ustawa o PIT -- art. 17 ust. 1ab pkt 1 (settlement date), art. 11a ust. 1 (kurs NBP), art. 30b (stawka 19%), art. 30a (dywidendy), art. 9 ust. 3 (straty)
- inwestomat.eu -- struktura PIT-38, przykłady (CAVEAT: używa trade date dla kursów NBP)
- podatekgieldowy.pl -- UX reference, FIFO methodology
- stockbroker.pl -- ETF taxation, IKE/IKZE
