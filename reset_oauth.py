#!/usr/bin/env python3
"""
reset_oauth.py — Reset QBO OAuth state for a clean reconnect.
Run this once, then restart your Streamlit app and click Connect again.

Usage:
    python3 reset_oauth.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q42.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Reset QBO connection to clean disconnected state
    conn.execute("""
        UPDATE q42_connections SET
            status='disconnected',
            access_token='', refresh_token='', token_expires_at='',
            company_id='', oauth_state=NULL,
            updated_at=datetime('now')
        WHERE service = 'qbo'
    """)
    conn.commit()

    # Verify
    cur = conn.cursor()
    cur.execute(
        "SELECT service, status, company_id, display_name FROM q42_connections"
    )
    print("\n--- Current connection state ---")
    for row in cur.fetchall():
        r = dict(row)
        print(f"  {r['service']}: status={r['status']}, company_id='{r['company_id']}', display={r['display_name']}")

    conn.close()
    print("\nDone! QBO connection reset to 'disconnected'.")
    print("Restart Streamlit and click Connect to re-authorize.\n")


if __name__ == "__main__":
    main()
