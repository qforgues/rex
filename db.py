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
            scope       TEXT    DEFAULT 'Personal',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS statements (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id       INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            opening_date     TEXT NOT NULL,
            closing_date     TEXT NOT NULL,
            opening_balance  REAL DEFAULT 0.0,
            closing_balance  REAL DEFAULT 0.0,
            total_charges    REAL DEFAULT 0.0,
            total_credits    REAL DEFAULT 0.0,
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            date            TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            merchant_name   TEXT,
            amount          REAL    NOT NULL,
            category        TEXT    DEFAULT 'Uncategorized',
            notes           TEXT,
            source_hash     TEXT    UNIQUE,
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS merchant_rules (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern       TEXT    NOT NULL UNIQUE,
            friendly_name TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            type        TEXT    DEFAULT 'Other',
            value       REAL    DEFAULT 0.0,
            liability   REAL    DEFAULT 0.0,
            notes       TEXT,
            updated_at  TEXT    DEFAULT (datetime('now')),
            created_at  TEXT    DEFAULT (datetime('now'))
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

        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            is_default INTEGER DEFAULT 0
        );
    """)

    conn.commit()

    # Migrations
    for migration in [
        "ALTER TABLE transactions ADD COLUMN merchant_name TEXT",
        "ALTER TABLE transactions ADD COLUMN excluded INTEGER DEFAULT 0",
        "ALTER TABLE accounts ADD COLUMN scope TEXT DEFAULT 'Personal'",
        "ALTER TABLE transactions ADD COLUMN statement_id INTEGER REFERENCES statements(id)",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass

    # Seed default categories if the table is empty
    defaults = [
        "Income", "Housing", "Groceries", "Food & Dining", "Transportation",
        "Gas & Fuel", "Utilities", "Health & Medical", "Health & Fitness",
        "Entertainment", "Shopping", "Travel", "Education", "Home Improvement",
        "Transfer", "Interest & Fees", "Investments", "Subscriptions",
        "Personal Care", "Gifts & Donations", "Uncategorized",
    ]
    existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO categories (name, is_default) VALUES (?, 1)",
            [(c,) for c in defaults],
        )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def get_accounts() -> list[dict]:
    """Return accounts; balance = most recent statement closing balance, else SUM of transactions."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, a.name, a.type, a.institution, a.currency, a.scope, a.created_at,
               COALESCE(
                   (SELECT s.closing_balance FROM statements s
                    WHERE s.account_id = a.id ORDER BY s.closing_date DESC LIMIT 1),
                   (SELECT ROUND(COALESCE(SUM(t.amount), 0), 2) FROM transactions t
                    WHERE t.account_id = a.id),
                   0.0
               ) AS balance
        FROM accounts a
        ORDER BY a.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_account(name: str, acct_type: str, institution: str, scope: str = "Personal") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO accounts (name, type, institution, balance, currency, scope) VALUES (?,?,?,0.0,'USD',?)",
        (name, acct_type, institution, scope),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_account(account_id: int, name: str, acct_type: str, institution: str, scope: str = "Personal") -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE accounts SET name=?, type=?, institution=?, scope=? WHERE id=?",
        (name, acct_type, institution, scope, account_id),
    )
    conn.commit()
    conn.close()


def insert_statement(account_id: int, opening_date: str, closing_date: str,
                     opening_balance: float, closing_balance: float,
                     total_charges: float, total_credits: float) -> int:
    """Record a statement import. Returns the new statement ID."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO statements "
        "(account_id, opening_date, closing_date, opening_balance, closing_balance, total_charges, total_credits) "
        "VALUES (?,?,?,?,?,?,?)",
        (account_id, opening_date, closing_date, opening_balance, closing_balance, total_charges, total_credits),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_account_statements(account_id: int) -> list[dict]:
    """Return all statements for an account, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM statements WHERE account_id=? ORDER BY closing_date DESC",
        (account_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_statement_closing_balance(account_id: int) -> float:
    """Return the closing balance of the most recent statement, or 0.0 if none."""
    conn = get_connection()
    row = conn.execute(
        "SELECT closing_balance FROM statements WHERE account_id=? ORDER BY closing_date DESC LIMIT 1",
        (account_id,),
    ).fetchone()
    conn.close()
    return float(row["closing_balance"]) if row else 0.0


def delete_import(statement_id: int) -> int:
    """
    Delete a statement and all its transactions.
    Handles both linked transactions (statement_id FK) and legacy unlinked
    transactions (imported before FK existed) via date-range fallback.
    Returns number of transactions deleted.
    """
    conn = get_connection()
    stmt = conn.execute(
        "SELECT account_id, opening_date, closing_date FROM statements WHERE id=?",
        (statement_id,),
    ).fetchone()
    if not stmt:
        conn.close()
        return 0

    # Delete transactions directly linked by FK
    conn.execute("DELETE FROM transactions WHERE statement_id=?", (statement_id,))

    # Also delete legacy unlinked transactions in the same account + date range
    conn.execute(
        "DELETE FROM transactions WHERE account_id=? AND statement_id IS NULL "
        "AND date >= ? AND date <= ?",
        (stmt["account_id"], stmt["opening_date"], stmt["closing_date"]),
    )

    row = conn.execute(
        "SELECT changes()",
    ).fetchone()
    txn_count = row[0] if row else 0

    conn.execute("DELETE FROM statements WHERE id=?", (statement_id,))
    conn.commit()
    conn.close()
    return txn_count


def get_all_imports() -> list[dict]:
    """Return all statement imports across all accounts, newest first, with transaction counts."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.id, s.account_id, a.name AS account_name, a.type AS account_type,
               s.opening_date, s.closing_date,
               s.opening_balance, s.closing_balance,
               s.total_charges, s.total_credits,
               (SELECT COUNT(*) FROM transactions t
                WHERE t.statement_id = s.id
                   OR (t.account_id = s.account_id AND t.statement_id IS NULL
                       AND t.date >= s.opening_date AND t.date <= s.closing_date)
               ) AS txn_count
        FROM statements s
        JOIN accounts a ON a.id = s.account_id
        ORDER BY s.closing_date DESC, a.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
                       category: str = "Uncategorized", notes: str = "", source_hash: str = "",
                       merchant_name: str = "", statement_id: int = None) -> bool:
    """
    Insert a transaction; returns True if newly inserted, False if it already existed.
    If it already existed and has no statement_id, links it to the provided one.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO transactions "
            "(account_id, date, description, merchant_name, amount, category, notes, source_hash, statement_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (account_id, date, description, merchant_name or None, amount, category, notes, source_hash, statement_id),
        )
        inserted = conn.execute("SELECT changes()").fetchone()[0] > 0
        if not inserted and statement_id and source_hash:
            # Transaction exists but may lack a statement link — backfill it
            conn.execute(
                "UPDATE transactions SET statement_id=? WHERE source_hash=? AND statement_id IS NULL",
                (statement_id, source_hash),
            )
        conn.commit()
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
    """Calculate current net worth from accounts + assets and save a snapshot."""
    conn = get_connection()

    # Liquid accounts — balance from most recent statement, else SUM of transactions
    acct_rows = conn.execute("""
        SELECT a.type,
               COALESCE(
                   (SELECT s.closing_balance FROM statements s
                    WHERE s.account_id = a.id ORDER BY s.closing_date DESC LIMIT 1),
                   (SELECT ROUND(COALESCE(SUM(t.amount), 0), 2) FROM transactions t
                    WHERE t.account_id = a.id),
                   0.0
               ) AS balance
        FROM accounts a
    """).fetchall()
    liquid_assets = sum(r["balance"] for r in acct_rows if r["type"] not in ("Credit Card", "Loan"))
    liquid_liabilities = abs(sum(r["balance"] for r in acct_rows if r["type"] in ("Credit Card", "Loan")))

    # Physical/investment assets
    asset_rows = conn.execute("SELECT value, liability FROM assets").fetchall()
    asset_values = sum(r["value"] for r in asset_rows)
    asset_liabilities = sum(r["liability"] for r in asset_rows)

    total_assets = liquid_assets + asset_values
    total_liabilities = liquid_liabilities + asset_liabilities
    net_worth = total_assets - total_liabilities

    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR REPLACE INTO net_worth_snapshots (snapshot_date, total_assets, total_liabilities, net_worth) VALUES (?,?,?,?)",
        (today, total_assets, total_liabilities, net_worth),
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
# Categories
# ---------------------------------------------------------------------------

def get_categories() -> list[str]:
    """Return all category names sorted alphabetically."""
    conn = get_connection()
    rows = conn.execute("SELECT name FROM categories ORDER BY name ASC").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def add_category(name: str) -> bool:
    """Add a new category. Returns True if inserted, False if it already exists."""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO categories (name, is_default) VALUES (?, 0)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_category(name: str) -> None:
    """Delete a custom category. Also resets any transactions using it to Uncategorized."""
    conn = get_connection()
    conn.execute("UPDATE transactions SET category='Uncategorized' WHERE category=?", (name,))
    conn.execute("DELETE FROM categories WHERE name=? AND is_default=0", (name,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Merchant Rules
# ---------------------------------------------------------------------------

def get_merchant_rules() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM merchant_rules ORDER BY friendly_name ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_matching_rule(description: str) -> Optional[str]:
    """
    Normalize the description and return the best-matching friendly_name,
    or None if no rule matches.
    Best match = longest stored pattern that is a substring of the normalized description.
    """
    from parsers import normalize_description
    normalized = normalize_description(description)
    rules = get_merchant_rules()
    best_name = None
    best_len = 0
    for rule in rules:
        pattern = rule["pattern"].upper()
        if pattern in normalized and len(pattern) > best_len:
            best_name = rule["friendly_name"]
            best_len = len(pattern)
    return best_name


def add_merchant_rule(pattern: str, friendly_name: str) -> bool:
    """Add a rule. Returns True if inserted, False if pattern already exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO merchant_rules (pattern, friendly_name) VALUES (?, ?)",
            (pattern.upper().strip(), friendly_name.strip()),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def update_merchant_rule(rule_id: int, pattern: str, friendly_name: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE merchant_rules SET pattern=?, friendly_name=? WHERE id=?",
        (pattern.upper().strip(), friendly_name.strip(), rule_id),
    )
    conn.commit()
    conn.close()


def delete_merchant_rule(rule_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM merchant_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def set_transaction_excluded(txn_id: int, excluded: bool) -> None:
    conn = get_connection()
    conn.execute("UPDATE transactions SET excluded=? WHERE id=?", (1 if excluded else 0, txn_id))
    conn.commit()
    conn.close()


def update_transaction_merchant_name(txn_id: int, merchant_name: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE transactions SET merchant_name=? WHERE id=?",
        (merchant_name.strip() if merchant_name else None, txn_id),
    )
    conn.commit()
    conn.close()


def get_transactions_needing_review(source_hashes: list[str]) -> list[dict]:
    """
    Given a list of source_hashes, return existing transactions that need review:
    category is Uncategorized or merchant_name is null.
    """
    if not source_hashes:
        return []
    conn = get_connection()
    placeholders = ",".join("?" * len(source_hashes))
    rows = conn.execute(
        f"SELECT t.*, a.name as account_name FROM transactions t "
        f"LEFT JOIN accounts a ON t.account_id = a.id "
        f"WHERE t.source_hash IN ({placeholders}) "
        f"AND (t.category = 'Uncategorized' OR t.merchant_name IS NULL OR t.merchant_name = '')",
        source_hashes,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

ASSET_TYPES = ["Real Estate", "Vehicle", "Investment", "Business", "Personal Property", "Other"]


def get_assets() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM assets ORDER BY type, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_asset(name: str, asset_type: str, value: float, liability: float, notes: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO assets (name, type, value, liability, notes) VALUES (?,?,?,?,?)",
        (name, asset_type, value, liability, notes),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_asset(asset_id: int, name: str, asset_type: str, value: float, liability: float, notes: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE assets SET name=?, type=?, value=?, liability=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, asset_type, value, liability, notes, asset_id),
    )
    conn.commit()
    conn.close()


def delete_asset(asset_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM assets WHERE id=?", (asset_id,))
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

    # --- Monthly expenses (negative amounts = spending, excluded transactions omitted) ---
    monthly_expenses_query = """
        SELECT
            strftime('%Y-%m', date) AS month,
            category,
            ROUND(SUM(ABS(amount)), 2) AS total
        FROM transactions
        WHERE amount < 0 AND (excluded IS NULL OR excluded = 0)
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

    # --- Category totals (all time, expenses only, excluded omitted) ---
    category_query = """
        SELECT
            category,
            ROUND(SUM(ABS(amount)), 2) AS total
        FROM transactions
        WHERE amount < 0 AND (excluded IS NULL OR excluded = 0)
        GROUP BY category
        ORDER BY total DESC
    """
    category_df = pd.read_sql_query(category_query, conn)

    # --- Monthly income vs expenses (excluded omitted from expenses) ---
    income_expense_query = """
        SELECT
            strftime('%Y-%m', date) AS month,
            ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
            ROUND(SUM(CASE WHEN amount < 0 AND (excluded IS NULL OR excluded = 0)
                          THEN ABS(amount) ELSE 0 END), 2) AS expenses
        FROM transactions
        GROUP BY month
        ORDER BY month ASC
    """
    income_expense_df = pd.read_sql_query(income_expense_query, conn)

    # --- Account balances (from most recent statement, else SUM of transactions) ---
    account_query = """
        SELECT a.name, a.type,
               COALESCE(
                   (SELECT s.closing_balance FROM statements s
                    WHERE s.account_id = a.id ORDER BY s.closing_date DESC LIMIT 1),
                   (SELECT ROUND(COALESCE(SUM(t.amount), 0), 2) FROM transactions t
                    WHERE t.account_id = a.id),
                   0.0
               ) AS balance
        FROM accounts a
        ORDER BY balance DESC
    """
    account_df = pd.read_sql_query(account_query, conn)

    # --- Top 10 largest expense transactions (excluded omitted) ---
    top_txn_query = """
        SELECT
            t.date,
            COALESCE(t.merchant_name, t.description) AS name,
            ROUND(ABS(t.amount), 2) AS amount,
            t.category,
            a.name AS account_name
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.amount < 0 AND (t.excluded IS NULL OR t.excluded = 0)
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
