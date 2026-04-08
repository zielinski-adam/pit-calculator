"""
CLI kalkulator PIT-38 -- click + rich.

Komendy:
  calculate  Oblicz PIT-38 z pliku CSV
  serve      Uruchom serwer API
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pit38.fifo import run_fifo
from pit38.nbp import NBPClient
from pit38.parsers.ibkr_csv import parse_ibkr_csv
from pit38.settlement import enrich_trades_with_settlement
from pit38.tax import calculate_pit38

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="pit38")
def main() -> None:
    """Kalkulator PIT-38 dla Interactive Brokers."""


@main.command()
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--tax-year", "-y",
    type=int,
    required=True,
    help="Rok podatkowy",
)
@click.option(
    "--prior-losses", "-l",
    type=str,
    default="0",
    help="Strata z lat ubiegłych do odliczenia (D.30)",
)
def calculate(csv_file: Path, tax_year: int, prior_losses: str) -> None:
    """Oblicz PIT-38 z pliku IBKR Activity Statement CSV."""
    losses = Decimal(prior_losses)

    with console.status("[bold green]Parsowanie CSV..."):
        parsed = parse_ibkr_csv(csv_file)

    console.print(
        f"[green]✓[/] Sparsowano: {len(parsed.trades)} transakcji, "
        f"{len(parsed.dividends)} dywidend, "
        f"{len(parsed.corporate_actions)} corporate actions"
    )

    with console.status("[bold green]Obliczanie settlement dates..."):
        trades_with_settle = enrich_trades_with_settlement(parsed.trades)

    with console.status("[bold green]FIFO + NBP + kalkulacja..."):
        with NBPClient() as nbp_client:
            fifo_result = run_fifo(
                trades=trades_with_settle,
                corporate_actions=parsed.corporate_actions,
                nbp_client=nbp_client,
                tax_year=tax_year,
            )
            report = calculate_pit38(
                tax_lots=fifo_result.tax_lots,
                dividends=parsed.dividends,
                withholding_taxes=parsed.withholding_taxes,
                nbp_client=nbp_client,
                tax_year=tax_year,
                prior_losses=losses,
            )

    console.print(
        f"[green]✓[/] FIFO: {len(fifo_result.tax_lots)} zamkniętych pozycji"
    )

    # Ostrzeżenia
    if fifo_result.warnings:
        console.print(f"\n[yellow]⚠ Ostrzeżenia ({len(fifo_result.warnings)}):[/]")
        for w in fifo_result.warnings:
            console.print(f"  [yellow]• {w}[/]")

    # Sekcja C
    table_c = Table(title="Sekcja C -- Przychody z odpłatnego zbycia")
    table_c.add_column("Pozycja", style="bold")
    table_c.add_column("Opis")
    table_c.add_column("Kwota (PLN)", justify="right")
    table_c.add_row("C.22", "Przychody", f"{report.c22_proceeds:,.2f}")
    table_c.add_row("C.23", "Koszty uzyskania", f"{report.c23_costs:,.2f}")
    table_c.add_row("C.26", "Razem przychody", f"{report.c26_total_proceeds:,.2f}")
    table_c.add_row("C.27", "Razem koszty", f"{report.c27_total_costs:,.2f}")
    table_c.add_row("C.28", "Dochód", f"{report.c28_income:,.2f}")
    table_c.add_row("C.29", "Strata", f"{report.c29_loss:,.2f}")
    console.print("\n", table_c)

    # Sekcja D
    table_d = Table(title="Sekcja D -- Obliczenie podatku")
    table_d.add_column("Pozycja", style="bold")
    table_d.add_column("Opis")
    table_d.add_column("Kwota (PLN)", justify="right")
    table_d.add_row("D.30", "Straty z lat ubiegłych", f"{report.d30_prior_losses:,.2f}")
    table_d.add_row("D.31", "Podstawa obliczenia", f"{report.d31_tax_base:,.0f}")
    table_d.add_row("D.32", "Stawka podatku", "19%")
    table_d.add_row("D.33", "Podatek obliczony", f"{report.d33_tax_calculated:,.2f}")
    table_d.add_row("D.34", "Podatek zagraniczny", f"{report.d34_foreign_tax:,.2f}")
    table_d.add_row("D.35", "Podatek należny", f"{report.d35_tax_due:,.0f}")
    console.print("\n", table_d)

    # Sekcja G
    table_g = Table(title="Sekcja G -- Dywidendy zagraniczne")
    table_g.add_column("Pozycja", style="bold")
    table_g.add_column("Opis")
    table_g.add_column("Kwota (PLN)", justify="right")
    table_g.add_row("", "Dywidendy brutto", f"{report.dividends_gross_pln:,.2f}")
    table_g.add_row("G.47", "19% podatku", f"{report.g47_dividend_tax:,.2f}")
    table_g.add_row("G.48", "WHT zapłacony", f"{report.g48_dividend_wht:,.2f}")
    table_g.add_row("", "Do dopłaty (dokładna)", f"{report.dividend_topup_exact:,.2f}")
    table_g.add_row("G.49", "Różnica (zaokrąglona)", f"{report.g49_dividend_difference:,.0f}")
    console.print("\n", table_g)

    # PIT/ZG
    if report.pit_zg_entries:
        table_zg = Table(title="PIT/ZG -- per kraj")
        table_zg.add_column("Kraj", style="bold")
        table_zg.add_column("Kod")
        table_zg.add_column("Zyski kapitałowe (PLN)", justify="right")
        table_zg.add_column("Podatek zagraniczny (PLN)", justify="right")
        for e in report.pit_zg_entries:
            table_zg.add_row(
                e.country_name,
                e.country_code,
                f"{e.capital_gains_income:,.2f}",
                f"{e.foreign_tax_paid:,.2f}",
            )
        console.print("\n", table_zg)

    # Podsumowanie
    console.print(
        Panel(
            f"[bold green]Podatek do zapłaty: {report.total_tax_due:,.0f} PLN[/]\n"
            f"  Zyski kapitałowe (D.35): {report.d35_tax_due:,.0f} PLN\n"
            f"  Dywidendy (G.49): {report.g49_dividend_difference:,.0f} PLN",
            title=f"PIT-38 za {report.tax_year}",
            border_style="green",
        )
    )


@main.command()
@click.option("--host", default="127.0.0.1", help="Host serwera")
@click.option("--port", "-p", default=8000, type=int, help="Port serwera")
@click.option("--reload", "do_reload", is_flag=True, help="Auto-reload przy zmianach")
def serve(host: str, port: int, do_reload: bool) -> None:
    """Uruchom serwer API (uvicorn)."""
    import uvicorn

    console.print(f"[green]Uruchamiam serwer API na {host}:{port}[/]")
    uvicorn.run(
        "pit38.api.app:app",
        host=host,
        port=port,
        reload=do_reload,
    )


if __name__ == "__main__":
    main()
