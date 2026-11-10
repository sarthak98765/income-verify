from typing import Dict, List
from ai_client import get_ai_output
from config import DOC_TYPES, MODEL_POLICY
from logger import custom_logger
from prompts import CLASSIFY_PROMPT
from utils import pages_text

KEYWORDS = {
    "payslip": ["salary slip", "payslip", "pay slip", "net pay", "earnings", "deductions", "gross earnings", "take home"],
    "bank_statement": ["statement of account", "account statement", "opening balance", "closing balance", "withdrawal", "deposit", "ifsc", "txn date", "value date"],
    "form16": ["form no. 16", "form 16", "part b", "tan of the deductor", "section 192", "assessment year", "traces"],
}
MIN_HITS = 3

def keyword_scores(text: str) -> Dict[str, int]:
    low = text.lower()
    return {doc_type: sum(1 for k in words if k in low) for doc_type, words in KEYWORDS.items()}

def by_rules(text: str) -> str | None:
    """A clear winner on keywords (≥ MIN_HITS and ahead of the runner-up by 2), else None."""
    ranked = sorted(keyword_scores(text).items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    return best if top >= MIN_HITS and top - second >= 2 else None

async def classify(pages: List[Dict]) -> Dict:
    """{"doc_type", "method": "rules"|"llm", "reason"}. Rules first; the model only when they are unsure."""
    first = pages[:2]
    found = by_rules(" ".join(p["markdown"] for p in first))
    if found:
        return {"doc_type": found, "method": "rules", "reason": "keywords"}
    parsed = await get_ai_output(CLASSIFY_PROMPT, pages_text(first), model=MODEL_POLICY["classify"], json_mode=True, name="classify")
    doc_type = parsed.get("doc_type") if isinstance(parsed, dict) else None
    doc_type = doc_type if doc_type in DOC_TYPES else "unknown"
    custom_logger.info(f"classify | llm → {doc_type}")
    return {"doc_type": doc_type, "method": "llm", "reason": (parsed or {}).get("reason", "")}
