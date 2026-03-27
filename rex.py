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

CATEGORY_SYSTEM_PROMPT = """
You are a financial transaction categorization engine.
You will receive a JSON array of transaction descriptions.
You must return a JSON array of category strings — one per description, in the same order.

Use ONLY these categories:
  Income, Housing, Groceries, Food & Dining, Transportation, Gas & Fuel,
  Utilities, Health & Medical, Health & Fitness, Entertainment, Shopping,
  Travel, Education, Home Improvement, Transfer, Interest & Fees,
  Investments, Subscriptions, Personal Care, Gifts & Donations, Uncategorized

Rules:
- Return ONLY a valid JSON array of strings, nothing else.
- Every element must be one of the categories listed above.
- If you cannot determine a category, use "Uncategorized".
- Do not include explanations, markdown, or any text outside the JSON array.

Example input:  ["NETFLIX.COM", "WHOLE FOODS #42", "MYSTERY CHARGE 9923"]
Example output: ["Entertainment", "Groceries", "Uncategorized"]
"""


# ---------------------------------------------------------------------------
# AI-assisted categorization
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "Income", "Housing", "Groceries", "Food & Dining", "Transportation",
    "Gas & Fuel", "Utilities", "Health & Medical", "Health & Fitness",
    "Entertainment", "Shopping", "Travel", "Education", "Home Improvement",
    "Transfer", "Interest & Fees", "Investments", "Subscriptions",
    "Personal Care", "Gifts & Donations", "Uncategorized",
}

# Maximum descriptions per API call to stay within token limits
_BATCH_SIZE = 50


def get_ai_categories(transaction_descriptions: List[str]) -> List[str]:
    """
    Use the Anthropic API to suggest categories for a list of transaction
    descriptions.

    Parameters
    ----------
    transaction_descriptions : List[str]
        Raw transaction description strings.

    Returns
    -------
    List[str]
        A list of category strings, one per input description.
        Falls back to "Uncategorized" for any item that cannot be resolved.
    """
    if not transaction_descriptions:
        return []

    client = _get_client()
    results: List[str] = []

    # Process in batches to avoid hitting token limits
    for batch_start in range(0, len(transaction_descriptions), _BATCH_SIZE):
        batch = transaction_descriptions[batch_start : batch_start + _BATCH_SIZE]
        batch_results = _categorize_batch(client, batch)
        results.extend(batch_results)

    return results


def _categorize_batch(client: anthropic.Anthropic, descriptions: List[str]) -> List[str]:
    """
    Send a single batch of descriptions to the API and return categories.
    Returns "Uncategorized" for every item if the API call fails.
    """
    try:
        payload = json.dumps(descriptions, ensure_ascii=False)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=CATEGORY_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": payload}
            ],
        )

        raw_text = message.content[0].text.strip()
        categories = _parse_category_response(raw_text, len(descriptions))
        return categories

    except Exception as exc:
        print(f"[rex.get_ai_categories] API call failed: {exc}")
        return ["Uncategorized"] * len(descriptions)


def _parse_category_response(raw_text: str, expected_count: int) -> List[str]:
    """
    Parse the raw API response text into a list of validated category strings.

    Handles:
    - Clean JSON arrays
    - JSON embedded in markdown code fences
    - Partial responses (pads with "Uncategorized")
    - Extra items (truncates to expected_count)
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text).strip().rstrip("`").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract a JSON array from somewhere in the text
        match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                return ["Uncategorized"] * expected_count
        else:
            return ["Uncategorized"] * expected_count

    if not isinstance(parsed, list):
        return ["Uncategorized"] * expected_count

    # Validate each entry against the allowed set
    validated: List[str] = []
    for item in parsed[:expected_count]:
        cat = str(item).strip() if item else "Uncategorized"
        validated.append(cat if cat in VALID_CATEGORIES else "Uncategorized")

    # Pad if the API returned fewer items than expected
    while len(validated) < expected_count:
        validated.append("Uncategorized")

    return validated


# ---------------------------------------------------------------------------
# AI merchant name suggestions
# ---------------------------------------------------------------------------

MERCHANT_NAME_SYSTEM_PROMPT = """
You are a financial transaction merchant name extractor.
You will receive a JSON array of raw bank/credit card transaction descriptions.
Return a JSON array of short, clean, human-readable merchant names — one per description, same order.

Rules:
- Extract only the core brand/merchant name — drop city, state, phone numbers, URLs, invoice numbers, and reference codes
- Strip banking prefixes: EFT PMT, ACH, POS, SYF PAYMNT, CHECKCARD, ORIG CO NAME, PREAUTH, etc.
- Strip trailing masked numbers (Xs, asterisks, trailing digits)
- Use the well-known brand name, not the legal entity: "ChatGPT" not "Openai Chatgpt Subscr", "T-Mobile" not "Tmobile Auto Pay", "GitHub" not "Github Inc"
- For credit card payments ("Payment Thank You", "Autopay", "Online Payment"), return "Credit Card Payment"
- For foreign transaction fees, return "Foreign Transaction Fee"
- For interest charges, return "Interest Charge"
- Title-case the result
- Never return an empty string — always best-guess
- Return ONLY a valid JSON array of strings, nothing else

Example input:  ["OPENAI *CHATGPT SUBSCR OPENAI.COM CA", "TMOBILE*AUTO PAY 800-937-8997 WA", "Payment Thank You-Mobile", "DNH*GODADDY#4015140893 AMSTERDAM", "AIRBNB * HMKYFYFM55 AIRBNB.COM CA"]
Example output: ["ChatGPT", "T-Mobile", "Credit Card Payment", "GoDaddy", "Airbnb"]
"""


def get_ai_merchant_names(descriptions: List[str]) -> List[str]:
    """
    Use AI to suggest friendly merchant names for raw bank descriptions.
    Returns one name per description. Falls back to the raw description on failure.
    """
    if not descriptions:
        return []

    client = _get_client()
    results: List[str] = []

    for batch_start in range(0, len(descriptions), _BATCH_SIZE):
        batch = descriptions[batch_start : batch_start + _BATCH_SIZE]
        try:
            payload = json.dumps(batch, ensure_ascii=False)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=MERCHANT_NAME_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": payload}],
            )
            raw = message.content[0].text.strip()
            cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                names = [str(item).strip() if item else batch[i] for i, item in enumerate(parsed[:len(batch)])]
                while len(names) < len(batch):
                    names.append(batch[len(names)])
                results.extend(names)
            else:
                results.extend(batch)
        except Exception as exc:
            print(f"[rex.get_ai_merchant_names] failed: {exc}")
            results.extend(batch)

    return results


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
