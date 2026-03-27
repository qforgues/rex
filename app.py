"""
app.py — Rex Mac: Personal Finance Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

import db
import parsers
from rex import chat_with_rex

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Rex — Personal Finance",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Init DB on first run
# ---------------------------------------------------------------------------
db.init_db()

# ---------------------------------------------------------------------------
# Dev log (session-scoped, copyable in dev mode)
# ---------------------------------------------------------------------------
if "dev_log" not in st.session_state:
    st.session_state["dev_log"] = []

def _dev_log(msg: str):
    from datetime import datetime as _dt
    st.session_state["dev_log"].append(f"[{_dt.now().strftime('%H:%M:%S')}] {msg}")

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("💰 Rex")
st.sidebar.caption("Your personal finance AI")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Accounts", "Assets", "Transactions", "Goals", "Reminders", "Chat with Rex"],
)

st.sidebar.divider()
dev_mode = st.sidebar.toggle("Dev Mode", value=False)

if dev_mode:
    st.sidebar.divider()
    st.sidebar.caption("⚠️ Danger Zone")
    if st.sidebar.button("Delete All Data", type="secondary"):
        conn = db.get_connection()
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM statements")
        conn.execute("DELETE FROM net_worth_snapshots")
        conn.commit()
        conn.close()
        st.session_state["dev_log"] = []
        st.sidebar.success("Data wiped.")
    if st.sidebar.button("Clear Error Log"):
        st.session_state["dev_log"] = []
        st.rerun()

if dev_mode and st.session_state.get("dev_log"):
    log_text = "\n".join(st.session_state["dev_log"])
    st.sidebar.caption(f"📋 Log — {len(st.session_state['dev_log'])} entries")
    _lc1, _lc2 = st.sidebar.columns(2)
    _lc1.download_button("Copy Log", data=log_text, file_name="rex_log.txt", mime="text/plain", use_container_width=True)
    if _lc2.button("View Log", use_container_width=True):
        st.session_state["show_dev_log"] = not st.session_state.get("show_dev_log", False)
    if st.session_state.get("show_dev_log"):
        st.sidebar.code(log_text, language=None)

st.sidebar.divider()
if st.sidebar.button("Quit Rex"):
    import signal, os as _os
    st.markdown("<script>window.close();</script>", unsafe_allow_html=True)
    st.sidebar.info("Shutting down...")
    _os.kill(_os.getpid(), signal.SIGTERM)

# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
if page == "Dashboard":

    data = db.get_financial_data()
    accounts = db.get_accounts()
    db_assets = db.get_assets()

    liquid_assets = sum(a["balance"] for a in accounts if a["type"] not in ("Credit Card", "Loan"))
    liquid_liab   = abs(sum(a["balance"] for a in accounts if a["type"] in ("Credit Card", "Loan")))
    asset_values  = sum(a["value"] for a in db_assets)
    asset_liab    = sum(a["liability"] for a in db_assets)
    total_assets  = liquid_assets + asset_values
    total_liab    = liquid_liab + asset_liab
    net_worth     = total_assets - total_liab

    income_df = data["monthly_income_expense"]
    this_month_income   = float(income_df["income"].iloc[-1])   if not income_df.empty else 0.0
    this_month_expenses = float(income_df["expenses"].iloc[-1]) if not income_df.empty else 0.0
    net_month = this_month_income - this_month_expenses

    nw_color   = "#2ecc71" if net_worth >= 0 else "#e74c3c"
    net_color  = "#2ecc71" if net_month >= 0 else "#e74c3c"

    def _stat(label, value, color="#f0f0f0"):
        return (
            f'<div style="padding:10px 14px;border-radius:6px;background:rgba(255,255,255,0.04);'
            f'border:1px solid rgba(255,255,255,0.08);min-width:0">'
            f'<div style="font-size:0.68rem;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">{label}</div>'
            f'<div style="font-size:1.05rem;font-weight:600;color:{color};white-space:nowrap">{value}</div>'
            f'</div>'
        )

    kpis = "".join([
        _stat("Net Worth",        f"${net_worth:,.0f}",          nw_color),
        _stat("Total Assets",     f"${total_assets:,.0f}",        "#f0f0f0"),
        _stat("Liabilities",      f"${total_liab:,.0f}",          "#e74c3c" if total_liab else "#f0f0f0"),
        _stat("This Month In",    f"${this_month_income:,.0f}",   "#2ecc71"),
        _stat("This Month Out",   f"${this_month_expenses:,.0f}", "#e74c3c"),
        _stat("Net This Month",   f"${net_month:+,.0f}",          net_color),
    ])
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:16px">{kpis}</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # --- Row 1: Income vs Expenses | Category donut ---
    ch1, ch2 = st.columns([3, 2])

    with ch1:
        st.caption("INCOME VS EXPENSES")
        if not income_df.empty:
            fig = go.Figure()
            fig.add_bar(x=income_df["month"], y=income_df["income"],
                        name="In", marker_color="#2ecc71",
                        hovertemplate="<b>%{x}</b><br>In: $%{y:,.0f}<extra></extra>")
            fig.add_bar(x=income_df["month"], y=income_df["expenses"],
                        name="Out", marker_color="#e74c3c",
                        hovertemplate="<b>%{x}</b><br>Out: $%{y:,.0f}<extra></extra>")
            fig.update_layout(
                barmode="group", hovermode="x unified", height=260,
                margin=dict(t=10, b=30, l=40, r=10),
                legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
                yaxis=dict(tickprefix="$", tickformat=",.0f"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Import transactions to populate charts.")

    with ch2:
        st.caption("SPENDING BY CATEGORY")
        cat_df = data["category_totals"]
        if not cat_df.empty:
            fig = px.pie(cat_df, names="category", values="total", hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_traces(
                textposition="inside", textinfo="percent",
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f} · %{percent}<extra></extra>",
            )
            fig.update_layout(
                height=260, margin=dict(t=10, b=10, l=10, r=10),
                showlegend=True,
                legend=dict(font=dict(size=10), orientation="v", x=1.02),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No spending data yet.")

    # --- Row 2: Net Worth trend | Account balances table ---
    ch3, ch4 = st.columns([3, 2])

    with ch3:
        st.caption("NET WORTH OVER TIME")
        nw_df = data["net_worth_history"]
        if not nw_df.empty:
            fig = px.area(nw_df, x="snapshot_date", y="net_worth",
                          color_discrete_sequence=["#3498db"])
            fig.update_traces(
                hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
                line=dict(width=2), fillcolor="rgba(52,152,219,0.15)",
            )
            fig.update_layout(
                height=220, margin=dict(t=10, b=30, l=40, r=10),
                xaxis_title="", yaxis=dict(tickprefix="$", tickformat=",.0f"),
                hovermode="x unified",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No net worth history yet.")

    with ch4:
        st.caption("ACCOUNTS")
        acct_df = data["account_balances"]
        if not acct_df.empty:
            for _, row in acct_df.iterrows():
                bal = row["balance"]
                color = "#e74c3c" if row["type"] in ("Credit Card", "Loan") and bal > 0 else "#2ecc71"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.06);font-size:0.85rem">'
                    f'<span style="color:#ccc">{row["name"]} <span style="color:#666;font-size:0.75rem">· {row["type"]}</span></span>'
                    f'<span style="font-weight:600;color:{color}">${bal:,.0f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No accounts yet.")

# ---------------------------------------------------------------------------
# ACCOUNTS
# ---------------------------------------------------------------------------
elif page == "Accounts":
    st.title("Accounts")

    accounts = db.get_accounts()

    ACCT_TYPES = ["Checking", "Savings", "Credit Card", "Investment", "Loan", "Other"]
    SCOPES = ["Personal", "Business"]

    with st.expander("➕ Add Account", expanded=not accounts):
        with st.form("add_account"):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            name = c1.text_input("Name")
            acct_type = c2.selectbox("Type", ACCT_TYPES)
            institution = c3.text_input("Institution")
            scope = c4.selectbox("Scope", SCOPES)
            if st.form_submit_button("Add Account", use_container_width=True):
                if not name:
                    st.error("Account name is required.")
                else:
                    db.add_account(name, acct_type, institution, scope)
                    db.save_net_worth_snapshot()
                    st.success(f"'{name}' added.")
                    st.rerun()

    st.markdown("""
    <style>
    details:has(.acct-liability) {
        background: rgba(231,76,60,0.08) !important;
        border-left: 3px solid #e74c3c !important;
        border-radius: 6px;
    }
    details:has(.acct-asset) {
        background: rgba(46,204,113,0.08) !important;
        border-left: 3px solid #2ecc71 !important;
        border-radius: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    if accounts:
        for acct in accounts:
            scope_tag = acct.get("scope") or "Personal"
            is_liability = acct["type"] in ("Credit Card", "Loan")
            label = f"**{acct['name']}** &nbsp;·&nbsp; {acct['type']} &nbsp;·&nbsp; {acct['institution'] or '—'} &nbsp;·&nbsp; {scope_tag} &nbsp;·&nbsp; ${acct['balance']:,.2f}"
            with st.expander(label):
                # Hidden marker lets CSS :has() color the parent <details>
                st.markdown(
                    '<span class="acct-liability" style="display:none"></span>' if is_liability
                    else '<span class="acct-asset" style="display:none"></span>',
                    unsafe_allow_html=True,
                )
                with st.form(f"edit_acct_{acct['id']}"):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                    new_name = c1.text_input("Name", value=acct["name"])
                    new_type = c2.selectbox("Type", ACCT_TYPES,
                                            index=ACCT_TYPES.index(acct["type"]) if acct["type"] in ACCT_TYPES else 0)
                    new_inst = c3.text_input("Institution", value=acct["institution"] or "")
                    new_scope = c4.selectbox("Scope", SCOPES,
                                             index=SCOPES.index(scope_tag) if scope_tag in SCOPES else 0)
                    cs, cd = st.columns(2)
                    if cs.form_submit_button("Save", use_container_width=True):
                        db.update_account(acct["id"], new_name, new_type, new_inst, new_scope)
                        db.save_net_worth_snapshot()
                        st.success("Updated.")
                        st.rerun()
                    if cd.form_submit_button("Delete", type="secondary", use_container_width=True):
                        db.delete_account(acct["id"])
                        st.rerun()

                statements = db.get_account_statements(acct["id"])
                if statements:
                    st.caption("Statement History")
                    for s in statements:
                        sc1, sc2, sc3, sc4, sc5 = st.columns([3, 2, 2, 2, 2])
                        sc1.write(f"{s['opening_date']} → {s['closing_date']}")
                        sc2.write(f"Open: ${s['opening_balance']:,.2f}")
                        sc3.write(f"Charges: ${s['total_charges']:,.2f}")
                        sc4.write(f"Payments: ${s['total_credits']:,.2f}")
                        sc5.write(f"Close: ${s['closing_balance']:,.2f}")
    else:
        st.info("No accounts yet. Add one above.")

# ---------------------------------------------------------------------------
# ASSETS
# ---------------------------------------------------------------------------
elif page == "Assets":
    st.title("Assets & Liabilities")
    st.caption("Track physical and investment assets alongside any debts tied to them. These feed directly into your net worth.")

    assets = db.get_assets()
    ASSET_TYPES = db.ASSET_TYPES

    # Summary KPIs
    if assets:
        total_val = sum(a["value"] for a in assets)
        total_liab = sum(a["liability"] for a in assets)
        net = total_val - total_liab
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Asset Value", f"${total_val:,.2f}")
        k2.metric("Total Liabilities", f"${total_liab:,.2f}")
        k3.metric("Net Asset Value", f"${net:,.2f}")
        st.divider()

    with st.expander("➕ Add Asset", expanded=not assets):
        with st.form("add_asset"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Asset Name", placeholder="e.g. Primary Residence, 2022 Toyota Camry")
            asset_type = c2.selectbox("Type", ASSET_TYPES)
            value = c1.number_input("Current Value ($)", value=0.0, step=100.0, format="%.2f")
            liability = c2.number_input("Tied Liability ($)", value=0.0, step=100.0, format="%.2f",
                                        help="e.g. mortgage balance, car loan — enter as positive number")
            notes = st.text_input("Notes (optional)", placeholder="e.g. Appraised 2025-01")
            submitted = st.form_submit_button("Add Asset")
            if submitted:
                if not name.strip():
                    st.error("Asset name is required.")
                else:
                    db.add_asset(name.strip(), asset_type, value, liability, notes)
                    db.save_net_worth_snapshot()
                    st.success(f"'{name}' added.")
                    st.rerun()

    if assets:
        # Group by type
        by_type: dict = {}
        for a in assets:
            by_type.setdefault(a["type"], []).append(a)

        for atype, group in by_type.items():
            st.subheader(atype)
            for asset in group:
                net_val = asset["value"] - asset["liability"]
                label = f"{asset['name']} — Value: ${asset['value']:,.0f}  |  Liability: ${asset['liability']:,.0f}  |  Net: ${net_val:,.0f}"
                with st.expander(label):
                    with st.form(f"edit_asset_{asset['id']}"):
                        c1, c2 = st.columns(2)
                        new_name = c1.text_input("Name", value=asset["name"])
                        new_type = c2.selectbox("Type", ASSET_TYPES,
                                                index=ASSET_TYPES.index(asset["type"]) if asset["type"] in ASSET_TYPES else 0)
                        new_val = c1.number_input("Current Value ($)", value=float(asset["value"]), step=100.0, format="%.2f")
                        new_liab = c2.number_input("Tied Liability ($)", value=float(asset["liability"]), step=100.0, format="%.2f")
                        new_notes = st.text_input("Notes", value=asset["notes"] or "")
                        if asset.get("updated_at"):
                            st.caption(f"Last updated: {asset['updated_at']}")
                        col_save, col_del = st.columns(2)
                        save = col_save.form_submit_button("Save Changes")
                        delete = col_del.form_submit_button("Delete Asset", type="secondary")
                        if save:
                            db.update_asset(asset["id"], new_name, new_type, new_val, new_liab, new_notes)
                            db.save_net_worth_snapshot()
                            st.success("Updated.")
                            st.rerun()
                        if delete:
                            db.delete_asset(asset["id"])
                            db.save_net_worth_snapshot()
                            st.success("Deleted.")
                            st.rerun()

        # Asset breakdown chart
        st.divider()
        st.subheader("Asset Breakdown")
        chart_data = [{"Asset": a["name"], "Value": a["value"], "Liability": a["liability"],
                       "Net": a["value"] - a["liability"]} for a in assets]
        chart_df = pd.DataFrame(chart_data)
        fig = go.Figure()
        fig.add_bar(x=chart_df["Asset"], y=chart_df["Value"], name="Value", marker_color="#3498db",
                    hovertemplate="<b>%{x}</b><br>Value: $%{y:,.2f}<extra></extra>")
        fig.add_bar(x=chart_df["Asset"], y=chart_df["Liability"], name="Liability", marker_color="#e74c3c",
                    hovertemplate="<b>%{x}</b><br>Liability: $%{y:,.2f}<extra></extra>")
        fig.add_bar(x=chart_df["Asset"], y=chart_df["Net"], name="Net", marker_color="#2ecc71",
                    hovertemplate="<b>%{x}</b><br>Net: $%{y:,.2f}<extra></extra>")
        fig.update_layout(barmode="group", margin=dict(t=20, b=20), xaxis_title="", yaxis_title="Amount ($)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No assets yet. Add one above.")

# ---------------------------------------------------------------------------
# TRANSACTIONS
# ---------------------------------------------------------------------------
elif page == "Transactions":
    st.title("Transactions")

    accounts = db.get_accounts()
    account_map = {a["name"]: a["id"] for a in accounts}

    tab_labels = ["View & Edit", "Categories", "Import"]
    if dev_mode:
        tab_labels.append("Import Log")
    tabs = st.tabs(tab_labels)
    tab1, tab3, tab4 = tabs[0], tabs[1], tabs[2]
    tab5 = tabs[3] if dev_mode else None

    with tab1:
        fc1, fc2, fc3 = st.columns([2, 2, 1])
        filter_acct = fc1.selectbox("Filter by Account", ["All"] + [a["name"] for a in accounts])
        filter_cat = fc2.selectbox("Filter by Category", ["All"] + db.get_categories())
        with fc3:
            st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
            if st.button("＋ Add", use_container_width=True):
                st.session_state["show_add_txn"] = not st.session_state.get("show_add_txn", False)

        if st.session_state.get("show_add_txn"):
            with st.form("add_txn"):
                fa1, fa2 = st.columns(2)
                add_acct = fa1.selectbox("Account", [a["name"] for a in accounts])
                add_date = fa2.date_input("Date", value=datetime.today())
                add_desc = fa1.text_input("Description")
                add_amt  = fa2.number_input("Amount (negative = expense)", value=0.0, step=0.01, format="%.2f")
                cat_options = db.get_categories()
                add_cat  = st.selectbox("Category", cat_options, index=cat_options.index("Uncategorized") if "Uncategorized" in cat_options else 0)
                add_note = st.text_input("Notes (optional)")
                a1, a2 = st.columns(2)
                if a1.form_submit_button("Add Transaction", use_container_width=True):
                    if not add_desc:
                        st.error("Description is required.")
                    else:
                        db.insert_transaction(account_map[add_acct], add_date.strftime("%Y-%m-%d"), add_desc, add_amt, add_cat, add_note)
                        st.session_state["show_add_txn"] = False
                        st.success("Transaction added.")
                        st.rerun()
                if a2.form_submit_button("Cancel", use_container_width=True):
                    st.session_state["show_add_txn"] = False
                    st.rerun()
        acct_id_filter = account_map.get(filter_acct) if filter_acct != "All" else None
        txns = db.get_transactions(account_id=acct_id_filter, limit=2000)

        if filter_cat != "All":
            txns = [t for t in txns if t.get("category") == filter_cat]

        # Column visibility — persisted in session state so reruns don't reset it
        all_cols = ["date", "name", "raw description", "amount", "category", "account", "notes", "exclude"]
        default_cols = ["date", "name", "amount", "category", "exclude"]
        if "txn_visible_cols" not in st.session_state:
            st.session_state["txn_visible_cols"] = default_cols
        visible = st.multiselect(
            "Visible columns", all_cols, default=st.session_state["txn_visible_cols"], key="txn_col_picker"
        )
        st.session_state["txn_visible_cols"] = visible

        if txns:
            df = pd.DataFrame(txns)
            cat_options = db.get_categories()

            df["name"] = df.apply(
                lambda r: r["merchant_name"] if r.get("merchant_name") else r["description"], axis=1
            )
            df["exclude"] = df["excluded"].apply(lambda v: bool(v))
            df["date"] = pd.to_datetime(df["date"], errors="coerce").apply(
                lambda d: d.strftime("%B %-d (%a)") if pd.notna(d) else ""
            )
            df = df.rename(columns={"account_name": "account", "description": "raw description"})

            # Map visible col names to df col names
            col_map = {
                "date": "date", "name": "name", "raw description": "raw description",
                "amount": "amount", "category": "category",
                "account": "account", "notes": "notes", "exclude": "exclude",
            }
            show_cols = ["id"] + [col_map[c] for c in visible if c in col_map]
            # Always include id (hidden) for saving
            table_df = df[show_cols].copy()

            st.data_editor(
                table_df,
                use_container_width=True,
                hide_index=True,
                disabled=["id", "date", "account", "raw description"],
                column_config={
                    "id": None,
                    "date": st.column_config.TextColumn("Date"),
                    "name": st.column_config.TextColumn("Name"),
                    "raw description": st.column_config.TextColumn("Raw Description"),
                    "amount": st.column_config.NumberColumn("Amount ($)", format="%.2f"),
                    "category": st.column_config.SelectboxColumn("Category", options=cat_options),
                    "account": st.column_config.TextColumn("Account"),
                    "notes": st.column_config.TextColumn("Notes"),
                    "exclude": st.column_config.CheckboxColumn("Exclude", help="Remove from expense totals & charts"),
                },
                num_rows="fixed",
                key="txn_editor",
            )

            if st.button("Save Changes"):
                # Read only the actual edited cells from session state — reliable across reruns
                editor_state = st.session_state.get("txn_editor", {})
                edited_rows = editor_state.get("edited_rows", {})
                changed = 0
                for row_idx, changes in edited_rows.items():
                    txn_id = int(table_df.iloc[int(row_idx)]["id"])
                    if "category" in changes or "notes" in changes:
                        current = df[df["id"] == txn_id].iloc[0]
                        cat = changes.get("category", current["category"])
                        notes = changes.get("notes", current.get("notes") or "")
                        db.update_transaction(txn_id, cat, str(notes or ""))
                        changed += 1
                    if "name" in changes:
                        db.update_transaction_merchant_name(txn_id, str(changes["name"] or ""))
                        changed += 1
                    if "exclude" in changes:
                        db.set_transaction_excluded(txn_id, bool(changes["exclude"]))
                        changed += 1
                if changed:
                    # Clear the editor state so it reloads clean
                    st.session_state.pop("txn_editor", None)
                    st.success(f"Saved {changed} change(s).")
                    st.rerun()
                else:
                    st.info("No changes to save.")

            st.divider()
            st.subheader("Delete a Transaction")
            txn_labels = [f"{t['date']} — {t['description'][:45]} — ${t['amount']:.2f}" for t in txns]
            selected_label = st.selectbox("Select transaction to delete", ["— select a transaction —"] + txn_labels)
            if selected_label != "— select a transaction —":
                selected_txn = txns[txn_labels.index(selected_label)]
                if st.button("Delete Selected", type="secondary"):
                    db.delete_transaction(selected_txn["id"])
                    st.session_state.pop("txn_editor", None)
                    st.success("Deleted.")
                    st.rerun()
        else:
            st.info("No transactions yet.")

    with tab3:
        st.subheader("Manage Categories")
        categories = db.get_categories()

        # Add new category
        with st.form("add_category"):
            new_cat_name = st.text_input("New Category Name")
            submitted = st.form_submit_button("Add Category")
            if submitted:
                name_clean = new_cat_name.strip()
                if not name_clean:
                    st.error("Category name cannot be empty.")
                else:
                    ok = db.add_category(name_clean)
                    if ok:
                        st.success(f"'{name_clean}' added.")
                        st.rerun()
                    else:
                        st.warning(f"'{name_clean}' already exists.")

        st.divider()
        st.write(f"**{len(categories)} categories**")

        # List all categories with delete button for custom ones
        # Load which are default
        import sqlite3 as _sqlite3
        _conn = db.get_connection()
        _rows = _conn.execute("SELECT name, is_default FROM categories ORDER BY name").fetchall()
        _conn.close()

        for row in _rows:
            col_name, col_btn = st.columns([5, 1])
            col_name.write(f"{'🔒' if row['is_default'] else '✏️'} {row['name']}")
            if not row["is_default"]:
                if col_btn.button("Delete", key=f"del_cat_{row['name']}"):
                    db.delete_category(row["name"])
                    st.success(f"'{row['name']}' deleted. Transactions reset to Uncategorized.")
                    st.rerun()
            else:
                col_btn.write("")

        st.divider()
        st.subheader("Merchant Name Rules")
        st.caption("These patterns are matched against raw bank descriptions to auto-apply friendly names on import.")

        rules = db.get_merchant_rules()

        with st.expander("➕ Add Rule Manually"):
            with st.form("add_rule"):
                c1, c2 = st.columns(2)
                rule_pattern = c1.text_input("Pattern (normalized keyword, e.g. AMAZON CORP)")
                rule_name = c2.text_input("Friendly Name (e.g. Amazon)")
                if st.form_submit_button("Add Rule"):
                    if rule_pattern.strip() and rule_name.strip():
                        ok = db.add_merchant_rule(rule_pattern, rule_name)
                        st.success("Rule added." if ok else "Pattern already exists.")
                        st.rerun()
                    else:
                        st.error("Both fields are required.")

        if rules:
            for rule in rules:
                c1, c2, c3 = st.columns([3, 3, 1])
                c1.code(rule["pattern"], language=None)
                c2.write(rule["friendly_name"])
                if c3.button("Delete", key=f"del_rule_{rule['id']}"):
                    db.delete_merchant_rule(rule["id"])
                    st.rerun()
        else:
            st.info("No rules yet — they're created automatically when you save names after import.")

    with tab4:
        if not accounts:
            st.warning("Add an account first.")
        else:
            import tempfile, os, hashlib

            # ── Name Review state (shown instead of uploader after import) ────
            if "review_stmt_id" in st.session_state:
                stmt_id = st.session_state["review_stmt_id"]
                inserted = st.session_state.get("review_inserted", 0)
                txns = db.get_statement_transactions(stmt_id)

                # Group by unique description → current merchant_name
                seen = {}
                for t in txns:
                    d = t["description"]
                    if d not in seen:
                        seen[d] = {"merchant_name": t["merchant_name"] or "", "has_rule": bool(db.find_matching_rule(d))}

                needs_review = {d: v for d, v in seen.items() if not v["has_rule"]}
                auto_names   = {d: v for d, v in seen.items() if  v["has_rule"]}

                st.markdown(f"**Review {inserted} imported transactions** — confirm or edit names below, then they'll auto-apply next time.")

                if needs_review:
                    st.caption(f"{len(needs_review)} AI-guessed names need confirmation")
                    for desc, info in needs_review.items():
                        rc1, rc2, rc3 = st.columns([3, 3, 1])
                        rc1.markdown(f"<small style='color:#888'>{desc[:55]}</small>", unsafe_allow_html=True)
                        new_name = rc2.text_input("", value=info["merchant_name"], key=f"rev_{desc}", label_visibility="collapsed")
                        if rc3.button("✓", key=f"conf_{desc}", help="Confirm and save as rule"):
                            from parsers import normalize_description
                            db.add_merchant_rule(normalize_description(desc), new_name.strip() or info["merchant_name"])
                            db.bulk_update_merchant_name(desc, new_name.strip() or info["merchant_name"])
                            db.save_net_worth_snapshot()
                            st.rerun()
                else:
                    # All confirmed — show category summary
                    st.success(f"✅ All names confirmed — {inserted} transactions imported")
                    cat_summary = {}
                    for t in txns:
                        cat = t["category"] or "Uncategorized"
                        cat_summary.setdefault(cat, {"count": 0, "total": 0.0})
                        cat_summary[cat]["count"] += 1
                        cat_summary[cat]["total"] += t["amount"]

                    rows_html = ""
                    for cat, s in sorted(cat_summary.items(), key=lambda x: -abs(x[1]["total"])):
                        color = "#e74c3c" if s["total"] < 0 else "#2ecc71"
                        rows_html += (
                            f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr;"
                            f"padding:5px 8px;border-top:1px solid #222;font-size:0.85rem'>"
                            f"<span>{cat}</span>"
                            f"<span style='color:#888'>{s['count']} txns</span>"
                            f"<span style='color:{color};text-align:right'>${s['total']:,.2f}</span>"
                            f"</div>"
                        )
                    st.markdown(
                        f"<div style='border:1px solid #333;border-radius:6px;margin:10px 0'>"
                        f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr;padding:4px 8px;"
                        f"font-size:0.68rem;color:#666;text-transform:uppercase'>"
                        f"<span>Category</span><span>Count</span><span style='text-align:right'>Total</span></div>"
                        f"{rows_html}</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("Done ✓", type="primary"):
                        st.session_state.pop("review_stmt_id", None)
                        st.session_state.pop("review_inserted", None)
                        st.rerun()
                st.stop()

            # Success message lives outside the uploader block so it survives widget reset
            if st.session_state.get("import_success_msg"):
                st.success(st.session_state.pop("import_success_msg"))

            acct_name = st.selectbox("Import into Account", [a["name"] for a in accounts])

            if "uploader_key" not in st.session_state:
                st.session_state["uploader_key"] = 0
            uploaded = st.file_uploader(
                "Upload CSV or Chase PDF", type=["csv", "pdf"],
                key=f"uploader_{st.session_state['uploader_key']}",
            )

            if uploaded:
                file_key = f"csv_{uploaded.name}_{uploaded.size}"
                if st.session_state.get("csv_file_key") != file_key:
                    is_pdf = uploaded.name.lower().endswith(".pdf")
                    suffix = ".pdf" if is_pdf else ".csv"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded.read())
                        tmp_path = tmp.name
                    try:
                        acct_id = account_map[acct_name]
                        if is_pdf:
                            parsed_df, stmt_meta = parsers.parse_chase_pdf(tmp_path, acct_id)
                        else:
                            parsed_df = parsers.parse_csv(tmp_path, acct_id)
                            # Build statement metadata from the transaction data
                            opening_balance = db.get_latest_statement_closing_balance(acct_id)
                            total_credits = float(parsed_df[parsed_df["amount"] > 0]["amount"].sum())
                            total_charges = float(parsed_df[parsed_df["amount"] < 0]["amount"].abs().sum())
                            closing_balance = opening_balance + total_credits - total_charges
                            stmt_meta = {
                                "opening_date": str(parsed_df["date"].min()),
                                "closing_date": str(parsed_df["date"].max()),
                                "opening_balance": opening_balance,
                                "closing_balance": closing_balance,
                                "total_charges": total_charges,
                                "total_credits": total_credits,
                            }
                        st.session_state["stmt_meta"] = stmt_meta
                        st.session_state["csv_file_key"] = file_key
                        st.session_state["csv_df"] = parsed_df
                        st.session_state["csv_acct_id"] = acct_id
                        st.session_state["csv_imported"] = False
                        st.session_state.pop("pending_names", None)
                    except ValueError as e:
                        st.error(str(e))
                        st.session_state.pop("csv_df", None)
                    finally:
                        os.unlink(tmp_path)

                if "csv_df" in st.session_state:
                    parsed_df = st.session_state["csv_df"]
                    acct_id = st.session_state["csv_acct_id"]

                    all_hashes = [
                        hashlib.md5(f"{acct_id}|{row['date']}|{row['description']}|{row['amount']}".encode()).hexdigest()
                        for _, row in parsed_df.iterrows()
                    ]

                    stmt_meta = st.session_state.get("stmt_meta")

                    # ── Header row: title + button ──────────────────────────
                    hcol1, hcol2 = st.columns([2, 1])
                    with hcol1:
                        period = ""
                        if stmt_meta:
                            period = f" &nbsp;·&nbsp; {stmt_meta['opening_date']} → {stmt_meta['closing_date']}"
                        st.markdown(
                            f"<div style='padding-top:6px;font-size:0.9rem;font-weight:600'>"
                            f"{len(parsed_df)} transactions{period}</div>",
                            unsafe_allow_html=True,
                        )
                    with hcol2:
                        do_import = st.button("⚡ Begin Import", use_container_width=True)

                    # ── Statement summary bar ───────────────────────────────
                    if stmt_meta:
                        m = stmt_meta
                        def _pill(label, val, color="#888"):
                            return (
                                f"<span style='margin-right:18px'>"
                                f"<span style='font-size:0.68rem;color:#888;text-transform:uppercase;letter-spacing:.04em'>{label}</span> "
                                f"<span style='font-size:0.88rem;font-weight:600;color:{color}'>{val}</span>"
                                f"</span>"
                            )
                        bar = (
                            _pill("Open", f"${m['opening_balance']:,.2f}") +
                            _pill("Charges", f"−${m['total_charges']:,.2f}", "#e74c3c") +
                            _pill("Payments", f"+${m['total_credits']:,.2f}", "#2ecc71") +
                            _pill("Close", f"${m['closing_balance']:,.2f}", "#3498db")
                        )
                        st.markdown(
                            f"<div style='padding:6px 0 10px 0;border-bottom:1px solid #333;margin-bottom:10px'>{bar}</div>",
                            unsafe_allow_html=True,
                        )

                    # ── Processing block (above preview so spinner shows at top) ──
                    if do_import:
                        try:
                            with st.spinner("Asking AI to categorize and name transactions..."):
                                from rex import enrich_transactions
                                descriptions = parsed_df["description"].astype(str).tolist()
                                _dev_log(f"Import started: {len(descriptions)} transactions for account_id={acct_id}")

                                # Check merchant rules first; only AI-enrich what's not covered
                                rule_names = {}
                                need_ai_idx = []
                                for i, desc in enumerate(descriptions):
                                    matched = db.find_matching_rule(desc)
                                    if matched:
                                        rule_names[i] = matched
                                    else:
                                        need_ai_idx.append(i)

                                _dev_log(f"Rule matches: {len(rule_names)} | Sending to AI: {len(need_ai_idx)}")
                                ai_results = {}
                                if need_ai_idx:
                                    ai_batch = [descriptions[i] for i in need_ai_idx]
                                    _dev_log(f"AI batch sample (first 3): {ai_batch[:3]}")
                                    try:
                                        enriched = enrich_transactions(ai_batch)
                                        _dev_log(f"AI response sample (first 3): {enriched[:3]}")
                                        for list_pos, orig_idx in enumerate(need_ai_idx):
                                            ai_results[orig_idx] = enriched[list_pos]
                                    except Exception as ai_exc:
                                        _dev_log(f"AI ERROR: {type(ai_exc).__name__}: {ai_exc}")
                                        raise

                            stmt_id = None
                            if stmt_meta:
                                stmt_id = db.insert_statement(
                                    acct_id,
                                    stmt_meta["opening_date"], stmt_meta["closing_date"],
                                    stmt_meta["opening_balance"], stmt_meta["closing_balance"],
                                    stmt_meta["total_charges"], stmt_meta["total_credits"],
                                )

                            inserted = linked = 0
                            for i, (_, row) in enumerate(parsed_df.iterrows()):
                                src_hash = all_hashes[i]
                                if i in rule_names:
                                    mname = rule_names[i]
                                    r = ai_results.get(i, {})
                                    category = r.get("category") or "Uncategorized"
                                else:
                                    r = ai_results.get(i, {})
                                    mname = r.get("name") or str(row["description"])
                                    category = r.get("category") or "Uncategorized"

                                ok = db.insert_transaction(
                                    acct_id, str(row["date"]), str(row["description"]),
                                    float(row["amount"]), category,
                                    source_hash=src_hash, merchant_name=mname,
                                    statement_id=stmt_id,
                                )
                                if ok:
                                    inserted += 1
                                else:
                                    linked += 1

                            db.save_net_worth_snapshot()
                            # Go to name review instead of straight success
                            st.session_state["review_stmt_id"] = stmt_id
                            st.session_state["review_inserted"] = inserted
                            for k in ["csv_file_key", "csv_df", "csv_acct_id", "stmt_meta"]:
                                st.session_state.pop(k, None)
                            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                            st.rerun()

                        except Exception as exc:
                            import traceback
                            _dev_log(f"IMPORT FAILED: {type(exc).__name__}: {exc}")
                            _dev_log(traceback.format_exc())
                            st.error(f"Import failed: {exc}")

                    else:
                        # ── Preview: 3 rows, shown only when not importing ──────
                        preview_df = parsed_df.head(3)[["date", "description", "amount"]].copy()
                        preview_df["amount"] = preview_df["amount"].map(lambda x: f"${x:,.2f}")
                        st.dataframe(preview_df, use_container_width=True, hide_index=True)

    if dev_mode and tab5:
        with tab5:
            st.subheader("Import Log")
            imports = db.get_all_imports()
            if not imports:
                st.info("No imports yet.")
            else:
                # Header row
                st.markdown(
                    "<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 40px;"
                    "gap:8px;padding:4px 8px;font-size:0.68rem;color:#666;"
                    "text-transform:uppercase;letter-spacing:.04em'>"
                    "<span>Account · Period</span><span>Open</span><span>Charges</span>"
                    "<span>Credits</span><span>Close · Txns</span><span></span></div>",
                    unsafe_allow_html=True,
                )
                for imp in imports:
                    row_html = (
                        f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 40px;"
                        f"gap:8px;padding:6px 8px;border-top:1px solid #222;font-size:0.82rem;"
                        f"align-items:center'>"
                        f"<span><b>{imp['account_name']}</b> &nbsp;{imp['opening_date']} → {imp['closing_date']}</span>"
                        f"<span style='color:#aaa'>{imp['opening_balance']:,.2f}</span>"
                        f"<span style='color:#e74c3c'>-{imp['total_charges']:,.2f}</span>"
                        f"<span style='color:#2ecc71'>+{imp['total_credits']:,.2f}</span>"
                        f"<span style='color:#3498db'>{imp['closing_balance']:,.2f} &nbsp;<span style='color:#666'>{imp['txn_count']}t</span></span>"
                        f"<span></span>"
                        f"</div>"
                    )
                    lc, rc = st.columns([12, 1])
                    lc.markdown(row_html, unsafe_allow_html=True)
                    if rc.button("🗑", key=f"log_del_{imp['id']}", help="Delete this import"):
                        count = db.delete_import(imp["id"])
                        db.save_net_worth_snapshot()
                        st.success(f"Deleted — {count} transactions removed.")
                        st.rerun()

            # Orphaned transactions (no linked statement — e.g. imported before statements were tracked)
            orphan_counts = db.get_orphaned_transaction_counts()
            if orphan_counts:
                st.divider()
                st.caption("Untracked transactions (imported before statement logging was added)")
                for acct_id, acct_name, count in orphan_counts:
                    oc1, oc2 = st.columns([10, 2])
                    oc1.markdown(f"**{acct_name}** — {count} transactions with no import record")
                    if oc2.button("Clear", key=f"clear_orphan_{acct_id}"):
                        db.delete_orphaned_transactions(acct_id)
                        db.save_net_worth_snapshot()
                        st.success(f"Cleared {count} orphaned transactions from {acct_name}.")
                        st.rerun()

# ---------------------------------------------------------------------------
# GOALS
# ---------------------------------------------------------------------------
elif page == "Goals":
    st.title("Goals")

    goals = db.get_goals()

    with st.expander("➕ Add Goal", expanded=not goals):
        with st.form("add_goal"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Goal Name")
            goal_type = c2.selectbox("Type", ["Cash Flow", "Savings", "Debt Paydown", "Investment", "Custom"])
            target = c1.number_input("Target Amount ($)", value=0.0, step=0.01, format="%.2f")
            current = c2.number_input("Current Amount ($)", value=0.0, step=0.01, format="%.2f")
            deadline = st.date_input("Deadline")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Goal")
            if submitted:
                if not name:
                    st.error("Goal name is required.")
                else:
                    db.add_goal(name, goal_type, target, current, deadline.strftime("%Y-%m-%d"), notes)
                    st.success("Goal added.")
                    st.rerun()

    if goals:
        for goal in goals:
            progress = min((goal["current_amount"] / goal["target_amount"]) if goal["target_amount"] else 0, 1.0)
            label = f"{goal['name']} — {goal['type']} — ${goal['current_amount']:,.0f} / ${goal['target_amount']:,.0f}"
            with st.expander(label):
                st.progress(progress, text=f"{progress*100:.1f}%")
                with st.form(f"edit_goal_{goal['id']}"):
                    c1, c2 = st.columns(2)
                    new_name = c1.text_input("Name", value=goal["name"])
                    new_type = c2.selectbox("Type", ["Cash Flow", "Savings", "Debt Paydown", "Investment", "Custom"],
                                            index=["Cash Flow", "Savings", "Debt Paydown", "Investment", "Custom"].index(goal["type"]) if goal["type"] in ["Cash Flow", "Savings", "Debt Paydown", "Investment", "Custom"] else 0)
                    new_target = c1.number_input("Target ($)", value=float(goal["target_amount"] or 0), step=0.01, format="%.2f")
                    new_current = c2.number_input("Current ($)", value=float(goal["current_amount"] or 0), step=0.01, format="%.2f")
                    new_deadline = st.text_input("Deadline (YYYY-MM-DD)", value=goal["deadline"] or "")
                    new_notes = st.text_area("Notes", value=goal["notes"] or "")
                    col_save, col_del = st.columns(2)
                    save = col_save.form_submit_button("Save")
                    delete = col_del.form_submit_button("Delete", type="secondary")
                    if save:
                        db.update_goal(goal["id"], new_name, new_type, new_target, new_current, new_deadline, new_notes)
                        st.success("Updated.")
                        st.rerun()
                    if delete:
                        db.delete_goal(goal["id"])
                        st.success("Deleted.")
                        st.rerun()
    else:
        st.info("No goals yet. Add one above.")

# ---------------------------------------------------------------------------
# REMINDERS
# ---------------------------------------------------------------------------
elif page == "Reminders":
    st.title("Reminders")

    show_done = st.checkbox("Show completed reminders")
    reminders = db.get_reminders(include_done=show_done)

    with st.expander("➕ Add Reminder"):
        with st.form("add_reminder"):
            c1, c2 = st.columns(2)
            title = c1.text_input("Title")
            due_date = c2.date_input("Due Date")
            notes = st.text_input("Notes (optional)")
            submitted = st.form_submit_button("Add Reminder")
            if submitted:
                if not title:
                    st.error("Title is required.")
                else:
                    db.add_reminder(title, due_date.strftime("%Y-%m-%d"), notes)
                    st.success("Reminder added.")
                    st.rerun()

    if reminders:
        for r in reminders:
            status = "✅" if r["done"] else "🔔"
            with st.expander(f"{status} {r['title']} — {r.get('due_date', '')}"):
                if r["notes"]:
                    st.write(r["notes"])
                c1, c2 = st.columns(2)
                if not r["done"]:
                    if c1.button("Mark Done", key=f"done_{r['id']}"):
                        db.mark_reminder_done(r["id"])
                        st.rerun()
                if c2.button("Delete", key=f"del_rem_{r['id']}"):
                    db.delete_reminder(r["id"])
                    st.rerun()
    else:
        st.info("No reminders.")

# ---------------------------------------------------------------------------
# CHAT WITH REX
# ---------------------------------------------------------------------------
elif page == "Chat with Rex":
    st.title("Chat with Rex")
    st.caption("Your brutally honest personal finance AI.")

    if "rex_history" not in st.session_state:
        st.session_state.rex_history = []

    # Build financial context summary for Rex
    accounts = db.get_accounts()
    txns = db.get_transactions(limit=50)
    goals = db.get_goals()

    context_parts = []
    if accounts:
        total_assets = sum(a["balance"] for a in accounts if a["type"] not in ("Credit Card", "Loan"))
        total_liab = abs(sum(a["balance"] for a in accounts if a["type"] in ("Credit Card", "Loan")))
        context_parts.append(f"Net worth: ${total_assets - total_liab:,.2f} (assets ${total_assets:,.2f}, liabilities ${total_liab:,.2f})")
        context_parts.append("Accounts: " + ", ".join(
            f"{a['name']} ({a['type']}, {a.get('scope','Personal')}) balance=${a['balance']:,.2f}" for a in accounts
        ))
        # Statement history per account
        stmt_lines = []
        for a in accounts:
            stmts = db.get_account_statements(a["id"])
            for s in stmts:
                net = s["total_credits"] - s["total_charges"]
                stmt_lines.append(
                    f"{a['name']} {s['opening_date']}→{s['closing_date']}: "
                    f"opening=${s['opening_balance']:,.2f} charges=${s['total_charges']:,.2f} "
                    f"credits=${s['total_credits']:,.2f} closing=${s['closing_balance']:,.2f} net={net:+,.2f}"
                )
        if stmt_lines:
            context_parts.append("Statement history:\n" + "\n".join(stmt_lines))
    if txns:
        recent = txns[:10]
        context_parts.append("Recent transactions: " + "; ".join(f"{t['date']} {t['description']} ${t['amount']}" for t in recent))
    if goals:
        context_parts.append("Goals: " + ", ".join(f"{g['name']} (${g['current_amount']:,.0f}/${g['target_amount']:,.0f})" for g in goals))

    financial_context = "\n".join(context_parts)

    # Display chat history
    for msg in st.session_state.rex_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask Rex anything about your finances...")
    if user_input:
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Rex is thinking..."):
                response = chat_with_rex(
                    user_input,
                    st.session_state.rex_history,
                    financial_context=financial_context,
                )
            st.write(response)

    if st.session_state.rex_history and st.button("Clear conversation"):
        st.session_state.rex_history = []
        st.rerun()
