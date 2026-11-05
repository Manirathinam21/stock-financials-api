"""
Shared parsing utilities, adapted from `niftyterminal/api/_utils.py`.
"""


def parse_number(value_str):
    """
    Convert a number string (as it appears in NSE/XBRL filings) to a float.

    Handles:
      - Indian-style commas: "29,26,400.00" -> 2926400.0
      - Parenthesized negatives: "(2,68,600.00)" -> -268600.0
      - Scientific notation: "1.92388E7" -> 19238800.0
      - Dashes / nulls / empty -> None
    """
    if not value_str:
        return None

    s = str(value_str).strip()
    if not s or s.lower() == "null" or s == "-":
        return None

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    s = s.replace(",", "").replace("\xa0", "").strip()
    if not s:
        return None

    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def has_valid_xbrl(filing: dict) -> bool:
    """Check if a filing dict has a usable XBRL URL (not the '-' placeholder)."""
    xbrl = filing.get("xbrl", "")
    return bool(xbrl) and not xbrl.endswith("/-") and not xbrl.endswith('/-"')
