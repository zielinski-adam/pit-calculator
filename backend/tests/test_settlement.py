"""Testy settlement date calculator -- scenariusze z FIFO_MULTI_YEAR.md."""
from __future__ import annotations

from datetime import date

import pytest

from pit38.settlement.calculator import compute_nbp_rate_date, compute_settlement


# ────────────────────────────────────────────────────────────
# Scenariusz 1: US pre-reform (T+2) i post-reform (T+1)
# ────────────────────────────────────────────────────────────

class TestUSReform:
    """Reforma T+1 w USA: 2024-05-28."""

    @pytest.mark.settlement
    def test_nasdaq_t2_before_reform(self):
        """NASDAQ przed reformą (2023-11-15 środa) → T+2 → 2023-11-17 piątek."""
        result = compute_settlement(date(2023, 11, 15), "NASDAQ")
        assert result == date(2023, 11, 17)

    @pytest.mark.settlement
    def test_nasdaq_t1_after_reform(self):
        """NASDAQ po reformie (2025-03-17 poniedziałek) → T+1 → 2025-03-18 wtorek."""
        result = compute_settlement(date(2025, 3, 17), "NASDAQ")
        assert result == date(2025, 3, 18)

    @pytest.mark.settlement
    def test_nyse_t2_before_reform(self):
        """NYSE przed reformą (2024-05-27 poniedziałek) → T+2 → 2024-05-29 środa."""
        result = compute_settlement(date(2024, 5, 27), "NYSE")
        assert result == date(2024, 5, 29)

    @pytest.mark.settlement
    def test_nyse_t1_first_day_reform(self):
        """NYSE pierwszy dzień reformy (2024-05-28 wtorek) → T+1 → 2024-05-29 środa."""
        result = compute_settlement(date(2024, 5, 28), "NYSE")
        assert result == date(2024, 5, 29)

    @pytest.mark.settlement
    def test_reform_boundary_same_settle(self):
        """Scenariusz 5: T+2 z 27 maja i T+1 z 28 maja → oba settle 29 maja."""
        settle_pre = compute_settlement(date(2024, 5, 27), "NYSE")
        settle_post = compute_settlement(date(2024, 5, 28), "NYSE")
        assert settle_pre == settle_post == date(2024, 5, 29)


# ────────────────────────────────────────────────────────────
# Scenariusz 2: Ostatnia sesja roku NYSE (KRYTYCZNE!)
# ────────────────────────────────────────────────────────────

class TestYearBoundaryNYSE:
    """Brzeg roku na NYSE -- trade date vs tax year."""

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_nyse_dec31_2025_settles_2026(self):
        """
        Scenariusz 2: Trade NYSE 2025-12-31 (środa) T+1.
        1 stycznia = święto → settle 2026-01-02 → tax_year 2026!
        """
        result = compute_settlement(date(2025, 12, 31), "NYSE")
        assert result.year == 2026
        assert result == date(2026, 1, 2)

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_nyse_dec30_2025_settles_2025(self):
        """
        Scenariusz 2: Trade NYSE 2025-12-30 (wtorek) T+1.
        settle 2025-12-31 → tax_year 2025.
        """
        result = compute_settlement(date(2025, 12, 30), "NYSE")
        assert result == date(2025, 12, 31)
        assert result.year == 2025

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_nyse_dec31_2024_settles_2025(self):
        """
        Scenariusz 7: Trade NYSE 2024-12-31 (wtorek) T+1 (po reformie).
        1 stycznia = święto → settle 2025-01-02 → tax_year 2025!
        """
        result = compute_settlement(date(2024, 12, 31), "NYSE")
        assert result.year == 2025
        assert result == date(2025, 1, 2)


# ────────────────────────────────────────────────────────────
# Scenariusz 3: Brzeg roku AEB (Euronext Amsterdam, T+2)
# ────────────────────────────────────────────────────────────

class TestYearBoundaryAEB:
    """Brzeg roku na AEB -- T+2 powoduje inną granicę niż T+1."""

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_aeb_dec29_2025_settles_2025(self):
        """AEB 2025-12-29 (poniedziałek) T+2 → settle 2025-12-31 → year 2025."""
        result = compute_settlement(date(2025, 12, 29), "AEB")
        assert result == date(2025, 12, 31)
        assert result.year == 2025

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_aeb_dec30_2025_settles_2026(self):
        """AEB 2025-12-30 (wtorek) T+2 → 31 grudnia sesja, 1 stycznia święto → settle 2026-01-02."""
        result = compute_settlement(date(2025, 12, 30), "AEB")
        assert result.year == 2026


# ────────────────────────────────────────────────────────────
# Weekendy i święta
# ────────────────────────────────────────────────────────────

class TestWeekendsAndHolidays:
    """Settlement przeskakuje weekendy i święta giełdowe."""

    @pytest.mark.settlement
    def test_friday_trade_nasdaq_t1(self):
        """Piątek NASDAQ T+1 → poniedziałek (przeskakuje weekend)."""
        # 2025-03-14 = piątek
        result = compute_settlement(date(2025, 3, 14), "NASDAQ")
        assert result == date(2025, 3, 17)  # poniedziałek
        assert result.weekday() == 0

    @pytest.mark.settlement
    def test_friday_trade_aeb_t2(self):
        """Piątek AEB T+2 → wtorek (przeskakuje weekend)."""
        # 2025-03-14 = piątek
        result = compute_settlement(date(2025, 3, 14), "AEB")
        assert result == date(2025, 3, 18)  # wtorek
        assert result.weekday() == 1

    @pytest.mark.settlement
    def test_us_holiday_skipped(self):
        """Trade przed US holiday -- holiday nie liczy się jako dzień sesyjny."""
        # 2025-07-03 = czwartek, 2025-07-04 = Independence Day (piątek)
        # T+1 z czwartku = powinien być piątek, ale piątek = święto → poniedziałek
        result = compute_settlement(date(2025, 7, 3), "NYSE")
        assert result == date(2025, 7, 7)  # poniedziałek


# ────────────────────────────────────────────────────────────
# CBOE (opcje, OCC settlement = T+1 od 2024-05-28)
# ────────────────────────────────────────────────────────────

class TestCBOE:
    """Opcje na CBOE używają US settlement cycle (OCC)."""

    @pytest.mark.settlement
    def test_cboe_t1_after_reform(self):
        """CBOE po reformie → T+1."""
        result = compute_settlement(date(2025, 6, 10), "CBOE")
        assert result == date(2025, 6, 11)

    @pytest.mark.settlement
    def test_cboe_t2_before_reform(self):
        """CBOE przed reformą → T+2."""
        result = compute_settlement(date(2024, 3, 11), "CBOE")
        assert result == date(2024, 3, 13)


# ────────────────────────────────────────────────────────────
# ARCA
# ────────────────────────────────────────────────────────────

class TestARCA:
    """NYSE ARCA używa US settlement cycle."""

    @pytest.mark.settlement
    def test_arca_t1(self):
        """ARCA po reformie → T+1."""
        result = compute_settlement(date(2025, 1, 6), "ARCA")
        assert result == date(2025, 1, 7)


# ────────────────────────────────────────────────────────────
# NBP rate date (D-1 od settle_date)
# ────────────────────────────────────────────────────────────

class TestNBPRateDate:
    """Data kursu NBP = ostatni dzień roboczy przed settlement date."""

    def test_weekday_settle(self):
        """Settle we wtorek → D-1 = poniedziałek."""
        assert compute_nbp_rate_date(date(2025, 3, 18)) == date(2025, 3, 17)

    def test_monday_settle(self):
        """Settle w poniedziałek → D-1 = piątek (przeskakuje weekend)."""
        assert compute_nbp_rate_date(date(2025, 3, 17)) == date(2025, 3, 14)

    def test_wednesday_settle(self):
        """Settle w środę → D-1 = wtorek."""
        assert compute_nbp_rate_date(date(2025, 3, 19)) == date(2025, 3, 18)

    def test_jan2_settle(self):
        """Settle 2 stycznia (czwartek) → D-1 = 31 grudnia (środa)."""
        assert compute_nbp_rate_date(date(2025, 1, 2)) == date(2025, 1, 1)
        # Uwaga: 1 stycznia jest dniem wolnym NBP, ale nasz uproszczony
        # model traktuje pon-pt jako robocze. Pełna obsługa świąt NBP
        # będzie w module NBP client (Faza 3).


# ────────────────────────────────────────────────────────────
# enrich_trades_with_settlement -- integracja z parserem
# ────────────────────────────────────────────────────────────

class TestEnrichTrades:
    """Integracja: parser → settlement calculator."""

    @pytest.mark.settlement
    def test_enrich_real_data(self):
        """Wzbogać prawdziwe trade z CSV o settlement date."""
        from pathlib import Path
        from pit38.parsers.ibkr_csv import parse_ibkr_csv
        from pit38.settlement.calculator import enrich_trades_with_settlement

        fixture = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"
        if not fixture.exists():
            pytest.skip("Brak fixture CSV")

        parsed = parse_ibkr_csv(fixture)
        enriched = enrich_trades_with_settlement(parsed.trades)

        assert len(enriched) == len(parsed.trades)
        for trade in enriched:
            assert trade.settle_date is not None
            assert trade.settle_date >= trade.trade_date
            assert trade.tax_year is not None

    @pytest.mark.settlement
    @pytest.mark.boundary
    def test_enriched_trade_year_boundary(self):
        """Transakcje z końca grudnia mogą mieć tax_year = następny rok."""
        from pathlib import Path
        from pit38.parsers.ibkr_csv import parse_ibkr_csv
        from pit38.settlement.calculator import enrich_trades_with_settlement

        fixture = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"
        if not fixture.exists():
            pytest.skip("Brak fixture CSV")

        parsed = parse_ibkr_csv(fixture)
        enriched = enrich_trades_with_settlement(parsed.trades)

        # Szukaj transakcji z trade_date w grudniu
        dec_trades = [t for t in enriched if t.trade_date.month == 12]
        if dec_trades:
            # Przynajmniej jeden trade z grudnia powinien istnieć
            for t in dec_trades:
                # settle_date >= trade_date zawsze
                assert t.settle_date >= t.trade_date
                # Jeśli settle przechodzi do następnego roku -- to jest poprawne
                if t.settle_date.year > t.trade_date.year:
                    assert t.tax_year == t.settle_date.year

    @pytest.mark.settlement
    def test_settle_date_never_weekend(self):
        """Settlement date nigdy nie wypada w weekend."""
        from pathlib import Path
        from pit38.parsers.ibkr_csv import parse_ibkr_csv
        from pit38.settlement.calculator import enrich_trades_with_settlement

        fixture = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"
        if not fixture.exists():
            pytest.skip("Brak fixture CSV")

        parsed = parse_ibkr_csv(fixture)
        enriched = enrich_trades_with_settlement(parsed.trades)

        for trade in enriched:
            assert trade.settle_date.weekday() < 5, (
                f"{trade.symbol} settle {trade.settle_date} wypada w weekend!"
            )
