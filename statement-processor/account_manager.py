import json
import os
from datetime import datetime
from typing import List, Dict, Optional

ACCOUNTS_FILE = "accounts.json"

def load_accounts() -> List[Dict]:
    """Load accounts from JSON file."""
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_accounts(accounts: List[Dict]) -> None:
    """Save accounts to JSON file."""
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=2)

def get_account_by_id(account_id: str) -> Optional[Dict]:
    """Get a specific account by ID."""
    accounts = load_accounts()
    for account in accounts:
        if account['account_id'] == account_id:
            return account
    return None

def get_accounts_by_holder(holder: str) -> List[Dict]:
    """Get all accounts for a specific holder (you, wife, joint, business)."""
    accounts = load_accounts()
    return [acc for acc in accounts if acc['holder'] == holder]

def get_accounts_by_category(category: str) -> List[Dict]:
    """Get accounts by category (bank, credit_card, investment, loan)."""
    accounts = load_accounts()
    return [acc for acc in accounts if acc['account_type'] == category]

def create_account(account_data: Dict) -> Dict:
    """Create a new account."""
    accounts = load_accounts()

    # Generate unique ID
    account_id = account_data.get('account_id') or f"acc_{len(accounts) + 1}"

    new_account = {
        "account_id": account_id,
        "account_name": account_data['account_name'],
        "institution": account_data['institution'],
        "account_type": account_data['account_type'],
        "holder": account_data['holder'],
        "folder_path": account_data['folder_path'],
        "account_number_last4": account_data.get('account_number_last4', 'XXXX'),
        "statement_frequency": account_data.get('statement_frequency', 'monthly'),
        "created_date": datetime.now().isoformat(),
        "notes": account_data.get('notes', '')
    }

    accounts.append(new_account)
    save_accounts(accounts)
    return new_account

def update_account(account_id: str, updates: Dict) -> Optional[Dict]:
    """Update an existing account."""
    accounts = load_accounts()

    for i, account in enumerate(accounts):
        if account['account_id'] == account_id:
            account.update(updates)
            save_accounts(accounts)
            return account

    return None

def delete_account(account_id: str) -> bool:
    """Delete an account."""
    accounts = load_accounts()
    accounts = [acc for acc in accounts if acc['account_id'] != account_id]
    save_accounts(accounts)
    return True

def get_holders() -> List[str]:
    """Get all unique holders."""
    accounts = load_accounts()
    holders = set(acc['holder'] for acc in accounts)
    return sorted(list(holders))

def get_institutions() -> List[str]:
    """Get all unique institutions."""
    accounts = load_accounts()
    institutions = set(acc['institution'] for acc in accounts)
    return sorted(list(institutions))
