# UX Reference -- Kalkulator PIT-38

## Analiza UI podatekgieldowy.pl

Screenshoty i snapshoty w `resources/screenshots/`.

### Layout

- **Sidebar** (lewy): nawigacja z ikonami i badge'ami (liczba elementów per sekcja)
- **Header**: logo, przyciski Eksportuj / Kontakt / Co nowego, avatar usera
- **Main content**: pełna szerokość, białe tło

### Nawigacja (sidebar)

```
Import
Akcje ▼
  FIFO (8)
  Transakcje (37)
  Splity (1)
  Portfolio (19)
Dywidendy (14)
Kryptowaluty (4)    ← out of scope MVP
Koszty (17)
Podsumowanie PIT-38
---
Demo
Dokumentacja
Pakiet
Ustawienia
Wyloguj
```

Badge w nawiasie = liczba elementów w danej sekcji po imporcie danych.

### Strona Import

- Grid kart brokerów (3 kolumny)
- Każda karta: logo brokera, nazwa, format pliku, drag-drop area, link "Zobacz instrukcję"
- Obsługiwani brokerzy: PodatekGieldowy.pl (.json), Trading212 (.csv), eToro (.xlsx), Degiro (.csv), **Interactive Brokers (.html)**, Revolut (.pdf/.csv), Exante (.csv), Tastytrade (.csv), Freedom24 (.xlsx)
- Link "Ustawienia importu" u góry

### Strona FIFO (Zamknięte pozycje)

- **Year selector** (dropdown): "Zamknięte pozycje w roku 2025"
- **Summary cards** (4 karty w rzędzie):
  - PRZYCHÓD ZE SPRZEDAŻY: 19 820,63 zł
  - KOSZT UZYSKANIA: 19 011,92 zł
  - ZREALIZOWANY ZYSK/STRATA: +808,70 zł
  - TRANSAKCJE ZAMKNIĘTE: 8
- **Search bar**: "Wyszukaj zasób, konto, id transakcji otwierającej lub zamykającej"
- **Grouped table**: każda zamknięta pozycja jako rozwijana sekcja

#### Nagłówek grupy zamkniętej pozycji

```
Zamknięcie pozycji: NVDA
Rodzaj: Spot  |  Kraj PIT/ZG: US 🇺🇸  |  Giełdy: XNAS  |  Typ pozycji: Długa  |  Konto: EXANTE
Przychód [PLN]: 3470.14  |  Koszt [PLN]: -3312.93
```

#### Kolumny tabeli FIFO

| Kolumna | Opis |
|---------|------|
| ID | Link do transakcji (kliknięcie → Transakcje z filtrem) |
| DATA | Trade date |
| TYP | K (kupno) / S (sprzedaż), sortowalne |
| JEDNOSTKI | Ilość (dodatnia = K, ujemna = S) |
| CENA ZA JEDNOSTKĘ | W walucie oryginalnej |
| KWOTA | Ilość × cena |
| PROWIZJA | W walucie oryginalnej |
| **DATA ROZLICZENIA** | Settlement date, sortowalna |
| **DATA D-1** | Dzień kursu NBP |
| KURS NBP JEDNOSTKI | Kurs użyty do przeliczenia kwoty |
| KURS NBP PROWIZJA | Kurs użyty do przeliczenia prowizji |
| PRZYCHÓD [PLN] | Tylko dla sprzedaży |
| KOSZT [PLN] | Tylko dla kupna |
| PRZEPŁYW [PLN] | Przychód - koszt |

#### Podsumowanie grupy (footer)

```
Przychód: 3470,14 zł  |  Koszt: -3312,93 zł  |  Zysk/Strata: 157,21 zł
```

#### Podsumowanie ogółem (na dole strony)

```
Ogółem
ZAMKNIĘCIA POZYCJI | CAŁKOWITY PRZYCHÓD | CAŁKOWITY KOSZT | ZYSK/STRATA BRUTTO
8                  | 19 820,63 zł       | -19 011,92 zł   | 808,70 zł
```

### Strona Transakcje

- **Heading**: "Transakcje"
- **Search bar**: "Wyszukaj zasób, konto lub id transakcji"
- **Sort dropdown**: "Data: od najstarszej"
- **Bulk select**: checkbox "Wybierz widoczne", "Wybrano: 0 elementów", przycisk "Działania"

#### Kolumny tabeli Transakcje

| Kolumna | Opis |
|---------|------|
| (checkbox) | Do zaznaczania |
| ID | Numer transakcji |
| ZASÓB | Symbol (np. AAPL) |
| RODZAJ | Spot (sortowalne) |
| DATA | Trade date z czasem |
| TYP | K/S (sortowalne) |
| LICZBA | Ilość |
| KWOTA | W walucie oryginalnej |
| PROWIZJA | W walucie oryginalnej |
| KONTO | Nazwa brokera/konta |
| GIEŁDA | Kod giełdy (sortowalne) |
| KRAJ PIT/ZG | Kod kraju + flaga emoji (sortowalne) |

### Strona Dywidendy

- **Year selector**: "Dywidendy i odsetki w roku 2025"
- **Summary cards**:
  - Suma brutto: 970,26 zł
  - WHT: 320,13 zł
  - Zysk/Strata: +650,14 zł
  - Liczba: 14

### Strona Podsumowanie PIT-38

- **Year selector**: "Podsumowanie roku 2025"
- **Buttons**: "Pobierz Raport PDF", "Instrukcja wypełniania PIT-38"
- **Tabele z pozycjami** -- kolumny: KOMÓRKA, NAZWA, WARTOŚĆ
  - Sekcja "PIT-38 - Akcje i Koszty" (C.20 - C.29)
  - Sekcja "PIT-38 - Obliczenie podatku" (D.31 - D.35)
  - Sekcja "PIT-38 - Kryptowaluty" (E.36 - E.40) -- skip w MVP
  - Sekcja "PIT-38 - Dywidendy" (G.47 - G.49 + wiersze pomocnicze)
  - Sekcja "PIT/ZG" -- per kraj, kolumny: PAŃSTWO, poz. 6, poz. 29, poz. 30

---

## Nasz MVP -- różnice vs podatekgieldowy.pl

### Zakładki (8 zamiast 9)

1. **Import** -- upload CSV, single broker (IBKR), drag-drop
2. **FIFO** -- zamknięte pozycje (akcje + opcje)
3. **Transakcje** -- pełna lista z inline edit
4. **Splity** -- lista splitów + formularz dodawania manualnego
5. **Portfolio** -- otwarte pozycje (read-only)
6. **Dywidendy** -- z WHT correlation
7. **Koszty** -- opłaty, prowizje (read-only w MVP)
8. **Podsumowanie PIT-38** -- gotowe wartości + PIT/ZG

Brak: Kryptowaluty (out of scope).

### Elementy dodatkowe (vs oryginał)

- **Year Boundary Badge** -- dla transakcji granicznych (ostatni tydzień grudnia / pierwszy tydzień stycznia), tooltip z settlement date i wyjaśnieniem dlaczego ta transakcja należy do tego/następnego roku podatkowego
- **Settlement date kolumna** -- eksplicytnie widoczna w tabeli Transakcje (oryginał pokazuje ją tylko w FIFO)
- **Open source** -- brak paywall, brak limitu transakcji

### Elementy do zachowania z oryginału

- Year selector w headerze każdej zakładki danych
- Export button (JSON snapshot sesji)
- Import session (wczytanie wcześniejszego JSON)
- Search bar z filtrowaniem
- Sortowanie kolumn
- Bulk select + "Działania" w Transakcjach
- Link z ID transakcji w FIFO → filtrowanie w Transakcjach
- Badge z liczbą elementów w sidebar nawigacji
- Flagi emoji przy kraju PIT/ZG
