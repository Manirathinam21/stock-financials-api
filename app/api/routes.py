"""
API routes for the Stock Financials API.

Inputs (per the project spec):
    symbol:       NSE stock symbol, e.g. "RELIANCE", "TCS", "HDFCBANK"
<<<<<<< HEAD
    report_type:  "both"         -> consolidated and standalone results (default)
                  "consolidated" -> consolidated only
                  "standalone"   -> standalone only
=======
    consolidated: None  -> both consolidated and standalone results (default)
                  True  -> consolidated only
                  False -> standalone only
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    period:       "Quarterly" (default), "Annual", or "Both"
                  (Balance Sheet / Cash Flow only exist in annual filings,
                  so they are included whenever `period` is "Annual" or "Both".)
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.financials import (
    AnnualReportResponse,
    BalanceSheetResponse,
    CashFlowResponse,
    CombinedFinancialsResponse,
    Period,
    ProfitLossResponse,
<<<<<<< HEAD
    ReportType,
=======
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
)
from app.services import annual_financials, profit_loss

logger = logging.getLogger("stock_financials_api")

router = APIRouter()

_SYMBOL = Path(..., description="NSE stock symbol, e.g. RELIANCE, TCS, HDFCBANK", min_length=1)
<<<<<<< HEAD
_REPORT_TYPE = Query(
    ReportType.BOTH,
    description="consolidated = consolidated only, standalone = standalone only, both = consolidated and standalone (default).",
=======
_CONSOLIDATED = Query(
    None,
    description="None/omitted = both consolidated and standalone, true = consolidated only, false = standalone only.",
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
)
_PERIOD = Query(Period.QUARTERLY, description="Quarterly (default), Annual, or Both.")


def _norm_symbol(symbol: str) -> str:
    return symbol.strip().upper()


# ---------------------------------------------------------------------------
<<<<<<< HEAD
# Combined endpoint — matches the symbol / report_type / period contract
=======
# Combined endpoint — matches the symbol / consolidated / period contract
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
# ---------------------------------------------------------------------------
@router.get(
    "/financials/{symbol}",
    response_model=CombinedFinancialsResponse,
    summary="Get P&L (+ Balance Sheet & Cash Flow for annual periods) for a stock",
)
async def get_financials(
    symbol: str = _SYMBOL,
<<<<<<< HEAD
    report_type: ReportType = _REPORT_TYPE,
=======
    consolidated: bool | None = _CONSOLIDATED,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    period: Period = _PERIOD,
):
    """
    Single entry point: Profit & Loss is always returned for the requested
    `period`. Balance Sheet and Cash Flow are only produced in NSE's annual
    (audited) filings, so they're attached whenever `period` is `Annual` or
    `Both`; for `Quarterly` they are omitted (null).
    """
    symbol = _norm_symbol(symbol)

<<<<<<< HEAD
    pnl = await profit_loss.get_stock_financials(symbol, report_type=report_type.value, period=period.value)
=======
    pnl = await profit_loss.get_stock_financials(symbol, consolidated=consolidated, period=period.value)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not pnl:
        raise HTTPException(status_code=404, detail=f"No financial data found for symbol '{symbol}'")

    balance_sheet = None
    cash_flow = None
    if period in (Period.ANNUAL, Period.BOTH):
<<<<<<< HEAD
        balance_sheet = await annual_financials.get_stock_balance_sheet(symbol, report_type=report_type.value)
        cash_flow = await annual_financials.get_stock_cash_flow(symbol, report_type=report_type.value)

    return CombinedFinancialsResponse(
        symbol=symbol,
        report_type=report_type,
=======
        balance_sheet = await annual_financials.get_stock_balance_sheet(symbol, consolidated=consolidated)
        cash_flow = await annual_financials.get_stock_cash_flow(symbol, consolidated=consolidated)

    return CombinedFinancialsResponse(
        symbol=symbol,
        consolidated=consolidated,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        period=period,
        profit_and_loss=pnl,
        balance_sheet=balance_sheet or None,
        cash_flow=cash_flow or None,
    )


# ---------------------------------------------------------------------------
# Granular endpoints — one per statement, mirroring the original library
# ---------------------------------------------------------------------------
@router.get(
    "/profit-loss/{symbol}",
    response_model=ProfitLossResponse,
    summary="Get quarterly/annual Profit & Loss statement for a stock",
)
async def get_profit_loss(
    symbol: str = _SYMBOL,
<<<<<<< HEAD
    report_type: ReportType = _REPORT_TYPE,
    period: Period = _PERIOD,
):
    symbol = _norm_symbol(symbol)
    data = await profit_loss.get_stock_financials(symbol, report_type=report_type.value, period=period.value)
=======
    consolidated: bool | None = _CONSOLIDATED,
    period: Period = _PERIOD,
):
    symbol = _norm_symbol(symbol)
    data = await profit_loss.get_stock_financials(symbol, consolidated=consolidated, period=period.value)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not data:
        raise HTTPException(status_code=404, detail=f"No P&L data found for symbol '{symbol}'")
    return ProfitLossResponse(
        symbol=data.get("symbol", symbol),
        company_name=data.get("company_name", ""),
<<<<<<< HEAD
        report_type=report_type,
=======
        consolidated=consolidated,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        period=period,
        total_filings=data.get("total_filings", 0),
        filings=data.get("filings", []),
    )


@router.get(
    "/balance-sheet/{symbol}",
    response_model=BalanceSheetResponse,
    summary="Get annual Balance Sheet for a stock (annual filings only)",
)
<<<<<<< HEAD
async def get_balance_sheet(symbol: str = _SYMBOL, report_type: ReportType = _REPORT_TYPE):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_balance_sheet(symbol, report_type=report_type.value)
=======
async def get_balance_sheet(symbol: str = _SYMBOL, consolidated: bool | None = _CONSOLIDATED):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_balance_sheet(symbol, consolidated=consolidated)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not data:
        raise HTTPException(status_code=404, detail=f"No balance sheet data found for symbol '{symbol}'")
    return BalanceSheetResponse(
        symbol=data.get("symbol", symbol),
<<<<<<< HEAD
        report_type=report_type,
=======
        consolidated=consolidated,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        total_filings=data.get("total_filings", 0),
        filings=data.get("filings", []),
    )


@router.get(
    "/cash-flow/{symbol}",
    response_model=CashFlowResponse,
    summary="Get annual Cash Flow statement for a stock (annual filings only)",
)
<<<<<<< HEAD
async def get_cash_flow(symbol: str = _SYMBOL, report_type: ReportType = _REPORT_TYPE):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_cash_flow(symbol, report_type=report_type.value)
=======
async def get_cash_flow(symbol: str = _SYMBOL, consolidated: bool | None = _CONSOLIDATED):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_cash_flow(symbol, consolidated=consolidated)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not data:
        raise HTTPException(status_code=404, detail=f"No cash flow data found for symbol '{symbol}'")
    return CashFlowResponse(
        symbol=data.get("symbol", symbol),
<<<<<<< HEAD
        report_type=report_type,
=======
        consolidated=consolidated,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        total_filings=data.get("total_filings", 0),
        filings=data.get("filings", []),
    )


@router.get(
    "/annual-report/{symbol}",
    response_model=AnnualReportResponse,
    summary="Get the full annual filing set (P&L + Balance Sheet + Cash Flow + Segments)",
)
<<<<<<< HEAD
async def get_annual_report(symbol: str = _SYMBOL, report_type: ReportType = _REPORT_TYPE):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_annual_report(symbol, report_type=report_type.value)
=======
async def get_annual_report(symbol: str = _SYMBOL, consolidated: bool | None = _CONSOLIDATED):
    symbol = _norm_symbol(symbol)
    data = await annual_financials.get_stock_annual_report(symbol, consolidated=consolidated)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not data:
        raise HTTPException(status_code=404, detail=f"No annual report data found for symbol '{symbol}'")
    return AnnualReportResponse(
        symbol=data.get("symbol", symbol),
<<<<<<< HEAD
        report_type=report_type,
=======
        consolidated=consolidated,
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        total_filings=data.get("total_filings", 0),
        filings=data.get("filings", []),
    )
