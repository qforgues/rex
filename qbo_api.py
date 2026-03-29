"""
qbo_api.py — QuickBooks Online data fetching for Portal42.
Pulls purchases, bills, and income for a date range.
"""
from __future__ import annotations

from typing import List, Dict

import httpx

import os as _os
_SANDBOX = _os.environ.get("QBO_SANDBOX", "true").lower() != "false"
_BASE = (
    "https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}"
    if _SANDBOX else
    "https://quickbooks.api.intuit.com/v3/company/{realm_id}"
)

# QBO account type / expense account name → Rex tax category
_CATEGORY_MAP = {
    "advertising":                          "Marketing & Advertising",
    "advertising and marketing":            "Marketing & Advertising",
    "marketing":                            "Marketing & Advertising",
    "auto":                                 "Vehicle & Mileage",
    "automobile":                           "Vehicle & Mileage",
    "car and truck":                        "Vehicle & Mileage",
    "vehicle":                              "Vehicle & Mileage",
    "meals and entertainment":              "Business Meals (50%)",
    "meals & entertainment":               "Business Meals (50%)",
    "entertainment":                        "Business Meals (50%)",
    "office supplies":                      "Office Supplies",
    "office expenses":                      "Office Supplies",
    "telephone":                            "Internet & Phone (Business %)",
    "telephone & internet":                 "Internet & Phone (Business %)",
    "internet":                             "Internet & Phone (Business %)",
    "utilities":                            "Utilities (Business %)",
    "rent":                                 "Rent & Lease (Business)",
    "rent or lease":                        "Rent & Lease (Business)",
    "insurance":                            "Insurance (Business)",
    "legal & professional fees":            "Legal & Accounting",
    "legal and professional fees":          "Legal & Accounting",
    "accounting":                           "Legal & Accounting",
    "professional fees":                    "Professional Services",
    "contractors":                          "Payroll & Contractors",
    "contract labor":                       "Payroll & Contractors",
    "payroll expenses":                     "Payroll & Contractors",
    "travel":                               "Business Travel",
    "computer and internet":               "Technology & Software",
    "software":                             "Technology & Software",
    "technology":                           "Technology & Software",
    "subscriptions":                        "Subscriptions (Business)",
    "equipment":                            "Equipment (Section 179)",
    "depreciation":                         "Equipment (Section 179)",
    "education":                            "Education & Training",
    "training":                             "Education & Training",
    "bank charges":                         "Bank Fees & Interest",
    "bank service charges":                 "Bank Fees & Interest",
    "interest expense":                     "Bank Fees & Interest",
    "home office":                          "Home Office",
    "repairs and maintenance":              "Office Supplies",
}


def _map_category(name: str) -> str:
    key = (name or "").lower().strip()
    return _CATEGORY_MAP.get(key, "Uncategorized")


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept":        "application/json",
    }


def _query(access_token: str, realm_id: str, sql: str) -> list:
    url = _BASE.format(realm_id=realm_id) + "/query"
    items = []
    start = 1
    page_size = 100
    with httpx.Client(headers=_headers(access_token), timeout=20) as client:
        while True:
            resp = client.get(url, params={
                "query":        f"{sql} STARTPOSITION {start} MAXRESULTS {page_size}",
                "minorversion": "65",
            })
            resp.raise_for_status()
            data = resp.json().get("QueryResponse", {})
            # Find the entity key (varies by entity type)
            entity_key = next((k for k in data if k not in ("startPosition", "maxResults", "totalCount")), None)
            if not entity_key:
                break
            batch = data.get(entity_key, [])
            items.extend(batch)
            if len(batch) < page_size:
                break
            start += page_size
    return items


def get_purchases(access_token: str, realm_id: str,
                   date_from: str, date_to: str) -> List[Dict]:
    """Fetch expense/purchase transactions from QBO."""
    sql = (
        f"SELECT * FROM Purchase "
        f"WHERE TxnDate >= '{date_from}' AND TxnDate <= '{date_to}'"
    )
    raw = _query(access_token, realm_id, sql)
    results = []
    for p in raw:
        amount = float(p.get("TotalAmt", 0) or 0)
        if amount == 0:
            continue
        # Get category from first line item account
        lines = p.get("Line", [])
        cat_name = ""
        for line in lines:
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct   = detail.get("AccountRef", {})
            cat_name = acct.get("name", "")
            if cat_name:
                break
        payee = p.get("EntityRef", {}).get("name", "") or p.get("PaymentMethodRef", {}).get("name", "") or "QBO Expense"
        memo  = p.get("PrivateNote") or p.get("Memo") or cat_name
        results.append({
            "date":          p.get("TxnDate", ""),
            "description":   memo or payee,
            "merchant_name": payee,
            "amount":        -abs(amount),
            "tax_category":  _map_category(cat_name),
            "external_id":   f"qbo_purch_{p.get('Id', '')}",
            "source":        "qbo",
        })
    return results


def get_invoices(access_token: str, realm_id: str,
                  date_from: str, date_to: str) -> List[Dict]:
    """Fetch invoices (income) from QBO."""
    sql = (
        f"SELECT * FROM Invoice "
        f"WHERE TxnDate >= '{date_from}' AND TxnDate <= '{date_to}'"
    )
    raw = _query(access_token, realm_id, sql)
    results = []
    for inv in raw:
        balance = float(inv.get("Balance", 0) or 0)
        total   = float(inv.get("TotalAmt", 0) or 0)
        if total == 0:
            continue
        customer = inv.get("CustomerRef", {}).get("name", "QBO Client")
        memo     = inv.get("PrivateNote") or f"Invoice #{inv.get('DocNumber','?')}"
        results.append({
            "date":          inv.get("TxnDate", ""),
            "description":   f"{memo} — {customer}",
            "merchant_name": customer,
            "amount":        abs(total),
            "tax_category":  "Business Income",
            "external_id":   f"qbo_inv_{inv.get('Id', '')}",
            "source":        "qbo",
        })
    return results


def get_sales_receipts(access_token: str, realm_id: str,
                       date_from: str, date_to: str) -> List[Dict]:
    """Fetch sales receipts (cash sales) from QBO."""
    sql = (
        f"SELECT * FROM SalesReceipt "
        f"WHERE TxnDate >= '{date_from}' AND TxnDate <= '{date_to}'"
    )
    raw = _query(access_token, realm_id, sql)
    results = []
    for sr in raw:
        total = float(sr.get("TotalAmt", 0) or 0)
        if total == 0:
            continue
        customer = sr.get("CustomerRef", {}).get("name", "QBO Client")
        memo     = sr.get("PrivateNote") or f"Sales receipt #{sr.get('DocNumber','?')}"
        results.append({
            "date":          sr.get("TxnDate", ""),
            "description":   f"{memo} — {customer}",
            "merchant_name": customer,
            "amount":        abs(total),
            "tax_category":  "Business Income",
            "external_id":   f"qbo_sr_{sr.get('Id', '')}",
            "source":        "qbo",
        })
    return results


def get_bills(access_token: str, realm_id: str,
               date_from: str, date_to: str) -> List[Dict]:
    """Fetch AP bills (vendor bills) from QBO."""
    sql = (
        f"SELECT * FROM Bill "
        f"WHERE TxnDate >= '{date_from}' AND TxnDate <= '{date_to}'"
    )
    raw = _query(access_token, realm_id, sql)
    results = []
    for b in raw:
        amount = float(b.get("TotalAmt", 0) or 0)
        if amount == 0:
            continue
        lines = b.get("Line", [])
        cat_name = ""
        for line in lines:
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct   = detail.get("AccountRef", {})
            cat_name = acct.get("name", "")
            if cat_name:
                break
        vendor = b.get("VendorRef", {}).get("name", "QBO Vendor")
        memo   = b.get("PrivateNote") or b.get("Memo") or cat_name
        results.append({
            "date":          b.get("TxnDate", ""),
            "description":   memo or vendor,
            "merchant_name": vendor,
            "amount":        -abs(amount),
            "tax_category":  _map_category(cat_name),
            "external_id":   f"qbo_bill_{b.get('Id', '')}",
            "source":        "qbo",
        })
    return results


def fetch_all(access_token: str, realm_id: str,
              date_from: str, date_to: str) -> List[Dict]:
    """Return all purchases + bills + income for the date range, sorted by date."""
    items = get_purchases(access_token, realm_id, date_from, date_to)
    items += get_bills(access_token, realm_id, date_from, date_to)
    items += get_invoices(access_token, realm_id, date_from, date_to)
    items += get_sales_receipts(access_token, realm_id, date_from, date_to)
    items.sort(key=lambda x: x["date"])
    return items
