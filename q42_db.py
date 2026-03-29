"""
q42_db.py — Portal42 Q42 database layer.
Separate SQLite database (q42.db) — purely for tax/accountant use.
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
Q42_DB_PATH = os.environ.get("Q42_DB_PATH", os.path.join(_HERE, "q42.db"))

# Tax-optimized category list (IRS Schedule C / Michigan CPA focused)
Q42_TAX_CATEGORIES = [
    "Business Income",
    "Home Office",
    "Vehicle & Mileage",
    "Business Meals (50%)",
    "Business Travel",
    "Technology & Software",
    "Subscriptions (Business)",
    "Marketing & Advertising",
    "Professional Services",
    "Legal & Accounting",
    "Education & Training",
    "Equipment (Section 179)",
    "Office Supplies",
    "Utilities (Business %)",
    "Internet & Phone (Business %)",
    "Health Insurance Premiums",
    "HSA Contributions",
    "Retirement Contributions",
    "Bank Fees & Interest",
    "Insurance (Business)",
    "Rent & Lease (Business)",
    "Payroll & Contractors",
    "Personal (Non-Deductible)",
    "Transfer",
    "Uncategorized",
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(Q42_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_q42_db() -> None:
    conn = get_connection()
    ddl = [
        """CREATE TABLE IF NOT EXISTS q42_imports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            account_label TEXT,
            source_type   TEXT,
            period_start  TEXT,
            period_end    TEXT,
            total_in      REAL DEFAULT 0.0,
            total_out     REAL DEFAULT 0.0,
            txn_count     INTEGER DEFAULT 0,
            imported_at   TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS q42_transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id      INTEGER REFERENCES q42_imports(id) ON DELETE CASCADE,
            date           TEXT NOT NULL,
            description    TEXT NOT NULL,
            merchant_name  TEXT,
            amount         REAL NOT NULL,
            tax_category   TEXT DEFAULT 'Uncategorized',
            business_pct   REAL DEFAULT 100.0,
            deductible_amt REAL DEFAULT 0.0,
            notes          TEXT,
            is_personal    INTEGER DEFAULT 0,
            source_hash    TEXT UNIQUE,
            data_source    TEXT DEFAULT 'bank',
            created_at     TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS q42_tax_profile (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT NOT NULL UNIQUE,
            value      TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS q42_connections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            service          TEXT NOT NULL UNIQUE,
            status           TEXT DEFAULT 'disconnected',
            company_id       TEXT,
            access_token     TEXT,
            refresh_token    TEXT,
            client_id        TEXT,
            client_secret    TEXT,
            redirect_uri     TEXT,
            oauth_state      TEXT,
            token_expires_at TEXT,
            display_name     TEXT,
            updated_at       TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS q42_conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT    NOT NULL,
            messages   TEXT    NOT NULL,
            created_at TEXT    DEFAULT (datetime('now')),
            updated_at TEXT    DEFAULT (datetime('now'))
        )""",
    ]
    for stmt in ddl:
        conn.execute(stmt)
    conn.commit()

    # Migration: add new columns to existing databases that predate them
    _migration_cols = [
        "ALTER TABLE q42_connections ADD COLUMN client_id TEXT",
        "ALTER TABLE q42_connections ADD COLUMN client_secret TEXT",
        "ALTER TABLE q42_connections ADD COLUMN redirect_uri TEXT",
        "ALTER TABLE q42_connections ADD COLUMN oauth_state TEXT",
        "ALTER TABLE q42_connections ADD COLUMN token_expires_at TEXT",
        "ALTER TABLE q42_connections ADD COLUMN display_name TEXT",
        "ALTER TABLE q42_transactions ADD COLUMN data_source TEXT DEFAULT 'bank'",
    ]
    for sql in _migration_cols:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    for svc in ["qbo"]:
        conn.execute(
            "INSERT OR IGNORE INTO q42_connections (service) VALUES (?)", (svc,)
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

def record_import(filename: str, account_label: str, source_type: str,
                  period_start: str, period_end: str,
                  total_in: float, total_out: float, txn_count: int) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO q42_imports "
        "(filename, account_label, source_type, period_start, period_end, total_in, total_out, txn_count) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (filename, account_label, source_type, period_start, period_end, total_in, total_out, txn_count),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_import_summary() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM q42_imports ORDER BY imported_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_import(import_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM q42_transactions WHERE import_id=?", (import_id,))
    conn.execute("DELETE FROM q42_imports WHERE id=?", (import_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def calculate_deductible(amount: float, tax_category: str, business_pct: float) -> float:
    """Calculate deductible amount based on category rules and business %."""
    if amount >= 0:
        return 0.0
    abs_amt = abs(amount)
    if tax_category == "Personal (Non-Deductible)":
        return 0.0
    if tax_category == "Transfer":
        return 0.0
    if tax_category == "Business Meals (50%)":
        return round(abs_amt * 0.50 * (business_pct / 100.0), 2)
    return round(abs_amt * (business_pct / 100.0), 2)


def insert_q42_transaction(import_id: int, date: str, description: str,
                            merchant_name: str, amount: float,
                            tax_category: str = "Uncategorized",
                            source_hash: str = "") -> bool:
    conn = get_connection()
    is_personal = 1 if tax_category in ("Personal (Non-Deductible)", "Transfer") else 0
    deductible = calculate_deductible(amount, tax_category, 100.0)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO q42_transactions "
            "(import_id, date, description, merchant_name, amount, tax_category, "
            "deductible_amt, is_personal, source_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (import_id, date, description, merchant_name, amount,
             tax_category, deductible, is_personal, source_hash),
        )
        inserted = conn.execute("SELECT changes()").fetchone()[0] > 0
        conn.commit()
    finally:
        conn.close()
    return inserted


def update_q42_transaction(txn_id: int, tax_category: str, business_pct: float,
                            notes: str, is_personal: bool) -> None:
    conn = get_connection()
    row = conn.execute(
        "SELECT amount FROM q42_transactions WHERE id=?", (txn_id,)
    ).fetchone()
    if row:
        deductible = calculate_deductible(float(row["amount"]), tax_category, business_pct)
        conn.execute(
            "UPDATE q42_transactions SET tax_category=?, business_pct=?, "
            "deductible_amt=?, notes=?, is_personal=? WHERE id=?",
            (tax_category, business_pct, deductible, notes,
             1 if is_personal else 0, txn_id),
        )
    conn.commit()
    conn.close()


def get_all_transactions(limit: int = 5000) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, i.account_label, i.filename
        FROM q42_transactions t
        LEFT JOIN q42_imports i ON t.import_id = i.id
        ORDER BY t.date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_period_summary() -> dict:
    conn = get_connection()
    row = conn.execute("""
        SELECT MIN(date) as start_date, MAX(date) as end_date,
               COUNT(*) as total_txns,
               ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) as total_in,
               ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) as total_out,
               ROUND(SUM(deductible_amt), 2) as total_deductible
        FROM q42_transactions
    """).fetchone()
    conn.close()
    if not row or not row["start_date"]:
        return {}
    return dict(row)


def get_deduction_summary() -> dict:
    conn = get_connection()
    rows = conn.execute("""
        SELECT tax_category,
               COUNT(*) as count,
               ROUND(SUM(ABS(amount)), 2) as gross_total,
               ROUND(SUM(deductible_amt), 2) as deductible_total
        FROM q42_transactions
        WHERE amount < 0 AND is_personal = 0 AND tax_category != 'Transfer'
        GROUP BY tax_category
        ORDER BY deductible_total DESC
    """).fetchall()
    income_row = conn.execute(
        "SELECT ROUND(SUM(amount), 2) as total_income FROM q42_transactions WHERE amount > 0"
    ).fetchone()
    conn.close()
    return {
        "by_category": [dict(r) for r in rows],
        "total_income": float(income_row["total_income"] or 0),
    }


# ---------------------------------------------------------------------------
# Tax Profile
# ---------------------------------------------------------------------------

def get_tax_profile() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM q42_tax_profile").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_tax_profile_key(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO q42_tax_profile (key, value, updated_at) "
        "VALUES (?, ?, datetime('now'))",
        (key, value),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def get_connection_status(service: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM q42_connections WHERE service=?", (service,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {"service": service, "status": "disconnected"}


def set_connection_status(service: str, status: str,
                          company_id: str = "", access_token: str = "") -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE q42_connections SET status=?, company_id=?, access_token=?, "
        "updated_at=datetime('now') WHERE service=?",
        (status, company_id, access_token, service),
    )
    conn.commit()
    conn.close()




# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def get_q42_conversations() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM q42_conversations ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_q42_conversation(conv_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, title, messages, created_at, updated_at FROM q42_conversations WHERE id=?",
        (conv_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    d["messages"] = json.loads(d["messages"])
    return d


def save_q42_conversation(title: str, messages: list) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO q42_conversations (title, messages) VALUES (?, ?)",
        (title, json.dumps(messages))
    )
    conv_id = cur.lastrowid
    conn.commit()
    conn.close()
    return conv_id


def update_q42_conversation(conv_id: int, messages: list) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE q42_conversations SET messages=?, updated_at=datetime('now') WHERE id=?",
        (json.dumps(messages), conv_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# QBO OAuth
# ---------------------------------------------------------------------------

def save_qbo_credentials(client_id: str, client_secret: str,
                          redirect_uri: str, oauth_state: str) -> None:
    """Persist QBO app credentials and state before starting OAuth.
    Clears stale tokens/company_id to avoid orphaned state on re-connect."""
    conn = get_connection()
    conn.execute(
        "UPDATE q42_connections SET client_id=?, client_secret=?, "
        "redirect_uri=?, oauth_state=?, status='pending', "
        "access_token='', refresh_token='', token_expires_at='', "
        "company_id='', "
        "updated_at=datetime('now') WHERE service='qbo'",
        (client_id, client_secret, redirect_uri, oauth_state),
    )
    conn.commit()
    conn.close()


def save_qbo_tokens(access_token: str, refresh_token: str,
                    token_expires_at: str, display_name: str,
                    realm_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE q42_connections SET status='connected', "
        "access_token=?, refresh_token=?, token_expires_at=?, "
        "display_name=?, company_id=?, oauth_state=NULL, "
        "updated_at=datetime('now') WHERE service='qbo'",
        (access_token, refresh_token, token_expires_at, display_name, realm_id),
    )
    conn.commit()
    conn.close()


def get_qbo_pending_state() -> Optional[str]:
    conn = get_connection()
    row = conn.execute(
        "SELECT oauth_state FROM q42_connections WHERE service='qbo'"
    ).fetchone()
    conn.close()
    return row["oauth_state"] if row else None


# ---------------------------------------------------------------------------
# API Import (FreshBooks / QBO)
# ---------------------------------------------------------------------------

def import_api_transactions(transactions: list, account_label: str,
                              source_type: str, period_start: str,
                              period_end: str) -> dict:
    """
    Insert a batch of transactions from an API source (freshbooks/qbo).
    Returns {"inserted": N, "dupes": N, "import_id": id}.
    """
    import hashlib
    total_in  = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_out = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)

    import_id = record_import(
        filename=f"{source_type}_api_{period_start}_{period_end}",
        account_label=account_label,
        source_type=source_type,
        period_start=period_start,
        period_end=period_end,
        total_in=total_in,
        total_out=total_out,
        txn_count=len(transactions),
    )

    inserted = dupes = 0
    conn = get_connection()
    for t in transactions:
        src_hash = hashlib.md5(t.get("external_id", "").encode()).hexdigest()
        is_personal = 1 if t["tax_category"] in ("Personal (Non-Deductible)", "Transfer") else 0
        deductible  = calculate_deductible(t["amount"], t["tax_category"], 100.0)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO q42_transactions "
                "(import_id, date, description, merchant_name, amount, tax_category, "
                "deductible_amt, is_personal, source_hash, data_source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (import_id, t["date"], t["description"], t["merchant_name"],
                 t["amount"], t["tax_category"], deductible, is_personal,
                 src_hash, t.get("source", source_type)),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
            else:
                dupes += 1
        except Exception:
            dupes += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "dupes": dupes, "import_id": import_id}


# ---------------------------------------------------------------------------
# Gap Analysis
# ---------------------------------------------------------------------------

def get_coverage_by_month() -> dict:
    """
    Return a dict of {YYYY-MM: {"count": N, "sources": set}} for all months
    that have transaction data, so gaps can be identified.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT substr(date,1,7) as month, data_source, COUNT(*) as cnt "
        "FROM q42_transactions "
        "WHERE date IS NOT NULL AND date != '' "
        "GROUP BY month, data_source"
    ).fetchall()
    conn.close()
    coverage: dict = {}
    for row in rows:
        m = row["month"]
        if m not in coverage:
            coverage[m] = {"count": 0, "sources": set()}
        coverage[m]["count"] += row["cnt"]
        if row["data_source"]:
            coverage[m]["sources"].add(row["data_source"])
    return coverage
