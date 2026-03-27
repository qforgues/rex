"""
rex.py — Rex's personality, AI chat, and AI-assisted categorization.

Rex is a sharp, no-nonsense personal finance AI with a dry sense of humour.
He tells it like it is, but always has your back.
"""

from __future__ import annotations

import json
import os
import re
from typing import List

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Rex's system prompt — his personality lives here
# ---------------------------------------------------------------------------

REX_SYSTEM_PROMPT = """
You are Rex, a personal finance AI assistant with a sharp wit and zero tolerance
for financial nonsense. You are direct, occasionally sarcastic, but always
genuinely helpful. You care deeply about the financial wellbeing of the people
you work with, even if you express it in a blunt way.

Your core traits:
- Brutally honest about bad financial habits, but constructive
- Dry humour — you find the absurdity in overspending on coffee
- Data-driven: you back opinions with numbers when possible
- Encouraging when users make good decisions
- Never preachy or repetitive — say it once, move on

You have access to the user's transaction history, account balances, and goals.
Use this context to give personalised, actionable advice.
"""

ENRICH_SYSTEM_PROMPT = """
You are a financial transaction analyzer.
You will receive a JSON array of raw bank/credit card transaction descriptions.
Return a JSON array of objects — one per description, in the same order — each with:
  "name": clean merchant/payee name (title-cased, brand-quality)
  "category": one of the allowed categories below

Rules for "name":
- Strip banking prefixes: EFT PMT, ACH, POS, SYF PAYMNT, CHECKCARD, ORIG CO NAME, PREAUTH, etc.
- Drop city, state, phone numbers, URLs, invoice/reference codes, and masked account numbers
- Use the well-known brand name: "ChatGPT" not "Openai Chatgpt Subscr", "T-Mobile" not "Tmobile Auto Pay"
- Credit card payments ("Payment Thank You", "Autopay", "Online Payment") → "Credit Card Payment"
- Foreign transaction fees → "Foreign Transaction Fee"
- Interest charges → "Interest Charge"
- Never return an empty string — always best-guess

Allowed categories:
  Income, Housing, Groceries, Food & Dining, Transportation, Gas & Fuel,
  Utilities, Health & Medical, Health & Fitness, Entertainment, Shopping,
  Travel, Education, Home Improvement, Transfer, Interest & Fees,
  Investments, Subscriptions, Personal Care, Gifts & Donations, Uncategorized

Return ONLY a valid JSON array of objects, no markdown, no explanation.

Example input:  ["OPENAI *CHATGPT SUBSCR OPENAI.COM CA", "WHOLE FOODS #422 AUSTIN TX", "Payment Thank You-Mobile"]
Example output: [{"name":"ChatGPT","category":"Subscriptions"},{"name":"Whole Foods","category":"Groceries"},{"name":"Credit Card Payment","category":"Transfer"}]
"""

VALID_CATEGORIES = {
    "Income", "Housing", "Groceries", "Food & Dining", "Transportation",
    "Gas & Fuel", "Utilities", "Health & Medical", "Health & Fitness",
    "Entertainment", "Shopping", "Travel", "Education", "Home Improvement",
    "Transfer", "Interest & Fees", "Investments", "Subscriptions",
    "Personal Care", "Gifts & Donations", "Uncategorized",
}

_BATCH_SIZE = 50


def _parse_json_response(raw: str) -> list:
    """Strip markdown fences and parse JSON, returning empty list on failure."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


def enrich_transactions(descriptions: List[str]) -> List[dict]:
    """
    Single AI call returning name + category for each description.
    Returns list of {"name": str, "category": str} dicts.
    Raises on total failure so the caller can show the error.
    """
    if not descriptions:
        return []

    client = _get_client()
    results: List[dict] = []

    for batch_start in range(0, len(descriptions), _BATCH_SIZE):
        batch = descriptions[batch_start: batch_start + _BATCH_SIZE]
        payload = json.dumps(batch, ensure_ascii=False)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=ENRICH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        parsed = _parse_json_response(message.content[0].text)

        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                name = str(parsed[i].get("name") or item).strip() or item
                cat = str(parsed[i].get("category") or "Uncategorized").strip()
                if cat not in VALID_CATEGORIES:
                    cat = "Uncategorized"
            else:
                name = item
                cat = "Uncategorized"
            results.append({"name": name, "category": cat})

    return results


# Keep for backwards compat with parsers.py categorize_transactions
def get_ai_categories(transaction_descriptions: List[str]) -> List[str]:
    """Thin wrapper around enrich_transactions, returns only categories."""
    if not transaction_descriptions:
        return []
    try:
        enriched = enrich_transactions(transaction_descriptions)
        return [r["category"] for r in enriched]
    except Exception as exc:
        print(f"[rex.get_ai_categories] failed: {exc}")
        return ["Uncategorized"] * len(transaction_descriptions)


# ---------------------------------------------------------------------------
# Rex chat
# ---------------------------------------------------------------------------

def chat_with_rex(
    user_message: str,
    conversation_history: list[dict],
    financial_context: str = "",
) -> str:
    """
    Send a message to Rex and get a response.

    Parameters
    ----------
    user_message : str
        The user's latest message.
    conversation_history : list[dict]
        List of previous {role, content} message dicts (mutated in place).
    financial_context : str
        Optional summary of the user's financial data to inject into context.

    Returns
    -------
    str
        Rex's response text.
    """
    client = _get_client()

    system = REX_SYSTEM_PROMPT
    if financial_context:
        system += f"\n\n--- USER FINANCIAL CONTEXT ---\n{financial_context}\n"

    # Append the new user message
    conversation_history.append({"role": "user", "content": user_message})

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system,
            messages=conversation_history,
        )
        assistant_text = response.content[0].text
        conversation_history.append({"role": "assistant", "content": assistant_text})
        return assistant_text
    except Exception as exc:
        error_msg = f"Rex is temporarily unavailable: {exc}"
        conversation_history.pop()  # Remove the user message we just added
        return error_msg
