"""FastAPI routes -- kalkulacja PIT-38."""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

from pit38.api.schemas import (
    CalculateResponse,
    CorporateActionResponse,
    DividendResponse,
    ErrorResponse,
    HealthResponse,
    OpenPositionResponse,
    PitZgResponse,
    TaxLotResponse,
    TradeResponse,
    WhtResponse,
)
from pit38.fifo import run_fifo
from pit38.nbp import NBPClient
from pit38.parsers.ibkr_csv import parse_ibkr_csv, merge_ibkr_results
from pit38.settlement import enrich_trades_with_settlement
from pit38.tax import calculate_pit38

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def calculate(
    files: list[UploadFile] = File(..., description="IBKR Activity Statement CSV (jeden lub więcej)"),
    tax_year: int = Form(..., description="Rok podatkowy", ge=2020, le=2030),
    prior_losses: Decimal = Form(
        default=Decimal("0"),
        description="Strata z lat ubiegłych (D.30)",
        ge=0,
    ),
) -> CalculateResponse:
    """
    Oblicz PIT-38 na podstawie IBKR Activity Statement CSV.

    Pełny pipeline: CSV → parser → settlement → FIFO → tax calculator → raport.
    Obsługuje wiele plików CSV (np. roczne eksporty z IBKR).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Wymagany co najmniej jeden plik CSV")

    tmp_paths: list[Path] = []
    try:
        for f in files:
            # Walidacja typu pliku
            if f.filename and not f.filename.lower().endswith(".csv"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Wymagany plik CSV: {f.filename}",
                )
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                content = f.file.read()
                if not content:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Pusty plik: {f.filename}",
                    )
                tmp.write(content)
                tmp_paths.append(Path(tmp.name))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd odczytu pliku: {e}")
        raise HTTPException(status_code=400, detail=f"Błąd odczytu pliku: {e}")

    try:
        return _run_pipeline(tmp_paths, tax_year, prior_losses)
    finally:
        for p in tmp_paths:
            try:
                p.unlink()
            except OSError:
                pass


def _run_pipeline(
    csv_paths: list[Path],
    tax_year: int,
    prior_losses: Decimal,
) -> CalculateResponse:
    """Uruchom pełny pipeline kalkulacji."""
    # 1. Parsuj CSV (jeden lub wiele plików z deduplikacją)
    try:
        results = [parse_ibkr_csv(p) for p in csv_paths]
        parsed = merge_ibkr_results(results) if len(results) > 1 else results[0]
    except Exception as e:
        logger.error(f"Błąd parsowania CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Błąd parsowania CSV: {e}")

    logger.info(
        f"Sparsowano: {len(parsed.trades)} transakcji, "
        f"{len(parsed.dividends)} dywidend, "
        f"{len(parsed.corporate_actions)} corporate actions"
    )

    # 2. Oblicz settlement dates
    try:
        trades_with_settle = enrich_trades_with_settlement(parsed.trades)
    except Exception as e:
        logger.error(f"Błąd obliczania settlement date: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Błąd obliczania settlement date: {e}",
        )

    # 3. FIFO + NBP
    with NBPClient() as nbp_client:
        fifo_result = run_fifo(
            trades=trades_with_settle,
            corporate_actions=parsed.corporate_actions,
            nbp_client=nbp_client,
            tax_year=tax_year,
        )

        logger.info(
            f"FIFO: {len(fifo_result.tax_lots)} zamkniętych pozycji, "
            f"{len(fifo_result.warnings)} ostrzeżeń"
        )

        # 4. Kalkulacja PIT-38
        report = calculate_pit38(
            tax_lots=fifo_result.tax_lots,
            dividends=parsed.dividends,
            withholding_taxes=parsed.withholding_taxes,
            nbp_client=nbp_client,
            tax_year=tax_year,
            prior_losses=prior_losses,
        )

    # 5. Mapuj dane szczegółowe
    tax_lots_resp = [
        TaxLotResponse(
            symbol=lot.symbol, isin=lot.isin, country=lot.country,
            listing_exchange=lot.listing_exchange, asset_category=lot.asset_category,
            currency=lot.currency, multiplier=lot.multiplier,
            buy_trade_date=lot.buy_trade_date, buy_settle_date=lot.buy_settle_date,
            buy_nbp_rate_date=lot.buy_nbp_rate_date, buy_nbp_rate=lot.buy_nbp_rate,
            buy_price=lot.buy_price, buy_quantity=lot.buy_quantity,
            buy_commission=lot.buy_commission, buy_cost_pln=lot.buy_cost_pln,
            sell_trade_date=lot.sell_trade_date, sell_settle_date=lot.sell_settle_date,
            sell_nbp_rate_date=lot.sell_nbp_rate_date, sell_nbp_rate=lot.sell_nbp_rate,
            sell_price=lot.sell_price, sell_quantity=lot.sell_quantity,
            sell_commission=lot.sell_commission, sell_proceeds_pln=lot.sell_proceeds_pln,
            profit_loss_pln=lot.profit_loss_pln,
        )
        for lot in fifo_result.tax_lots
    ]

    trades_resp = [
        TradeResponse(
            symbol=t.symbol, isin=t.isin, asset_category=t.asset_category,
            currency=t.currency, listing_exchange=t.listing_exchange,
            trade_date=t.trade_date, settle_date=t.settle_date,
            quantity=t.quantity, price=t.price, proceeds=t.proceeds,
            commission=t.commission, multiplier=t.multiplier, codes=t.codes,
        )
        for t in trades_with_settle
    ]

    dividends_resp = [
        DividendResponse(
            symbol=d.symbol, isin=d.isin, currency=d.currency,
            payment_date=d.payment_date, amount=d.amount,
            dividend_type=d.dividend_type, description=d.description,
        )
        for d in parsed.dividends
    ]

    wht_resp = [
        WhtResponse(
            symbol=w.symbol, isin=w.isin, currency=w.currency,
            payment_date=w.payment_date, amount=w.amount,
            wht_type=w.wht_type, description=w.description,
        )
        for w in parsed.withholding_taxes
    ]

    ca_resp = [
        CorporateActionResponse(
            symbol=ca.symbol, isin=ca.isin, action_date=ca.action_date,
            action_type=ca.action_type, description=ca.description,
            quantity=ca.quantity, ratio_from=ca.ratio_from, ratio_to=ca.ratio_to,
        )
        for ca in parsed.corporate_actions
    ]

    open_resp = [
        OpenPositionResponse(
            symbol=key,
            remaining_quantity=lot.remaining_quantity,
            price_per_unit=lot.price_per_unit,
            trade_date=lot.trade.trade_date,
            settle_date=lot.trade.settle_date,
            currency=lot.trade.currency,
        )
        for key, lots in fifo_result.open_positions.items()
        for lot in lots
    ]

    # 6. Buduj response
    return CalculateResponse(
        tax_year=report.tax_year,
        c22_proceeds=report.c22_proceeds,
        c23_costs=report.c23_costs,
        c26_total_proceeds=report.c26_total_proceeds,
        c27_total_costs=report.c27_total_costs,
        c28_income=report.c28_income,
        c29_loss=report.c29_loss,
        d30_prior_losses=report.d30_prior_losses,
        d31_tax_base=report.d31_tax_base,
        d32_tax_rate=report.d32_tax_rate,
        d33_tax_calculated=report.d33_tax_calculated,
        d34_foreign_tax=report.d34_foreign_tax,
        d35_tax_due=report.d35_tax_due,
        dividends_gross_pln=report.dividends_gross_pln,
        g47_dividend_tax=report.g47_dividend_tax,
        g48_dividend_wht=report.g48_dividend_wht,
        dividend_topup_exact=report.dividend_topup_exact,
        g49_dividend_difference=report.g49_dividend_difference,
        pit_zg_entries=[
            PitZgResponse(
                country_code=e.country_code,
                country_name=e.country_name,
                capital_gains_income=e.capital_gains_income,
                other_income=e.other_income,
                foreign_tax_paid=e.foreign_tax_paid,
            )
            for e in report.pit_zg_entries
        ],
        total_tax_due=report.total_tax_due,
        tax_lots=tax_lots_resp,
        trades=trades_resp,
        dividends=dividends_resp,
        withholding_taxes=wht_resp,
        corporate_actions=ca_resp,
        open_positions=open_resp,
        trades_count=len(parsed.trades),
        tax_lots_count=len(fifo_result.tax_lots),
        dividends_count=len(parsed.dividends),
        warnings=fifo_result.warnings,
    )
