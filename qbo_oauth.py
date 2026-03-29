"""
qbo_oauth.py — QuickBooks Online OAuth2 flow for Portal42.
"""
from __future__ import annotations

import base64
import secrets
import urllib.parse

import httpx

QBO_AUTH_URL  = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_SCOPE     = "com.intuit.quickbooks.accounting"


def generate_state() -> str:
    return "qbo:" + secrets.token_urlsafe(20)


def get_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = urllib.parse.urlencode({
        "client_id":     client_id,
        "response_type": "code",
        "scope":         QBO_SCOPE,
        "redirect_uri":  redirect_uri,
        "state":         state,
    })
    return f"{QBO_AUTH_URL}?{params}"


def _auth_header(client_id: str, client_secret: str) -> str:
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return f"Basic {encoded}"


def exchange_code(client_id: str, client_secret: str,
                  code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            QBO_TOKEN_URL,
            headers={
                "Authorization": _auth_header(client_id, client_secret),
                "Accept":        "application/json",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(client_id: str, client_secret: str,
                          refresh_token: str) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            QBO_TOKEN_URL,
            headers={
                "Authorization": _auth_header(client_id, client_secret),
                "Accept":        "application/json",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


def get_company_info(access_token: str, realm_id: str) -> dict:
    """Return basic company info from QBO."""
    import os as _os
    base = (
        "https://sandbox-quickbooks.api.intuit.com"
        if _os.environ.get("QBO_SANDBOX", "true").lower() != "false"
        else "https://quickbooks.api.intuit.com"
    )
    url = f"{base}/v3/company/{realm_id}/companyinfo/{realm_id}"
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept":        "application/json",
            },
            params={"minorversion": "65"},
        )
        resp.raise_for_status()
        return resp.json().get("CompanyInfo", {})
