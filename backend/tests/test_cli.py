"""Testy CLI (click)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from decimal import Decimal

from pit38.cli import main
from pit38.models.pit38_report import PIT38Report, PitZgEntry


# Ścieżka do prawdziwego CSV z IBKR
REAL_CSV = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"


def _make_mock_report(tax_year: int = 2025) -> PIT38Report:
    """Twórz testowy raport PIT-38."""
    return PIT38Report(
        tax_year=tax_year,
        c22_proceeds=Decimal("50000.00"),
        c23_costs=Decimal("40000.00"),
        c26_total_proceeds=Decimal("50000.00"),
        c27_total_costs=Decimal("40000.00"),
        c28_income=Decimal("10000.00"),
        c29_loss=Decimal("0"),
        d30_prior_losses=Decimal("0"),
        d31_tax_base=Decimal("10000"),
        d33_tax_calculated=Decimal("1900.00"),
        d34_foreign_tax=Decimal("0"),
        d35_tax_due=Decimal("1900"),
        dividends_gross_pln=Decimal("1000.00"),
        g47_dividend_tax=Decimal("190.00"),
        g48_dividend_wht=Decimal("150.00"),
        dividend_topup_exact=Decimal("40.00"),
        g49_dividend_difference=Decimal("40"),
        pit_zg_entries=[
            PitZgEntry(
                country_code="US",
                country_name="Stany Zjednoczone Ameryki",
                capital_gains_income=Decimal("10000.00"),
                other_income=Decimal("0"),
                foreign_tax_paid=Decimal("0"),
            ),
        ],
        total_tax_due=Decimal("1940"),
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIVersion:
    """Testy --version."""

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIHelp:
    """Testy --help."""

    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "calculate" in result.output
        assert "serve" in result.output

    def test_calculate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["calculate", "--help"])
        assert result.exit_code == 0
        assert "--tax-year" in result.output
        assert "--prior-losses" in result.output


class TestCLICalculateValidation:
    """Testy walidacji inputu CLI."""

    def test_missing_csv_file(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["calculate", "--tax-year", "2025"])
        assert result.exit_code != 0

    def test_nonexistent_csv_file(self, runner: CliRunner) -> None:
        result = runner.invoke(main, [
            "calculate", "nonexistent.csv", "--tax-year", "2025"
        ])
        assert result.exit_code != 0

    def test_missing_tax_year(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["calculate", "file.csv"])
        assert result.exit_code != 0


class TestCLICalculateMocked:
    """Testy calculate z mockowanym pipeline."""

    def test_calculate_output_format(self, runner: CliRunner, tmp_path: Path) -> None:
        """Sprawdź format wyjścia (sekcje C, D, G, PIT/ZG, podsumowanie)."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Statement,Data,Title,Activity Statement\n")

        mock_report = _make_mock_report()
        mock_parsed = MagicMock()
        mock_parsed.trades = []
        mock_parsed.dividends = []
        mock_parsed.withholding_taxes = []
        mock_parsed.corporate_actions = []

        mock_fifo = MagicMock()
        mock_fifo.tax_lots = []
        mock_fifo.warnings = []

        with patch("pit38.cli.parse_ibkr_csv", return_value=mock_parsed), \
             patch("pit38.cli.enrich_trades_with_settlement", return_value=[]), \
             patch("pit38.cli.run_fifo", return_value=mock_fifo), \
             patch("pit38.cli.calculate_pit38", return_value=mock_report), \
             patch("pit38.cli.NBPClient") as mock_nbp_cls:

            mock_nbp_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_nbp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(main, [
                "calculate", str(csv_file), "--tax-year", "2025"
            ])

        assert result.exit_code == 0
        # Sprawdź obecność sekcji w output
        assert "Sekcja C" in result.output
        assert "Sekcja D" in result.output
        assert "Sekcja G" in result.output
        assert "PIT/ZG" in result.output
        assert "1,940" in result.output  # total_tax_due

    def test_calculate_with_warnings(self, runner: CliRunner, tmp_path: Path) -> None:
        """Ostrzeżenia FIFO są wyświetlane."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Statement,Data,Title,Activity Statement\n")

        mock_report = _make_mock_report()
        mock_parsed = MagicMock()
        mock_parsed.trades = []
        mock_parsed.dividends = []
        mock_parsed.withholding_taxes = []
        mock_parsed.corporate_actions = []

        mock_fifo = MagicMock()
        mock_fifo.tax_lots = []
        mock_fifo.warnings = ["Short sell AAPL 2025-03-10: brak otwartych pozycji"]

        with patch("pit38.cli.parse_ibkr_csv", return_value=mock_parsed), \
             patch("pit38.cli.enrich_trades_with_settlement", return_value=[]), \
             patch("pit38.cli.run_fifo", return_value=mock_fifo), \
             patch("pit38.cli.calculate_pit38", return_value=mock_report), \
             patch("pit38.cli.NBPClient") as mock_nbp_cls:

            mock_nbp_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_nbp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(main, [
                "calculate", str(csv_file), "--tax-year", "2025"
            ])

        assert result.exit_code == 0
        assert "Short sell AAPL" in result.output

    def test_calculate_with_prior_losses(self, runner: CliRunner, tmp_path: Path) -> None:
        """prior-losses jest przekazywany poprawnie."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Statement,Data,Title,Activity Statement\n")

        mock_report = _make_mock_report()
        mock_parsed = MagicMock()
        mock_parsed.trades = []
        mock_parsed.dividends = []
        mock_parsed.withholding_taxes = []
        mock_parsed.corporate_actions = []

        mock_fifo = MagicMock()
        mock_fifo.tax_lots = []
        mock_fifo.warnings = []

        with patch("pit38.cli.parse_ibkr_csv", return_value=mock_parsed), \
             patch("pit38.cli.enrich_trades_with_settlement", return_value=[]), \
             patch("pit38.cli.run_fifo", return_value=mock_fifo), \
             patch("pit38.cli.calculate_pit38", return_value=mock_report) as mock_calc, \
             patch("pit38.cli.NBPClient") as mock_nbp_cls:

            mock_nbp_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_nbp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(main, [
                "calculate", str(csv_file),
                "--tax-year", "2025",
                "--prior-losses", "5000.00",
            ])

        assert result.exit_code == 0
        # Sprawdź że calculate_pit38 został wywołany z prior_losses=5000
        call_kwargs = mock_calc.call_args[1]
        assert call_kwargs["prior_losses"] == Decimal("5000.00")


@pytest.mark.nbp
class TestCLICalculateReal:
    """Testy CLI z prawdziwym CSV (wymaga internetu)."""

    def test_real_csv(self, runner: CliRunner) -> None:
        if not REAL_CSV.exists():
            pytest.skip("Brak pliku CSV z IBKR")
        result = runner.invoke(main, [
            "calculate", str(REAL_CSV), "--tax-year", "2025"
        ])
        assert result.exit_code == 0
        assert "PIT-38 za 2025" in result.output
