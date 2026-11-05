"""
Annual Balance Sheet, Cash Flow Statement, and full Annual Report extraction.

Uses NSE's Integrated
Filing API (iXBRL), which provides complete financial statements for listed
companies. Annual (audited) filings contain Balance Sheet and Cash Flow;
quarterly filings contain only P&L (use `app.services.profit_loss` for a
more complete quarterly P&L source).

Namespace: ``in-capmkt:`` (SEBI capital markets taxonomy).
"""

import asyncio
import random
from urllib.parse import quote

from app.core.http_session import afetch_with_backoff
from app.services.utils import parse_number

_QUOTE_API = "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
async def _fetch_integrated_filing_list(symbol: str) -> list:
    """
    Fetch the list of Integrated Filing metadata for *symbol*.

    Uses a direct client with a quotes-page Referer, since the shared
    session's option-chain Referer doesn't work for this endpoint.
    """
    import httpx as _httpx

    url = f"{_QUOTE_API}?functionName=getIntegratedFilingData&symbol={quote(symbol)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={quote(symbol)}",
    }
    warmup_headers = {
        "User-Agent": headers["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }

    try:
        async with _httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com", headers=warmup_headers, timeout=15)
            await asyncio.sleep(random.uniform(0.3, 0.6))

            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("data", [])
    except Exception:
        pass
    return []


def _detect_filing_type(filename: str) -> str:
    """Return 'BANKING' or 'INDAS' based on the XML filename."""
    fn = (filename or "").upper()
    return "BANKING" if "BANKING" in fn else "INDAS"


def _make_soup(xml_text: str):
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    import warnings

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    return BeautifulSoup(xml_text, "html.parser")


def _get_val(soup, tag_names, ctx_ids=("OneD", "OneI", "FourD")):
    """Get a float value from one or more tag names across allowed contexts."""
    if isinstance(tag_names, str):
        tag_names = [tag_names]
    for tag_name in tag_names:
        for tag in soup.find_all(tag_name.lower()):
            ctx = tag.get("contextref", "")
            if ctx in ctx_ids:
                val = parse_number(tag.get_text(strip=True))
                if val is not None:
                    return val
    return None


def _get_text(soup, tag_name, ctx_ids=("OneD", "OneI")):
    for tag in soup.find_all(tag_name.lower()):
        ctx = tag.get("contextref", "")
        if ctx in ctx_ids:
            return tag.get_text(strip=True)
    return ""


# ---------------------------------------------------------------------------
# General Info parser (shared across all statement types)
# ---------------------------------------------------------------------------
def _parse_general_info(soup) -> dict:
    return {
        "symbol": _get_text(soup, "in-capmkt:symbol"),
        "company_name": _get_text(soup, "in-capmkt:nameofthecompany") or _get_text(soup, "in-capmkt:nameofbank"),
        "fy_start": _get_text(soup, "in-capmkt:dateofstartoffinancialyear"),
        "fy_end": _get_text(soup, "in-capmkt:dateofendoffinancialyear"),
        "from_date": _get_text(soup, "in-capmkt:dateofstartofreportingperiod"),
        "to_date": _get_text(soup, "in-capmkt:dateofendofreportingperiod"),
        "reporting_quarter": _get_text(soup, "in-capmkt:reportingquarter"),
        "reporting_period_type": _get_text(soup, "in-capmkt:typeofreportingperiod"),
        "nature": _get_text(soup, "in-capmkt:natureofreportstandaloneconsolidated"),
        "audited": _get_text(soup, "in-capmkt:whetherresultsareauditedorunaudited"),
        "rounding": _get_text(soup, "in-capmkt:levelofrounding"),
        "currency": _get_text(soup, "in-capmkt:descriptionofpresentationcurrency"),
    }


# ---------------------------------------------------------------------------
# P&L parser (Integrated Filing — only used as fallback metadata here;
# app.services.profit_loss is the primary P&L source)
# ---------------------------------------------------------------------------
def _parse_pnl(soup, filing_type: str) -> dict:
    dur = ("FourD", "OneD")

    def v(tags):
        return _get_val(soup, tags, ctx_ids=dur)

    if filing_type == "BANKING":
        return {
            "interest_earned": v("in-capmkt:interestearned"),
            "revenue_on_investments": v("in-capmkt:revenueoninvestments"),
            "other_income": v("in-capmkt:otherincome"),
            "total_income": v("in-capmkt:income"),
            "interest_expended": v("in-capmkt:interestexpended"),
            "employees_cost": v("in-capmkt:employeescost"),
            "operating_expenses": v("in-capmkt:operatingexpenses"),
            "other_operating_expenses": v("in-capmkt:otheroperatingexpenses"),
            "total_expenditure": v("in-capmkt:expenditureexcludingprovisionsandcontingencies"),
            "operating_profit": v("in-capmkt:operatingprofitbeforeprovisionandcontingencies"),
            "provisions_and_contingencies": v("in-capmkt:provisionsotherthantaxandcontingencies"),
            "exceptional_items": v("in-capmkt:exceptionalitems"),
            "profit_before_tax": v("in-capmkt:profitlossfromordinaryactivitiesbeforetax"),
            "tax_expense": v("in-capmkt:taxexpense"),
            "net_profit": v([
                "in-capmkt:profitlossfortheperiod",
                "in-capmkt:profitlossfromordinaryactivitiesaftertax",
            ]),
            "profit_attributable_to_owners": v(
                "in-capmkt:profitlossaftertaxesminorityinterestandshareofprofitlossofassociates"
            ),
            "eps_basic": v([
                "in-capmkt:basicearningspershareafterextraordinaryitems",
                "in-capmkt:basicearningspersharebeforeextraordinaryitems",
            ]),
            "eps_diluted": v([
                "in-capmkt:dilutedearningspershareafterextraordinaryitems",
                "in-capmkt:dilutedearningspersharebeforeextraordinaryitems",
            ]),
            "gross_npa": v("in-capmkt:grossnonperformingassets"),
            "net_npa": v("in-capmkt:nonperformingassets"),
            "gross_npa_pct": v("in-capmkt:percentageofgrossnpa"),
            "net_npa_pct": v("in-capmkt:percentageofnpa"),
            "cet1_ratio": v("in-capmkt:cet1ratio"),
            "additional_tier1_ratio": v("in-capmkt:additionaltier1ratio"),
            "return_on_assets": v("in-capmkt:returnonassets"),
        }
    else:
        return {
            "revenue_from_operations": v("in-capmkt:revenuefromoperations"),
            "other_income": v("in-capmkt:otherincome"),
            "total_income": v("in-capmkt:income"),
            "cost_of_materials_consumed": v("in-capmkt:costofmaterialsconsumed"),
            "purchases_of_stock_in_trade": v("in-capmkt:purchasesofstockintrade"),
            "changes_in_inventories": v(
                "in-capmkt:changesininventoriesoffinishedgoodsworkinprogressandstockintrade"
            ),
            "employee_benefit_expense": v("in-capmkt:employeebenefitexpense"),
            "finance_costs": v("in-capmkt:financecosts"),
            "depreciation": v("in-capmkt:depreciationdepletionandamortisationexpense"),
            "other_expenses": v("in-capmkt:otherexpenses"),
            "total_expenses": v("in-capmkt:expenses"),
            "profit_before_exceptional_items_and_tax": v("in-capmkt:profitbeforeexceptionalitemsandtax"),
            "exceptional_items": v("in-capmkt:exceptionalitemsbeforetax"),
            "profit_before_tax": v("in-capmkt:profitbeforetax"),
            "current_tax": v("in-capmkt:currenttax"),
            "deferred_tax": v("in-capmkt:deferredtax"),
            "tax_expense": v("in-capmkt:taxexpense"),
            "net_profit_continuing": v("in-capmkt:profitlossforperiodfromcontinuingoperations"),
            "profit_discontinued_before_tax": v("in-capmkt:profitlossfromdiscontinuedoperationsbeforetax"),
            "profit_discontinued_after_tax": v("in-capmkt:profitlossfromdiscontinuedoperationsaftertax"),
            "share_of_profit_associates": v(
                "in-capmkt:shareofprofitlossofassociatesandjointventuresaccountedforusingequitymethod"
            ),
            "net_profit": v("in-capmkt:profitlossforperiod"),
            "other_comprehensive_income": v("in-capmkt:othercomprehensiveincomenetoftaxes"),
            "total_comprehensive_income": v("in-capmkt:comprehensiveincomefortheperiod"),
            "profit_attributable_to_owners": v("in-capmkt:profitorlossattributabletoownersofparent"),
            "profit_attributable_to_nci": v("in-capmkt:profitorlossattributabletononcontrollinginterests"),
            "comprehensive_income_owners": v(
                "in-capmkt:comprehensiveincomefortheperiodattributabletoownersofparent"
            ),
            "comprehensive_income_nci": v(
                "in-capmkt:comprehensiveincomefortheperiodattributabletoownersofparentnoncontrollinginterests"
            ),
            "paid_up_capital": _get_val(soup, "in-capmkt:paidupvalueofequitysharecapital", ctx_ids=("FourD", "OneD")),
            "face_value": _get_val(soup, "in-capmkt:facevalueofequitysharecapital", ctx_ids=("FourD", "OneD")),
            "eps_basic": v("in-capmkt:basicearningslosspersharefromcontinuinganddiscontinuedoperations"),
            "eps_diluted": v("in-capmkt:dilutedearningslosspersharefromcontinuinganddiscontinuedoperations"),
            "debt_equity_ratio": v("in-capmkt:debtequityratio"),
        }


# ---------------------------------------------------------------------------
# Balance Sheet parser
# ---------------------------------------------------------------------------
def _parse_balance_sheet(soup, filing_type: str) -> dict:
    """
    Parse Balance Sheet from an annual Integrated Filing.

    Only available in annual (audited) filings. Returns {} for quarterly
    filings that lack balance sheet data.
    """
    inst = ("OneI",)
    prev = ("PY_I",)

    def v(tags, ctx=inst):
        return _get_val(soup, tags, ctx_ids=ctx)

    if v("in-capmkt:assets") is None:
        return {}

    if filing_type == "BANKING":
        return {
            "total_assets": v("in-capmkt:assets"),
            "total_equity_and_liabilities": v("in-capmkt:equityandliabilities"),
            "equity": v("in-capmkt:equity"),
            "equity_share_capital": v("in-capmkt:equitysharecapital"),
            "equity_attributable_to_owners": v("in-capmkt:equityattributabletoownersofparent"),
            "liabilities": v("in-capmkt:liabilities"),
            "segment_assets": v("in-capmkt:netsegmentassets"),
            "segment_liabilities": v("in-capmkt:netsegmentliabilities"),
            "prev_total_assets": v("in-capmkt:assets", ctx=prev),
            "prev_equity": v("in-capmkt:equity", ctx=prev),
        }

    return {
        "non_current_assets": {
            "property_plant_equipment": v("in-capmkt:propertyplantandequipment"),
            "capital_work_in_progress": v("in-capmkt:capitalworkinprogress"),
            "investment_property": v("in-capmkt:investmentproperty"),
            "goodwill": v("in-capmkt:goodwill"),
            "other_intangible_assets": v("in-capmkt:otherintangibleassets"),
            "intangible_assets_under_development": v("in-capmkt:intangibleassetsunderdevelopment"),
            "biological_assets": v("in-capmkt:biologicalassetsotherthanbearerplants"),
            "investments_equity_method": v("in-capmkt:investmentsaccountedforusingequitymethod"),
            "investments": v("in-capmkt:noncurrentinvestments"),
            "trade_receivables": v("in-capmkt:tradereceivablesnoncurrent"),
            "loans": v("in-capmkt:loansnoncurrent"),
            "other_financial_assets": v("in-capmkt:othernoncurrentfinancialassets"),
            "total_financial_assets": v("in-capmkt:noncurrentfinancialassets"),
            "deferred_tax_assets": v("in-capmkt:deferredtaxassetsnet"),
            "other_non_current_assets": v("in-capmkt:othernoncurrentassets"),
            "total": v("in-capmkt:noncurrentassets"),
        },
        "current_assets": {
            "inventories": v("in-capmkt:inventories"),
            "investments": v("in-capmkt:currentinvestments"),
            "trade_receivables": v("in-capmkt:tradereceivablescurrent"),
            "cash_and_cash_equivalents": v("in-capmkt:cashandcashequivalents"),
            "bank_balances_other": v("in-capmkt:bankbalanceotherthancashandcashequivalents"),
            "loans": v("in-capmkt:loanscurrent"),
            "other_financial_assets": v("in-capmkt:othercurrentfinancialassets"),
            "total_financial_assets": v("in-capmkt:currentfinancialassets"),
            "current_tax_assets": v("in-capmkt:currenttaxassets"),
            "other_current_assets": v("in-capmkt:othercurrentassets"),
            "total": v("in-capmkt:currentassets"),
        },
        "assets_held_for_sale": v("in-capmkt:noncurrentassetsclassifiedasheldforsale"),
        "total_assets": v("in-capmkt:assets"),
        "equity": {
            "share_capital": v("in-capmkt:equitysharecapital"),
            "other_equity": v("in-capmkt:otherequity"),
            "equity_attributable_to_owners": v("in-capmkt:equityattributabletoownersofparent"),
            "total": v("in-capmkt:equity"),
        },
        "non_current_liabilities": {
            "borrowings": v("in-capmkt:borrowingsnoncurrent"),
            "trade_payables": v("in-capmkt:tradepayablesnoncurrent"),
            "other_financial_liabilities": v("in-capmkt:othernoncurrentfinancialliabilities"),
            "total_financial_liabilities": v("in-capmkt:noncurrentfinancialliabilities"),
            "provisions": v("in-capmkt:provisionsnoncurrent"),
            "deferred_tax_liabilities": v("in-capmkt:deferredtaxliabilitiesnet"),
            "deferred_government_grants": v("in-capmkt:deferredgovernmentgrantsnoncurrent"),
            "other_non_current_liabilities": v("in-capmkt:othernoncurrentliabilities"),
            "total": v("in-capmkt:noncurrentliabilities"),
        },
        "current_liabilities": {
            "borrowings": v("in-capmkt:borrowingscurrent"),
            "trade_payables": v("in-capmkt:tradepayablescurrent"),
            "trade_payables_msme": v("in-capmkt:totaloutstandingduesofmicroenterpriseandsmallenterprisecurrent"),
            "trade_payables_others": v(
                "in-capmkt:totaloutstandingduesofcreditorsotherthanmicroenterpriseandsmallenterprisecurrent"
            ),
            "other_financial_liabilities": v("in-capmkt:othercurrentfinancialliabilities"),
            "total_financial_liabilities": v("in-capmkt:currentfinancialliabilities"),
            "other_current_liabilities": v("in-capmkt:othercurrentliabilities"),
            "provisions": v("in-capmkt:provisionscurrent"),
            "current_tax_liabilities": v("in-capmkt:currenttaxliabilities"),
            "deferred_government_grants": v("in-capmkt:deferredgovernmentgrantscurrent"),
            "total": v("in-capmkt:currentliabilities"),
        },
        "liabilities_held_for_sale": v(
            "in-capmkt:liabilitiesdirectlyassociatedwithassetsindisposalgroupclassifiedasheldforsale"
        ),
        "total_liabilities": v("in-capmkt:liabilities"),
        "total_equity_and_liabilities": v("in-capmkt:equityandliabilities"),
        "previous_year": {
            "total_assets": v("in-capmkt:assets", ctx=prev),
            "total_equity": v("in-capmkt:equity", ctx=prev),
            "total_liabilities": v("in-capmkt:liabilities", ctx=prev),
            "cash_and_cash_equivalents": v("in-capmkt:cashandcashequivalents", ctx=prev),
        },
    }


# ---------------------------------------------------------------------------
# Cash Flow parser
# ---------------------------------------------------------------------------
def _parse_cash_flow(soup, filing_type: str) -> dict:
    """
    Parse Cash Flow Statement from an annual Integrated Filing.

    Only available in annual (audited) filings. Returns {} for quarterly
    filings that lack cash flow data.
    """
    dur = ("FourD",)
    inst = ("OneI",)
    prev_inst = ("PY_I",)

    def v(tags, ctx=dur):
        return _get_val(soup, tags, ctx_ids=ctx)

    has_cf = v("in-capmkt:cashflowsfromusedinoperatingactivities") is not None
    if not has_cf:
        return {}

    return {
        "type": _get_text(soup, "in-capmkt:typeofcashflowstatement"),
        "operating": {
            "profit_before_tax": v("in-capmkt:profitbeforetax"),
            "adj_depreciation": v("in-capmkt:adjustmentsfordepreciationandamortisationexpense"),
            "adj_finance_costs": v("in-capmkt:adjustmentsforfinancecosts"),
            "adj_interest_income": v("in-capmkt:adjustmentsforinterestincome"),
            "adj_dividend_income": v("in-capmkt:adjustmentsfordividendincome"),
            "adj_impairment": v(
                "in-capmkt:adjustmentsforimpairmentlossreversalofimpairmentlossrecognisedinprofitorloss"
            ),
            "adj_unrealised_forex": v("in-capmkt:adjustmentsforunrealisedforeignexchangelossesgains"),
            "adj_fair_value": v("in-capmkt:adjustmentsforfairvaluegainslosses"),
            "adj_share_based_payments": v("in-capmkt:adjustmentsforsharebasedpayments"),
            "adj_inventories": v("in-capmkt:adjustmentsfordecreaseincreaseininventories"),
            "adj_trade_receivables_current": v("in-capmkt:adjustmentsfordecreaseincreaseintradereceivablescurrent"),
            "adj_trade_receivables_noncurrent": v(
                "in-capmkt:adjustmentsfordecreaseincreaseintradereceivablesnoncurrent"
            ),
            "adj_other_current_assets": v("in-capmkt:adjustmentsfordecreaseincreaseinothercurrentassets"),
            "adj_other_noncurrent_assets": v("in-capmkt:adjustmentsfordecreaseincreaseinothernoncurrentassets"),
            "adj_trade_payables_current": v("in-capmkt:adjustmentsforincreasedecreaseintradepayablescurrent"),
            "adj_trade_payables_noncurrent": v(
                "in-capmkt:adjustmentsforincreasedecreaseintradepayablesnoncurrent"
            ),
            "adj_other_current_liabilities": v("in-capmkt:adjustmentsforincreasedecreaseinothercurrentliabilities"),
            "adj_other_noncurrent_liabilities": v(
                "in-capmkt:adjustmentsforincreasedecreaseinothernoncurrentliabilities"
            ),
            "adj_other_financial_assets_current": v("in-capmkt:adjustmentsforotherfinancialassetscurrent"),
            "adj_other_financial_assets_noncurrent": v("in-capmkt:adjustmentsforotherfinancialassetsnoncurrent"),
            "adj_other_financial_liabilities_current": v("in-capmkt:adjustmentsforotherfinancialliabilitiescurrent"),
            "adj_other_financial_liabilities_noncurrent": v(
                "in-capmkt:adjustmentsforotherfinancialliabilitiesnoncurrent"
            ),
            "adj_provisions_current": v("in-capmkt:adjustmentsforprovisionscurrent"),
            "adj_provisions_noncurrent": v("in-capmkt:adjustmentsforprovisionsnoncurrent"),
            "adj_other_noncash": v("in-capmkt:otheradjustmentsfornoncashitems"),
            "adj_other_investing_financing": v(
                "in-capmkt:otheradjustmentsforwhichcasheffectsareinvestingorfinancingcashflow"
            ),
            "total_adjustments": v("in-capmkt:adjustmentsforreconcileprofitloss"),
            "cash_from_operations": v("in-capmkt:cashflowsfromusedinoperations"),
            "dividends_received": v("in-capmkt:dividendsreceivedclassifiedasoperatingactivities"),
            "interest_paid": v("in-capmkt:interestpaidclassifiedasoperatingactivities"),
            "interest_received": v("in-capmkt:interestreceivedclassifiedasoperatingactivities"),
            "income_tax_paid": v("in-capmkt:incometaxespaidrefundclassifiedasoperatingactivities"),
            "other": v("in-capmkt:otherinflowsoutflowsofcashclassifiedasoperatingactivities"),
            "net_cash": v("in-capmkt:cashflowsfromusedinoperatingactivities"),
        },
        "investing": {
            "purchase_ppe": v("in-capmkt:purchaseofpropertyplantandequipmentclassifiedasinvestingactivities"),
            "sale_ppe": v("in-capmkt:proceedsfromsalesofpropertyplantandequipmentclassifiedasinvestingactivities"),
            "purchase_intangibles": v("in-capmkt:purchaseofintangibleassetsclassifiedasinvestingactivities"),
            "sale_intangibles": v("in-capmkt:proceedsfromsalesofintangibleassetsclassifiedasinvestingactivities"),
            "purchase_intangibles_under_dev": v("in-capmkt:purchaseofintangibleassetsunderdevelopment"),
            "purchase_investment_property": v(
                "in-capmkt:purchaseofinvestmentpropertyclassifiedasinvestingactivities"
            ),
            "sale_investment_property": v(
                "in-capmkt:proceedsfromsalesofinvestmentpropertyclassifiedasinvestingactivities"
            ),
            "purchase_other_long_term_assets": v(
                "in-capmkt:purchaseofotherlongtermassetsclassifiedasinvestingactivities"
            ),
            "sale_other_long_term_assets": v(
                "in-capmkt:proceedsfromsalesofotherlongtermassetsclassifiedasinvestingactivities"
            ),
            "purchase_equity_instruments": v(
                "in-capmkt:othercashpaymentstoacquireequityordebtinstrumentsofotherentitiesclassifiedasinvestingactivities"
            ),
            "sale_equity_instruments": v(
                "in-capmkt:othercashreceiptsfromsalesofequityordebtinstrumentsofotherentitiesclassifiedasinvestingactivities"
            ),
            "purchase_joint_ventures": v(
                "in-capmkt:othercashpaymentstoacquireinterestsinjointventuresclassifiedasinvestingactivities"
            ),
            "sale_joint_ventures": v(
                "in-capmkt:othercashreceiptsfromsalesofinterestsinjointventuresclassifiedasinvestingactivities"
            ),
            "obtaining_subsidiaries": v(
                "in-capmkt:cashflowsusedinobtainingcontrolofsubsidiariesorotherbusinessesclassifiedasinvestingactivities"
            ),
            "losing_subsidiaries": v(
                "in-capmkt:cashflowsfromlosingcontrolofsubsidiariesorotherbusinessesclassifiedasinvestingactivities"
            ),
            "loans_made": v("in-capmkt:cashadvancesandloansmadetootherpartiesclassifiedasinvestingactivities"),
            "loans_repaid": v(
                "in-capmkt:cashreceiptsfromrepaymentofadvancesandloansmadetootherpartiesclassifiedasinvestingactivities"
            ),
            "dividends_received": v("in-capmkt:dividendsreceivedclassifiedasinvestingactivities"),
            "interest_received": v("in-capmkt:interestreceivedclassifiedasinvestingactivities"),
            "income_tax": v("in-capmkt:incometaxespaidrefundclassifiedasinvestingactivities"),
            "other": v("in-capmkt:otherinflowsoutflowsofcashclassifiedasinvestingactivities"),
            "net_cash": v("in-capmkt:cashflowsfromusedininvestingactivities"),
        },
        "financing": {
            "proceeds_from_shares": v("in-capmkt:proceedsfromissuingsharesclassifiedasfinancingactivities"),
            "proceeds_from_borrowings": v("in-capmkt:proceedsfromborrowingsclassifiedasfinancingactivities"),
            "repayment_of_borrowings": v("in-capmkt:repaymentsofborrowingsclassifiedasfinancingactivities"),
            "proceeds_from_debentures": v("in-capmkt:proceedsfromissuingdebenturesnotesbondsetc"),
            "proceeds_from_stock_options": v("in-capmkt:proceedsfromexerciseofstockoptions"),
            "proceeds_from_other_equity": v("in-capmkt:proceedsfromissuingotherequityinstruments"),
            "payments_of_other_equity": v("in-capmkt:paymentsofotherequityinstruments"),
            "buyback_of_shares": v("in-capmkt:paymentstoacquireorredeementitysshares"),
            "lease_payments": v("in-capmkt:paymentsofleaseliabilitiesclassifiedasfinancingactivities"),
            "dividends_paid": v("in-capmkt:dividendspaidclassifiedasfinancingactivities"),
            "interest_paid": v("in-capmkt:interestpaidclassifiedasfinancingactivities"),
            "income_tax": v("in-capmkt:incometaxespaidrefundclassifiedasfinancingactivities"),
            "subsidiary_ownership_changes_proceeds": v(
                "in-capmkt:proceedsfromchangesinownershipinterestsinsubsidiaries"
            ),
            "subsidiary_ownership_changes_payments": v(
                "in-capmkt:paymentsfromchangesinownershipinterestsinsubsidiaries"
            ),
            "other": v("in-capmkt:otherinflowsoutflowsofcashclassifiedasfinancingactivities"),
            "net_cash": v("in-capmkt:cashflowsfromusedinfinancingactivities"),
        },
        "net_increase_decrease_before_forex": v(
            "in-capmkt:increasedecreaseincashandcashequivalentsbeforeeffectofexchangeratechanges"
        ),
        "forex_effect": v("in-capmkt:effectofexchangeratechangesoncashandcashequivalents"),
        "net_increase_decrease": v("in-capmkt:increasedecreaseincashandcashequivalents"),
        "cash_at_beginning": v("in-capmkt:cashandcashequivalentscashflowstatement", ctx=prev_inst),
        "cash_at_end": v("in-capmkt:cashandcashequivalentscashflowstatement", ctx=inst),
    }


# ---------------------------------------------------------------------------
# Segment parser
# ---------------------------------------------------------------------------
def _parse_segments(soup) -> dict:
    segments = {}

    def _collect(tag_name: str, field: str):
        for tag in soup.find_all(tag_name):
            ctx = tag.get("contextref", "")
            desc_tags = soup.find_all("in-capmkt:descriptionofreportablesegment")
            for d in desc_tags:
                if d.get("contextref") == ctx:
                    name = d.get_text(strip=True)
                    segments.setdefault(name, {})[field] = parse_number(tag.get_text(strip=True))
                    break

    _collect("in-capmkt:segmentrevenue", "revenue")
    _collect("in-capmkt:segmentprofitlossbeforetaxandfinancecosts", "profit")
    _collect("in-capmkt:segmentassets", "assets")
    _collect("in-capmkt:segmentliabilities", "liabilities")

    return segments


# ---------------------------------------------------------------------------
# Full filing parser
# ---------------------------------------------------------------------------
def _parse_integrated_filing(xml_text: str, filename: str = "") -> dict:
    soup = _make_soup(xml_text)
    filing_type = _detect_filing_type(filename)

    return {
        "general_info": _parse_general_info(soup),
        "filing_type": filing_type,
        "profit_and_loss": _parse_pnl(soup, filing_type),
        "balance_sheet": _parse_balance_sheet(soup, filing_type),
        "cash_flow": _parse_cash_flow(soup, filing_type),
        "segments": _parse_segments(soup),
    }


async def _process_filing(filing: dict, sem: asyncio.Semaphore) -> dict:
    """Fetch and parse a single Integrated Filing."""
    xbrl_url = filing.get("gfrXbrlFname", "")
    if not xbrl_url:
        return {}

    async with sem:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        xml_text = await afetch_with_backoff(xbrl_url, timeout=30)

    if not xml_text:
        return {}

    financial_data = _parse_integrated_filing(xml_text, filename=xbrl_url)

    return {
        "quarter_ended": filing.get("gfrQuaterEnded", ""),
        "nature": filing.get("gfrConsolidated", ""),
        "audited": filing.get("gfrAuditedUnaudited", ""),
        "filing_date": filing.get("gfSystym", ""),
        "xbrl_url": xbrl_url,
        "xbrl_file_size": filing.get("gfrXbrlFileSize"),
        "summary": {
            "total_income": parse_number(filing.get("gfrTotalIncome")),
            "profit_before_tax": parse_number(filing.get("gfrProBefTax")),
            "net_profit": parse_number(filing.get("gfrNetProLoss")),
            "eps": parse_number(filing.get("gfrErnPerShare")),
        },
        "financial_data": financial_data,
    }


def _filter_by_report_type(filings: list, report_type: str) -> list:
    if report_type == "consolidated":
        return [f for f in filings if f.get("gfrConsolidated") == "Consolidated"]
    if report_type == "standalone":
        return [f for f in filings if f.get("gfrConsolidated") == "Standalone"]
    return filings


async def _fetch_and_process_filings(symbol: str, report_type: str = "both") -> list:
    filings_raw = await _fetch_integrated_filing_list(symbol)
    if not filings_raw:
        return []

    filings_raw = _filter_by_report_type(filings_raw, report_type)
    if not filings_raw:
        return []

    sem = asyncio.Semaphore(2)
    tasks = [_process_filing(f, sem) for f in filings_raw]
    all_filings = await asyncio.gather(*tasks)
    return [f for f in all_filings if f]


async def get_stock_balance_sheet(symbol: str, report_type: str = "both") -> dict:
    """
    Get annual Balance Sheet data for a stock (only available in annual
    audited filings).

    report_type: "both" (default), "consolidated" only, or "standalone" only.
    """
    all_filings = await _fetch_and_process_filings(symbol, report_type)
    if not all_filings:
        return {}

    bs_filings = []
    for f in all_filings:
        bs = f.get("financial_data", {}).get("balance_sheet", {})
        if bs:
            bs_filings.append({
                "quarter_ended": f["quarter_ended"],
                "nature": f["nature"],
                "audited": f["audited"],
                "filing_date": f["filing_date"],
                "general_info": f["financial_data"]["general_info"],
                "balance_sheet": bs,
            })

    return {"symbol": symbol, "total_filings": len(bs_filings), "filings": bs_filings}


async def get_stock_cash_flow(symbol: str, report_type: str = "both") -> dict:
    """
    Get annual Cash Flow Statement for a stock (only available in annual
    audited filings).

    report_type: "both" (default), "consolidated" only, or "standalone" only.
    """
    all_filings = await _fetch_and_process_filings(symbol, report_type)
    if not all_filings:
        return {}

    cf_filings = []
    for f in all_filings:
        cf = f.get("financial_data", {}).get("cash_flow", {})
        if cf:
            cf_filings.append({
                "quarter_ended": f["quarter_ended"],
                "nature": f["nature"],
                "audited": f["audited"],
                "filing_date": f["filing_date"],
                "general_info": f["financial_data"]["general_info"],
                "cash_flow": cf,
            })

    return {"symbol": symbol, "total_filings": len(cf_filings), "filings": cf_filings}


async def get_stock_annual_report(symbol: str, report_type: str = "both") -> dict:
    """
    Get the comprehensive annual filing set (P&L, Balance Sheet, Cash Flow,
    Segments) from NSE's Integrated Filing API. For quarterly filings in
    this feed, only P&L and segments are populated.

    report_type: "both" (default), "consolidated" only, or "standalone" only.
    """
    results = await _fetch_and_process_filings(symbol, report_type)
    return {"symbol": symbol, "total_filings": len(results), "filings": results}
