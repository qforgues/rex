"""
q42_app.py — Portal42 Q42 mode.
Pure accountant / tax-prep interface for self-employed Michigan business owners.
"""

import hashlib
import os
import re
import tempfile
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import parsers
import q42_db
import q42_rex
import parser_workshop
import gl_csv_profiles
import invoice_recon


# ---------------------------------------------------------------------------
# OAuth config — read once from .env, never entered manually
# ---------------------------------------------------------------------------

def _oauth_cfg() -> dict:
    """Return permanent OAuth credentials from environment variables."""
    return {
        "redirect_uri":    os.environ.get("REDIRECT_URI", "https://rex.myeasyapp.com").rstrip("/"),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _copyable_error(msg: str) -> None:
    """Render an error label + copyable code block (native copy button top-right)."""
    st.error("Import error — copy details below")
    st.code(msg, language=None)


def _stmt_date_label(filename: str, fallback: str = "") -> str:
    """
    Extract the statement date from a filename and return it as 'D Mon YY'.
    E.g. 'Portal42_...May_2025_05_30_2025.pdf' → '30 May 25'.
    Falls back to the period_end date from the import record if no date found in filename.
    """
    # MM_DD_YYYY at end of filename (before extension)
    m = re.search(r"(\d{2})_(\d{2})_(\d{4})(?:\.\w+)?$", filename)
    if m:
        try:
            from datetime import date as _date
            d = _date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            return d.strftime("%-d %b %y")
        except Exception:
            pass
    # YYYY-MM-DD fallback (period_end from DB)
    if fallback:
        try:
            d = datetime.strptime(fallback[:10], "%Y-%m-%d")
            return d.strftime("%-d %b %y")
        except Exception:
            pass
    return filename


# Dev log helpers
# ---------------------------------------------------------------------------

def _q42_log(msg: str) -> None:
    from datetime import datetime as _dt
    if "q42_dev_log" not in st.session_state:
        st.session_state["q42_dev_log"] = []
    st.session_state["q42_dev_log"].append(
        f"[{_dt.now().strftime('%H:%M:%S')}] {msg}"
    )

# ---------------------------------------------------------------------------
# Wire animation CSS — the visual heart of the Connections page
# ---------------------------------------------------------------------------
_WIRE_CSS = """<style>
.wire-rig {
    display: flex; align-items: center; padding: 28px 0 8px 0; gap: 0;
    user-select: none;
}
.svc-box {
    padding: 14px 20px; border-radius: 10px; font-weight: 700;
    font-size: 0.95rem; min-width: 100px; text-align: center;
    font-family: 'SF Mono', 'Courier New', monospace; letter-spacing: 0.06em;
    flex-shrink: 0;
}
.svc-fb   { background: #1e3a5f; color: #93c5fd; border: 2px solid #3b82f6; }
.svc-rex  { background: #0f172a; color: #cbd5e1; border: 2px solid #334155; }

/* Wire halves */
.wire-half { height: 6px; flex: 1; position: relative; }
.wire-bar  { height: 100%; border-radius: 3px; background: #374151; transition: all 0.6s ease; }

/* Jagged broken ends */
.break-tip-r {
    position: absolute; right: -11px; top: -6px;
    width: 0; height: 0;
    border-top: 9px solid transparent;
    border-bottom: 9px solid transparent;
    border-left: 13px solid #374151;
    transition: opacity 0.4s;
}
.break-tip-l {
    position: absolute; left: -11px; top: -6px;
    width: 0; height: 0;
    border-top: 9px solid transparent;
    border-bottom: 9px solid transparent;
    border-right: 13px solid #374151;
    transition: opacity 0.4s;
}
.gap-zone {
    width: 52px; text-align: center; font-size: 0.65rem;
    color: #4b5563; flex-shrink: 0; letter-spacing: 0.1em;
}

/* Connected states — hide jagged tips, add glow */
.wire-full-fb  .break-tip-r,
.wire-full-fb  .break-tip-l { display: none; }

.wire-full-fb .wire-bar {
    background: linear-gradient(90deg, #3b82f6, #2563eb);
    box-shadow: 0 0 10px #3b82f680, 0 0 20px #3b82f630;
    animation: glow-fb 2s ease-in-out infinite;
}
@keyframes glow-fb {
    0%,100% { box-shadow: 0 0 8px #3b82f680,  0 0 16px #3b82f620; }
    50%      { box-shadow: 0 0 20px #3b82f6a0, 0 0 40px #3b82f650; }
}
.status-line { font-size: 0.82rem; color: #94a3b8; margin-bottom: 12px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.dot-green { background: #22c55e; box-shadow: 0 0 5px #22c55e; }
.dot-blue  { background: #3b82f6; box-shadow: 0 0 5px #3b82f6; }
.dot-grey  { background: #4b5563; }
</style>"""




# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _handle_oauth_callbacks() -> bool:
    """
    Detect and complete OAuth callbacks.
    Currently handles QBO only (FreshBooks removed).
    Returns True if a callback was processed.
    """
    return False


@st.dialog("Dev Log", width="large")
def _show_dev_log_modal():
    log_entries = st.session_state.get("q42_dev_log", [])
    if not log_entries:
        st.info("Log is empty.")
        return
    log_text = "\n".join(log_entries)
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇ Download log", data=log_text,
        file_name="q42_log.txt", mime="text/plain",
        use_container_width=True,
    )
    if c2.button("🗑 Clear log", use_container_width=True):
        st.session_state["q42_dev_log"] = []
        st.rerun()
    st.code(log_text, language=None)


def render_q42():
    """Called from app.py when Q42 profile is active."""
    q42_db.init_q42_db()

    # Handle OAuth callbacks (FreshBooks or QBO) before any rendering.
    # The callback arrives through the Cloudflare tunnel (rex.myeasyapp.com),
    # where Streamlit's JS modules don't load. The server-side code above
    # exchanges the code and saves tokens regardless. We just need to get the
    # user back to localhost. Use st.markdown with a meta-refresh + JS fallback
    # so it works even when Streamlit's module system is broken.
    if _handle_oauth_callbacks():
        st.markdown(
            '<meta http-equiv="refresh" content="1;url=http://localhost:8501/?profile=Q42">'
            '<p style="font-family:sans-serif;padding:40px;text-align:center">'
            'Connection saved! Redirecting to <a href="http://localhost:8501/?profile=Q42">localhost:8501</a>...'
            '</p>'
            '<script>window.location.href="http://localhost:8501/?profile=Q42";</script>',
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Sidebar ──────────────────────────────────────────────────────────
    st.sidebar.markdown("""
<div style="text-align:center;padding:6px 0 10px">
  <div style="font-size:1.25rem;font-weight:800;color:#60a5fa;letter-spacing:0.1em">PORTAL42</div>
  <div style="font-size:0.62rem;color:#475569;letter-spacing:0.14em;text-transform:uppercase;margin-top:2px">Tax Advisor Mode</div>
</div>""", unsafe_allow_html=True)

    _nav_options = ["Overview", "Transactions", "Tax Report", "Ask Rex", "Invoice Recon", "Parser Workshop"]
    # Apply any pending programmatic navigation BEFORE the widget is instantiated
    if "q42_nav_pending" in st.session_state:
        st.session_state["q42_nav_radio"] = st.session_state.pop("q42_nav_pending")
    if "q42_nav_radio" not in st.session_state:
        _restored = st.query_params.get("page", "Overview")
        st.session_state["q42_nav_radio"] = _restored if _restored in _nav_options else "Overview"
    page = st.sidebar.radio(
        "Navigate",
        _nav_options,
        label_visibility="collapsed",
        key="q42_nav_radio",
    )
    st.query_params["profile"] = "Q42"
    st.query_params["page"] = page

    summary = q42_db.get_period_summary()
    if summary:
        st.sidebar.divider()
        st.sidebar.caption("PERIOD SNAPSHOT")
        st.sidebar.metric("Total In",        f"${summary.get('total_in', 0):,.0f}")
        st.sidebar.metric("Total Out",       f"${summary.get('total_out', 0):,.0f}")
        st.sidebar.metric("Est. Deductible", f"${summary.get('total_deductible', 0):,.0f}")

    st.sidebar.divider()
    q42_dev_mode = st.sidebar.toggle("Dev Mode", value=st.session_state.get("q42_dev_mode", False), key="q42_dev_mode_toggle")
    st.session_state["q42_dev_mode"] = q42_dev_mode

    if q42_dev_mode:
        st.sidebar.divider()
        st.sidebar.caption("⚠️ Danger Zone")
        if st.sidebar.button("Clear All Q42 Data", type="secondary", use_container_width=True):
            conn = q42_db.get_connection()
            conn.execute("DELETE FROM q42_transactions")
            conn.execute("DELETE FROM q42_imports")
            conn.execute("DELETE FROM q42_tax_profile")
            conn.commit()
            conn.close()
            for k in [k for k in st.session_state if k.startswith("q42_")]:
                del st.session_state[k]
            st.rerun()
        if st.sidebar.button("Clear Error Log", use_container_width=True):
            st.session_state["q42_dev_log"] = []
            st.rerun()

    if q42_dev_mode and st.session_state.get("q42_dev_log"):
        log_text = "\n".join(st.session_state["q42_dev_log"])
        n = len(st.session_state["q42_dev_log"])
        st.sidebar.caption(f"📋 Log — {n} entries")
        _lc1, _lc2 = st.sidebar.columns(2)
        _lc1.download_button(
            "⬇ Log", data=log_text,
            file_name="q42_log.txt", mime="text/plain",
            use_container_width=True,
        )
        if _lc2.button("👁 View", use_container_width=True, key="q42_view_log_btn"):
            _show_dev_log_modal()

    if st.session_state.get("q42_open_log_modal"):
        st.session_state.pop("q42_open_log_modal")
        _show_dev_log_modal()

    st.sidebar.divider()
    if st.sidebar.button("Quit Rex", use_container_width=True):
        import signal, os as _os
        st.sidebar.info("Shutting down...")
        _os.kill(_os.getpid(), signal.SIGTERM)

    # ── Pages ─────────────────────────────────────────────────────────────
    if page == "Overview":
        _page_overview()
    elif page == "Transactions":
        _page_transactions()
    elif page == "Tax Report":
        _page_tax_report()
    elif page == "Ask Rex":
        _page_ask_rex()
    elif page == "Invoice Recon":
        invoice_recon.render_invoice_recon()
    elif page == "Parser Workshop":
        parser_workshop.render_workshop("q42")


# ---------------------------------------------------------------------------
# OVERVIEW — drop files, get synopsis
# ---------------------------------------------------------------------------

def _page_overview():
    st.title("Portal42 — Tax Overview")
    st.caption(
        "Drop bank and credit card statements (CSV or PDF). "
        "Rex reads them, categorizes for taxes, and builds your accountant report."
    )

    # Show stored import result (survives across the st.rerun() in _run_import)
    if "q42_import_result" in st.session_state:
        result = st.session_state.pop("q42_import_result")
        if result.get("success"):
            st.success(result["success"])
        for err in result.get("errors", []):
            _copyable_error(err)

    # Import form
    st.markdown("### Import Statements")
    acct_label = st.text_input(
        "Account / Card Label",
        placeholder="e.g. Chase Checking, Amex Blue Business",
        help="A friendly name for this batch of statements",
    )

    if "q42_uploader_key" not in st.session_state:
        st.session_state["q42_uploader_key"] = 0

    uploaded_files = st.file_uploader(
        "Drop statements here — CSV or PDF, multiple files OK",
        type=["csv", "pdf"],
        accept_multiple_files=True,
        key=f"q42_uploader_{st.session_state['q42_uploader_key']}",
    )

    if uploaded_files and acct_label.strip():
        if st.button("⚡ Analyze & Import", type="primary", use_container_width=True):
            _run_import(uploaded_files, acct_label.strip())
    elif uploaded_files:
        st.warning("Enter an account label above before importing.")

    # Import history
    imports = q42_db.get_import_summary()
    if imports:
        st.divider()
        st.markdown("### Imported Statements")

        # Controls
        imp_df = pd.DataFrame(imports)
        imp_df["_date_label"] = imp_df.apply(
            lambda r: _stmt_date_label(r["filename"], r.get("period_end", "")), axis=1
        )
        all_accounts = sorted(imp_df["account_label"].dropna().unique().tolist())
        ic1, ic2, ic3 = st.columns([2, 2, 2])
        sel_acct = ic1.selectbox("Account", ["All"] + all_accounts, key="imp_filter_acct")
        sel_sort = ic2.selectbox("Sort", ["Date ↑", "Date ↓", "Amount ↑", "Amount ↓"], key="imp_sort")
        ic3.markdown("")  # spacer

        filtered = imp_df.copy()
        if sel_acct != "All":
            filtered = filtered[filtered["account_label"] == sel_acct]
        if sel_sort == "Date ↑":
            filtered = filtered.sort_values("period_end", ascending=True)
        elif sel_sort == "Date ↓":
            filtered = filtered.sort_values("period_end", ascending=False)
        elif sel_sort == "Amount ↑":
            filtered = filtered.sort_values("total_in", ascending=True)
        elif sel_sort == "Amount ↓":
            filtered = filtered.sort_values("total_in", ascending=False)

        # Header row
        st.markdown(
            "<div style='display:grid;grid-template-columns:90px 1fr 160px 60px 100px 100px 36px;"
            "gap:0 12px;padding:4px 0;border-bottom:1px solid #334155;"
            "font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.06em'>"
            "<span>Date</span><span>Account</span><span>Period</span>"
            "<span style='text-align:right'>Txns</span>"
            "<span style='text-align:right'>In</span>"
            "<span style='text-align:right'>Out</span>"
            "<span></span>"
            "</div>",
            unsafe_allow_html=True,
        )

        for _, imp in filtered.iterrows():
            rc1, rc2 = st.columns([20, 1])
            rc1.markdown(
                f"<div style='display:grid;grid-template-columns:90px 1fr 160px 60px 100px 100px;"
                f"gap:0 12px;padding:5px 0;border-bottom:1px solid #1e293b;align-items:center'>"
                f"<span style='color:#4ade80;font-weight:600;font-size:0.85rem'>{imp['_date_label']}</span>"
                f"<span style='color:#cbd5e1;font-size:0.85rem'>{imp['account_label']}</span>"
                f"<span style='color:#64748b;font-size:0.78rem'>{imp['period_start']} → {imp['period_end']}</span>"
                f"<span style='color:#64748b;font-size:0.78rem;text-align:right'>{imp['txn_count']}</span>"
                f"<span style='color:#4ade80;font-size:0.78rem;text-align:right'>+${imp['total_in']:,.2f}</span>"
                f"<span style='color:#f87171;font-size:0.78rem;text-align:right'>−${imp['total_out']:,.2f}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if rc2.button("✕", key=f"del_imp_{imp['id']}", help=f"Remove {imp['filename']}"):
                q42_db.delete_import(int(imp["id"]))
                st.session_state.pop("q42_synopsis", None)
                st.rerun()

        # Import More
        st.divider()
        if st.button("＋ Import More Statements", use_container_width=True):
            st.session_state["q42_uploader_key"] = st.session_state.get("q42_uploader_key", 0) + 1
            st.session_state["q42_nav_pending"] = "Overview"
            st.rerun()

        # AI Synopsis
        st.divider()
        st.markdown("### AI Synopsis")
        st.caption("Rex reviews your full dataset and writes a briefing for your accountant.")

        if st.button("Generate Synopsis", type="primary"):
            st.session_state["q42_confirm_synopsis"] = True

        if st.session_state.get("q42_confirm_synopsis"):
            st.warning(
                "Are you done importing all your statements? "
                "The synopsis will reflect everything currently in the database."
            )
            _sc1, _sc2 = st.columns(2)
            if _sc1.button("Yes, generate it", type="primary", use_container_width=True):
                st.session_state.pop("q42_confirm_synopsis", None)
                with st.spinner("Rex is analyzing your financial picture..."):
                    period = q42_db.get_period_summary()
                    deductions = q42_db.get_deduction_summary()
                    profile = q42_db.get_tax_profile()
                    synopsis = q42_rex.q42_generate_synopsis(period, deductions, profile)
                    st.session_state["q42_synopsis"] = synopsis
            if _sc2.button("Not yet — go back", use_container_width=True):
                st.session_state.pop("q42_confirm_synopsis", None)
                st.session_state["q42_uploader_key"] = st.session_state.get("q42_uploader_key", 0) + 1
                st.rerun()

        if "q42_synopsis" in st.session_state:
            st.markdown(
                f"<div style='background:rgba(96,165,250,0.06);"
                f"border:1px solid rgba(96,165,250,0.2);border-radius:8px;"
                f"padding:18px 22px;line-height:1.75;font-size:0.9rem'>"
                f"{st.session_state['q42_synopsis'].replace(chr(10), '<br>')}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "No statements imported yet. Add an account label and drop your CSV or PDF "
            "bank/credit card statements above."
        )


def _run_import(uploaded_files, acct_label: str):
    total_imported = 0
    total_dupes = 0
    errors = []

    _q42_log(f"Import started: {len(uploaded_files)} file(s) → '{acct_label}'")

    with st.spinner(f"Rex is reading {len(uploaded_files)} file(s)..."):
        for uf in uploaded_files:
            is_pdf = uf.name.lower().endswith(".pdf")
            suffix = ".pdf" if is_pdf else ".csv"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uf.read())
                tmp_path = tmp.name

            try:
                _q42_log(f"  Parsing: {uf.name} ({uf.size} bytes, {'PDF' if is_pdf else 'CSV'})")

                if is_pdf:
                    parsed_df, stmt_meta = parsers.parse_auto(tmp_path, 0)
                    gl_format = None
                else:
                    try:
                        gl_format = gl_csv_profiles.detect_gl_format(tmp_path)
                    except Exception as det_err:
                        _q42_log(f"  GL detection error: {det_err}")
                        gl_format = None
                    if gl_format:
                        _q42_log(f"  Detected GL format: {gl_format}")
                    else:
                        _q42_log(f"  No GL format detected for {uf.name} — using standard CSV parser")

                # ── GL CSV path (FreshBooks / QBO General Ledger) ──
                if gl_format:
                    if gl_format == "freshbooks_gl":
                        gl_txns = gl_csv_profiles.parse_freshbooks_gl(tmp_path)
                        source_type = "freshbooks"
                    else:
                        gl_txns = gl_csv_profiles.parse_qbo_gl(tmp_path)
                        source_type = "qbo"

                    if not gl_txns:
                        errors.append(f"{uf.name}: No transactions found in {gl_format} export")
                        continue

                    dates = [t["date"] for t in gl_txns if t["date"]]
                    total_in  = sum(t["amount"] for t in gl_txns if t["amount"] > 0)
                    total_out = sum(abs(t["amount"]) for t in gl_txns if t["amount"] < 0)

                    import_id = q42_db.record_import(
                        filename=uf.name,
                        account_label=acct_label,
                        source_type=source_type,
                        period_start=min(dates) if dates else "",
                        period_end=max(dates) if dates else "",
                        total_in=total_in,
                        total_out=total_out,
                        txn_count=len(gl_txns),
                    )

                    file_inserted = 0
                    file_dupes = 0
                    for t in gl_txns:
                        src = f"{source_type}|{t['date']}|{t['description']}|{t['amount']}"
                        src_hash = hashlib.md5(src.encode()).hexdigest()
                        inserted = q42_db.insert_q42_transaction(
                            import_id=import_id,
                            date=t["date"],
                            description=t["description"],
                            merchant_name=t["merchant_name"],
                            amount=float(t["amount"]),
                            tax_category=t["tax_category"],
                            source_hash=src_hash,
                        )
                        if inserted:
                            file_inserted += 1
                        else:
                            file_dupes += 1

                    total_imported += file_inserted
                    total_dupes   += file_dupes
                    _q42_log(f"  {uf.name} ({gl_format}): {file_inserted} inserted, {file_dupes} dupes skipped")
                    continue

                # ── Standard bank CSV / PDF path ──
                if not is_pdf:
                    parsed_df = parsers.parse_csv(tmp_path, 0)
                    stmt_meta = {
                        "opening_date": str(parsed_df["date"].min()),
                        "closing_date": str(parsed_df["date"].max()),
                    }

                _q42_log(f"  Parsed {len(parsed_df)} rows: {stmt_meta['opening_date']} → {stmt_meta['closing_date']}")

                descs = parsed_df["description"].tolist()
                _q42_log(f"  Enriching {len(descs)} descriptions via AI...")
                enriched = q42_rex.q42_enrich_transactions(descs)
                _q42_log(f"  Enrichment done for {uf.name}")

                total_in  = float(parsed_df[parsed_df["amount"] > 0]["amount"].sum())
                total_out = float(parsed_df[parsed_df["amount"] < 0]["amount"].abs().sum())

                import_id = q42_db.record_import(
                    filename=uf.name,
                    account_label=acct_label,
                    source_type="pdf" if is_pdf else "csv",
                    period_start=stmt_meta["opening_date"],
                    period_end=stmt_meta["closing_date"],
                    total_in=total_in,
                    total_out=total_out,
                    txn_count=len(parsed_df),
                )

                file_inserted = 0
                file_dupes = 0
                for (_, row), enriched_item in zip(parsed_df.iterrows(), enriched):
                    src = f"q42|{row['date']}|{row['description']}|{row['amount']}"
                    src_hash = hashlib.md5(src.encode()).hexdigest()
                    inserted = q42_db.insert_q42_transaction(
                        import_id=import_id,
                        date=str(row["date"]),
                        description=row["description"],
                        merchant_name=enriched_item.get("name", row["description"]),
                        amount=float(row["amount"]),
                        tax_category=enriched_item.get("tax_category", "Uncategorized"),
                        source_hash=src_hash,
                    )
                    if inserted:
                        file_inserted += 1
                    else:
                        file_dupes += 1

                total_imported += file_inserted
                total_dupes   += file_dupes
                _q42_log(f"  {uf.name}: {file_inserted} inserted, {file_dupes} dupes skipped")

            except parsers.UnknownInstitutionError as e:
                parser_workshop.push_unknown_file("q42", uf.name, e.raw_text)
                errors.append(f"{uf.name}: Unknown institution — sent to Parser Workshop")
                _q42_log(f"  UNKNOWN INSTITUTION {uf.name}: sent to Parser Workshop")
            except Exception as e:
                import traceback
                err_detail = traceback.format_exc()
                errors.append(f"{uf.name}: {e}")
                _q42_log(f"  ERROR {uf.name}: {e}")
                _q42_log(f"  TRACEBACK: {err_detail}")
            finally:
                os.unlink(tmp_path)

    _q42_log(f"Import complete: {total_imported} inserted, {total_dupes} dupes, {len(errors)} errors")

    # Store results in session state so they survive the st.rerun() below
    result: dict = {"errors": [f"Import error — {e}" for e in errors]}
    if total_imported:
        dupe_note = f" ({total_dupes} duplicates skipped)" if total_dupes else ""
        result["success"] = (
            f"Imported {total_imported} transactions from {len(uploaded_files)} file(s){dupe_note}. "
            "Review categories in Transactions, then generate a Synopsis."
        )
    elif not errors:
        dupe_note = f" — {total_dupes} were already in the database (duplicates skipped)." if total_dupes else "."
        result["success"] = f"No new transactions imported{dupe_note}"

    st.session_state["q42_import_result"] = result
    st.session_state["q42_uploader_key"] += 1
    st.session_state.pop("q42_synopsis", None)
    # If any files were unrecognized, navigate to Parser Workshop automatically
    if st.session_state.get("q42_workshop_pending"):
        st.session_state["q42_nav_pending"] = "Parser Workshop"
    st.rerun()


# ---------------------------------------------------------------------------
# TRANSACTIONS — tax category view
# ---------------------------------------------------------------------------

def _page_transactions():
    st.title("Transactions — Tax View")

    txns = q42_db.get_all_transactions()
    if not txns:
        st.info("No transactions yet. Import statements in Overview.")
        return

    df = pd.DataFrame(txns)

    # Filters — account first so you can narrow before anything else
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 1])
    accounts = ["All"] + sorted(df["account_label"].dropna().unique().tolist())
    facct = fc1.selectbox("Account", accounts, key="q42_txn_facct")
    cats = ["All"] + q42_db.Q42_TAX_CATEGORIES
    fcat = fc2.selectbox("Category", cats, key="q42_txn_fcat")
    ftype = fc3.selectbox("Type", ["All", "Business Only", "Personal Only", "Expenses Only", "Income Only"], key="q42_txn_ftype")
    sort_col = fc4.selectbox("Sort by", ["Date ↑", "Date ↓", "Amount ↑", "Amount ↓"], key="q42_txn_fsort")
    fc5.markdown("<br>", unsafe_allow_html=True)

    if facct != "All":
        df = df[df["account_label"] == facct]
    if fcat != "All":
        df = df[df["tax_category"] == fcat]
    if ftype == "Business Only":
        df = df[df["is_personal"] == 0]
    elif ftype == "Personal Only":
        df = df[df["is_personal"] == 1]
    elif ftype == "Expenses Only":
        df = df[df["amount"] < 0]
    elif ftype == "Income Only":
        df = df[df["amount"] > 0]

    # Sort
    if sort_col == "Date ↑":
        df = df.sort_values("date", ascending=True)
    elif sort_col == "Date ↓":
        df = df.sort_values("date", ascending=False)
    elif sort_col == "Amount ↑":
        df = df.sort_values("amount", ascending=True)
    elif sort_col == "Amount ↓":
        df = df.sort_values("amount", ascending=False)

    # Quick KPIs
    if not df.empty:
        total_ded = df["deductible_amt"].sum()
        total_exp = df[df["amount"] < 0]["amount"].abs().sum()
        total_inc = df[df["amount"] > 0]["amount"].sum()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Transactions", len(df))
        k2.metric("Income", f"${total_inc:,.2f}")
        k3.metric("Expenses", f"${total_exp:,.2f}")
        k4.metric("Est. Deductible", f"${total_ded:,.2f}")

    st.divider()

    display_df = df[[
        "id", "date", "merchant_name", "amount",
        "tax_category", "business_pct", "deductible_amt",
        "is_personal", "notes", "account_label",
    ]].copy()
    display_df = display_df.rename(columns={
        "merchant_name": "name",
        "tax_category": "category",
        "business_pct": "biz %",
        "deductible_amt": "deductible",
        "is_personal": "personal",
        "account_label": "account",
    })

    st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        disabled=["id", "date", "amount", "deductible", "account"],
        column_config={
            "id": None,
            "date": st.column_config.TextColumn("Date", width="small"),
            "name": st.column_config.TextColumn("Merchant", width="medium"),
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f", width="small"),
            "category": st.column_config.SelectboxColumn(
                "Category", options=q42_db.Q42_TAX_CATEGORIES, width="medium"
            ),
            "biz %": st.column_config.NumberColumn(
                "Biz %", min_value=0, max_value=100, step=5, format="%.0f%%", width="small"
            ),
            "deductible": st.column_config.NumberColumn("Deductible", format="$%.2f", width="small"),
            "personal": st.column_config.CheckboxColumn("Personal?", width="small"),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
            "account": st.column_config.TextColumn("Account", width="small"),
        },
        num_rows="fixed",
        key="q42_txn_editor",
    )

    if st.button("💾 Save Changes", type="primary"):
        editor_state = st.session_state.get("q42_txn_editor", {})
        edited_rows = editor_state.get("edited_rows", {})
        changed = 0
        for row_idx, changes in edited_rows.items():
            txn_id = int(display_df.iloc[int(row_idx)]["id"])
            current = display_df.iloc[int(row_idx)]
            cat = changes.get("category", current["category"])
            biz_pct = float(changes.get("biz %", current.get("biz %") or 100.0))
            notes = str(changes.get("notes", current.get("notes") or ""))
            is_personal = bool(changes.get("personal", bool(current.get("personal", 0))))
            q42_db.update_q42_transaction(txn_id, cat, biz_pct, notes, is_personal)
            changed += 1
        if changed:
            st.session_state.pop("q42_txn_editor", None)
            st.success(f"Saved {changed} change(s).")
            st.rerun()
        else:
            st.info("No changes detected.")


# ---------------------------------------------------------------------------
# TAX REPORT — accounting view + share
# ---------------------------------------------------------------------------

def _page_tax_report():
    st.title("Tax Report — Accounting View")

    summary = q42_db.get_deduction_summary()
    period = q42_db.get_period_summary()

    if not period:
        st.info("No data yet. Import statements in Overview.")
        return

    # Header
    st.markdown(
        f"**Period:** {period.get('start_date', '?')} → {period.get('end_date', '?')} "
        f"&nbsp;·&nbsp; {period.get('total_txns', 0)} transactions",
        unsafe_allow_html=True,
    )

    # KPIs
    net_profit = summary.get("total_income", 0) - period.get("total_out", 0)
    total_ded = sum(c["deductible_total"] for c in summary.get("by_category", []))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gross Income", f"${summary.get('total_income', 0):,.2f}")
    k2.metric("Total Expenses", f"${period.get('total_out', 0):,.2f}")
    k3.metric("Est. Deductions", f"${total_ded:,.2f}", delta_color="off")
    k4.metric("Est. Net Profit", f"${net_profit:,.2f}", delta_color="off")

    st.divider()

    cats = summary.get("by_category", [])
    if cats:
        st.subheader("Deductions by Category")

        # Bar chart
        cat_df = pd.DataFrame(cats)
        fig = go.Figure()
        fig.add_bar(
            x=cat_df["tax_category"],
            y=cat_df["deductible_total"],
            marker_color="#60a5fa",
            hovertemplate="<b>%{x}</b><br>Deductible: $%{y:,.2f}<extra></extra>",
        )
        fig.update_layout(
            height=260, margin=dict(t=10, b=100, l=40, r=10),
            xaxis=dict(tickangle=-40),
            yaxis=dict(tickprefix="$", tickformat=",.0f"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Detail table
        rows_html = ""
        for cat in cats:
            rows_html += (
                f"<div style='display:grid;grid-template-columns:3fr 1fr 1fr 1fr;"
                f"padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.86rem'>"
                f"<span style='color:#e2e8f0'>{cat['tax_category']}</span>"
                f"<span style='color:#64748b;text-align:center'>{cat['count']}</span>"
                f"<span style='color:#f87171;text-align:right'>−${cat['gross_total']:,.2f}</span>"
                f"<span style='color:#4ade80;text-align:right'>${cat['deductible_total']:,.2f}</span>"
                f"</div>"
            )
        header = (
            "<div style='display:grid;grid-template-columns:3fr 1fr 1fr 1fr;"
            "padding:4px 10px;font-size:0.68rem;color:#64748b;text-transform:uppercase;"
            "letter-spacing:0.06em'>"
            "<span>Category</span><span style='text-align:center'>Count</span>"
            "<span style='text-align:right'>Gross</span><span style='text-align:right'>Deductible</span>"
            "</div>"
        )
        total_row = (
            f"<div style='display:grid;grid-template-columns:3fr 1fr 1fr 1fr;"
            f"padding:8px 10px;border-top:2px solid rgba(255,255,255,0.1);"
            f"font-size:0.9rem;font-weight:700'>"
            f"<span>TOTAL</span><span></span><span></span>"
            f"<span style='color:#4ade80;text-align:right'>${total_ded:,.2f}</span>"
            f"</div>"
        )
        st.markdown(
            f"<div style='border:1px solid rgba(255,255,255,0.07);border-radius:8px;overflow:hidden'>"
            f"{header}{rows_html}{total_row}</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Michigan Tax Notes")
    st.markdown("""
- **Michigan Income Tax:** 4.25% flat rate on AGI (follows federal with Michigan-specific adjustments)
- **Self-Employment Tax:** 15.3% federal SE tax on net earnings; deduct 50% above the line (Form 1040)
- **QBI Deduction (§199A):** Up to 20% of qualified business income — confirm eligibility with your CPA
- **Home Office:** Must satisfy "regular and exclusive use" test; use Form 8829 (actual method) or simplified ($5/sq ft, max 300 sq ft)
- **Vehicle:** Choose standard mileage ($0.67/mile, 2024) OR actual expense — cannot switch once actual expenses are used for a vehicle
- **SEP-IRA Deadline:** Contributions for prior tax year can be made up to the filing deadline *including extensions*
- **1099 Requirement:** Issue 1099-NEC to any contractor paid $600+ in the calendar year
- **Estimated Taxes:** Quarterly due dates — April 15, June 15, September 15, January 15

*This report is prepared for informational purposes. Verify all figures with your licensed CPA before filing.*
""")

    st.divider()
    st.subheader("Export & Share")
    st.caption("Share any of these with your accountant. The HTML report is the most complete.")

    all_txns = q42_db.get_all_transactions()
    if not all_txns:
        st.info("No transactions to export yet.")
        return

    c1, c2 = st.columns(2)

    # CSV export
    export_df = pd.DataFrame(all_txns)[[
        "date", "merchant_name", "amount", "tax_category",
        "business_pct", "deductible_amt", "notes", "account_label",
    ]]
    export_df.columns = [
        "Date", "Merchant", "Amount", "Tax Category",
        "Business %", "Deductible Amount", "Notes", "Account",
    ]
    c1.download_button(
        "📥 Download CSV",
        data=export_df.to_csv(index=False),
        file_name=f"portal42_tax_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Full accountant HTML report
    report_html = _build_accountant_report(period, summary, cats or [], total_ded)
    c2.download_button(
        "📄 Accountant Report",
        data=report_html,
        file_name=f"portal42_report_{datetime.now().strftime('%Y%m%d')}.html",
        mime="text/html",
        use_container_width=True,
    )


def _build_accountant_report(period: dict, summary: dict,
                              cats: list, total_ded: float) -> str:
    rows = ""
    for cat in cats:
        rows += (
            f"<tr><td>{cat['tax_category']}</td>"
            f"<td style='text-align:center'>{cat['count']}</td>"
            f"<td style='text-align:right'>−${cat['gross_total']:,.2f}</td>"
            f"<td style='text-align:right;color:#16a34a;font-weight:600'>"
            f"${cat['deductible_total']:,.2f}</td></tr>"
        )
    net_profit = summary.get("total_income", 0) - period.get("total_out", 0)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Portal42 Tax Report</title>
<style>
  body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:820px;margin:40px auto;color:#1e293b;padding:0 24px;}}
  h1 {{color:#1d4ed8;border-bottom:2px solid #1d4ed8;padding-bottom:8px;margin-bottom:4px;}}
  h2 {{color:#334155;margin-top:36px;font-size:1.1rem;}}
  .meta {{color:#64748b;font-size:0.85rem;margin-bottom:28px;}}
  .kpi-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0;}}
  .kpi {{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;}}
  .kpi-label {{font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;}}
  .kpi-value {{font-size:1.25rem;font-weight:700;margin-top:4px;}}
  table {{width:100%;border-collapse:collapse;margin-top:14px;font-size:0.9rem;}}
  th {{background:#f1f5f9;padding:9px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;}}
  td {{padding:8px 12px;border-bottom:1px solid #f1f5f9;}}
  .total-row td {{background:#eff6ff;font-weight:700;border-top:2px solid #bfdbfe;}}
  ul {{line-height:1.9;font-size:0.9rem;}}
  .disclaimer {{background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:14px 18px;margin-top:32px;font-size:0.83rem;color:#9a3412;line-height:1.6;}}
  .footer {{margin-top:40px;font-size:0.75rem;color:#94a3b8;text-align:center;padding-top:16px;border-top:1px solid #e2e8f0;}}
</style>
</head><body>
<h1>Portal42 — Tax Preparation Report</h1>
<p class="meta">
  Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')} &nbsp;·&nbsp;
  Period: {period.get('start_date','?')} to {period.get('end_date','?')}
</p>
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">Gross Income</div>
    <div class="kpi-value" style="color:#16a34a">${summary.get('total_income',0):,.2f}</div></div>
  <div class="kpi"><div class="kpi-label">Total Expenses</div>
    <div class="kpi-value" style="color:#dc2626">${period.get('total_out',0):,.2f}</div></div>
  <div class="kpi"><div class="kpi-label">Est. Deductions</div>
    <div class="kpi-value" style="color:#1d4ed8">${total_ded:,.2f}</div></div>
  <div class="kpi"><div class="kpi-label">Est. Net Profit</div>
    <div class="kpi-value">${net_profit:,.2f}</div></div>
</div>
<h2>Deductions by Category</h2>
<table>
<thead><tr>
  <th>Category</th><th style="text-align:center">Transactions</th>
  <th style="text-align:right">Gross Amount</th><th style="text-align:right">Deductible</th>
</tr></thead>
<tbody>
{rows}
<tr class="total-row">
  <td>TOTAL ESTIMATED DEDUCTIONS</td><td></td><td></td>
  <td style="text-align:right;color:#16a34a">${total_ded:,.2f}</td>
</tr>
</tbody></table>
<h2>Michigan Tax Reminders for CPA</h2>
<ul>
<li>Michigan income tax: 4.25% flat rate — confirm Schedule 1 adjustments</li>
<li>Self-employment tax: 15.3% federal; deduct 50% above-the-line on Form 1040</li>
<li>Verify home office: regular &amp; exclusive use test, Form 8829 (actual method preferred)</li>
<li>QBI deduction (§199A): up to 20% of qualified business income — confirm eligibility</li>
<li>Vehicle: confirm mileage log exists; verify standard vs actual method election</li>
<li>SEP-IRA: can fund prior year up to filing deadline (including extensions)</li>
<li>1099-NEC: confirm issued to all contractors paid $600+ in calendar year</li>
</ul>
<div class="disclaimer">
  <strong>Disclaimer:</strong> This report is prepared for informational purposes to assist
  your licensed CPA. All figures should be verified against original source documents,
  mileage logs, and receipts. This does not constitute tax advice or a tax return.
</div>
<div class="footer">Generated by Portal42 · Rex Tax Advisor Mode · {datetime.now().year}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# API IMPORT UI — shared by FreshBooks and QBO
# ---------------------------------------------------------------------------



def _render_gap_analysis(date_from: str, date_to: str, key_suffix: str = "default") -> None:
    """Show coverage heatmap and flag gaps for the selected date range."""
    from datetime import datetime, timedelta
    import calendar

    coverage = q42_db.get_coverage_by_month()
    if not coverage:
        return

    # Build list of months in range
    try:
        start = datetime.strptime(date_from[:7], "%Y-%m")
        end   = datetime.strptime(date_to[:7],   "%Y-%m")
    except ValueError:
        return

    months = []
    cur = start
    while cur <= end:
        months.append(cur.strftime("%Y-%m"))
        # advance one month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    if not months:
        return

    gaps = [m for m in months if m not in coverage]
    thin = [m for m in months if m in coverage and coverage[m]["count"] < 3]

    if not gaps and not thin:
        return

    st.markdown("---")
    st.markdown("**Coverage gaps in selected range**")

    if gaps:
        gap_str = ", ".join(gaps)
        st.warning(
            f"**{len(gaps)} month(s) with no data:** {gap_str}  \n"
            "Ask Rex to make CPA-style estimates for these periods, or import statements to fill them."
        )

    if thin:
        thin_str = ", ".join(thin)
        st.info(
            f"**{len(thin)} month(s) with very few transactions:** {thin_str}  \n"
            "This may indicate missing imports or low-activity periods."
        )

    if gaps and st.button("Ask Rex to estimate gaps",
                           key=f"q42_gap_ask_rex_{key_suffix}_{date_from}_{date_to}",
                           type="secondary", use_container_width=True):
        avg_monthly = _compute_monthly_average(coverage, gaps)
        gap_prompt  = _build_gap_prompt(gaps, thin, avg_monthly)
        st.session_state["q42_nav_pending"] = "Ask Rex"
        st.session_state["q42_gap_prompt"] = gap_prompt
        st.rerun()


def _compute_monthly_average(coverage: dict, gaps: list) -> dict:
    """Compute average monthly in/out from months that DO have data."""
    conn = q42_db.get_connection()
    rows = conn.execute(
        "SELECT substr(date,1,7) as month, "
        "SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) as total_in, "
        "SUM(CASE WHEN amount<0 THEN ABS(amount) ELSE 0 END) as total_out "
        "FROM q42_transactions GROUP BY month"
    ).fetchall()
    conn.close()
    known = [r for r in rows if r["month"] not in gaps]
    if not known:
        return {"avg_in": 0, "avg_out": 0}
    avg_in  = sum(r["total_in"]  for r in known) / len(known)
    avg_out = sum(r["total_out"] for r in known) / len(known)
    return {"avg_in": avg_in, "avg_out": avg_out}


def _build_gap_prompt(gaps: list, thin: list, avg: dict) -> str:
    gap_list  = ", ".join(gaps)
    thin_list = ", ".join(thin) if thin else "none"
    return (
        f"I have gaps in my financial data. Months with NO transactions: {gap_list}. "
        f"Months with very few transactions: {thin_list}. "
        f"Based on the months I DO have data for, my average monthly income is "
        f"${avg['avg_in']:,.2f} and average monthly expenses are ${avg['avg_out']:,.2f}. "
        f"As my CPA, please: (1) estimate what the missing months likely looked like based on "
        f"these averages and any seasonal patterns you can infer, (2) flag any deductions I "
        f"might be missing from those periods, and (3) tell me what documentation I should try "
        f"to track down to fill these gaps properly."
    )


# ---------------------------------------------------------------------------
# CONNECTIONS — animated wire UI
# ---------------------------------------------------------------------------

def _page_connections():
    st.markdown(_WIRE_CSS, unsafe_allow_html=True)
    st.title("Connections")
    st.caption(
        "Connect Rex to your accounting platforms. "
        "Rex is the source of truth — data flows outward."
    )

# ---------------------------------------------------------------------------
# ASK REX — tax chat + Ready for Review
# ---------------------------------------------------------------------------

def _page_ask_rex():
    st.title("Ask Rex — Tax Advisor")

    period = q42_db.get_period_summary()
    deductions = q42_db.get_deduction_summary()
    profile = q42_db.get_tax_profile()

    # Ready for Review banner
    st.markdown("""
<div style="background:rgba(96,165,250,0.07);border:1px solid rgba(96,165,250,0.22);
border-radius:10px;padding:16px 20px;margin-bottom:20px">
<div style="font-weight:700;font-size:0.97rem;color:#93c5fd;margin-bottom:5px">
  Ready for Deep Review?
</div>
<div style="font-size:0.86rem;color:#94a3b8;line-height:1.65">
  Rex will walk through targeted questions to surface every deduction —
  home office, mileage, health insurance, retirement strategy, and more.
  Takes about 5 minutes. Results are saved to your tax profile.
</div>
</div>""", unsafe_allow_html=True)

    review_mode = st.session_state.get("q42_review_mode", False)
    if not review_mode:
        c1, _ = st.columns([1, 3])
        if c1.button("Start Review", type="primary", use_container_width=True):
            st.session_state["q42_review_mode"] = True
            st.session_state["q42_review_step"] = 0
            st.session_state["q42_review_answers"] = {}
            st.session_state.pop("q42_review_result", None)
            st.rerun()
    else:
        _run_review_flow(period, deductions, profile)

    st.divider()

    # ── Chat with Rex ─────────────────────────────────────────────────────────

    def _q42_conv_title(messages: list) -> str:
        for m in messages:
            if m["role"] == "user":
                t = m["content"][:50]
                return (t + "…") if len(m["content"]) > 50 else t
        return "Untitled"

    def _q42_format_conv(messages: list) -> str:
        lines = []
        for m in messages:
            role = "You" if m["role"] == "user" else "Rex"
            lines.append(f"[{role}]\n{m['content']}\n")
        return "\n".join(lines)

    # load persisted conversations
    q42_convs = q42_db.get_q42_conversations()

    if "q42_chat_history" not in st.session_state:
        st.session_state["q42_chat_history"] = []
        st.session_state["q42_current_conv_id"] = None
        if q42_convs:
            recent_q42 = q42_db.get_q42_conversation(q42_convs[0]["id"])
            st.session_state["q42_chat_history"] = recent_q42["messages"]
            st.session_state["q42_current_conv_id"] = q42_convs[0]["id"]

    if "q42_current_conv_id" not in st.session_state:
        st.session_state["q42_current_conv_id"] = None

    # header row
    st.subheader("Chat with Rex")

    q42_conv_ids = [None] + [c["id"] for c in q42_convs]
    q42_conv_labels = ["+ New Conversation"] + [
        f"{c['title'][:45]}{'…' if len(c['title']) > 45 else ''}  ·  {c['updated_at'][:10]}"
        for c in q42_convs
    ]

    q42_cur_id = st.session_state["q42_current_conv_id"]
    q42_cur_idx = 0
    if q42_cur_id is not None:
        try:
            q42_cur_idx = q42_conv_ids.index(q42_cur_id)
        except ValueError:
            q42_cur_idx = 0

    q42_has_content = bool(st.session_state["q42_chat_history"])

    dcol, copyc, expc = st.columns([4, 1, 1])
    with dcol:
        q42_sel_idx = st.selectbox(
            "Tax conversation",
            options=list(range(len(q42_conv_labels))),
            format_func=lambda i: q42_conv_labels[i],
            index=q42_cur_idx,
            label_visibility="collapsed",
            key="q42_conv_selector",
        )
        q42_new_id = q42_conv_ids[q42_sel_idx]
        if q42_new_id != q42_cur_id:
            if q42_new_id is None:
                st.session_state["q42_chat_history"] = []
                st.session_state["q42_current_conv_id"] = None
            else:
                q42_loaded = q42_db.get_q42_conversation(q42_new_id)
                st.session_state["q42_chat_history"] = q42_loaded["messages"]
                st.session_state["q42_current_conv_id"] = q42_new_id
            st.rerun()

    with copyc:
        if q42_has_content:
            if st.button("Copy", use_container_width=True, key="q42_copy_btn"):
                st.session_state["q42_show_copy"] = not st.session_state.get("q42_show_copy", False)

    with expc:
        if q42_has_content:
            q42_export_txt = _q42_format_conv(st.session_state["q42_chat_history"])
            q42_slug = _q42_conv_title(st.session_state["q42_chat_history"])[:30].replace(" ", "_")
            st.download_button(
                "Export",
                data=q42_export_txt,
                file_name=f"rex_tax_{q42_slug}.txt",
                mime="text/plain",
                use_container_width=True,
                key="q42_export_btn",
            )

    if st.session_state.get("q42_show_copy") and q42_has_content:
        with st.expander("Conversation text — click the icon to copy", expanded=True):
            st.code(_q42_format_conv(st.session_state["q42_chat_history"]), language=None)

    # Build financial context
    ctx_parts = []
    if period:
        ctx_parts.append(
            f"Period: {period.get('start_date','?')} to {period.get('end_date','?')}\n"
            f"Total Income: ${period.get('total_in', 0):,.2f}\n"
            f"Total Expenses: ${period.get('total_out', 0):,.2f}\n"
            f"Est. Deductible: ${period.get('total_deductible', 0):,.2f}"
        )
    by_cat = deductions.get("by_category", [])
    if by_cat:
        lines = "\n".join(
            f"  {c['tax_category']}: ${c['deductible_total']:,.2f}"
            for c in by_cat[:8]
        )
        ctx_parts.append(f"Top deduction categories:\n{lines}")
    if profile:
        p_lines = "\n".join(f"  {k}: {v}" for k, v in profile.items() if v)
        if p_lines:
            ctx_parts.append(f"Tax profile:\n{p_lines}")
    fin_context = "\n\n".join(ctx_parts)

    # Auto-fire gap analysis prompt when navigated here from gap UI
    if "q42_gap_prompt" in st.session_state:
        gap_prompt = st.session_state.pop("q42_gap_prompt")
        with st.chat_message("user"):
            st.markdown(gap_prompt)
        with st.chat_message("assistant"):
            with st.spinner("Rex is analyzing your data gaps..."):
                response = q42_rex.q42_chat(
                    gap_prompt,
                    st.session_state["q42_chat_history"],
                    financial_context=fin_context,
                )
            st.markdown(response)
        msgs = st.session_state["q42_chat_history"]
        if st.session_state["q42_current_conv_id"] is None:
            new_id = q42_db.save_q42_conversation(_q42_conv_title(msgs), msgs)
            st.session_state["q42_current_conv_id"] = new_id
        else:
            q42_db.update_q42_conversation(st.session_state["q42_current_conv_id"], msgs)

    # Chat history display
    for msg in st.session_state["q42_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input(
        "Ask Rex about deductions, Michigan taxes, QBI, mileage, home office..."
    )
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Rex is thinking..."):
                response = q42_rex.q42_chat(
                    user_input,
                    st.session_state["q42_chat_history"],
                    financial_context=fin_context,
                )
            st.markdown(response)

        # auto-save / update conversation in DB
        msgs = st.session_state["q42_chat_history"]
        if st.session_state["q42_current_conv_id"] is None:
            new_id = q42_db.save_q42_conversation(_q42_conv_title(msgs), msgs)
            st.session_state["q42_current_conv_id"] = new_id
        else:
            q42_db.update_q42_conversation(st.session_state["q42_current_conv_id"], msgs)
        st.rerun()


def _run_review_flow(period: dict, deductions: dict, profile: dict):
    """Structured review Q&A — walks through targeted tax questions."""
    step = st.session_state.get("q42_review_step", 0)
    answers = st.session_state.get("q42_review_answers", {})
    questions = q42_rex.REVIEW_QUESTIONS

    if step < len(questions):
        q = questions[step]

        st.progress(step / len(questions), text=f"Question {step + 1} of {len(questions)}")

        st.markdown(
            f"<div style='background:rgba(96,165,250,0.06);border-left:3px solid #60a5fa;"
            f"border-radius:0 8px 8px 0;padding:14px 18px;margin:12px 0'>"
            f"<div style='font-size:1rem;color:#e2e8f0;margin-bottom:8px'>{q['question']}</div>"
            f"<div style='font-size:0.78rem;color:#64748b;font-style:italic'>{q['context']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        prev_answer = answers.get(q["key"], profile.get(q["key"], ""))
        answer = st.text_area("Your answer", value=prev_answer,
                              key=f"q42_rev_q_{step}", height=90)

        c1, c2, c3 = st.columns([1, 1, 3])
        if c1.button("Next →", type="primary", use_container_width=True):
            ans = answer.strip()
            if ans:
                answers[q["key"]] = ans
                q42_db.set_tax_profile_key(q["key"], ans)
            st.session_state["q42_review_answers"] = answers
            st.session_state["q42_review_step"] = step + 1
            st.rerun()
        if c2.button("Skip", use_container_width=True):
            st.session_state["q42_review_step"] = step + 1
            st.rerun()
        if c3.button("Exit Review", use_container_width=True):
            st.session_state["q42_review_mode"] = False
            st.rerun()

    else:
        # All questions answered — run the full analysis
        if "q42_review_result" not in st.session_state:
            with st.spinner("Rex is building your complete tax analysis..."):
                result = q42_rex.q42_run_review(answers, deductions, period)
                st.session_state["q42_review_result"] = result

        st.success("Review complete — here is Rex's full analysis:")
        st.markdown(
            f"<div style='background:rgba(74,222,128,0.05);border:1px solid rgba(74,222,128,0.18);"
            f"border-radius:8px;padding:18px 22px;line-height:1.8;font-size:0.9rem'>"
            f"{st.session_state['q42_review_result'].replace(chr(10), '<br>')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        if c1.button("Start Over", type="secondary"):
            st.session_state["q42_review_mode"] = False
            st.session_state.pop("q42_review_result", None)
            st.session_state.pop("q42_review_answers", None)
            st.session_state["q42_review_step"] = 0
            st.rerun()
        if c2.button("Save to Profile", type="primary"):
            q42_db.set_tax_profile_key("review_analysis", st.session_state["q42_review_result"])
            st.success("Analysis saved to your tax profile.")
        if c3.button("Continue to Chat", use_container_width=True):
            st.session_state["q42_review_mode"] = False
            st.rerun()
