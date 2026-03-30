# FreshBooks Reconnect — Verification Checklist

When re-enabling the FreshBooks OAuth flow, one field must be verified before
Invoice Reconciliation can call the API correctly.

---

## The thing to verify

After a successful OAuth callback, the FreshBooks `account_id` must be saved
to the `company_id` column of `q42_connections` for `service = 'freshbooks'`.

```sql
SELECT service, status, company_id, display_name
FROM q42_connections
WHERE service = 'freshbooks';
```

`company_id` should hold the numeric FreshBooks account ID — the string that
appears in every API URL:

```
https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices
https://api.freshbooks.com/accounting/account/{account_id}/payments/payments
```

If `company_id` is empty after connecting, fetch it from the identity endpoint:

```python
import httpx
r = httpx.get(
    "https://api.freshbooks.com/auth/api/v1/users/me",
    headers={"Authorization": f"Bearer {access_token}"}
)
account_id = r.json()["response"]["business_memberships"][0]["business"]["account_id"]
```

Then write it back:

```python
q42_db.set_connection_status("freshbooks", "connected",
                              company_id=account_id,
                              access_token=access_token)
```

---

## Where this is used

`invoice_recon.py` → `_fb_creds()` reads `company_id` from `q42_connections`
before every API call. If the field is blank it raises a `ValueError` with a
clear message rather than hitting the API with a broken URL.

---

## FreshBooks API write payload (payment creation)

```json
POST /accounting/account/{account_id}/payments/payments
{
  "payment": {
    "invoiceid": 12345,
    "amount": "500.00",
    "date": "2026-03-15",
    "type": "Check",
    "vis_state": 0
  }
}
```

`invoiceid` is the internal FreshBooks integer ID (stored in `recon_rows.invoice`
as `id`), not the human-readable invoice number.

---

## Invoice statuses fetched

Invoice Reconciliation only pulls invoices with `v3_status` in:
`sent`, `viewed`, `partial`, `overdue`, `disputed`

Paid, draft, auto-paid, and void invoices are skipped automatically.
