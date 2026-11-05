"""Pydantic request/response schemas for the Stock Financials API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Period(str, Enum):
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"
    BOTH = "Both"


class ReportType(str, Enum):
    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"
    BOTH = "both"


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Individual-statement envelopes (mirror the underlying service return shape)
# ---------------------------------------------------------------------------
class ProfitLossResponse(BaseModel):
    symbol: str
    company_name: Optional[str] = ""
    report_type: ReportType = ReportType.BOTH
    period: Period
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class BalanceSheetResponse(BaseModel):
    symbol: str
    report_type: ReportType = ReportType.BOTH
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class CashFlowResponse(BaseModel):
    symbol: str
    report_type: ReportType = ReportType.BOTH
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class AnnualReportResponse(BaseModel):
    symbol: str
    report_type: ReportType = ReportType.BOTH
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Combined endpoint: symbol + report_type + period -> P&L (+ BS/CF when
# the requested period includes annual data)
# ---------------------------------------------------------------------------
class CombinedFinancialsResponse(BaseModel):
    symbol: str
    report_type: ReportType = ReportType.BOTH
    period: Period
    profit_and_loss: Dict[str, Any] = Field(default_factory=dict)
    balance_sheet: Optional[Dict[str, Any]] = None
    cash_flow: Optional[Dict[str, Any]] = None
