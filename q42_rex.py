"""
q42_rex.py — Rex in Portal42 / Tax Advisor mode.
Sharp, thorough, aggressive about finding every legitimate deduction.
Michigan self-employed / small business focused.
"""
from __future__ import annotations

import json
import os
import re
from typing import List


def _ascii_safe(text: str) -> str:
    """Replace Unicode characters that break ASCII-only HTTP headers/encoders."""
    return (
        text
        .replace('\u2014', '--')   # em dash  —
        .replace('\u2013', '-')    # en dash  –
        .replace('\u2019', "'")    # right single quote  '
        .replace('\u2018', "'")    # left single quote   '
        .replace('\u201c', '"')    # left double quote   "
        .replace('\u201d', '"')    # right double quote  "
        .replace('\u2026', '...')  # ellipsis  …
        .replace('\u00e9', 'e').replace('\u00e0', 'a')
        .replace('\u00fc', 'u').replace('\u00e4', 'a').replace('\u00f6', 'o')
        .encode('ascii', 'ignore').decode('ascii')
    )

import anthropic
from dotenv import load_dotenv

load_dotenv()


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Q42 System Prompt
# ---------------------------------------------------------------------------

Q42_SYSTEM_PROMPT = """
You are Rex in Portal42 mode — a sharp, thorough tax strategy AI for self-employed
individuals and small business owners in Michigan.

You are not a licensed CPA, but you are deeply knowledgeable about:
- Federal self-employment taxes: Schedule C, Schedule SE
- Michigan state income tax: flat 4.25% on adjusted gross income
- Home office deduction — regular and exclusive use test (IRS Form 8829)
- Vehicle deduction — standard mileage ($0.67/mile in 2024, $0.655 in 2023) vs actual expense
- Section 179 equipment expensing (immediate full deduction in year of purchase)
- QBI deduction (§199A) — up to 20% of qualified business income
- Self-employed health insurance deduction — 100% above-the-line
- SEP-IRA contributions — up to 25% of net self-employment income, max $69,000 (2024)
- Solo 401(k) for owner-only businesses
- Business meals — 50% deductible with documentation
- Home office utilities, internet, rent/mortgage proportional deduction
- Michigan Schedule 1 adjustments, Michigan Business Tax considerations
- Quarterly estimated tax planning (Form 1040-ES)

Your personality in Q42 mode:
- Thorough and aggressive about finding every legitimate deduction
- Ask probing questions to surface overlooked write-offs
- Spot spending patterns and flag strategic opportunities
- Flag ambiguous items that need CPA clarification
- Think: what is the MAXIMUM possible legal deduction here?

When reviewing data, prioritize these often-overlooked deductions:
1. Home office — square footage ratio applied to rent/mortgage, utilities, internet
2. Vehicle mileage — most self-employed dramatically undercount business miles
3. Technology and software — nearly always 100% deductible
4. Self-employed health insurance — above-the-line, huge benefit
5. SEP-IRA — can fund AFTER year-end up to filing deadline; reduces SE tax base too
6. QBI deduction — free 20% on top of everything else if eligible

You produce clean, structured output that an accountant can use directly.
Always end your analysis with specific, actionable next steps.
"""

# ---------------------------------------------------------------------------
# AI Enrichment for Tax Categorization
# ---------------------------------------------------------------------------

Q42_ENRICH_PROMPT = """
You are a tax categorization specialist for self-employed business owners.
Receive a JSON array of raw bank/credit card transaction descriptions.
Return a JSON array (one per description, same order) each with:
  "name": clean merchant/payee name (brand-quality)
  "tax_category": one of the allowed categories below

When in doubt, lean toward a business category — the user will confirm.

Allowed tax_category values:
  Business Income, Home Office, Vehicle & Mileage, Business Meals (50%),
  Business Travel, Technology & Software, Subscriptions (Business),
  Marketing & Advertising, Professional Services, Legal & Accounting,
  Education & Training, Equipment (Section 179), Office Supplies,
  Utilities (Business %), Internet & Phone (Business %), Health Insurance Premiums,
  HSA Contributions, Retirement Contributions, Bank Fees & Interest,
  Insurance (Business), Rent & Lease (Business), Payroll & Contractors,
  Personal (Non-Deductible), Transfer, Uncategorized

Name rules:
- Use brand-quality names: "Adobe Creative Cloud" not "ADOBE SYSTEMS SUBSCR"
- Strip banking noise: ACH, EFT PMT, CHECKCARD, POS, PREAUTH, SYF PAYMNT, etc.
- "Payment Thank You", "Autopay", "Online Payment" → "Credit Card Payment" (Transfer)
- Software/SaaS subscriptions → Technology & Software or Subscriptions (Business)
- Gas stations → Vehicle & Mileage (business default)
- Restaurants → Business Meals (50%) if ambiguous

Return ONLY valid JSON array, no markdown, no explanation.
"""

Q42_VALID_CATEGORIES = {
    "Business Income", "Home Office", "Vehicle & Mileage", "Business Meals (50%)",
    "Business Travel", "Technology & Software", "Subscriptions (Business)",
    "Marketing & Advertising", "Professional Services", "Legal & Accounting",
    "Education & Training", "Equipment (Section 179)", "Office Supplies",
    "Utilities (Business %)", "Internet & Phone (Business %)", "Health Insurance Premiums",
    "HSA Contributions", "Retirement Contributions", "Bank Fees & Interest",
    "Insurance (Business)", "Rent & Lease (Business)", "Payroll & Contractors",
    "Personal (Non-Deductible)", "Transfer", "Uncategorized",
}

_BATCH_SIZE = 50


def _parse_json(raw: str) -> list:
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


def q42_enrich_transactions(descriptions: List[str]) -> List[dict]:
    """AI-powered tax categorization. Returns list of {name, tax_category} dicts."""
    if not descriptions:
        return []
    client = _get_client()
    results: List[dict] = []
    for batch_start in range(0, len(descriptions), _BATCH_SIZE):
        batch = [_ascii_safe(d) for d in descriptions[batch_start: batch_start + _BATCH_SIZE]]
        payload = json.dumps(batch, ensure_ascii=True)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=_ascii_safe(Q42_ENRICH_PROMPT),
            messages=[{"role": "user", "content": payload}],
        )
        parsed = _parse_json(message.content[0].text)
        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                name = str(parsed[i].get("name") or item).strip() or item
                cat = str(parsed[i].get("tax_category") or "Uncategorized").strip()
                if cat not in Q42_VALID_CATEGORIES:
                    cat = "Uncategorized"
            else:
                name = item
                cat = "Uncategorized"
            results.append({"name": name, "tax_category": cat})
    return results


# ---------------------------------------------------------------------------
# Q42 Chat
# ---------------------------------------------------------------------------

def q42_chat(user_message: str, conversation_history: list,
             financial_context: str = "") -> str:
    client = _get_client()
    system = _ascii_safe(Q42_SYSTEM_PROMPT)
    if financial_context:
        system += f"\n\n--- TAX DATA CONTEXT ---\n{financial_context}\n"
    conversation_history.append({"role": "user", "content": user_message})
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system=system,
            messages=conversation_history,
        )
        text = response.content[0].text
        conversation_history.append({"role": "assistant", "content": text})
        return text
    except Exception as exc:
        conversation_history.pop()
        return f"Rex is temporarily unavailable: {exc}"


# ---------------------------------------------------------------------------
# Synopsis Generator
# ---------------------------------------------------------------------------

def q42_generate_synopsis(period_summary: dict, deduction_summary: dict,
                           tax_profile: dict) -> str:
    """Generate an AI financial synopsis for the period to hand to a CPA."""
    client = _get_client()

    cat_lines = "\n".join(
        f"  {c['tax_category']}: ${c['deductible_total']:,.2f} ({c['count']} txns)"
        for c in deduction_summary.get("by_category", [])[:10]
    )
    profile_lines = "\n".join(
        f"  {k}: {v}" for k, v in tax_profile.items() if v
    )

    prompt = f"""
Analyze this financial data and write a concise but comprehensive synopsis for the accountant.

Period: {period_summary.get('start_date','?')} to {period_summary.get('end_date','?')}
Total Income: ${period_summary.get('total_in', 0):,.2f}
Total Expenses: ${period_summary.get('total_out', 0):,.2f}
Total Transactions: {period_summary.get('total_txns', 0)}
Estimated Deductible: ${period_summary.get('total_deductible', 0):,.2f}

Top deduction categories:
{cat_lines or '  (none identified yet)'}

Tax profile on file:
{profile_lines or '  (not yet gathered)'}

Write the synopsis covering:
1. Overall financial picture for the period
2. Top spending areas and strongest deduction categories
3. Key opportunities or flags for the CPA to investigate
4. Estimated total deductions identified and what's still unverified
5. Any spending patterns worth discussing for tax strategy

Keep it professional and direct — this will be handed to a licensed CPA.
"""
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            system=_ascii_safe(Q42_SYSTEM_PROMPT),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        return f"Unable to generate synopsis: {exc}"


# ---------------------------------------------------------------------------
# Ready for Review — Structured Q&A
# ---------------------------------------------------------------------------

REVIEW_QUESTIONS = [
    {
        "key": "business_structure",
        "question": "What is your business structure? (Sole proprietor, LLC single-member, LLC multi-member, S-Corp, or other?)",
        "context": "This determines how self-employment tax is calculated and which strategies are available.",
    },
    {
        "key": "home_office",
        "question": "Do you have a dedicated home office space? If yes: what is its square footage, and the total square footage of your home?",
        "context": "Home office deduction = office sqft ÷ total sqft × qualifying home expenses. Often one of the biggest overlooked deductions.",
    },
    {
        "key": "home_costs_monthly",
        "question": "What are your approximate monthly housing costs? (Rent or mortgage payment, and separately: electricity, gas, water, internet combined.)",
        "context": "These are partially deductible based on your home office percentage.",
    },
    {
        "key": "vehicle_business_use",
        "question": "Did you use a vehicle for business this period? Roughly how many business miles? (Client visits, supply runs, networking — any business-purpose driving counts.)",
        "context": "Standard mileage: $0.67/mile (2024). Most self-employed dramatically undercount. Keep a mileage log going forward.",
    },
    {
        "key": "health_insurance",
        "question": "Are you paying your own health, dental, or vision insurance premiums (not through an employer)? If so, approximately how much per month?",
        "context": "100% deductible above the line — one of the most powerful self-employed deductions. Reduces both income tax and SE tax base.",
    },
    {
        "key": "retirement_contributions",
        "question": "Did you make any retirement contributions this period — SEP-IRA, Solo 401(k), Traditional IRA? If not, are you aware you can contribute to a SEP-IRA up until your filing deadline?",
        "context": "SEP-IRA: up to 25% of net SE income (max $69,000 for 2024). This can be contributed AFTER year-end, directly reducing taxable income.",
    },
    {
        "key": "contractors_payroll",
        "question": "Did you pay any contractors, freelancers, or employees this period? Did you issue 1099s where required (anyone paid $600+ in a year)?",
        "context": "Contractor payments are fully deductible. Missing 1099s can trigger penalties.",
    },
    {
        "key": "meals_documentation",
        "question": "For restaurant / dining expenses — do you have documentation of the business purpose (who you met with, what was discussed)? Roughly what percentage of your dining expenses were business-related?",
        "context": "Business meals are 50% deductible but require substantiation: date, attendees, business purpose.",
    },
    {
        "key": "additional_info",
        "question": "Anything else Rex should know? Any large unusual expenses, asset purchases, loans taken out, or income sources not in the imported statements?",
        "context": "This catches things that don't show in bank statements: cash purchases, barter income, depreciation on prior-year assets, etc.",
    },
]


def q42_run_review(answers: dict, deduction_summary: dict, period_summary: dict) -> str:
    """Generate a complete tax optimization analysis from Q&A answers."""
    client = _get_client()

    qa_lines = "\n".join(
        f"Q: {q['question']}\nA: {answers.get(q['key'], 'Not answered')}\n"
        for q in REVIEW_QUESTIONS
    )

    cat_lines = "\n".join(
        f"  {c['tax_category']}: ${c['deductible_total']:,.2f} ({c['count']} txns)"
        for c in deduction_summary.get("by_category", [])
    )

    prompt = f"""
I have reviewed all transaction data and gathered additional information from the client.

Period: {period_summary.get('start_date','?')} to {period_summary.get('end_date','?')}
Total Income: ${period_summary.get('total_in', 0):,.2f}
Total Expenses: ${period_summary.get('total_out', 0):,.2f}

Deductions identified from transaction data:
{cat_lines or '  (none yet)'}

Client Q&A responses:
{qa_lines}

Please provide a complete tax optimization analysis:

1. **Total Deduction Estimate** — add up everything identified from both the transaction data AND the Q&A answers (home office, mileage, health insurance, etc.) with dollar estimates

2. **Additional Deductions from Q&A** — itemize deductions surfaced by the interview that weren't in the transaction data, with estimates

3. **Strategies to Implement Now or Before Filing** — specific, actionable steps (e.g., max out SEP-IRA before deadline, establish a mileage log)

4. **Michigan-Specific Notes** — any Michigan state-level considerations worth flagging for the CPA

5. **Questions for the CPA** — anything ambiguous that needs professional judgment

6. **Red Flags or Compliance Notes** — anything that needs documentation or could raise scrutiny

Be specific with dollar estimates wherever possible. Think like an aggressive-but-ethical Michigan CPA.
"""
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3500,
            system=_ascii_safe(Q42_SYSTEM_PROMPT),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        return f"Unable to complete review: {exc}"
