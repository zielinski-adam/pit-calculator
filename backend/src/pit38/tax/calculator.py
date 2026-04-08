"""
Kalkulator PIT-38 -- mapowanie wyników FIFO i dywidend na pozycje formularza.

Sekcja C: zyski kapitałowe (akcje + opcje)
Sekcja D: obliczenie podatku
Sekcja G: dywidendy zagraniczne
PIT/ZG: per kraj (tylko zyski kapitałowe, NIE dywidendy)
"""
from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from math import floor

from pit38.models.dividend import Dividend, WithholdingTax
from pit38.models.enums import WhtType
from pit38.models.pit38_report import PIT38Report, PitZgEntry
from pit38.models.tax_lot import TaxLot
from pit38.nbp.client import NBPClient
from pit38.settlement.calculator import compute_nbp_rate_date

# Mapowanie kodów krajów → nazwy (dla PIT/ZG)
COUNTRY_NAMES: dict[str, str] = {
    "US": "Stany Zjednoczone Ameryki",
    "IE": "Irlandia",
    "NL": "Holandia",
    "GB": "Wielka Brytania",
    "DE": "Niemcy",
    "FR": "Francja",
    "CH": "Szwajcaria",
    "KY": "Kajmany",
    "CA": "Kanada",
    "JP": "Japonia",
    "AU": "Australia",
    "IL": "Izrael",
    "SE": "Szwecja",
    "DK": "Dania",
    "NO": "Norwegia",
    "FI": "Finlandia",
    "BE": "Belgia",
    "LU": "Luksemburg",
    "HK": "Hongkong",
    "SG": "Singapur",
    "TW": "Tajwan",
    "KR": "Korea Południowa",
    "BR": "Brazylia",
    "MX": "Meksyk",
    "ZA": "Republika Południowej Afryki",
    "CN": "Chiny",
    "IN": "Indie",
}

TAX_RATE = Decimal("0.19")


def calculate_pit38(
    tax_lots: list[TaxLot],
    dividends: list[Dividend],
    withholding_taxes: list[WithholdingTax],
    nbp_client: NBPClient,
    tax_year: int,
    prior_losses: Decimal = Decimal("0"),
) -> PIT38Report:
    """
    Oblicz pełny raport PIT-38 na podstawie wyników FIFO, dywidend i WHT.

    Args:
        tax_lots: Zamknięte pozycje z FIFO (już przefiltrowane po tax_year)
        dividends: Dywidendy z CSV
        withholding_taxes: WHT z CSV
        nbp_client: Klient NBP do przeliczania dywidend/WHT
        tax_year: Rok podatkowy
        prior_losses: Strata z lat ubiegłych do odliczenia (D.30)

    Returns:
        PIT38Report z gotowymi wartościami
    """
    # ── Sekcja C: zyski kapitałowe ──
    section_c = _calculate_section_c(tax_lots)

    # ── Sekcja D: obliczenie podatku ──
    section_d = _calculate_section_d(section_c, prior_losses)

    # ── Sekcja G: dywidendy ──
    section_g = _calculate_section_g(
        dividends, withholding_taxes, nbp_client, tax_year
    )

    # ── PIT/ZG: per kraj (tylko zyski kapitałowe) ──
    pit_zg = _calculate_pit_zg(tax_lots)

    # ── Suma końcowa ──
    total_tax = section_d["d35"] + section_g["g49"]

    return PIT38Report(
        tax_year=tax_year,
        # Sekcja C
        c22_proceeds=section_c["c22"],
        c23_costs=section_c["c23"],
        c26_total_proceeds=section_c["c22"],  # = c22 bo c20 = 0
        c27_total_costs=section_c["c23"],      # = c23 bo c21 = 0
        c28_income=section_c["c28"],
        c29_loss=section_c["c29"],
        # Sekcja D
        d30_prior_losses=prior_losses,
        d31_tax_base=section_d["d31"],
        d33_tax_calculated=section_d["d33"],
        d34_foreign_tax=Decimal("0"),  # IBKR nie pobiera podatku od zysków
        d35_tax_due=section_d["d35"],
        # Sekcja G
        dividends_gross_pln=section_g["dividends_gross_pln"],
        g47_dividend_tax=section_g["g47"],
        g48_dividend_wht=section_g["g48"],
        dividend_topup_exact=section_g["topup_exact"],
        g49_dividend_difference=section_g["g49"],
        # PIT/ZG
        pit_zg_entries=pit_zg,
        # Suma
        total_tax_due=total_tax,
    )


def _calculate_section_c(tax_lots: list[TaxLot]) -> dict[str, Decimal]:
    """Sekcja C -- przychody i koszty z odpłatnego zbycia papierów wartościowych."""
    # C.22: suma przychodów ze sprzedaży w PLN
    c22 = sum(
        (lot.sell_proceeds_pln for lot in tax_lots),
        start=Decimal("0"),
    )

    # C.23: suma kosztów FIFO w PLN (koszt kupna + prowizje)
    c23 = sum(
        (lot.buy_cost_pln for lot in tax_lots),
        start=Decimal("0"),
    )

    # Zaokrąglenie do groszy
    c22 = c22.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    c23 = c23.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # C.28 / C.29
    diff = c22 - c23
    c28 = max(diff, Decimal("0"))
    c29 = max(-diff, Decimal("0"))

    return {"c22": c22, "c23": c23, "c28": c28, "c29": c29}


def _calculate_section_d(
    section_c: dict[str, Decimal],
    prior_losses: Decimal,
) -> dict[str, Decimal]:
    """Sekcja D -- obliczenie podatku."""
    c28 = section_c["c28"]

    # D.31: podstawa = dochód - straty, zaokrąglona w dół do pełnych PLN
    tax_base_raw = max(c28 - prior_losses, Decimal("0"))
    d31 = Decimal(str(int(tax_base_raw)))  # floor do pełnych PLN

    # D.33: podatek obliczony
    d33 = (d31 * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # D.35: podatek należny (zaokrąglony do pełnych PLN)
    d35 = Decimal(str(round(d33)))

    return {"d31": d31, "d33": d33, "d35": d35}


def _calculate_section_g(
    dividends: list[Dividend],
    withholding_taxes: list[WithholdingTax],
    nbp_client: NBPClient,
    tax_year: int,
) -> dict[str, Decimal]:
    """Sekcja G -- dywidendy zagraniczne."""
    # Filtruj dywidendy po roku
    year_dividends = [d for d in dividends if d.payment_date.year == tax_year]

    # Przelicz dywidendy na PLN
    dividends_gross_pln = Decimal("0")
    for div in year_dividends:
        nbp_date = compute_nbp_rate_date(div.payment_date)
        rate = nbp_client.get_rate(div.currency, nbp_date)
        dividends_gross_pln += div.amount * rate

    dividends_gross_pln = dividends_gross_pln.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # G.47: 19% × suma dywidend brutto
    g47 = (dividends_gross_pln * TAX_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # WHT -- tylko dividend WHT, przelicz na PLN
    year_div_whts = [
        w for w in withholding_taxes
        if w.wht_type == WhtType.DIVIDEND_WHT and w.payment_date.year == tax_year
    ]

    wht_pln = Decimal("0")
    for wht in year_div_whts:
        nbp_date = compute_nbp_rate_date(wht.payment_date)
        rate = nbp_client.get_rate(wht.currency, nbp_date)
        # WHT.amount jest ujemny (potrącony), bierzemy wartość bezwzględną
        wht_pln += abs(wht.amount) * rate

    wht_pln = wht_pln.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # G.48: WHT, ale max = G.47
    g48 = min(wht_pln, g47)

    # Dopłata
    topup_exact = g47 - g48

    # G.49: zaokrąglona do pełnych PLN
    g49 = Decimal(str(round(topup_exact)))

    return {
        "dividends_gross_pln": dividends_gross_pln,
        "g47": g47,
        "g48": g48,
        "topup_exact": topup_exact,
        "g49": g49,
    }


def _calculate_pit_zg(tax_lots: list[TaxLot]) -> list[PitZgEntry]:
    """
    PIT/ZG -- załącznik per kraj.

    Kraj = kraj giełdy (listing_exchange), NIE prefiks ISIN.
    Tylko zyski kapitałowe (sekcja C), NIE dywidendy.
    """
    # Grupuj po kraju
    by_country: dict[str, list[TaxLot]] = defaultdict(list)
    for lot in tax_lots:
        by_country[lot.country].append(lot)

    entries = []
    for country_code, lots in sorted(by_country.items()):
        # poz. 6: dochód z zysków kapitałowych
        total_pnl = sum(
            (lot.profit_loss_pln for lot in lots),
            start=Decimal("0"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        capital_gains = max(total_pnl, Decimal("0"))

        country_name = COUNTRY_NAMES.get(country_code, country_code)

        entries.append(PitZgEntry(
            country_code=country_code,
            country_name=country_name,
            capital_gains_income=capital_gains,
            other_income=Decimal("0"),      # nie mamy "innych przychodów"
            foreign_tax_paid=Decimal("0"),   # IBKR nie pobiera podatku od zysków
        ))

    return entries
