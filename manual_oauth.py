#!/usr/bin/env python3
"""
manual_oauth.py — Manually exchange an OAuth callback URL.

When the tunnel gives you a blank page, copy the full URL from your
browser's address bar and paste it here. This script extracts the code,
exchanges it for tokens, and saves them to the database.

Usage:
    python3 manual_oauth.py "https://rex.myeasyapp.com/?code=XAB...&state=qbo%3A...&realmId=1234"
    python3 manual_oauth.py   (interactive — will prompt for the URL)
"""
from __future__ import annotations

import os
import sys
import sqlite3
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # dotenv not required if env vars are already set

import qbo_oauth

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q42.db")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://rex.myeasyapp.com").rstrip("/")
QBO_CLIENT_ID = os.environ.get("QBO_CLIENT_ID", "")
QBO_CLIENT_SECRET = os.environ.get("QBO_CLIENT_SECRET", "")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def process_url(url: str):
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    code = params.get("code")
    state = params.get("state", "")
    realm_id = params.get("realmId", "")

    if not code:
        print("ERROR: No 'code' parameter found in URL.")
        return

    print(f"  Code:     {code[:20]}…")
    print(f"  State:    {state}")
    if realm_id:
        print(f"  RealmId:  {realm_id}")

    if realm_id:
        # ── QBO ────────────────────────────────────────────────────────
        print(f"\n→ Processing as QBO callback (realm {realm_id})...")
        print(f"  Using redirect_uri: {REDIRECT_URI}")

        try:
            tokens = qbo_oauth.exchange_code(
                QBO_CLIENT_ID, QBO_CLIENT_SECRET, code, REDIRECT_URI
            )
        except Exception as exc:
            print(f"\n  FAILED to exchange code: {exc}")
            print("  (Codes expire in ~60 seconds. If it's been longer, try again.)")
            return

        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token", "")
        expires_in = tokens.get("expires_in", 3600)
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

        # Get company info
        try:
            info = qbo_oauth.get_company_info(access_token, realm_id)
            display_name = info.get("CompanyName", "") or f"QBO {realm_id}"
            legal_name = info.get("LegalName", "")
            addr = info.get("CompanyAddr", {})
            city = addr.get("City", "")
            region = addr.get("CountrySubDivisionCode", "")
            print(f"\n  Company:    {display_name}")
            if legal_name and legal_name != display_name:
                print(f"  Legal name: {legal_name}")
            if city or region:
                print(f"  Location:   {city}, {region}")
        except Exception:
            display_name = f"QBO {realm_id}"
            print(f"  (Could not fetch company info, using: {display_name})")

        # Save tokens
        conn = db()
        conn.execute(
            "UPDATE q42_connections SET status='connected', "
            "access_token=?, refresh_token=?, token_expires_at=?, "
            "display_name=?, company_id=?, oauth_state=NULL, "
            "updated_at=datetime('now') WHERE service='qbo'",
            (access_token, refresh_token, expires_at, display_name, realm_id),
        )
        conn.commit()
        conn.close()
        print(f"\n  ✓ QBO connected! Realm: {realm_id}")
        print(f"  ✓ Tokens saved. Go to http://localhost:8501 → Q42 → Connections")

    else:
        # FreshBooks support removed
        print("\n→ ERROR: FreshBooks integration has been removed.")
        print("  Please use QBO (QuickBooks Online) instead.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        print("Paste the full callback URL from your browser:")
        url = input("> ").strip()

    if not url:
        print("No URL provided.")
        sys.exit(1)

    print(f"\nParsing: {url[:80]}…\n")
    process_url(url)
