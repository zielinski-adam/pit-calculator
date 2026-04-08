"""Klient API NBP -- pobieranie kursów średnich walut (tabela A)."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

# Domyślna ścieżka do cache SQLite
DEFAULT_CACHE_PATH = Path.home() / ".pit38" / "nbp_cache.db"

# API NBP
NBP_API_BASE = "https://api.nbp.pl/api/exchangerates/rates"

# Maksymalna liczba dni wstecz przy szukaniu kursu (weekendy + święta)
MAX_LOOKBACK_DAYS = 10


class NBPError(Exception):
    """Błąd pobierania kursu NBP."""


class NBPClient:
    """
    Klient do pobierania kursów średnich NBP z cache SQLite.

    Algorytm get_rate(currency, rate_date):
    1. Sprawdź cache SQLite
    2. Jeśli brak → pobierz z API NBP
    3. Zapisz do cache
    4. Zwróć kurs jako Decimal

    rate_date to data kursu (D-1 od settlement date), NIE settlement date.
    Jeśli rate_date to dzień wolny NBP (weekend/święto), API zwróci 404.
    Wtedy cofamy się dzień po dniu aż znajdziemy kurs (max MAX_LOOKBACK_DAYS).
    """

    def __init__(
        self,
        cache_path: Path | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._cache_path = cache_path or DEFAULT_CACHE_PATH
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._init_cache()

    def _init_cache(self) -> None:
        """Utwórz tabelę cache jeśli nie istnieje."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nbp_rates (
                    currency TEXT NOT NULL,
                    rate_date TEXT NOT NULL,
                    rate TEXT NOT NULL,
                    table_no TEXT NOT NULL,
                    fetched_date TEXT NOT NULL,
                    PRIMARY KEY (currency, rate_date)
                )
            """)

    def _get_db(self) -> sqlite3.Connection:
        """Połączenie do SQLite."""
        return sqlite3.connect(str(self._cache_path))

    def _get_http_client(self) -> httpx.Client:
        """Lazy init klienta HTTP."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=15.0)
        return self._http_client

    def get_rate(self, currency: str, rate_date: date) -> Decimal:
        """
        Pobierz kurs średni NBP dla waluty na podaną datę.

        Args:
            currency: Kod waluty ISO 4217 (np. "USD", "EUR")
            rate_date: Data kursu (D-1 od settlement date)

        Returns:
            Kurs średni jako Decimal

        Raises:
            NBPError: Gdy nie udało się pobrać kursu
        """
        currency = currency.upper()

        # PLN → zawsze 1
        if currency == "PLN":
            return Decimal("1")

        # Szukaj kursu z cofaniem się (rate_date może być świętem NBP)
        current_date = rate_date
        for _ in range(MAX_LOOKBACK_DAYS):
            # Pomiń weekendy
            if current_date.weekday() >= 5:
                current_date -= timedelta(days=1)
                continue

            # Sprawdź cache
            cached = self._get_from_cache(currency, current_date)
            if cached is not None:
                return cached

            # Pobierz z API
            result = self._fetch_from_api(currency, current_date)
            if result is not None:
                rate, table_no = result
                self._save_to_cache(currency, current_date, rate, table_no)
                return rate

            # 404 = dzień wolny NBP, cofaj się
            current_date -= timedelta(days=1)

        raise NBPError(
            f"Nie znaleziono kursu {currency} w zakresie "
            f"{current_date} - {rate_date} (sprawdzono {MAX_LOOKBACK_DAYS} dni)"
        )

    def get_rate_with_date(
        self, currency: str, rate_date: date
    ) -> tuple[Decimal, date]:
        """
        Jak get_rate, ale zwraca też faktyczną datę kursu
        (może się różnić od rate_date jeśli to był dzień wolny NBP).

        Returns:
            (kurs, faktyczna_data_kursu)
        """
        currency = currency.upper()

        if currency == "PLN":
            return Decimal("1"), rate_date

        current_date = rate_date
        for _ in range(MAX_LOOKBACK_DAYS):
            if current_date.weekday() >= 5:
                current_date -= timedelta(days=1)
                continue

            cached = self._get_from_cache(currency, current_date)
            if cached is not None:
                return cached, current_date

            result = self._fetch_from_api(currency, current_date)
            if result is not None:
                rate, table_no = result
                self._save_to_cache(currency, current_date, rate, table_no)
                return rate, current_date

            current_date -= timedelta(days=1)

        raise NBPError(
            f"Nie znaleziono kursu {currency} w zakresie "
            f"{current_date} - {rate_date}"
        )

    def _get_from_cache(self, currency: str, rate_date: date) -> Decimal | None:
        """Sprawdź cache SQLite."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT rate FROM nbp_rates WHERE currency = ? AND rate_date = ?",
                (currency, rate_date.isoformat()),
            ).fetchone()
        if row:
            return Decimal(row[0])
        return None

    def _save_to_cache(
        self, currency: str, rate_date: date, rate: Decimal, table_no: str
    ) -> None:
        """Zapisz kurs do cache SQLite."""
        with self._get_db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO nbp_rates
                   (currency, rate_date, rate, table_no, fetched_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    currency,
                    rate_date.isoformat(),
                    str(rate),
                    table_no,
                    date.today().isoformat(),
                ),
            )

    def _fetch_from_api(
        self, currency: str, rate_date: date
    ) -> tuple[Decimal, str] | None:
        """
        Pobierz kurs z API NBP.

        Returns:
            (rate, table_no) lub None jeśli 404 (dzień wolny)

        Raises:
            NBPError: Przy błędach HTTP innych niż 404
        """
        # Tabela A -- kursy średnie
        url = f"{NBP_API_BASE}/a/{currency.lower()}/{rate_date.isoformat()}/"
        client = self._get_http_client()

        try:
            resp = client.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            raise NBPError(f"Błąd HTTP przy pobieraniu kursu {currency}/{rate_date}: {e}") from e

        if resp.status_code == 404:
            # Dzień wolny NBP lub brak danych
            return None

        if resp.status_code != 200:
            raise NBPError(
                f"API NBP zwróciło status {resp.status_code} "
                f"dla {currency}/{rate_date}: {resp.text}"
            )

        data = resp.json()
        rates = data.get("rates", [])
        if not rates:
            return None

        mid = rates[0]["mid"]
        table_no = rates[0].get("no", "")
        # Konwertuj na Decimal z pełną precyzją
        rate = Decimal(str(mid))
        return rate, table_no

    def close(self) -> None:
        """Zamknij klienta HTTP jeśli został utworzony wewnętrznie."""
        if self._owns_http_client and self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def __enter__(self) -> NBPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def clear_cache(self) -> None:
        """Wyczyść całą tabelę cache (do debugowania)."""
        with self._get_db() as conn:
            conn.execute("DELETE FROM nbp_rates")

    def cache_stats(self) -> dict[str, int]:
        """Statystyki cache (do debugowania)."""
        with self._get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM nbp_rates").fetchone()[0]
            currencies = conn.execute(
                "SELECT COUNT(DISTINCT currency) FROM nbp_rates"
            ).fetchone()[0]
        return {"total_entries": total, "currencies": currencies}
