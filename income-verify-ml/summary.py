"""The underwriter note: written by a cheap model from pre-formatted facts, then checked so it can't introduce a number."""
import json
import re
from typing import Dict
from ai_client import get_ai_output
from config import MODEL_POLICY
from logger import custom_logger
from prompts import SUMMARY_PROMPT

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

def money(x) -> str:
    return "not verified" if x is None else f"₹{x:,.2f}"

def facts_for(application: Dict, result: Dict) -> Dict:
    """Numbers already formatted, so the model copies strings instead of doing arithmetic."""
    m = result["metrics"]
    return {
        "applicant": application["applicant_name"], "verdict": result["status"], "authenticity_score": f"{result['authenticity_score']}/100",
        "verified_monthly_income": money(m.get("verified_monthly_income")),
        "salary_months_matched": f"{m.get('salary_months_matched', 0)} of {m.get('salary_months_checked', 0)}",
        "average_balance": money(m.get("average_balance")), "minimum_balance": money(m.get("minimum_balance")),
        "existing_emis_per_month": money(m.get("emi_total")), "foir": "not available" if m.get("foir") is None else f"{m['foir'] * 100:.1f}%",
        "bounces": str(len(m.get("bounces") or [])), "flags": result["reasons"][:8],
    }

def numbers_in(text: str) -> set:
    return {n.replace(",", "").rstrip(".") for n in NUMBER_RE.findall(text)}

def is_grounded(summary: str, facts: Dict) -> bool:
    """Every number in the note must occur in the facts."""
    allowed = numbers_in(json.dumps(facts, ensure_ascii=False))
    return numbers_in(summary) <= allowed

def fallback(facts: Dict) -> str:
    flags = "; ".join(facts["flags"]) or "none"
    return (f"Verified monthly income: {facts['verified_monthly_income']} (salary matched in {facts['salary_months_matched']} months). "
            f"Existing EMIs {facts['existing_emis_per_month']} per month, FOIR {facts['foir']}, {facts['bounces']} bounce(s). "
            f"Authenticity {facts['authenticity_score']}. Flags: {flags}.")

async def write_summary(application: Dict, result: Dict) -> Dict:
    facts = facts_for(application, result)
    try:
        parsed = await get_ai_output(SUMMARY_PROMPT, json.dumps(facts, ensure_ascii=False, indent=1), model=MODEL_POLICY["summary"], json_mode=True, name="summary")
        text = str((parsed or {}).get("summary", "")).strip()
        if text and is_grounded(text, facts):
            return {"summary": text, "summary_by": "model"}
        custom_logger.warning(f"summary | model note had numbers not in the facts — using the template")
    except Exception as e:
        custom_logger.error(f"summary | failed: {e}")
    return {"summary": fallback(facts), "summary_by": "template"}
