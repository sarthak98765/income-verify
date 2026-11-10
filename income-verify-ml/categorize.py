import re
from typing import Dict, List
from ai_client import get_ai_output, halving
from config import MODEL_POLICY
from logger import custom_logger
from prompts import CATEGORIZE_PROMPT
from utils import name_key

CATEGORIES = {"salary", "emi", "bounce", "bank_charge", "rent", "utility", "upi", "card", "cash_deposit", "cash_withdrawal", "transfer_in", "transfer_out", "interest", "refund", "investment", "tax", "other"}
# (category, narration pattern, side): side "cr"/"dr" limits a rule to credits/debits. First match wins, so order matters.
RULES = [
    ("bounce", r"\b(rtn|return|returned|bounce|insuff|unpaid|dishono?u?r|reject)", None),
    ("salary", r"\b(sal|salary|payroll|wages)\b", "cr"),
    ("emi", r"\b(nach|ecs|ach|emi|loan)\b", "dr"),
    ("bank_charge", r"\b(chg|chrg|charges?|fee|sms alert|gst on)\b", "dr"),
    ("interest", r"\b(int\.?\s?pd|interest|int\.?\s?cr)\b", "cr"),
    ("cash_deposit", r"\b(cash dep|by cash|cdm|cash deposit)\b", "cr"),
    ("cash_withdrawal", r"\b(atm|cash wdl|atw|nfs|cash withdrawal)\b", "dr"),
    ("rent", r"\brent\b", None),
    ("investment", r"\b(sip|mutual fund|\bmf\b|zerodha|groww|ppf)\b", "dr"),
    ("utility", r"\b(electric|bescom|msedcl|bill ?pay|broadband|airtel|jio|gas)\b", "dr"),
    ("refund", r"\b(refund|reversal|rev)\b", "cr"),
    ("upi", r"\bupi\b", None),
    ("card", r"\b(pos|ecom|card)\b", "dr"),
    ("transfer_in", r"\b(neft|imps|rtgs|trf|transfer)\b", "cr"),
    ("transfer_out", r"\b(neft|imps|rtgs|trf|transfer)\b", "dr"),
]

def by_rules(t: Dict, employer: str = "") -> str | None:
    text, side = t["description"].lower(), "cr" if t["amount"] > 0 else "dr"
    if side == "cr" and employer and name_key(employer).split()[0] in name_key(text):
        return "salary"
    return next((cat for cat, pattern, only in RULES if (only is None or only == side) and re.search(pattern, text)), None)

async def by_model(rows: List[Dict]) -> Dict[int, str]:
    """One cheap call for the narrations no rule recognised. Returns {row: category}."""
    async def call(chunk, start):
        body = "\n".join(f"{i}. [{'credit' if t['amount'] > 0 else 'debit'} ₹{abs(t['amount']):,.2f}] {t['description']}" for i, t in enumerate(chunk))
        parsed = await get_ai_output(CATEGORIZE_PROMPT, body, model=MODEL_POLICY["categorize"], json_mode=True, name="categorize")
        found = {}
        for r in (parsed or {}).get("result") or []:
            try:
                found[int(r["index"]) + start] = r["category"] if r.get("category") in CATEGORIES else "other"
            except (KeyError, TypeError, ValueError):
                continue
        return [found.get(start + i, "other") for i in range(len(chunk))]
    labels = await halving(rows, call)
    return {t["row"]: label for t, label in zip(rows, labels)}

async def categorize(transactions: List[Dict], employer: str = "", use_model: bool = True) -> List[Dict]:
    """Sets `category` and `category_by` (rules | model) on every row, in place."""
    leftovers = []
    for t in transactions:
        t["category"] = by_rules(t, employer)
        t["category_by"] = "rules"
        if t["category"] is None:
            leftovers.append(t)
    if leftovers and use_model:
        try:
            found = await by_model(leftovers)
        except Exception as e:
            custom_logger.error(f"categorize | model failed, leaving {len(leftovers)} as other: {e}")
            found = {}
        for t in leftovers:
            t["category"], t["category_by"] = found.get(t["row"], "other"), "model"
    for t in leftovers if not use_model else []:
        t["category"] = "other"
    custom_logger.info(f"categorize | {len(transactions)} rows, {len(leftovers)} needed the model")
    return transactions
