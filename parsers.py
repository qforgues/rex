import pandas as pd
import re
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Description normalization for merchant rule matching
# ---------------------------------------------------------------------------

_PREFIX_RE = re.compile(
    r"^(EFT PMT|ACH PMT|ACH|POS|DEBIT CARD|CREDIT CARD|CHECKCARD|CHECK CARD|"
    r"ONLINE PMT|ONLINE PAYMENT|BILL PAY|BILL PAYMENT|RECURRING PMT|RECURRING|"
    r"PREAUTH|PRE-AUTH|PREAUTHORIZED|PYMT|PAYMENT|PURCHASE|ORIG CO NAME:?\s*|"
    r"SYF PAYMNT|SYF|PAYMNT|PMT)\s+",
    re.IGNORECASE,
)

_SUFFIX_RE = re.compile(r"[\s\dX#\*]{4,}$")


def normalize_description(desc: str) -> str:
    """
    Strip common banking prefixes and trailing masked account/card numbers
    so the meaningful merchant name remains for pattern matching.

    Example:
      "EFT PMT AMAZON CORP SYF PAYMNT XXXXXXXXXXX9053" → "AMAZON CORP"
      "EFT PMT GREENLIGHT APP XXXXXXXXXXXIGHT"          → "GREENLIGHT APP"
    """
    s = desc.strip()
    # Strip prefixes up to 4 passes (some descriptions stack multiple prefixes)
    for _ in range(4):
        new_s = _PREFIX_RE.sub("", s).strip()
        if new_s == s:
            break
        s = new_s
    # Strip trailing masked numbers / X sequences (min 4 chars to avoid false strips)
    s = _SUFFIX_RE.sub("", s).strip()
    # Collapse internal whitespace
    s = re.sub(r"\s+", " ", s)
    return s.upper()

# ---------------------------------------------------------------------------
# Keyword → Category mapping
# Keys are lowercase substrings; first match wins.
# ---------------------------------------------------------------------------
KEYWORD_CATEGORIES: dict[str, str] = {
    # Food & Dining
    "mcdonald": "Food & Dining",
    "starbucks": "Food & Dining",
    "chipotle": "Food & Dining",
    "subway": "Food & Dining",
    "doordash": "Food & Dining",
    "uber eats": "Food & Dining",
    "grubhub": "Food & Dining",
    "instacart": "Groceries",
    "whole foods": "Groceries",
    "trader joe": "Groceries",
    "kroger": "Groceries",
    "safeway": "Groceries",
    "costco": "Groceries",
    "walmart": "Shopping",
    "target": "Shopping",
    # Transportation
    "uber": "Transportation",
    "lyft": "Transportation",
    "shell": "Gas & Fuel",
    "chevron": "Gas & Fuel",
    "exxon": "Gas & Fuel",
    "bp ": "Gas & Fuel",
    "sunoco": "Gas & Fuel",
    # Utilities
    "electric": "Utilities",
    "water bill": "Utilities",
    "gas bill": "Utilities",
    "internet": "Utilities",
    "comcast": "Utilities",
    "at&t": "Utilities",
    "verizon": "Utilities",
    "t-mobile": "Utilities",
    # Entertainment
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "hulu": "Entertainment",
    "disney+": "Entertainment",
    "apple tv": "Entertainment",
    "amazon prime": "Entertainment",
    "youtube": "Entertainment",
    "steam": "Entertainment",
    # Health
    "pharmacy": "Health & Medical",
    "cvs": "Health & Medical",
    "walgreens": "Health & Medical",
    "doctor": "Health & Medical",
    "hospital": "Health & Medical",
    "dental": "Health & Medical",
    "gym": "Health & Fitness",
    "planet fitness": "Health & Fitness",
    # Travel
    "airbnb": "Travel",
    "hotel": "Travel",
    "airline": "Travel",
    "delta": "Travel",
    "united air": "Travel",
    "southwest": "Travel",
    "american air": "Travel",
    # Finance
    "transfer": "Transfer",
    "zelle": "Transfer",
    "venmo": "Transfer",
    "paypal": "Transfer",
    "interest charge": "Interest & Fees",
    "late fee": "Interest & Fees",
    "atm fee": "Interest & Fees",
    "overdraft": "Interest & Fees",
    # Income
    "payroll": "Income",
    "direct deposit": "Income",
    "salary": "Income",
    "dividend": "Income",
    # Shopping
    "amazon": "Shopping",
    "ebay": "Shopping",
    "etsy": "Shopping",
    "best buy": "Shopping",
    "apple store": "Shopping",
    # Home
    "home depot": "Home Improvement",
    "lowe's": "Home Improvement",
    "rent": "Housing",
    "mortgage": "Housing",
    # Education
    "tuition": "Education",
    "student loan": "Education",
    "udemy": "Education",
    "coursera": "Education",
}


def _keyword_category(description: str) -> Optional[str]:
    """Return the first matching keyword category for a description, or None."""
    lower = description.lower()
    for keyword, category in KEYWORD_CATEGORIES.items():
        if keyword in lower:
            return category
    return None


def categorize_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Categorize a DataFrame of transactions.

    Strategy:
      1. Apply keyword-based matching first (fast, offline).
      2. Batch any remaining uncategorized rows and send to the Anthropic API
         via rex.get_ai_categories().
      3. Fall back to "Uncategorized" for anything that still has no category.

    Parameters
    ----------
    transactions : pd.DataFrame
        Must contain at least a ``description`` column.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with a ``category`` column populated.
    """
    if transactions.empty:
        transactions["category"] = pd.Series(dtype=str)
        return transactions

    df = transactions.copy()

    # Ensure a category column exists
    if "category" not in df.columns:
        df["category"] = None

    # ------------------------------------------------------------------
    # Step 1: keyword-based categorization
    # ------------------------------------------------------------------
    desc_col = "description" if "description" in df.columns else df.columns[0]

    for idx, row in df.iterrows():
        # Skip rows that already have a non-empty category
        existing = row.get("category", None)
        if existing and str(existing).strip() and str(existing).strip() != "Uncategorized":
            continue

        desc = str(row.get(desc_col, ""))
        matched = _keyword_category(desc)
        if matched:
            df.at[idx, "category"] = matched

    # ------------------------------------------------------------------
    # Step 2: AI-assisted categorization for remaining uncategorized rows
    # ------------------------------------------------------------------
    uncategorized_mask = (
        df["category"].isna()
        | (df["category"].astype(str).str.strip() == "")
        | (df["category"].astype(str).str.strip() == "None")
    )
    uncategorized_indices = df[uncategorized_mask].index.tolist()

    if uncategorized_indices:
        try:
            # Import here to avoid circular imports and allow the module to
            # load even when the Anthropic key is not yet configured.
            from rex import get_ai_categories  # type: ignore

            descriptions = df.loc[uncategorized_indices, desc_col].astype(str).tolist()
            ai_categories = get_ai_categories(descriptions)

            for idx, category in zip(uncategorized_indices, ai_categories):
                df.at[idx, "category"] = category if category else "Uncategorized"
        except Exception as exc:
            # If AI categorization fails for any reason, fall back gracefully
            print(f"[categorize_transactions] AI categorization failed: {exc}")
            for idx in uncategorized_indices:
                if not df.at[idx, "category"] or str(df.at[idx, "category"]).strip() in ("", "None"):
                    df.at[idx, "category"] = "Uncategorized"

    # ------------------------------------------------------------------
    # Step 3: Final fallback — fill any remaining NaN / empty values
    # ------------------------------------------------------------------
    df["category"] = df["category"].fillna("Uncategorized")
    df.loc[df["category"].astype(str).str.strip() == "", "category"] = "Uncategorized"
    df.loc[df["category"].astype(str).str.strip() == "None", "category"] = "Uncategorized"

    return df


# ---------------------------------------------------------------------------
# CSV parsing helpers (kept from previous rounds)
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "transaction date", "trans date", "posted date", "posting date"],
    "description": ["description", "memo", "payee", "transaction description", "details", "name"],
    "amount": ["amount", "transaction amount", "debit", "credit", "sum"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical names based on COLUMN_ALIASES."""
    rename_map: dict[str, str] = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols and canonical not in rename_map.values():
                rename_map[lower_cols[alias]] = canonical
                break
    return df.rename(columns=rename_map)


def parse_chase_pdf(filepath: str, account_id: int) -> pd.DataFrame:
    """
    Parse a Chase credit card PDF statement into a normalised DataFrame.

    Returns a DataFrame with columns: date, description, amount, account_id.
    Amounts are signed: negative = payment/credit, positive = charge.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required to parse PDFs. Run: pip3 install pdfplumber")

    try:
        pdf = pdfplumber.open(filepath)
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    # Extract all text across pages
    full_text = ""
    with pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

    # Detect statement year from "Opening/Closing Date MM/DD/YY - MM/DD/YY"
    year_match = re.search(r"Opening/Closing Date\s+\d{2}/\d{2}/(\d{2,4})", full_text, re.IGNORECASE)
    if year_match:
        yr = year_match.group(1)
        stmt_year = int(yr) if len(yr) == 4 else 2000 + int(yr)
    else:
        stmt_year = datetime.now().year

    # Find the ACCOUNT ACTIVITY section (Chase PDFs may double every character in headers)
    activity_match = re.search(r"A+C+O+U+N+T+\s+A+C+T+I+V+I+T+Y+", full_text, re.IGNORECASE)
    if not activity_match:
        raise ValueError("Could not find ACCOUNT ACTIVITY section in the PDF.")

    activity_text = full_text[activity_match.end():]

    # Stop when we hit summary/totals lines that follow the transaction list
    stop_match = re.search(
        r"(TRANSACTIONS THIS CYCLE|Year-to-Date|INTEREST CHARGES\n|IINNTTEERREESSTT|YEAR-TO-DATE TOTALS)",
        activity_text, re.IGNORECASE
    )
    if stop_match:
        activity_text = activity_text[: stop_match.start()]

    # Match transaction lines: MM/DD <description> <amount>
    # Amount may be negative (payments) e.g. -5,000.00 or positive 22.26 or .66
    txn_re = re.compile(
        r"^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]*\.\d{2})\s*$",
        re.MULTILINE,
    )

    # Determine closing month for year-rollover detection (e.g. Jan statement has Dec txns)
    closing_month_match = re.search(r"Opening/Closing Date\s+\d{2}/\d{2}/\d{2,4}\s*-\s*(\d{2})/", full_text, re.IGNORECASE)
    closing_month = int(closing_month_match.group(1)) if closing_month_match else 12

    rows = []
    for m in txn_re.finditer(activity_text):
        date_str = m.group(1)   # MM/DD
        desc = m.group(2).strip()
        amt_str = m.group(3).replace(",", "")

        # If transaction month is after the closing month, it's from the prior year
        mm = int(date_str.split("/")[0])
        year = stmt_year if mm <= closing_month else stmt_year - 1

        full_date = f"{year}-{date_str.replace('/', '-')}"
        try:
            full_date = pd.to_datetime(full_date, format="%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            pass

        amount = float(amt_str)
        rows.append({"date": full_date, "description": desc, "amount": amount, "account_id": account_id})

    if not rows:
        raise ValueError("No transactions found in the PDF. The statement format may not be supported.")

    df = pd.DataFrame(rows)
    return df


def parse_csv(filepath: str, account_id: int) -> pd.DataFrame:
    """
    Parse a bank/credit-card CSV file into a normalised DataFrame.

    Returns a DataFrame with columns: date, description, amount, account_id.
    Raises ValueError if required columns are missing.
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        raise ValueError(f"Could not read CSV file: {exc}") from exc

    df = _normalise_columns(df)

    missing = [col for col in ("date", "description", "amount") if col not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Clean up
    df["date"] = pd.to_datetime(df["date"], infer_datetime_format=True, errors="coerce")
    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df["description"] = df["description"].astype(str).str.strip()
    df["account_id"] = account_id
    df = df.dropna(subset=["date", "amount"])
    df = df[["date", "description", "amount", "account_id"]]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return df
