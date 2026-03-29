import pandas as pd
import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Institution registry
# ---------------------------------------------------------------------------

class UnknownInstitutionError(Exception):
    """Raised when a PDF cannot be matched to any known institution parser."""
    def __init__(self, filepath: str, raw_text: str):
        self.filepath = filepath
        self.raw_text = raw_text
        super().__init__(f"Unknown institution format: {filepath}")

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


def _parse_dollar(text: str, pattern: str) -> Optional[float]:
    """Extract a dollar amount from text using a regex pattern with one capture group."""
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace("$", "").replace("+", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def parse_chase_pdf(filepath: str, account_id: int) -> tuple:
    """
    Parse a Chase credit card PDF statement.

    Returns:
        (df, meta) where df has columns [date, description, amount, account_id]
        and meta is a dict with keys:
            opening_date, closing_date,
            opening_balance, closing_balance,
            total_charges, total_credits
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required to parse PDFs. Run: pip3 install pdfplumber")

    try:
        pdf = pdfplumber.open(filepath)
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    full_text = ""
    with pdf:
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    # --- Statement dates ---
    date_match = re.search(
        r"Opening/Closing Date\s+(\d{2}/\d{2}/\d{2,4})\s*-\s*(\d{2}/\d{2}/\d{2,4})",
        full_text, re.IGNORECASE
    )

    def _to_iso(mmddyy: str) -> str:
        parts = mmddyy.split("/")
        mm, dd, yy = parts
        year = int(yy) if len(yy) == 4 else 2000 + int(yy)
        return f"{year}-{mm}-{dd}"

    if date_match:
        opening_date = _to_iso(date_match.group(1))
        closing_date = _to_iso(date_match.group(2))
        stmt_year = int(closing_date[:4])
        closing_month = int(closing_date[5:7])
    else:
        opening_date = closing_date = datetime.now().strftime("%Y-%m-%d")
        stmt_year = datetime.now().year
        closing_month = datetime.now().month

    # --- Statement summary balances ---
    opening_balance = _parse_dollar(full_text, r"Previous Balance\s+\$?([\d,]+\.\d{2})")
    closing_balance = _parse_dollar(full_text, r"New Balance\s+\$?([\d,]+\.\d{2})")
    total_credits_raw = _parse_dollar(full_text, r"Payment[s]?,?\s*Credits?\s+(-?[\$\d,]+\.\d{2})")
    total_charges_raw = _parse_dollar(full_text, r"Purchases\s+\+?\$?([\d,]+\.\d{2})")

    meta = {
        "opening_date": opening_date,
        "closing_date": closing_date,
        "opening_balance": opening_balance or 0.0,
        "closing_balance": closing_balance or 0.0,
        "total_charges": total_charges_raw or 0.0,
        "total_credits": abs(total_credits_raw) if total_credits_raw else 0.0,
    }

    # --- Transactions ---
    activity_match = re.search(r"A+C+O+U+N+T+\s+A+C+T+I+V+I+T+Y+", full_text, re.IGNORECASE)
    if not activity_match:
        raise ValueError("Could not find ACCOUNT ACTIVITY section in the PDF.")

    activity_text = full_text[activity_match.end():]
    stop_match = re.search(
        r"(TRANSACTIONS THIS CYCLE|Year-to-Date|INTEREST CHARGES\n|IINNTTEERREESSTT|YEAR-TO-DATE TOTALS)",
        activity_text, re.IGNORECASE,
    )
    if stop_match:
        activity_text = activity_text[: stop_match.start()]

    txn_re = re.compile(r"^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]*\.\d{2})\s*$", re.MULTILINE)

    rows = []
    for m in txn_re.finditer(activity_text):
        date_str = m.group(1)
        desc = m.group(2).strip()
        amt_str = m.group(3).replace(",", "")
        mm = int(date_str.split("/")[0])
        year = stmt_year if mm <= closing_month else stmt_year - 1
        full_date = f"{year}-{date_str.replace('/', '-')}"
        try:
            full_date = pd.to_datetime(full_date, format="%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            pass
        rows.append({"date": full_date, "description": desc, "amount": float(amt_str), "account_id": account_id})

    if not rows:
        raise ValueError("No transactions found in the PDF. The statement format may not be supported.")

    return pd.DataFrame(rows), meta


def parse_dart_pdf(filepath: str, account_id: int) -> tuple:
    """
    Parse a Dart Bank 'Enhanced Customer Statement' PDF.

    Dart Bank format:
      - Statement date line: 'Statement Dates 5/01/25 thru 6/01/25'
      - Sections: 'DEPOSITS AND OTHER CREDITS' (positive), 'OTHER DEBITS' (negative)
      - Transaction line: '5 / 0 6  Wire Transfer Credit  1,000.00'
      - Negative amounts end with '-': '10.00-'
      - Stop parsing at: 'DAILY BALANCE SUMMARY'
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required. Run: pip3 install pdfplumber")

    try:
        pdf = pdfplumber.open(filepath)
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    full_text = ""
    with pdf:
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    # --- Statement dates ---
    date_match = re.search(
        r"Statement Dates\s+(\d{1,2}/\d{2}/\d{2,4})\s+thru\s+(\d{1,2}/\d{2}/\d{2,4})",
        full_text, re.IGNORECASE,
    )

    def _dart_to_iso(d: str) -> str:
        parts = d.split("/")
        mm, dd, yy = parts[0].zfill(2), parts[1].zfill(2), parts[2]
        year = int(yy) if len(yy) == 4 else 2000 + int(yy)
        return f"{year}-{mm}-{dd}"

    if date_match:
        opening_date = _dart_to_iso(date_match.group(1))
        closing_date  = _dart_to_iso(date_match.group(2))
        stmt_year     = int(closing_date[:4])
    else:
        opening_date = closing_date = datetime.now().strftime("%Y-%m-%d")
        stmt_year = datetime.now().year

    meta = {
        "opening_date": opening_date,
        "closing_date": closing_date,
        "opening_balance": 0.0,
        "closing_balance": 0.0,
        "total_charges": 0.0,
        "total_credits": 0.0,
    }

    # --- Stop at DAILY BALANCE SUMMARY ---
    stop = re.search(r"DAILY BALANCE SUMMARY", full_text, re.IGNORECASE)
    work_text = full_text[: stop.start()] if stop else full_text

    # --- Transaction line regex ---
    # Matches: '5 / 0 6  Description text  1,234.56-'  or '5 / 0 6  Description  1,234.56'
    txn_re = re.compile(
        r"^\s*(\d\s?\d?\s*/\s*\d\s?\d)\s+(.+?)\s+([\d,]+\.\d{2})(-?)\s*$",
        re.MULTILINE,
    )

    # Determine sign by section: credits = positive, debits = negative
    # We scan the text and track which section we're in.
    credit_section_re = re.compile(r"DEPOSITS AND OTHER CREDITS", re.IGNORECASE)
    debit_section_re  = re.compile(r"OTHER DEBITS", re.IGNORECASE)

    # Build a list of (position, sign) section markers
    markers = []
    for m in credit_section_re.finditer(work_text):
        markers.append((m.start(), +1))
    for m in debit_section_re.finditer(work_text):
        markers.append((m.start(), -1))
    markers.sort()

    def _sign_at(pos: int) -> int:
        """Return the section sign that applies at text position pos."""
        current = +1  # default to positive if no section header seen
        for marker_pos, sign in markers:
            if marker_pos <= pos:
                current = sign
            else:
                break
        return current

    rows = []
    for m in txn_re.finditer(work_text):
        raw_date  = re.sub(r"\s+", "", m.group(1))  # '5/06'
        desc      = m.group(2).strip()
        amt_str   = m.group(3).replace(",", "")
        has_minus = m.group(4) == "-"

        # Parse date — Dart uses M/DD without year
        try:
            date_parts = raw_date.split("/")
            mm, dd = int(date_parts[0]), int(date_parts[1])
            full_date = f"{stmt_year}-{mm:02d}-{dd:02d}"
        except Exception:
            full_date = opening_date

        # Determine sign: trailing minus overrides, otherwise use section
        if has_minus:
            sign = -1
        else:
            sign = _sign_at(m.start())

        amount = sign * float(amt_str)
        rows.append({"date": full_date, "description": desc, "amount": amount, "account_id": account_id})

    if not rows:
        raise ValueError("No transactions found in the Dart Bank PDF.")

    df = pd.DataFrame(rows)
    meta["total_credits"] = float(df[df["amount"] > 0]["amount"].sum())
    meta["total_charges"] = float(df[df["amount"] < 0]["amount"].abs().sum())
    return df, meta


def parse_csv(filepath: str, account_id: int) -> pd.DataFrame:
    """
    Parse a bank/credit-card CSV file into a normalised DataFrame.

    Handles single-amount columns as well as split Debit/Credit columns
    (e.g. Capital One exports).

    Returns a DataFrame with columns: date, description, amount, account_id.
    Raises ValueError if required columns are missing.
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        raise ValueError(f"Could not read CSV file: {exc}") from exc

    lower_cols = {c.lower().strip(): c for c in df.columns}

    # --- Capital One split debit/credit handling ---
    # Cap One exports have separate "Debit" and "Credit" columns; no single Amount.
    has_debit = "debit" in lower_cols
    has_credit = "credit" in lower_cols
    has_amount = "amount" in lower_cols or "transaction amount" in lower_cols

    if (has_debit or has_credit) and not has_amount:
        def _to_float(series):
            return (
                series.astype(str)
                .str.replace(r"[\$,]", "", regex=True)
                .str.strip()
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0.0)
            )
        debit_vals  = _to_float(df[lower_cols["debit"]])  if has_debit  else pd.Series(0.0, index=df.index)
        credit_vals = _to_float(df[lower_cols["credit"]]) if has_credit else pd.Series(0.0, index=df.index)
        # Debits are expenses (negative), credits are income (positive)
        df["amount"] = credit_vals - debit_vals

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


# ---------------------------------------------------------------------------
# Institution detection & auto-dispatch
# ---------------------------------------------------------------------------

# Each entry: (institution_name, display_name, detection_fn, parser_fn)
# detection_fn(text: str) -> bool
# parser_fn(filepath: str, account_id: int) -> (df, meta)

_INSTITUTION_REGISTRY = [
    (
        "chase",
        "Chase Bank",
        lambda t: bool(re.search(r"A+C+O+U+N+T+\s+A+C+T+I+V+I+T+Y+", t, re.IGNORECASE)),
        parse_chase_pdf,
    ),
    (
        "dart",
        "Dart Bank",
        lambda t: (
            "dart atm" in t.lower()
            or bool(re.search(r"Statement Dates\s+\d{1,2}/\d{2}/\d{2}", t, re.IGNORECASE))
        ),
        parse_dart_pdf,
    ),
]


def detect_institution(text: str) -> Optional[str]:
    """
    Return the institution key ('chase', 'dart', …) for the given PDF text,
    or None if no registered parser matches.
    """
    for key, _label, detect_fn, _parser in _INSTITUTION_REGISTRY:
        try:
            if detect_fn(text):
                return key
        except Exception:
            pass
    return None


def get_institution_list() -> list:
    """Return list of (key, display_name) for all registered institutions."""
    return [(key, label) for key, label, _, _ in _INSTITUTION_REGISTRY]


def parse_auto(filepath: str, account_id: int) -> tuple:
    """
    Detect the institution from the PDF and dispatch to the correct parser.

    Raises:
        UnknownInstitutionError — if no registered parser matches, carrying
                                  the raw text for the Parser Workshop.
        ValueError              — if a matched parser fails to extract data.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required. Run: pip3 install pdfplumber")

    try:
        pdf = pdfplumber.open(filepath)
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    full_text = ""
    with pdf:
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    key = detect_institution(full_text)
    if key is None:
        raise UnknownInstitutionError(filepath, full_text)

    # Find the matching parser function
    for inst_key, _label, _detect, parser_fn in _INSTITUTION_REGISTRY:
        if inst_key == key:
            return parser_fn(filepath, account_id)

    raise UnknownInstitutionError(filepath, full_text)
