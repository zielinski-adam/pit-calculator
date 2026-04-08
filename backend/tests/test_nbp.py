"""Testy klienta NBP -- cache SQLite + API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from pit38.nbp.client import NBPClient, NBPError


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    """Tymczasowa ścieżka do cache."""
    return tmp_path / "test_nbp_cache.db"


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Mock klienta HTTP."""
    return MagicMock(spec=httpx.Client)


def _make_nbp_response(mid: float, table_no: str = "001/A/NBP/2025") -> httpx.Response:
    """Stwórz mock odpowiedzi NBP API."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "table": "A",
        "currency": "dolar amerykański",
        "code": "USD",
        "rates": [{"no": table_no, "effectiveDate": "2025-03-17", "mid": mid}],
    }
    return resp


def _make_404_response() -> httpx.Response:
    """Stwórz mock odpowiedzi 404 (dzień wolny)."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    resp.text = "NotFound"
    return resp


# ────────────────────────────────────────────────────────────
# PLN -- zawsze 1, bez API
# ────────────────────────────────────────────────────────────

class TestPLN:
    """PLN nie wymaga zapytania do API."""

    def test_pln_returns_one(self, tmp_cache: Path):
        client = NBPClient(cache_path=tmp_cache)
        assert client.get_rate("PLN", date(2025, 3, 17)) == Decimal("1")

    def test_pln_case_insensitive(self, tmp_cache: Path):
        client = NBPClient(cache_path=tmp_cache)
        assert client.get_rate("pln", date(2025, 3, 17)) == Decimal("1")

    def test_pln_with_date(self, tmp_cache: Path):
        client = NBPClient(cache_path=tmp_cache)
        rate, actual_date = client.get_rate_with_date("PLN", date(2025, 3, 17))
        assert rate == Decimal("1")
        assert actual_date == date(2025, 3, 17)


# ────────────────────────────────────────────────────────────
# Pobieranie kursu z API
# ────────────────────────────────────────────────────────────

class TestAPIFetch:
    """Pobieranie kursu z API NBP."""

    def test_fetch_usd(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Pobranie kursu USD z API."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        rate = client.get_rate("USD", date(2025, 3, 17))

        assert rate == Decimal("4.0234")
        mock_http_client.get.assert_called_once()

    def test_fetch_eur(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Pobranie kursu EUR z API."""
        mock_http_client.get.return_value = _make_nbp_response(4.2891)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        rate = client.get_rate("EUR", date(2025, 3, 17))

        assert rate == Decimal("4.2891")

    def test_rate_is_decimal(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Kurs MUSI być Decimal, nie float."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        rate = client.get_rate("USD", date(2025, 3, 17))

        assert isinstance(rate, Decimal)


# ────────────────────────────────────────────────────────────
# Cache SQLite
# ────────────────────────────────────────────────────────────

class TestCache:
    """Cache SQLite zapisuje i odczytuje kursy."""

    def test_cache_hit(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Drugie zapytanie o ten sam kurs bierze z cache."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        # Pierwsze pobranie -- z API
        rate1 = client.get_rate("USD", date(2025, 3, 17))
        # Drugie pobranie -- z cache (bez API)
        rate2 = client.get_rate("USD", date(2025, 3, 17))

        assert rate1 == rate2 == Decimal("4.0234")
        # API wywołane tylko raz
        assert mock_http_client.get.call_count == 1

    def test_different_dates_separate_cache(
        self, tmp_cache: Path, mock_http_client: MagicMock
    ):
        """Różne daty mają osobne wpisy w cache."""
        mock_http_client.get.side_effect = [
            _make_nbp_response(4.0234),
            _make_nbp_response(4.0567),
        ]
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        rate1 = client.get_rate("USD", date(2025, 3, 17))
        rate2 = client.get_rate("USD", date(2025, 3, 18))

        assert rate1 == Decimal("4.0234")
        assert rate2 == Decimal("4.0567")
        assert mock_http_client.get.call_count == 2

    def test_cache_stats(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Statystyki cache."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)
        client.get_rate("USD", date(2025, 3, 17))

        stats = client.cache_stats()
        assert stats["total_entries"] == 1
        assert stats["currencies"] == 1

    def test_clear_cache(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Czyszczenie cache."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)
        client.get_rate("USD", date(2025, 3, 17))

        client.clear_cache()
        stats = client.cache_stats()
        assert stats["total_entries"] == 0


# ────────────────────────────────────────────────────────────
# Lookback -- cofanie się przy dniach wolnych NBP
# ────────────────────────────────────────────────────────────

class TestLookback:
    """Cofanie się do ostatniego dnia z kursem."""

    def test_weekend_skip(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Sobota → piątek (bez wywołania API dla soboty)."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        # 2025-03-15 = sobota → powinien skoczyć do piątku 14
        rate = client.get_rate("USD", date(2025, 3, 15))

        assert rate == Decimal("4.0234")
        # API wywołane dla piątku
        call_url = mock_http_client.get.call_args[0][0]
        assert "2025-03-14" in call_url

    def test_sunday_skip(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Niedziela → piątek."""
        mock_http_client.get.return_value = _make_nbp_response(4.0234)
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        # 2025-03-16 = niedziela → piątek 14
        rate = client.get_rate("USD", date(2025, 3, 16))
        call_url = mock_http_client.get.call_args[0][0]
        assert "2025-03-14" in call_url

    def test_holiday_404_lookback(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Święto NBP (404) → cofnij o dzień."""
        mock_http_client.get.side_effect = [
            _make_404_response(),  # 2025-01-06 -- Trzech Króli? (lub inny)
            _make_nbp_response(4.0234),  # 2025-01-03 -- piątek
        ]
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        rate = client.get_rate("USD", date(2025, 1, 6))

        assert rate == Decimal("4.0234")
        assert mock_http_client.get.call_count == 2

    def test_max_lookback_exceeded(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Przekroczenie MAX_LOOKBACK_DAYS → NBPError."""
        mock_http_client.get.return_value = _make_404_response()
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        with pytest.raises(NBPError, match="Nie znaleziono kursu"):
            client.get_rate("USD", date(2025, 3, 17))


# ────────────────────────────────────────────────────────────
# Obsługa błędów
# ────────────────────────────────────────────────────────────

class TestErrors:
    """Obsługa błędów API."""

    def test_http_error(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Błąd sieciowy → NBPError."""
        mock_http_client.get.side_effect = httpx.ConnectError("Connection refused")
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        with pytest.raises(NBPError, match="Błąd HTTP"):
            client.get_rate("USD", date(2025, 3, 17))

    def test_server_error(self, tmp_cache: Path, mock_http_client: MagicMock):
        """Błąd serwera (500) → NBPError."""
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 500
        resp.text = "Internal Server Error"
        mock_http_client.get.return_value = resp
        client = NBPClient(cache_path=tmp_cache, http_client=mock_http_client)

        with pytest.raises(NBPError, match="status 500"):
            client.get_rate("USD", date(2025, 3, 17))


# ────────────────────────────────────────────────────────────
# Context manager
# ────────────────────────────────────────────────────────────

class TestContextManager:
    """NBPClient jako context manager."""

    def test_context_manager(self, tmp_cache: Path):
        """with NBPClient() zamyka klienta HTTP."""
        with NBPClient(cache_path=tmp_cache) as client:
            rate = client.get_rate("PLN", date(2025, 3, 17))
            assert rate == Decimal("1")


# ────────────────────────────────────────────────────────────
# Integracja z prawdziwym API NBP (oznaczone @pytest.mark.nbp)
# ────────────────────────────────────────────────────────────

class TestRealAPI:
    """Testy z prawdziwym API NBP -- wymagają internetu."""

    @pytest.mark.nbp
    def test_real_usd_rate(self, tmp_cache: Path):
        """Pobierz prawdziwy kurs USD z API NBP."""
        with NBPClient(cache_path=tmp_cache) as client:
            # 2025-03-17 = poniedziałek, powinien istnieć
            rate = client.get_rate("USD", date(2025, 3, 17))

            assert isinstance(rate, Decimal)
            # Kurs USD powinien być w rozsądnym zakresie (3-5 PLN)
            assert Decimal("3") < rate < Decimal("5")

    @pytest.mark.nbp
    def test_real_eur_rate(self, tmp_cache: Path):
        """Pobierz prawdziwy kurs EUR z API NBP."""
        with NBPClient(cache_path=tmp_cache) as client:
            rate = client.get_rate("EUR", date(2025, 3, 17))

            assert isinstance(rate, Decimal)
            assert Decimal("3.5") < rate < Decimal("5.5")

    @pytest.mark.nbp
    def test_real_cache_works(self, tmp_cache: Path):
        """Drugie pobranie bierze z cache (szybsze)."""
        with NBPClient(cache_path=tmp_cache) as client:
            rate1 = client.get_rate("USD", date(2025, 3, 17))
            rate2 = client.get_rate("USD", date(2025, 3, 17))

            assert rate1 == rate2
            stats = client.cache_stats()
            assert stats["total_entries"] >= 1

    @pytest.mark.nbp
    def test_real_rate_with_date(self, tmp_cache: Path):
        """get_rate_with_date zwraca faktyczną datę kursu."""
        with NBPClient(cache_path=tmp_cache) as client:
            rate, actual_date = client.get_rate_with_date("USD", date(2025, 3, 17))

            assert isinstance(rate, Decimal)
            assert actual_date <= date(2025, 3, 17)
            # Nie powinno cofnąć się więcej niż 3 dni
            assert (date(2025, 3, 17) - actual_date).days <= 3

    @pytest.mark.nbp
    def test_real_weekend_lookback(self, tmp_cache: Path):
        """Kurs z soboty → zwraca piątkowy."""
        with NBPClient(cache_path=tmp_cache) as client:
            # 2025-03-15 = sobota
            rate, actual_date = client.get_rate_with_date("USD", date(2025, 3, 15))

            assert isinstance(rate, Decimal)
            # Powinien zwrócić piątek 14 marca
            assert actual_date == date(2025, 3, 14)
