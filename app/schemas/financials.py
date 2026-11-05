"""Pydantic request/response schemas for the Stock Financials API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Period(str, Enum):
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"
    BOTH = "Both"


<<<<<<< HEAD
class ReportType(str, Enum):
    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"
    BOTH = "both"


=======
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Individual-statement envelopes (mirror the underlying service return shape)
# ---------------------------------------------------------------------------
class ProfitLossResponse(BaseModel):
    symbol: str
    company_name: Optional[str] = ""
<<<<<<< HEAD
    report_type: ReportType = ReportType.BOTH
=======
    consolidated: Optional[bool] = None
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    period: Period
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class BalanceSheetResponse(BaseModel):
    symbol: str
<<<<<<< HEAD
    report_type: ReportType = ReportType.BOTH
=======
    consolidated: Optional[bool] = None
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class CashFlowResponse(BaseModel):
    symbol: str
<<<<<<< HEAD
    report_type: ReportType = ReportType.BOTH
=======
    consolidated: Optional[bool] = None
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class AnnualReportResponse(BaseModel):
    symbol: str
<<<<<<< HEAD
    report_type: ReportType = ReportType.BOTH
=======
    consolidated: Optional[bool] = None
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
<<<<<<< HEAD
# Combined endpoint: symbol + report_type + period -> P&L (+ BS/CF when
=======
# Combined endpoint: symbol + consolidated + period -> P&L (+ BS/CF when
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
# the requested period includes annual data)
# ---------------------------------------------------------------------------
class CombinedFinancialsResponse(BaseModel):
    symbol: str
<<<<<<< HEAD
    report_type: ReportType = ReportType.BOTH
=======
    consolidated: Optional[bool] = None
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    period: Period
    profit_and_loss: Dict[str, Any] = Field(default_factory=dict)
    balance_sheet: Optional[Dict[str, Any]] = None
    cash_flow: Optional[Dict[str, Any]] = None
