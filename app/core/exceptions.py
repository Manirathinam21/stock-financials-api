"""Custom exceptions for the Stock Financials API."""


class StockFinancialsError(Exception):
    """Base exception for all app errors."""


class SymbolNotFoundError(StockFinancialsError):
    """Raised when NSE has no data for the requested symbol."""

    def __init__(self, symbol: str, statement: str = "financials"):
        self.symbol = symbol
        self.statement = statement
        super().__init__(f"No {statement} data found for symbol '{symbol}'")


class UpstreamFetchError(StockFinancialsError):
    """Raised when the NSE upstream API/fetch fails unexpectedly."""
