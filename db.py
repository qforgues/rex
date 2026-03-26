import sqlite3
import os
from datetime import datetime
from typing import Optional
import pandas as pd

DB_PATH = os.environ.get("REX_DB_PATH", "rex.db")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize all database tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            type        TEXT    CHECK(type IN ('Checking','Savings','Credit Card','Investment','Loan','Other')),
            institution TEXT,
            balance     REAL    DEFAULT 0.0,
            currency    TEXT    DEFAULT 'USD',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            date            TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            amount          REAL    NOT NULL,
            category        TEXT    DEFAULT 'Uncategorized',
            notes           TEXT,
            source_hash     TEXT    UNIQUE,
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS net_worth_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT  NOT NULL,
            total_assets  REAL  DEFAULT 0.0,
            total_liabilities REAL DEFAULT 0.0,
            net_worth     REAL  DEFAULT 0.0,
            created_at    TEXT  DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS goals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            type           TEXT CHECK(type IN ('Cash Flow','Savings','Debt Paydown','Investment','Custom')),
            target_amount  REAL,
            current_amount REAL DEFAULT 0.0,
            deadline       TEXT,
            notes          TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            due_date    TEXT,
            notes       TEXT,
            done        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def get_accounts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_account(name: str, acct_type: str, institution: str, balance: float, currency: str = "USD") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO accounts (name, type, institution, balance, currency) VALUES (?,?,?,?,?)",
        (name, acct_type, institution, balance, currency),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_account(account_id: int, name: str, acct_type: str, institution: str, balance: float, currency: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE accounts SET name=?, type=?, institution=?, balance=?, currency=? WHERE id=?",
        (name, acct_type, institution, balance, currency, account_id),
    )
    conn.commit()
    conn.close()


def delete_account(account_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def get_transactions(account_id: Optional[int] = None, limit: int = 1000) -> list[dict]:
    conn = get_connection()
    if account_id:
        rows = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t "
            "LEFT JOIN accounts a ON t.account_id = a.id "
            "WHERE t.account_id=? ORDER BY t.date DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t "
            "LEFT JOIN accounts a ON t.account_id = a.id "
            "ORDER BY t.date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_transaction(account_id: int, date: str, description: str, amount: float,
                       category: str = "Uncategorized", notes: str = "", source_hash: str = "") -> bool:
    """Insert a transaction; returns True if inserted, False if duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO transactions (account_id, date, description, amount, category, notes, source_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (account_id, date, description, amount, category, notes, source_hash),
        )
        conn.commit()
        inserted = conn.execute("SELECT changes()").fetchone()[0] > 0
    finally:
        conn.close()
    return inserted


def update_transaction(txn_id: int, category: str, notes: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE transactions SET category=?, notes=? WHERE id=?",
        (category, notes, txn_id),
    )
    conn.commit()
    conn.close()


def delete_transaction(txn_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Net Worth Snapshots
# ---------------------------------------------------------------------------

def save_net_worth_snapshot() -> None:
    """Calculate current net worth from accounts and save a snapshot."""
    conn = get_connection()
    rows = conn.execute("SELECT type, balance FROM accounts").fetchall()
    assets = sum(r["balance"] for r in rows if r["type"] not in ("Credit Card", "Loan"))
    liabilities = abs(sum(r["balance"] for r in rows if r["type"] in ("Credit Card", "Loan")))
    net_worth = assets - liabilities
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO net_worth_snapshots (snapshot_date, total_assets, total_liabilities, net_worth) VALUES (?,?,?,?)",
        (today, assets, liabilities, net_worth),
    )
    conn.commit()
    conn.close()


def get_net_worth_history() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM net_worth_snapshots ORDER BY snapshot_date ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def get_goals() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_goal(name: str, goal_type: str, target_amount: float, current_amount: float,
             deadline: str, notes: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO goals (name, type, target_amount, current_amount, deadline, notes) VALUES (?,?,?,?,?,?)",
        (name, goal_type, target_amount, current_amount, deadline, notes),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_goal(goal_id: int, name: str, goal_type: str, target_amount: float,
                current_amount: float, deadline: str, notes: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE goals SET name=?, type=?, target_amount=?, current_amount=?, deadline=?, notes=? WHERE id=?",
        (name, goal_type, target_amount, current_amount, deadline, notes, goal_id),
    )
    conn.commit()
    conn.close()


def delete_goal(goal_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

def get_reminders(include_done: bool = False) -> list[dict]:
    conn = get_connection()
    if include_done:
        rows = conn.execute("SELECT * FROM reminders ORDER BY due_date ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM reminders WHERE done=0 ORDER BY due_date ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_reminder(title: str, due_date: str, notes: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO reminders (title, due_date, notes) VALUES (?,?,?)",
        (title, due_date, notes),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def mark_reminder_done(reminder_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def delete_reminder(reminder_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Dashboard / Financial Data
# ---------------------------------------------------------------------------

def get_financial_data() -> dict:
    """
    Retrieve all financial data needed for the Dashboard tab.

    Returns a dict with keys:
      - 'monthly_expenses'  : pd.DataFrame  columns=[month, category, total]
      - 'net_worth_history' : pd.DataFrame  columns=[snapshot_date, net_worth, total_assets, total_liabilities]
      - 'category_totals'   : pd.DataFrame  columns=[category, total]
      - 'monthly_income_expense': pd.DataFrame columns=[month, income, expenses]
      - 'account_balances'  : pd.DataFrame  columns=[name, type, balance]
      - 'top_transactions'  : pd.DataFrame  columns=[date, description, amount, category, account_name]
    """
    conn = get_connection()

    # --- Monthly expenses (negative amounts = spending) ---
    monthly_expenses_query = """
        SELECT
            strftime('%Y-%m', date) AS month,
            category,
            ROUND(SUM(ABS(amount)), 2) AS total
        FROM transactions
        WHERE amount < 0
        GROUP BY month, category
        ORDER BY month ASC, total DESC
    """
    monthly_expenses_df = pd.read_sql_query(monthly_expenses_query, conn)

    # --- Net worth history ---
    net_worth_query = """
        SELECT snapshot_date, net_worth, total_assets, total_liabilities
        FROM net_worth_snapshots
        ORDER BY snapshot_date ASC
    """
    net_worth_df = pd.read_sql_query(net_worth_query, conn)

    # --- Category totals (all time, expenses only) ---
    category_query = """
        SELECT
            category,
            ROUND(SUM(ABS(amount)), 2) AS total
        FROM transactions
        WHERE amount < 0
        GROUP BY category
        ORDER BY total DESC
    """
    category_df = pd.read_sql_query(category_query, conn)

    # --- Monthly income vs expenses ---
    income_expense_query = """
        SELECT
            strftime('%Y-%m', date) AS month,
            ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
            ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) AS expenses
        FROM transactions
        GROUP BY month
        ORDER BY month ASC
    """
    income_expense_df = pd.read_sql_query(income_expense_query, conn)

    # --- Account balances ---
    account_query = """
        SELECT name, type, ROUND(balance, 2) AS balance
        FROM accounts
        ORDER BY balance DESC
    """
    account_df = pd.read_sql_query(account_query, conn)

    # --- Top 10 largest expense transactions ---
    top_txn_query = """
        SELECT
            t.date,
            t.description,
            ROUND(ABS(t.amount), 2) AS amount,
            t.category,
            a.name AS account_name
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.amount < 0
        ORDER BY ABS(t.amount) DESC
        LIMIT 10
    """
    top_txn_df = pd.read_sql_query(top_txn_query, conn)

    conn.close()

    return {
        "monthly_expenses": monthly_expenses_df,
        "net_worth_history": net_worth_df,
        "category_totals": category_df,
        "monthly_income_expense": income_expense_df,
        "account_balances": account_df,
        "top_transactions": top_txn_df,
    }
