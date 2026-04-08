"""Testy API FastAPI."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit38.api.app import create_app

# Ścieżka do prawdziwego CSV z IBKR
REAL_CSV = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"


@pytest.fixture
def client() -> TestClient:
    """Test client FastAPI."""
    app = create_app()
    return TestClient(app)


class TestHealthCheck:
    """Testy health check."""

    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


class TestCalculateValidation:
    """Testy walidacji inputu."""

    def test_missing_file(self, client: TestClient) -> None:
        resp = client.post("/api/calculate", data={"tax_year": 2025})
        assert resp.status_code == 422

    def test_missing_tax_year(self, client: TestClient) -> None:
        csv_content = b"dummy,csv,content"
        resp = client.post(
            "/api/calculate",
            files=[("files", ("test.csv", io.BytesIO(csv_content), "text/csv"))],
        )
        assert resp.status_code == 422

    def test_invalid_file_extension(self, client: TestClient) -> None:
        resp = client.post(
            "/api/calculate",
            files=[("files", ("test.txt", io.BytesIO(b"data"), "text/plain"))],
            data={"tax_year": 2025},
        )
        assert resp.status_code == 400
        assert "CSV" in resp.json()["detail"]

    def test_empty_file(self, client: TestClient) -> None:
        resp = client.post(
            "/api/calculate",
            files=[("files", ("test.csv", io.BytesIO(b""), "text/csv"))],
            data={"tax_year": 2025},
        )
        assert resp.status_code == 400

    def test_tax_year_out_of_range(self, client: TestClient) -> None:
        csv_content = b"dummy,csv,content"
        resp = client.post(
            "/api/calculate",
            files=[("files", ("test.csv", io.BytesIO(csv_content), "text/csv"))],
            data={"tax_year": 2019},
        )
        assert resp.status_code == 422


class TestCalculateWithMinimalCSV:
    """Testy z minimalnym CSV (brak transakcji)."""

    def test_empty_csv_returns_zeros(self, client: TestClient) -> None:
        """Pusty CSV (bez sekcji Trades) → zerowy raport."""
        csv_content = b"Statement,Data,Title,Activity Statement\n"
        resp = client.post(
            "/api/calculate",
            files=[("files", ("empty.csv", io.BytesIO(csv_content), "text/csv"))],
            data={"tax_year": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tax_year"] == 2025
        assert float(data["c22_proceeds"]) == 0
        assert float(data["c23_costs"]) == 0
        assert float(data["total_tax_due"]) == 0
        assert data["trades_count"] == 0
        assert data["tax_lots_count"] == 0

    def test_prior_losses_param(self, client: TestClient) -> None:
        """prior_losses jest przekazywany do raportu."""
        csv_content = b"Statement,Data,Title,Activity Statement\n"
        resp = client.post(
            "/api/calculate",
            files=[("files", ("empty.csv", io.BytesIO(csv_content), "text/csv"))],
            data={"tax_year": 2025, "prior_losses": "1000.50"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["d30_prior_losses"]) == 1000.50


@pytest.mark.nbp
class TestCalculateWithRealCSV:
    """Testy z prawdziwym plikiem CSV IBKR (wymaga internetu)."""

    @pytest.fixture
    def real_csv_bytes(self) -> bytes:
        if not REAL_CSV.exists():
            pytest.skip("Brak pliku CSV z IBKR")
        return REAL_CSV.read_bytes()

    def test_full_pipeline(self, client: TestClient, real_csv_bytes: bytes) -> None:
        """Pełny pipeline na prawdziwych danych."""
        resp = client.post(
            "/api/calculate",
            files=[("files", ("statement.csv", io.BytesIO(real_csv_bytes), "text/csv"))],
            data={"tax_year": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Podstawowe warunki
        assert data["tax_year"] == 2025
        assert data["trades_count"] > 0
        assert data["d32_tax_rate"] == 19
        assert isinstance(data["pit_zg_entries"], list)
        assert isinstance(data["warnings"], list)

    def test_response_has_all_fields(self, client: TestClient, real_csv_bytes: bytes) -> None:
        """Odpowiedź zawiera wszystkie pola PIT-38."""
        resp = client.post(
            "/api/calculate",
            files=[("files", ("statement.csv", io.BytesIO(real_csv_bytes), "text/csv"))],
            data={"tax_year": 2025},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Sekcja C
        for field in ["c22_proceeds", "c23_costs", "c26_total_proceeds",
                       "c27_total_costs", "c28_income", "c29_loss"]:
            assert field in data, f"Brak pola {field}"

        # Sekcja D
        for field in ["d30_prior_losses", "d31_tax_base", "d32_tax_rate",
                       "d33_tax_calculated", "d34_foreign_tax", "d35_tax_due"]:
            assert field in data, f"Brak pola {field}"

        # Sekcja G
        for field in ["dividends_gross_pln", "g47_dividend_tax", "g48_dividend_wht",
                       "dividend_topup_exact", "g49_dividend_difference"]:
            assert field in data, f"Brak pola {field}"

        # Suma + meta
        assert "total_tax_due" in data
        assert "pit_zg_entries" in data
