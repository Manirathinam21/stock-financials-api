"""Pydantic request/response schemas for the Stock Financials API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Period(str, Enum):
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"
    BOTH = "Both"


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Individual-statement envelopes (mirror the underlying service return shape)
# ---------------------------------------------------------------------------
class ProfitLossResponse(BaseModel):
    symbol: str
    company_name: Optional[str] = ""
    consolidated: Optional[bool] = None
    period: Period
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class BalanceSheetResponse(BaseModel):
    symbol: str
    consolidated: Optional[bool] = None
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class CashFlowResponse(BaseModel):
    symbol: str
    consolidated: Optional[bool] = None
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


class AnnualReportResponse(BaseModel):
    symbol: str
    consolidated: Optional[bool] = None
    total_filings: int = 0
    filings: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Combined endpoint: symbol + consolidated + period -> P&L (+ BS/CF when
# the requested period includes annual data)
# ---------------------------------------------------------------------------
class CombinedFinancialsResponse(BaseModel):
    symbol: str
    consolidated: Optional[bool] = None
    period: Period
    profit_and_loss: Dict[str, Any] = Field(default_factory=dict)
    balance_sheet: Optional[Dict[str, Any]] = None
    cash_flow: Optional[Dict[str, Any]] = None
