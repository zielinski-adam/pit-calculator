"""Model raportu PIT-38 -- gotowe wartości do wypełnienia formularza."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PitZgEntry(BaseModel):
    """Wpis PIT/ZG dla jednego kraju."""
    model_config = ConfigDict(frozen=True)

    country_code: str              # np. "US", "IE", "NL"
    country_name: str              # np. "Stany Zjednoczone Ameryki"
    # poz. 6 -- Dochód z zysków kapitałowych
    capital_gains_income: Decimal
    # poz. 29 -- Inne przychody - Dochód
    other_income: Decimal
    # poz. 30 -- Podatek zapłacony za granicą
    foreign_tax_paid: Decimal


class PIT38Report(BaseModel):
    """Kompletny raport PIT-38 z gotowymi wartościami do wpisania w formularz."""
    model_config = ConfigDict(frozen=True)

    tax_year: int

    # Sekcja C -- Przychody z odpłatnego zbycia
    c22_proceeds: Decimal           # Inne przychody / Przychód
    c23_costs: Decimal              # Inne przychody / Koszty uzyskania
    c26_total_proceeds: Decimal     # Razem Przychód (= c22, bo c20 = 0)
    c27_total_costs: Decimal        # Razem Koszty (= c23, bo c21 = 0)
    c28_income: Decimal             # Dochód (c26 - c27, jeśli > 0)
    c29_loss: Decimal               # Strata (c27 - c26, jeśli > 0)

    # Sekcja D -- Obliczenie podatku
    d30_prior_losses: Decimal       # Strata z lat ubiegłych (input od usera)
    d31_tax_base: Decimal           # Podstawa (zaokrąglona do pełnych PLN w dół)
    d32_tax_rate: Decimal = Decimal("19")  # Stawka %
    d33_tax_calculated: Decimal     # Podatek obliczony (d31 × 19%)
    d34_foreign_tax: Decimal        # Podatek zapłacony za granicą
    d35_tax_due: Decimal            # Podatek należny (zaokrąglony do pełnych PLN)

    # Sekcja G -- Dywidendy
    dividends_gross_pln: Decimal    # Wiersz pomocniczy: suma dywidend brutto w PLN
    g47_dividend_tax: Decimal       # 19% × dividends_gross_pln
    g48_dividend_wht: Decimal       # WHT zapłacony za granicą (max = g47)
    dividend_topup_exact: Decimal   # Wiersz pomocniczy: g47 - g48 (dokładna)
    g49_dividend_difference: Decimal  # Różnica (zaokrąglona do pełnych PLN)

    # PIT/ZG
    pit_zg_entries: list[PitZgEntry]

    # Suma końcowa
    total_tax_due: Decimal          # d35 + g49
