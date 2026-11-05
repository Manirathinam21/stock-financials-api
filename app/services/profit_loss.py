"""
Quarterly / Annual Profit & Loss statement extraction.

Adapted from `niftyterminal/api/stocks.py` (`get_stock_financials` and its
XBRL / legacy-HTML parsers). Source: NSE's Corporates Financial Results API
(`corporates-financial-results`), which lists every quarterly/annual result
filing for a symbol; each filing is then downloaded as XBRL XML (recent
filings) or legacy HTML (older filings, pre-~2018) and parsed into a
structured dict.
"""

import asyncio
import random
from urllib.parse import quote

from app.core.http_session import afetch, afetch_with_backoff
from app.services.utils import parse_number, has_valid_xbrl

CORPORATES_FINANCIAL_URL = "https://www.nseindia.com/api/corporates-financial-results"


# ---------------------------------------------------------------------------
# XBRL (XML) parser — modern filings
# ---------------------------------------------------------------------------
def _parse_xbrl_xml(xml_text: str) -> dict:
    """
    Parse an XBRL XML filing into a structured P&L dict.

    Tags use the `in-bse-fin:` namespace, e.g.
      <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR">
    """
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    import warnings

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(xml_text, "html.parser")

    def _get_val(tag_names):
        if isinstance(tag_names, str):
            tag_names = [tag_names]
        for tag_name in tag_names:
            for tag in soup.find_all(tag_name.lower()):
                ctx = tag.get("contextref", "")
                if ctx in ("OneD", "OneI"):
                    val = parse_number(tag.get_text(strip=True))
                    if val is not None:
                        return val
        return None

    def _get_text(tag_name: str) -> str:
        for tag in soup.find_all(tag_name.lower()):
            ctx = tag.get("contextref", "")
            if ctx in ("OneD", "OneI"):
                return tag.get_text(strip=True)
        return ""

    general_info = {
        "symbol": _get_text("in-bse-fin:symbol"),
        "fy_start": _get_text("in-bse-fin:dateofstartoffinancialyear"),
        "fy_end": _get_text("in-bse-fin:dateofendoffinancialyear"),
        "rounding_unit": _get_text("in-bse-fin:levelofroundingusedinfinancialstatements"),
        "reporting_quarter": _get_text("in-bse-fin:reportingquarter"),
        "nature": _get_text("in-bse-fin:natureofreportstandaloneconsolidated"),
        "audited": _get_text("in-bse-fin:whetherresultsareauditedorunaudited"),
        "from_date": _get_text("in-bse-fin:dateofstartofreportingperiod"),
        "to_date": _get_text("in-bse-fin:dateofendofreportingperiod"),
        "segment_type": _get_text("in-bse-fin:iscompanyreportingmultisegmentorsinglesegment"),
    }

    financials = {
        "revenue_from_operations": _get_val([
            "in-bse-fin:revenuefromoperations",
            "in-bse-fin:interestearned",  # Banking format
        ]),
        "other_income": _get_val("in-bse-fin:otherincome"),
        "total_income": _get_val(["in-bse-fin:income", "in-bse-fin:totalincome"]),
        "cost_of_materials_consumed": _get_val("in-bse-fin:costofmaterialsconsumed"),
        "purchases_of_stock_in_trade": _get_val("in-bse-fin:purchasesofstockintrade"),
        "changes_in_inventories": _get_val(
            "in-bse-fin:changesininventoriesoffinishedgoodsworkinprogressandstockintrade"
        ),
        "employee_benefit_expense": _get_val([
            "in-bse-fin:employeebenefitexpense",
            "in-bse-fin:paymentstoandprovisionsforemployees",
            "in-bse-fin:employeescost",  # Banking format
        ]),
        "finance_costs": _get_val([
            "in-bse-fin:financecosts",
            "in-bse-fin:interestexpended",  # Banking format
        ]),
        "depreciation": _get_val("in-bse-fin:depreciationdepletionandamortisationexpense"),
        "other_expenses": _get_val([
            "in-bse-fin:otherexpenses",
            "in-bse-fin:otheroperatingexpenses",  # Banking format
            "in-bse-fin:operatingexpenses",
        ]),
        "total_expenses": _get_val([
            "in-bse-fin:expenses",
            "in-bse-fin:totalexpenditure",
            "in-bse-fin:expenditureexcludingprovisionsandcontingencies",  # Banking format
        ]),
        "profit_before_exceptional_items_and_tax": _get_val([
            "in-bse-fin:profitbeforeexceptionalitemsandtax",
            "in-bse-fin:operatingprofitlossbeforeprovisionsandcontingencies",
            "in-bse-fin:operatingprofitbeforeprovisionandcontingencies",  # Banking format
        ]),
        "exceptional_items": _get_val([
            "in-bse-fin:exceptionalitemsbeforetax",
            "in-bse-fin:exceptionalitems",  # Banking format
        ]),
        "profit_before_tax": _get_val([
            "in-bse-fin:profitbeforetax",
            "in-bse-fin:netprofitlossbeforetax",
            "in-bse-fin:profitlossfromordinaryactivitiesbeforetax",  # Banking format
        ]),
        "current_tax": _get_val("in-bse-fin:currenttax"),
        "deferred_tax": _get_val("in-bse-fin:deferredtax"),
        "tax_expense": _get_val(["in-bse-fin:taxexpense", "in-bse-fin:provisionfortaxes"]),
        "net_profit_continuing_operations": _get_val("in-bse-fin:profitlossforperiodfromcontinuingoperations"),
        "profit_discontinued_before_tax": _get_val("in-bse-fin:profitlossfromdiscontinuedoperationsbeforetax"),
        "profit_discontinued_after_tax": _get_val("in-bse-fin:profitlossfromdiscontinuedoperationsaftertax"),
        "share_of_profit_associates": _get_val([
            "in-bse-fin:shareofprofitlossofassociatesandjointventuresaccountedforusingequitymethod",
            "in-bse-fin:shareofprofitlossofassociates",  # Banking format
        ]),
        "net_profit": _get_val([
            "in-bse-fin:profitlossforperiod",
            "in-bse-fin:netprofitlossforperiod",
            "in-bse-fin:profitlossfortheperiod",  # Banking format
            "in-bse-fin:profitlossfromordinaryactivitiesaftertax",  # Banking format alt
        ]),
        "other_comprehensive_income": _get_val("in-bse-fin:othercomprehensiveincomenetoftaxes"),
        "total_comprehensive_income": _get_val("in-bse-fin:comprehensiveincomefortheperiod"),
        "profit_attributable_to_owners": _get_val([
            "in-bse-fin:profitorlossattributabletoownersofparent",
            "in-bse-fin:profitlossaftertaxesminorityinterestandshareofprofitlossofassociates",  # Banking format
        ]),
        "profit_attributable_to_nci": _get_val([
            "in-bse-fin:profitorlossattributabletononcontrollinginterests",
            "in-bse-fin:profitlossofminorityinterest",  # Banking format
        ]),
        "comprehensive_income_owners": _get_val(
            "in-bse-fin:comprehensiveincomefortheperiodattributabletoownersofparent"
        ),
        "comprehensive_income_nci": _get_val(
            "in-bse-fin:comprehensiveincomefortheperiodattributabletoownersofparentnoncontrollinginterests"
        ),
    }

    equity = {
        "paid_up_capital": _get_val("in-bse-fin:paidupvalueofequitysharecapital"),
        "face_value": _get_val("in-bse-fin:facevalueofequitysharecapital"),
    }

    eps = {
        "basic_continuing": _get_val([
            "in-bse-fin:basicearningslossperSharefromcontinuingoperations",
            "in-bse-fin:basicearningspersharebeforeextraordinaryitems",  # Banking format
        ]),
        "diluted_continuing": _get_val([
            "in-bse-fin:dilutedearningslossperSharefromcontinuingoperations",
            "in-bse-fin:dilutedearningspersharebeforeextraordinaryitems",  # Banking format
        ]),
        "basic_discontinued": _get_val("in-bse-fin:basicearningslosspersharefromdiscontinuedoperations"),
        "diluted_discontinued": _get_val("in-bse-fin:dilutedearningslosspersharefromdiscontinuedoperations"),
        "basic_total": _get_val([
            "in-bse-fin:basicearningslosspersharefromcontinuinganddiscontinuedoperations",
            "in-bse-fin:basicearningslosspershare",
            "in-bse-fin:basicearningspershare",
            "in-bse-fin:earningsperequitysharebasic",
            "in-bse-fin:basicearningspershareafterextraordinaryitems",  # Banking format
        ]),
        "diluted_total": _get_val([
            "in-bse-fin:dilutedearningslosspersharefromcontinuinganddiscontinuedoperations",
            "in-bse-fin:dilutedearningslosspershare",
            "in-bse-fin:dilutedearningspershare",
            "in-bse-fin:earningsperequitysharediluted",
            "in-bse-fin:dilutedearningspershareafterextraordinaryitems",  # Banking format
        ]),
    }

    # Catch-all EPS parsing if exact tags weren't hit (different XML variants)
    if not eps["basic_total"]:
        for tag in soup.find_all(True):
            tag_name = tag.name.lower()
            if "basic" in tag_name and ("earning" in tag_name or "eps" in tag_name):
                ctx = tag.get("contextref", "")
                if ctx in ("OneD", "OneI"):
                    val = parse_number(tag.get_text(strip=True))
                    if val is not None:
                        eps["basic_total"] = val
                        break

    if not eps["diluted_total"]:
        for tag in soup.find_all(True):
            tag_name = tag.name.lower()
            if "diluted" in tag_name and ("earning" in tag_name or "eps" in tag_name):
                ctx = tag.get("contextref", "")
                if ctx in ("OneD", "OneI"):
                    val = parse_number(tag.get_text(strip=True))
                    if val is not None:
                        eps["diluted_total"] = val
                        break

    # --- Segments ---
    segments = {}

    revenue_tags = soup.find_all("in-bse-fin:segmentrevenue")
    for tag in revenue_tags:
        ctx = tag.get("contextref", "")
        if not ctx.startswith("OneReportableSegmentRevenue"):
            continue
        desc_tags = soup.find_all("in-bse-fin:descriptionofreportablesegment")
        for d in desc_tags:
            if d.get("contextref") == ctx:
                name = d.get_text(strip=True)
                segments.setdefault(name, {})["revenue"] = parse_number(tag.get_text(strip=True))
                break

    profit_tags = soup.find_all("in-bse-fin:segmentprofitlossbeforetaxandfinancecosts")
    for tag in profit_tags:
        ctx = tag.get("contextref", "")
        if not ctx.startswith("OneReportableSegmentResults"):
            continue
        desc_tags = soup.find_all("in-bse-fin:descriptionofreportablesegment")
        for d in desc_tags:
            if d.get("contextref") == ctx:
                name = d.get_text(strip=True)
                segments.setdefault(name, {})["profit"] = parse_number(tag.get_text(strip=True))
                break

    asset_tags = soup.find_all("in-bse-fin:segmentassets")
    for tag in asset_tags:
        ctx = tag.get("contextref", "")
        if not ctx.startswith("OneReportableSegmentAssets"):
            continue
        desc_tags = soup.find_all("in-bse-fin:descriptionofreportablesegment")
        for d in desc_tags:
            if d.get("contextref") == ctx:
                name = d.get_text(strip=True)
                segments.setdefault(name, {})["assets"] = parse_number(tag.get_text(strip=True))
                break

    liability_tags = soup.find_all("in-bse-fin:segmentliabilities")
    for tag in liability_tags:
        ctx = tag.get("contextref", "")
        if "ReportableSegmentLiabilities" not in ctx:
            continue
        d_ctx = ctx.replace("I", "D") if ctx.endswith("I") else ctx
        desc_tags = soup.find_all("in-bse-fin:descriptionofreportablesegment")
        for d in desc_tags:
            if d.get("contextref") == d_ctx:
                name = d.get_text(strip=True)
                segments.setdefault(name, {})["liabilities"] = parse_number(tag.get_text(strip=True))
                break

    inter_seg = _get_val("in-bse-fin:intersegmentrevenue")
    if inter_seg is not None:
        financials["inter_segment_revenue"] = inter_seg

    return {
        "general_info": general_info,
        "financials": financials,
        "equity": equity,
        "eps": eps,
        "segments": segments,
    }


# ---------------------------------------------------------------------------
# Legacy HTML parser — pre-~2018 filings
# ---------------------------------------------------------------------------
def _parse_legacy_html(html: str) -> dict:
    """
    Parse a legacy NSE financial-results HTML page (simple two-column
    Description | Amount table, plus an optional Segment Reporting table).
    """
    from bs4 import BeautifulSoup
    import re as _re

    if html.strip().startswith("From:") or "MultipartBoundary" in html[:500]:
        match = _re.search(
            r"Content-Location:.*?\.html\r?\n\r?\n(.*?)(?:------MultipartBoundary|$)",
            html,
            _re.DOTALL,
        )
        if match:
            raw = match.group(1)
            import quopri

            html = quopri.decodestring(raw.encode("utf-8", errors="replace")).decode(
                "utf-8", errors="replace"
            )

    soup = BeautifulSoup(html, "html.parser")

    general_info = {}
    header_table = soup.find("table", class_="table")
    if header_table:
        for tr in header_table.find_all("tr"):
            cells = tr.find_all("td")
            i = 0
            while i < len(cells) - 1:
                label = cells[i].get_text(strip=True).lower()
                value = cells[i + 1].get_text(strip=True)
                if "symbol" in label and "symbol" not in general_info:
                    general_info["symbol"] = value
                elif "company" in label:
                    general_info["company_name"] = value
                elif "audited" in label:
                    general_info["audited"] = value
                elif "consolidated" in label:
                    general_info["nature"] = value
                elif "period ended" in label:
                    general_info["to_date"] = value
                elif "financial year" in label:
                    general_info["financial_year"] = value
                elif "relating to" in label:
                    general_info["reporting_quarter"] = value
                i += 2

    general_info["rounding_unit"] = "Lakhs"

    tables = soup.find_all("table", class_="table")
    financials, equity, eps, segments = {}, {}, {}, {}

    financial_key_map = {
        "net sales/income from operations": "revenue_from_operations",
        "other operating income": "other_operating_income",
        "total income from operations": "revenue_from_operations",
        "other income": "other_income",
        "total income": "total_income",
        "cost of materials consumed": "cost_of_materials_consumed",
        "purchases of stock-in-trade": "purchases_of_stock_in_trade",
        "purchases of stock in trade": "purchases_of_stock_in_trade",
        "changes in inventories": "changes_in_inventories",
        "employee benefits expense": "employee_benefit_expense",
        "employee benefit expense": "employee_benefit_expense",
        "depreciation and amortisation": "depreciation",
        "depreciation": "depreciation",
        "finance costs": "finance_costs",
        "other expenses": "other_expenses",
        "total expenses": "total_expenses",
        "profit / (loss) from before exceptional": "profit_before_exceptional_items_and_tax",
        "exceptional items": "exceptional_items",
        "profit / (loss) from ordinary activities before tax": "profit_before_tax",
        "profit before tax": "profit_before_tax",
        "tax expense": "tax_expense",
        "profit (loss) for the period from continuing operations": "net_profit_continuing_operations",
        "profit/(loss) from discontinued operations": "profit_discontinued_before_tax",
        "profit/(loss) from discontinued operations (after tax)": "profit_discontinued_after_tax",
        "net profit / (loss) for the period": "net_profit",
        "net profit/(loss) for the period": "net_profit",
        "consolidated net profit/loss": "net_profit",
        "share of profit / (loss) of associates": "share_of_profit_associates",
        "minority interest": "profit_attributable_to_nci",
        "other comprehensive income": "other_comprehensive_income",
        "total comprehensive income": "total_comprehensive_income",
    }

    eps_key_map = {
        "basic eps  for continuing operations": "basic_continuing",
        "basic eps for continuing operations": "basic_continuing",
        "diluted eps  for continuing operations": "diluted_continuing",
        "diluted eps for continuing operations": "diluted_continuing",
        "basic eps  for discontinued operations": "basic_discontinued",
        "basic eps for discontinued operations": "basic_discontinued",
        "diluted eps  for discontinued operations": "diluted_discontinued",
        "diluted eps for discontinued operations": "diluted_discontinued",
        "basic eps  for continued and discontinued": "basic_total",
        "basic eps for continued and discontinued": "basic_total",
        "diluted eps for continued and discontinued": "diluted_total",
        "diluted eps  for continued and discontinued": "diluted_total",
    }

    for table in tables:
        rows = table.find_all("tr")
        header_text = table.get_text(strip=True).lower()
        is_segment = "segment" in header_text and "revenue" in header_text

        if is_segment:
            current_section = None
            for tr in rows:
                cells = tr.find_all("td")
                text = tr.get_text(strip=True).lower()

                if "segment revenue" in text and len(cells) <= 2:
                    current_section = "revenue"
                    continue
                elif "segment results" in text and len(cells) <= 2:
                    current_section = "profit"
                    continue
                elif "segment assets" in text and len(cells) <= 2:
                    current_section = "assets"
                    continue
                elif "segment liabilit" in text and len(cells) <= 2:
                    current_section = "liabilities"
                    continue

                if len(cells) == 2 and current_section:
                    label = cells[0].get_text(strip=True)
                    value = parse_number(cells[1].get_text(strip=True))
                    low = label.lower()
                    if any(
                        skip in low
                        for skip in [
                            "total",
                            "inter segment",
                            "less:",
                            "net sales",
                            "interest",
                            "un-allocable",
                            "unallocable",
                        ]
                    ):
                        continue
                    if label and value is not None:
                        segments.setdefault(label, {})[current_section] = value
        else:
            for tr in rows:
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue

                label = cells[0].get_text(strip=True).lower()
                val_text = cells[-1].get_text(strip=True)

                if len(cells) == 1 or not val_text:
                    continue

                for pattern, key in financial_key_map.items():
                    if pattern in label:
                        val = parse_number(val_text)
                        if val is not None:
                            financials[key] = val
                        break

                for pattern, key in eps_key_map.items():
                    if pattern in label:
                        eps[key] = parse_number(val_text)
                        break

                if "paid-up equity share capital" in label or "paid up equity" in label:
                    equity["paid_up_capital"] = parse_number(val_text)
                elif "face value" in label:
                    equity["face_value"] = parse_number(val_text)

    return {
        "general_info": general_info,
        "financials": financials,
        "equity": equity,
        "eps": eps,
        "segments": segments,
    }


async def _fetch_financial_detail(filing: dict) -> dict:
    """Fetch and parse one filing: XBRL XML first, legacy HTML as fallback."""
    if has_valid_xbrl(filing):
        xml_text = await afetch_with_backoff(filing["xbrl"], timeout=15)
        if xml_text:
            return _parse_xbrl_xml(xml_text)

    html_url = filing.get("resultDetailedDataLink")
    if html_url:
        html = await afetch_with_backoff(html_url, timeout=15)
        if html:
            return _parse_legacy_html(html)

    return {}


<<<<<<< HEAD
def _filter_by_report_type(filings_raw: list, report_type: str) -> list:
    if report_type == "consolidated":
        return [f for f in filings_raw if f.get("consolidated") == "Consolidated"]
    if report_type == "standalone":
=======
def _filter_consolidated(filings_raw: list, consolidated) -> list:
    if consolidated is True:
        return [f for f in filings_raw if f.get("consolidated") == "Consolidated"]
    if consolidated is False:
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        return [f for f in filings_raw if f.get("consolidated") in ("Non-Consolidated", "Standalone")]
    return filings_raw


<<<<<<< HEAD
async def get_stock_financials(symbol: str, report_type: str = "both", period: str = "Quarterly") -> dict:
=======
async def get_stock_financials(symbol: str, consolidated: bool = None, period: str = "Quarterly") -> dict:
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    """
    Get quarterly/annual Profit & Loss results for a stock.

    Fetches filing metadata from NSE's Corporates Financial Results API,
    then downloads and parses each result (XBRL XML for recent filings,
    legacy HTML for older ones).

    Args:
        symbol: NSE stock symbol (e.g. "RELIANCE", "HINDALCO").
<<<<<<< HEAD
        report_type:
            "both"         -> both standalone and consolidated filings (default)
            "consolidated" -> only consolidated filings
            "standalone"   -> only standalone filings
=======
        consolidated:
            None  -> both standalone and consolidated filings (default)
            True  -> only consolidated filings
            False -> only standalone filings
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
        period: "Quarterly" (default), "Annual", or "Both".
    """
    if period not in ("Quarterly", "Annual", "Both"):
        period = "Quarterly"

    if period == "Both":
        url_q = f"{CORPORATES_FINANCIAL_URL}?index=equities&symbol={quote(symbol)}&period=Quarterly"
        url_a = f"{CORPORATES_FINANCIAL_URL}?index=equities&symbol={quote(symbol)}&period=Annual"
        resp_q, resp_a = await asyncio.gather(afetch(url_q, timeout=15), afetch(url_a, timeout=15))
        raw_q = resp_q if isinstance(resp_q, list) else (resp_q.get("data", []) if resp_q else [])
        raw_a = resp_a if isinstance(resp_a, list) else (resp_a.get("data", []) if resp_a else [])
        seen = set()
        filings_raw = []
        for f in raw_q + raw_a:
            seq = f.get("seqNumber")
            if seq not in seen:
                seen.add(seq)
                filings_raw.append(f)
    else:
        url = f"{CORPORATES_FINANCIAL_URL}?index=equities&symbol={quote(symbol)}&period={period}"
        response = await afetch(url, timeout=15)
        if not response:
            return {}
        filings_raw = response if isinstance(response, list) else response.get("data", [])

    if not filings_raw:
        return {}

<<<<<<< HEAD
    filings_raw = _filter_by_report_type(filings_raw, report_type)
=======
    filings_raw = _filter_consolidated(filings_raw, consolidated)
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
    if not filings_raw:
        return {}

    company_name = filings_raw[0].get("companyName", "")

    sem = asyncio.Semaphore(2)

    async def _process_filing(filing: dict) -> dict:
        async with sem:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            financial_data = await _fetch_financial_detail(filing)

        return {
            "seq_number": filing.get("seqNumber"),
            "from_date": filing.get("fromDate", ""),
            "to_date": filing.get("toDate", ""),
            "nature": filing.get("consolidated", ""),
            "audited": filing.get("audited", ""),
            "period": filing.get("period", ""),
            "relating_to": filing.get("relatingTo", ""),
            "financial_year": filing.get("financialYear", ""),
            "format": filing.get("format", ""),
            "ind_as": filing.get("indAs", ""),
            "filing_date": filing.get("filingDate", ""),
            "xbrl_url": filing.get("xbrl", ""),
            "html_url": filing.get("resultDetailedDataLink", ""),
            "financial_data": financial_data,
        }

    tasks = [_process_filing(f) for f in filings_raw]
    filings = await asyncio.gather(*tasks)

    return {
        "symbol": symbol,
        "company_name": company_name,
        "total_filings": len(filings),
        "filings": list(filings),
    }
