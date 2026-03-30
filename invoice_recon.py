"""
invoice_recon.py — Portal42 Invoice Reconciliation widget.

Flow:
  1. Upload Dart Bank deposit CSV.
  2. Fetch open invoices from FreshBooks via API.
  3. Match deposits to invoices (company name + amount).
  4. Review matches; approve the ones that are correct.
  5. Mark approved matches as paid in FreshBooks via API (idempotent).
  6. Summary: invoices still open + Dart rows with no match.
  7. Optionally finalize approved income to the business ledger.

FreshBooks is not written to until Step 5 is explicitly triggered.
The business ledger is not touched until Step 7 is explicitly confirmed.
"""

import hashlib
import json
import tempfile
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import httpx
import pandas as pd
import streamlit as st

import q42_db


# ── FreshBooks API ─────────────────────────────────────────────────────────────

_FB_BASE = "https://api.freshbooks.com"
# v3_status values that mean the invoice is still open/collectible
_FB_OPEN_STATUSES = {"sent", "viewed", "partial", "overdue", "disputed"}


def _fb_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Api-Version": "alpha", "Content-Type": "application/json"}


def _fb_creds() -> tuple[str, str]:
    """
    Return (access_token, account_id) from the stored FreshBooks connection.
    Raises ValueError if not connected or missing fields.
    """
    rec = q42_db.get_connection_status("freshbooks")
    token = rec.get("access_token", "")
    acct  = rec.get("company_id", "")
    if not token or rec.get("status") != "connected":
        raise ValueError("FreshBooks is not connected. Connect it on the Connections page first.")
    if not acct:
        raise ValueError("FreshBooks account ID is missing. Reconnect on the Connections page.")
    return token, acct


def fb_fetch_open_invoices() -> list:
    """
    Fetch all open (unpaid) invoices from FreshBooks.
    Returns list of dicts: id | invoice_number | client | amount | date | status
    """
    token, acct = _fb_creds()
    url = f"{_FB_BASE}/accounting/account/{acct}/invoices/invoices"

    invoices = []
    page = 1
    per_page = 100

    while True:
        params = {
            "page":     page,
            "per_page": per_page,
        }
        r = httpx.get(url, headers=_fb_headers(token), params=params, timeout=20)
        r.raise_for_status()

        result   = r.json().get("response", {}).get("result", {})
        raw_list = result.get("invoices", [])
        pages    = result.get("pages", 1)

        for inv in raw_list:
            v3 = str(inv.get("v3_status", "")).lower()
            if v3 not in _FB_OPEN_STATUSES:
                continue

            # Prefer outstanding balance; fall back to invoice total
            outstanding = inv.get("outstanding", {})
            total_obj   = inv.get("amount", {})
            amt_str = (
                outstanding.get("amount")
                or total_obj.get("amount")
                or "0"
            )
            try:
                amt = float(amt_str)
            except (ValueError, TypeError):
                continue
            if amt <= 0:
                continue

            invoices.append({
                "id":             str(inv.get("id", "")),
                "invoice_number": str(inv.get("invoice_number") or inv.get("invoicenumber") or ""),
                "client":         str(inv.get("current_organization") or inv.get("organization") or ""),
                "amount":         amt,
                "date":           str(inv.get("create_date") or inv.get("date") or ""),
                "status":         v3,
            })

        if page >= pages:
            break
        page += 1

    return invoices


def fb_create_payment(invoice_id: str, amount: float, date: str) -> str:
    """
    Create a payment record in FreshBooks for one invoice.
    Returns the new payment ID.
    Raises httpx.HTTPStatusError on API error.
    """
    token, acct = _fb_creds()
    url = f"{_FB_BASE}/accounting/account/{acct}/payments/payments"
    payload = {
        "payment": {
            "invoiceid": int(invoice_id),
            "amount":    f"{amount:.2f}",
            "date":      date,
            "type":      "Check",
            "vis_state": 0,
        }
    }
    r = httpx.post(url, headers=_fb_headers(token), json=payload, timeout=20)
    r.raise_for_status()
    payment = r.json().get("response", {}).get("result", {}).get("payment", {})
    return str(payment.get("id", ""))


# ── Confidence thresholds ─────────────────────────────────────────────────────

CONF_MATCHED   = 0.90
CONF_AMBIGUOUS = 0.70


# ── DB schema ─────────────────────────────────────────────────────────────────

def _init_recon_tables() -> None:
    conn = q42_db.get_connection()
    for stmt in [
        """CREATE TABLE IF NOT EXISTS recon_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            csv_file    TEXT    DEFAULT '',
            period      TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'draft',
            summary     TEXT    DEFAULT '{}',
            created_at  TEXT    DEFAULT (datetime('now')),
            updated_at  TEXT    DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS recon_rows (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    INTEGER NOT NULL REFERENCES recon_sessions(id) ON DELETE CASCADE,
            bucket        TEXT    NOT NULL,
            csv_row       TEXT    DEFAULT '{}',
            invoice       TEXT    DEFAULT '{}',
            confidence    REAL    DEFAULT 0.0,
            match_reason  TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'pending',
            fb_payment_id TEXT    DEFAULT '',
            ledger_txn_id INTEGER DEFAULT NULL,
            audit_log     TEXT    DEFAULT '[]',
            created_at    TEXT    DEFAULT (datetime('now')),
            updated_at    TEXT    DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS recon_aliases (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_name   TEXT    NOT NULL,
            canonical  TEXT    NOT NULL,
            session_id INTEGER DEFAULT NULL,
            created_at TEXT    DEFAULT (datetime('now')),
            UNIQUE(raw_name)
        )""",
    ]:
        conn.execute(stmt)
    conn.commit()
    conn.close()


# ── Alias learning ─────────────────────────────────────────────────────────────

def _get_aliases() -> dict:
    conn = q42_db.get_connection()
    try:
        rows = conn.execute("SELECT raw_name, canonical FROM recon_aliases").fetchall()
        return {r["raw_name"]: r["canonical"] for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def _save_alias(raw: str, canonical: str, session_id: int) -> None:
    if not raw or not canonical:
        return
    conn = q42_db.get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO recon_aliases (raw_name, canonical, session_id) VALUES (?,?,?)",
        (raw.strip().lower(), canonical.strip(), session_id),
    )
    conn.commit()
    conn.close()


def _resolve_alias(name: str, aliases: dict) -> str:
    return aliases.get(name.strip().lower(), name)


# ── Deposit CSV parsing ───────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    import re
    name = str(name).upper().strip()
    name = re.sub(r"[^A-Z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    for prefix in [
        "ACH DEPOSIT ", "ACH CR ", "WIRE FROM ", "DIRECT DEP ",
        "DDA CREDIT ", "ORIG CO NAME:", "MEMO:",
    ]:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    return name


def _parse_date(s: str) -> str:
    s = str(s).strip()
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%m/%d/%y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def _find_col(df: pd.DataFrame, candidates: list) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def parse_deposit_csv(path: str) -> pd.DataFrame:
    """
    Auto-detect date, description, and credit/amount columns.
    Returns only rows with amount > 0 (deposits / credits).
    Columns: date | amount | description | raw_description | _row_hash
    """
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    date_col = _find_col(df, ["date", "posted date", "transaction date", "trans date", "post date", "value date"])
    desc_col = _find_col(df, ["description", "merchant", "payee", "memo", "name", "details", "narrative"])
    amt_col  = _find_col(df, ["credit", "deposit", "credits", "amount credited", "deposit amount"])
    if not amt_col:
        amt_col = _find_col(df, ["amount", "transaction amount", "debit/credit"])

    missing = [lbl for lbl, col in [("date", date_col), ("description", desc_col), ("amount", amt_col)] if not col]
    if missing:
        raise ValueError(
            f"Could not detect column(s): {missing}. Found: {list(df.columns)}. "
            "Expected headers like: date, description, amount (or credit/deposit)."
        )

    rows = []
    for _, row in df.iterrows():
        raw_amt = (
            str(row.get(amt_col, ""))
            .replace(",", "").replace("$", "")
            .replace("(", "-").replace(")", "").strip()
        )
        if not raw_amt or raw_amt.lower() == "nan":
            continue
        try:
            amt = float(raw_amt)
        except ValueError:
            continue
        if amt <= 0:
            continue

        raw_desc = str(row.get(desc_col, "")).strip()
        date_str = _parse_date(str(row.get(date_col, "")))
        row_hash = hashlib.md5(f"{date_str}|{amt}|{raw_desc}".encode()).hexdigest()

        rows.append({
            "date":            date_str,
            "amount":          amt,
            "description":     _normalize_name(raw_desc),
            "raw_description": raw_desc,
            "_row_hash":       row_hash,
        })

    if not rows:
        raise ValueError("No positive deposit rows found. Verify the CSV has credit/deposit entries.")
    return pd.DataFrame(rows)


# ── Match engine ──────────────────────────────────────────────────────────────

def _name_sim(a: str, b: str) -> float:
    a = _normalize_name(a)
    b = _normalize_name(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _ref_in_desc(description: str, invoice_number: str) -> bool:
    if not invoice_number:
        return False
    clean_inv  = invoice_number.replace("-", "").replace("#", "").upper().strip()
    clean_desc = description.replace("-", "").upper()
    return bool(clean_inv) and clean_inv in clean_desc


def run_match_engine(
    deposits: pd.DataFrame,
    invoices: list,
    aliases: dict,
    tolerance: float = 0.01,
    strict: bool = False,
) -> dict:
    """
    Match each deposit row against open FreshBooks invoices.

    Confidence:
      name_similarity × 0.70
      + 0.30 if invoice number found in deposit description
      boosted to 0.85 if name_sim ≥ 0.80 (without ref match)
      strict mode: name < 85% and no ref → capped at 0.65

    Buckets: matched | ambiguous | unmatched | unpaid
    """
    matched   = []
    ambiguous = []
    unmatched = []
    matched_invoice_ids: set = set()

    for _, dep in deposits.iterrows():
        dep_name = _resolve_alias(dep["description"], aliases)
        dep_amt  = float(dep["amount"])

        candidates = [
            inv for inv in invoices
            if abs(dep_amt - inv["amount"]) <= tolerance
        ]

        if not candidates:
            unmatched.append({
                "csv_row":      dep.to_dict(),
                "invoice":      {},
                "confidence":   0.0,
                "match_reason": f"No open invoice matches deposit of ${dep_amt:,.2f}",
                "bucket":       "unmatched",
            })
            continue

        scored = []
        for inv in candidates:
            sim     = _name_sim(dep_name, inv["client"])
            ref_hit = _ref_in_desc(dep["description"], inv["invoice_number"])
            conf = sim * 0.70
            if ref_hit:
                conf += 0.30
            elif sim >= 0.80:
                conf = max(conf, 0.85)
            if strict and sim < 0.85 and not ref_hit:
                conf = min(conf, 0.65)
            scored.append((conf, inv, sim, ref_hit))

        scored.sort(key=lambda x: -x[0])
        best_conf, best_inv, best_sim, best_ref = scored[0]

        parts = [f"${dep_amt:,.2f} amount match"]
        if best_ref:
            parts.append(f"invoice # '{best_inv['invoice_number']}' in description")
        else:
            parts.append(f"name similarity {best_sim:.0%} vs '{best_inv['client']}'")
        reason = " · ".join(parts)

        entry = {
            "csv_row":      dep.to_dict(),
            "invoice":      best_inv,
            "confidence":   best_conf,
            "match_reason": reason,
            "candidates":   [{"invoice": inv, "confidence": c} for c, inv, _, _ in scored],
        }

        if best_conf >= CONF_MATCHED:
            entry["bucket"] = "matched"
            matched.append(entry)
            matched_invoice_ids.add(best_inv["id"])
        elif best_conf >= CONF_AMBIGUOUS:
            entry["bucket"] = "ambiguous"
            ambiguous.append(entry)
        else:
            entry["bucket"] = "unmatched"
            unmatched.append(entry)

    unpaid = [
        {
            "csv_row":      {},
            "invoice":      inv,
            "confidence":   0.0,
            "match_reason": "Invoice not found in statement",
            "bucket":       "unpaid",
        }
        for inv in invoices
        if inv["id"] not in matched_invoice_ids
    ]

    return {"matched": matched, "ambiguous": ambiguous, "unmatched": unmatched, "unpaid": unpaid}


# ── Session DB helpers ─────────────────────────────────────────────────────────

def _create_session(name: str, csv_file: str, period: str) -> int:
    conn = q42_db.get_connection()
    cur = conn.execute(
        "INSERT INTO recon_sessions (name, csv_file, period) VALUES (?,?,?)",
        (name, csv_file, period),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def _save_rows(session_id: int, results: dict) -> None:
    summary = {k: len(v) for k, v in results.items()}
    conn = q42_db.get_connection()
    for bucket, rows in results.items():
        for row in rows:
            conn.execute(
                "INSERT INTO recon_rows "
                "(session_id, bucket, csv_row, invoice, confidence, match_reason) "
                "VALUES (?,?,?,?,?,?)",
                (session_id, bucket,
                 json.dumps(row.get("csv_row", {})),
                 json.dumps(row.get("invoice", {})),
                 row.get("confidence", 0.0),
                 row.get("match_reason", "")),
            )
    conn.execute(
        "UPDATE recon_sessions SET summary=?, updated_at=datetime('now') WHERE id=?",
        (json.dumps(summary), session_id),
    )
    conn.commit()
    conn.close()


def _get_sessions() -> list:
    conn = q42_db.get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM recon_sessions ORDER BY created_at DESC"
        ).fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def _get_session_rows(session_id: int) -> list:
    conn = q42_db.get_connection()
    rows = conn.execute(
        "SELECT * FROM recon_rows WHERE session_id=? ORDER BY bucket, confidence DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["csv_row"]   = json.loads(d["csv_row"])
        d["invoice"]   = json.loads(d["invoice"])
        d["audit_log"] = json.loads(d["audit_log"])
        out.append(d)
    return out


def _update_row(row_id: int, status: str, fb_payment_id: str = "", note: str = "") -> None:
    conn = q42_db.get_connection()
    row = conn.execute("SELECT audit_log FROM recon_rows WHERE id=?", (row_id,)).fetchone()
    audit = json.loads(row["audit_log"]) if row else []
    audit.append({"ts": datetime.now().isoformat(), "status": status, "note": note})
    conn.execute(
        "UPDATE recon_rows SET status=?, fb_payment_id=?, audit_log=?, updated_at=datetime('now') WHERE id=?",
        (status, fb_payment_id, json.dumps(audit), row_id),
    )
    conn.commit()
    conn.close()


def _finalize_to_ledger(session_id: int) -> dict:
    """
    Write approved rows into q42_transactions as Business Income.
    Idempotent via source_hash. Only runs after FreshBooks has been marked.
    """
    rows     = _get_session_rows(session_id)
    approved = [r for r in rows if r["status"] == "paid_fb" and r["csv_row"]]

    if not approved:
        return {"inserted": 0, "dupes": 0}

    conn = q42_db.get_connection()
    cur  = conn.execute(
        "INSERT INTO q42_imports "
        "(filename, account_label, source_type, period_start, period_end, total_in, total_out, txn_count) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (f"recon_session_{session_id}", "Invoice Reconciliation", "invoice_recon", "", "", 0.0, 0.0, len(approved)),
    )
    import_id = cur.lastrowid
    inserted = dupes = 0
    total_in = 0.0

    for r in approved:
        dep    = r["csv_row"]
        inv    = r["invoice"]
        amt    = float(dep.get("amount", 0))
        date   = dep.get("date", "")
        desc   = dep.get("raw_description") or dep.get("description", "")
        client = inv.get("client") or dep.get("description", "")
        src_hash = hashlib.md5(f"recon_{session_id}_{r['id']}".encode()).hexdigest()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO q42_transactions "
                "(import_id, date, description, merchant_name, amount, tax_category, "
                "deductible_amt, is_personal, source_hash, data_source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (import_id, date, desc, client, amt, "Business Income", 0.0, 0, src_hash, "invoice_recon"),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
                total_in += amt
            else:
                dupes += 1
        except Exception:
            dupes += 1

    conn.execute(
        "UPDATE q42_imports SET total_in=?, txn_count=? WHERE id=?",
        (round(total_in, 2), inserted, import_id),
    )
    conn.execute(
        "UPDATE recon_sessions SET status='finalized', updated_at=datetime('now') WHERE id=?",
        (session_id,),
    )
    conn.commit()
    conn.close()
    return {"inserted": inserted, "dupes": dupes}


# ── AI context ────────────────────────────────────────────────────────────────

def get_latest_recon_summary() -> str:
    sessions = _get_sessions()
    if not sessions:
        return ""
    s = sessions[0]
    d = json.loads(s.get("summary", "{}"))
    return (
        f"Latest invoice reconciliation: '{s['name']}' (period: {s['period'] or 'unset'}) — "
        f"{d.get('matched', 0)} matched, {d.get('ambiguous', 0)} needs review, "
        f"{d.get('unmatched', 0)} unmatched Dart deposits, {d.get('unpaid', 0)} unpaid FreshBooks invoices. "
        f"Status: {s['status']}."
    )


# ── UI helpers ────────────────────────────────────────────────────────────────

def _pill(status: str) -> str:
    palette = {
        "pending":   ("#94a3b8", "#1e293b"),
        "approved":  ("#fbbf24", "#2d1f00"),
        "paid_fb":   ("#4ade80", "#052e16"),
        "rejected":  ("#f87171", "#2d0000"),
        "finalized": ("#60a5fa", "#0f1e40"),
    }
    labels = {
        "pending":  "PENDING",
        "approved": "APPROVED",
        "paid_fb":  "PAID IN FB",
        "rejected": "REJECTED",
    }
    fg, bg = palette.get(status, ("#94a3b8", "#1e293b"))
    label  = labels.get(status, status.upper())
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 9px;'
        f'border-radius:4px;font-size:0.76rem;font-weight:700;letter-spacing:0.04em">'
        f'{label}</span>'
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def render_invoice_recon():
    _init_recon_tables()

    st.title("Invoice Reconciliation")
    st.caption(
        "Upload your Dart Bank deposit CSV → fetch open FreshBooks invoices → "
        "match by company name and amount → mark matches as paid."
    )

    sessions = _get_sessions()

    c_new, c_load = st.columns([1, 3])
    with c_new:
        if st.button("＋ New Session", type="primary", use_container_width=True):
            for k in ["recon_session_id", "recon_confirm_fb", "recon_confirm_ledger"]:
                st.session_state.pop(k, None)
            st.rerun()

    if sessions:
        with c_load:
            labels = [
                f"{s['name']}  ·  {s['status'].upper()}  ·  {s['created_at'][:10]}"
                for s in sessions
            ]
            sel = st.selectbox(
                "Load session",
                range(len(sessions)),
                format_func=lambda i: labels[i],
                label_visibility="collapsed",
                key="recon_session_sel",
            )
            if st.button("Load", use_container_width=False):
                for k in ["recon_session_id", "recon_confirm_fb", "recon_confirm_ledger"]:
                    st.session_state.pop(k, None)
                st.session_state["recon_session_id"] = sessions[sel]["id"]
                st.rerun()

    st.divider()

    active = st.session_state.get("recon_session_id")
    if active:
        _session_view(active)
    else:
        _upload_phase()


# ── Upload & match phase ──────────────────────────────────────────────────────

def _upload_phase():
    st.subheader("New Session")

    lc1, lc2 = st.columns(2)
    with lc1:
        name = st.text_input("Session name", placeholder="e.g. March 2026 Invoices")
    with lc2:
        period = st.text_input("Period", placeholder="e.g. 2026-03")

    st.markdown("#### Upload Dart Bank deposit CSV")
    st.caption("Rex auto-detects date, description, and amount columns. Only deposit / credit rows are used.")
    dep_file = st.file_uploader(
        "Dart Bank CSV",
        type=["csv"],
        key="recon_dep_file",
        label_visibility="collapsed",
    )

    dep_df   = None
    dep_path = None

    if dep_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as t:
            t.write(dep_file.read())
            dep_path = t.name
        try:
            dep_df = parse_deposit_csv(dep_path)
            st.success(f"**{len(dep_df)} deposit rows** detected.")
            st.dataframe(dep_df[["date", "amount", "description"]].head(8), use_container_width=True)
        except Exception as e:
            st.error(f"CSV error: {e}")

    if dep_df is not None:
        st.divider()
        oc1, oc2, _ = st.columns([1, 1, 2])
        with oc1:
            tolerance = st.number_input(
                "Amount tolerance ($)",
                min_value=0.0, max_value=10.0,
                value=0.01, step=0.01,
                help="How close the deposit amount and invoice amount need to be.",
            )
        with oc2:
            strict = st.toggle("Strict mode", value=False, help="Name similarity ≥ 85% required.")

        if st.button("Fetch FreshBooks Invoices & Match", type="primary"):
            try:
                with st.spinner("Fetching open invoices from FreshBooks…"):
                    invoices = fb_fetch_open_invoices()
                if not invoices:
                    st.warning("No open invoices found in FreshBooks for this account.")
                    return
                st.success(f"Fetched **{len(invoices)} open invoices** from FreshBooks.")

                aliases = _get_aliases()
                with st.spinner("Running match engine…"):
                    results = run_match_engine(dep_df, invoices, aliases, tolerance=tolerance, strict=strict)

                session_name = name.strip() or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                sid = _create_session(
                    name=session_name,
                    csv_file=dep_file.name if dep_file else "",
                    period=period,
                )
                _save_rows(sid, results)
                st.session_state["recon_session_id"] = sid
                st.rerun()

            except ValueError as e:
                st.error(str(e))
            except httpx.HTTPStatusError as e:
                st.error(f"FreshBooks API error {e.response.status_code}: {e.response.text[:300]}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")


# ── Session view ──────────────────────────────────────────────────────────────

def _session_view(session_id: int):
    conn = q42_db.get_connection()
    sess_row = conn.execute("SELECT * FROM recon_sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    if not sess_row:
        st.error("Session not found.")
        return

    sess    = dict(sess_row)
    summary = json.loads(sess.get("summary", "{}"))
    status  = sess["status"]

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.subheader(sess["name"])
        st.caption(
            f"Period: **{sess['period'] or '—'}** · "
            f"File: {sess['csv_file'] or '—'} · "
            f"Created: {sess['created_at'][:10]}"
        )
    with hc2:
        st.markdown(_pill(status if status in ("pending", "paid_fb", "finalized") else "pending"), unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Matched",            summary.get("matched",   0))
    k2.metric("Needs Review",       summary.get("ambiguous", 0))
    k3.metric("Unmatched (Dart)",   summary.get("unmatched", 0))
    k4.metric("Unpaid (FreshBooks)", summary.get("unpaid",   0))

    st.divider()

    all_rows   = _get_session_rows(session_id)
    matched_r  = [r for r in all_rows if r["bucket"] == "matched"]
    ambig_r    = [r for r in all_rows if r["bucket"] == "ambiguous"]
    unmatch_r  = [r for r in all_rows if r["bucket"] == "unmatched"]
    unpaid_r   = [r for r in all_rows if r["bucket"] == "unpaid"]

    t_m, t_r, t_u, t_p, t_s = st.tabs([
        f"Matched ({len(matched_r)})",
        f"Needs Review ({len(ambig_r)})",
        f"Unmatched Dart Rows ({len(unmatch_r)})",
        f"Unpaid Invoices ({len(unpaid_r)})",
        "Summary",
    ])

    with t_m:
        _tab_matched(matched_r, session_id, status)
    with t_r:
        _tab_review(ambig_r, session_id, status)
    with t_u:
        _tab_unmatched(unmatch_r)
    with t_p:
        _tab_unpaid(unpaid_r)
    with t_s:
        _tab_summary(session_id, all_rows, sess, status)


# ── Tab: Matched ──────────────────────────────────────────────────────────────

def _tab_matched(rows: list, session_id: int, sess_status: str):
    if not rows:
        st.info("No high-confidence matches in this session.")
        return

    pending = [r for r in rows if r["status"] == "pending"]
    if pending and sess_status != "finalized":
        ac, _ = st.columns([1, 4])
        if ac.button("Approve All", type="primary", use_container_width=True, key="approve_all"):
            for r in pending:
                _update_row(r["id"], "approved", note="Batch approved")
                _save_alias(r["csv_row"].get("description", ""), r["invoice"].get("client", ""), session_id)
            st.rerun()

    for r in rows:
        dep  = r["csv_row"]
        inv  = r["invoice"]
        c1, c2, c3, c4 = st.columns([3, 3, 1, 2])
        c1.markdown(
            f"**{dep.get('description', '—')}**  \n"
            f"<small style='color:#64748b'>{dep.get('date', '')}</small>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"Inv `{inv.get('invoice_number', '—')}` — {inv.get('client', '—')}  \n"
            f"<small style='color:#64748b'>{r['match_reason']}</small>",
            unsafe_allow_html=True,
        )
        c3.markdown(f"**${dep.get('amount', 0):,.2f}**  \n{r['confidence']:.0%}")
        with c4:
            st.markdown(_pill(r["status"]), unsafe_allow_html=True)
            if r["status"] == "pending" and sess_status != "finalized":
                b1, b2 = st.columns(2)
                if b1.button("✓", key=f"ma_{r['id']}", help="Approve"):
                    _update_row(r["id"], "approved")
                    _save_alias(dep.get("description", ""), inv.get("client", ""), session_id)
                    st.rerun()
                if b2.button("✗", key=f"mr_{r['id']}", help="Reject"):
                    _update_row(r["id"], "rejected")
                    st.rerun()
        st.divider()


# ── Tab: Needs Review ─────────────────────────────────────────────────────────

def _tab_review(rows: list, session_id: int, sess_status: str):
    if not rows:
        st.success("Nothing needs manual review.")
        return

    st.caption("Amount matched but name similarity is below the auto-approve threshold.")

    for r in rows:
        dep    = r["csv_row"]
        inv    = r["invoice"]
        status = r["status"]

        with st.expander(
            f"{dep.get('description', '—')}  ·  ${dep.get('amount', 0):,.2f}  ·  {r['confidence']:.0%}",
            expanded=(status == "pending"),
        ):
            ec1, ec2 = st.columns(2)
            with ec1:
                st.markdown("**Dart deposit**")
                st.markdown(f"Date: `{dep.get('date', '')}`  \nAmount: `${dep.get('amount', 0):,.2f}`  \nDescription: `{dep.get('raw_description', '')}`")
            with ec2:
                st.markdown("**FreshBooks invoice**")
                st.markdown(
                    f"Inv #: `{inv.get('invoice_number', '—')}`  \n"
                    f"Client: `{inv.get('client', '—')}`  \n"
                    f"Amount: `${inv.get('amount', 0):,.2f}`  \n"
                    f"Date: `{inv.get('date', '')}`"
                )
            st.caption(r["match_reason"])
            st.markdown(_pill(status), unsafe_allow_html=True)
            if status == "pending" and sess_status != "finalized":
                ra1, ra2, _ = st.columns([1, 1, 3])
                if ra1.button("Approve", type="primary", key=f"ra_{r['id']}"):
                    _update_row(r["id"], "approved", note="Manual review: approved")
                    _save_alias(dep.get("description", ""), inv.get("client", ""), session_id)
                    st.rerun()
                if ra2.button("Reject", key=f"rr_{r['id']}"):
                    _update_row(r["id"], "rejected", note="Manual review: rejected")
                    st.rerun()


# ── Tab: Unmatched Dart rows ──────────────────────────────────────────────────

def _tab_unmatched(rows: list):
    if not rows:
        st.success("Every Dart deposit matched a FreshBooks invoice.")
        return

    st.caption(
        "Dart Bank deposit rows that could not be matched to any open FreshBooks invoice. "
        "These are not written to FreshBooks or the ledger."
    )
    data = pd.DataFrame([
        {
            "Date":        r["csv_row"].get("date", ""),
            "Amount":      f"${r['csv_row'].get('amount', 0):,.2f}",
            "Description": r["csv_row"].get("raw_description") or r["csv_row"].get("description", ""),
            "Reason":      r["match_reason"],
        }
        for r in rows
    ])
    st.dataframe(data, use_container_width=True)
    st.download_button(
        "Export CSV",
        data=data.to_csv(index=False),
        file_name=f"dart_unmatched_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ── Tab: Unpaid Invoices ──────────────────────────────────────────────────────

def _tab_unpaid(rows: list):
    if not rows:
        st.success("All open FreshBooks invoices were found in the Dart statement.")
        return

    st.caption("Open FreshBooks invoices not found in this Dart Bank statement. These remain outstanding.")
    data = pd.DataFrame([
        {
            "Invoice #": r["invoice"].get("invoice_number", ""),
            "Client":    r["invoice"].get("client", ""),
            "Amount":    f"${r['invoice'].get('amount', 0):,.2f}",
            "Date":      r["invoice"].get("date", ""),
            "Status":    r["invoice"].get("status", ""),
        }
        for r in rows
    ])
    st.dataframe(data, use_container_width=True)
    st.download_button(
        "Export CSV",
        data=data.to_csv(index=False),
        file_name=f"freshbooks_unpaid_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ── Tab: Summary ──────────────────────────────────────────────────────────────

def _tab_summary(session_id: int, all_rows: list, sess: dict, sess_status: str):
    approved  = [r for r in all_rows if r["status"] == "approved"  and r["csv_row"]]
    paid_fb   = [r for r in all_rows if r["status"] == "paid_fb"   and r["csv_row"]]
    pending   = [r for r in all_rows if r["status"] == "pending"]
    unmatched = [r for r in all_rows if r["bucket"] == "unmatched"]
    unpaid    = [r for r in all_rows if r["bucket"] == "unpaid"]

    approved_amt = sum(float(r["csv_row"].get("amount", 0)) for r in approved)
    paid_amt     = sum(float(r["csv_row"].get("amount", 0)) for r in paid_fb)
    unmatched_amt = sum(float(r["csv_row"].get("amount", 0)) for r in unmatched if r["csv_row"])
    unpaid_amt    = sum(float(r["invoice"].get("amount", 0)) for r in unpaid if r["invoice"])

    st.markdown("#### Session summary")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Approved (pending FB)", len(approved),  f"${approved_amt:,.2f}")
    sc2.metric("Paid in FreshBooks",    len(paid_fb),   f"${paid_amt:,.2f}")
    sc3.metric("Unmatched Dart rows",   len(unmatched), f"${unmatched_amt:,.2f}")
    sc4.metric("Outstanding invoices",  len(unpaid),    f"${unpaid_amt:,.2f}")

    # ── Mark as Paid in FreshBooks ────────────────────────────────────────────
    st.divider()
    st.markdown("#### Mark approved matches as paid in FreshBooks")

    if sess_status == "finalized":
        st.success("Session finalized. Approved rows were written to FreshBooks and the business ledger.")
        return

    if not approved:
        if paid_fb:
            st.info(f"{len(paid_fb)} rows already marked paid in FreshBooks. Finalize to ledger below.")
        else:
            st.warning("Approve matches on the Matched or Needs Review tabs first.")
    else:
        st.markdown(
            f"**{len(approved)} approved matches** will be marked as paid in FreshBooks. "
            "This creates a payment record on each matched invoice."
        )

        if not st.session_state.get("recon_confirm_fb"):
            if st.button("Mark as Paid in FreshBooks", type="primary"):
                st.session_state["recon_confirm_fb"] = True
                st.rerun()
        else:
            st.warning(f"Confirm: create payment records for {len(approved)} invoice(s) in FreshBooks?")
            fb1, fb2, _ = st.columns([1, 1, 3])
            if fb1.button("Yes, mark paid", type="primary", key="fb_yes"):
                errors = []
                for r in approved:
                    dep = r["csv_row"]
                    inv = r["invoice"]
                    try:
                        pid = fb_create_payment(
                            invoice_id=inv["id"],
                            amount=float(dep.get("amount", 0)),
                            date=dep.get("date", datetime.now().strftime("%Y-%m-%d")),
                        )
                        _update_row(r["id"], "paid_fb", fb_payment_id=pid, note=f"FB payment {pid}")
                    except httpx.HTTPStatusError as e:
                        errors.append(f"Invoice {inv.get('invoice_number', inv['id'])}: {e.response.status_code}")
                    except Exception as e:
                        errors.append(f"Invoice {inv.get('invoice_number', inv['id'])}: {e}")
                st.session_state.pop("recon_confirm_fb", None)
                if errors:
                    st.error("Some payments failed:\n" + "\n".join(errors))
                else:
                    st.success(f"{len(approved)} invoice(s) marked as paid in FreshBooks.")
                st.rerun()
            if fb2.button("Cancel", key="fb_cancel"):
                st.session_state.pop("recon_confirm_fb", None)
                st.rerun()

    # ── Finalize to business ledger ───────────────────────────────────────────
    st.divider()
    st.markdown("#### Finalize to business ledger")

    ready = [r for r in all_rows if r["status"] == "paid_fb" and r["csv_row"]]
    if not ready:
        st.caption("Once matches are marked paid in FreshBooks, you can pull them into the business ledger here.")
        return

    ready_amt = sum(float(r["csv_row"].get("amount", 0)) for r in ready)
    st.markdown(
        f"**{len(ready)} rows totaling ${ready_amt:,.2f}** have been marked paid in FreshBooks "
        "and are ready to write to your business ledger as **Business Income**."
    )

    if not st.session_state.get("recon_confirm_ledger"):
        if st.button("Finalize to Business Ledger", type="secondary"):
            st.session_state["recon_confirm_ledger"] = True
            st.rerun()
    else:
        st.warning("Confirm: write these rows permanently to the business ledger?")
        lc1, lc2, _ = st.columns([1, 1, 3])
        if lc1.button("Yes, Finalize", type="primary", key="led_yes"):
            result = _finalize_to_ledger(session_id)
            st.session_state.pop("recon_confirm_ledger", None)
            st.success(
                f"Done: **{result['inserted']} records** written to business ledger"
                + (f", {result['dupes']} duplicate(s) skipped." if result["dupes"] else ".")
            )
            st.rerun()
        if lc2.button("Cancel", key="led_cancel"):
            st.session_state.pop("recon_confirm_ledger", None)
            st.rerun()
