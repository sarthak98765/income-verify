import json
import re
from datetime import date, datetime
from typing import Dict, List
from rapidfuzz import fuzz

FENCE_RE = re.compile(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", re.MULTILINE)
AMOUNT_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
NAME_NOISE_RE = re.compile(r"\b(mr|mrs|ms|miss|dr|shri|smt|kumari)\b\.?", re.I)
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
TAN_RE = re.compile(r"^[A-Z]{4}\d{5}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%d-%b-%y", "%d %B %Y", "%Y-%m-%d", "%b %d, %Y", "%d %b %y")
MONTH_FORMATS = ("%B %Y", "%b %Y", "%b-%Y", "%b-%y", "%m/%Y", "%m-%Y", "%Y-%m", "%B, %Y")
TUNABLE = ("response_format", "temperature", "max_completion_tokens", "reasoning_effort")
REJECTION_MARKERS = ("400", "422", "unsupported", "not supported", "invalid")
JSON_RULES = (
    "\n\nCRITICAL OUTPUT RULES (these override anything above):\n"
    "1. Your ENTIRE response must be a single JSON object and NOTHING ELSE.\n"
    "2. Do NOT wrap the JSON in code fences or add any text around it.\n"
    "3. The first character MUST be `{` and the last `}`."
)

# ── JSON from model replies ──────────────────────────────────────────────────

def find_json_object(text: str) -> str:
    """The first balanced {...} in `text`, honouring strings and escapes."""
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise json.JSONDecodeError("unterminated JSON object", text, start)

def extract_json(text: str):
    fenced = FENCE_RE.match(text)
    text = (fenced.group(1) if fenced else text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(find_json_object(text))

def rejected_param(error: Exception) -> str | None:
    """The request parameter a model refused (e.g. temperature on a reasoning model), so the call can retry without it."""
    message = str(error).lower()
    if not any(marker in message for marker in REJECTION_MARKERS):
        return None
    return next((p for p in TUNABLE if p in message or p.replace("_", " ") in message), None)

def user_content(user_prompt: str, images: List[str]):
    """Plain text, or text followed by images (data URLs) for a vision call."""
    if not images:
        return user_prompt
    return [{"type": "text", "text": user_prompt}] + [{"type": "image_url", "image_url": {"url": url}} for url in images]

# ── Numbers, dates, names ────────────────────────────────────────────────────

def parse_amount(value) -> float | None:
    """"₹1,23,456.50" → 123456.5; "1,200.00 Dr" → -1200.0; "(500)" → -500.0; blanks and "-" → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip()
    match = AMOUNT_RE.search(text.replace(" ", ""))
    if not match:
        return None
    amount = float(match.group(0).replace(",", ""))
    negative = text.startswith("(") or bool(re.search(r"\bdr\b\.?$", text, re.I))
    return round(-abs(amount) if negative else amount, 2)

# a time printed after the date: "01-01-2024 11:30:55", "02/01/2024 12:12:52 PM"
TRAILING_TIME_RE = re.compile(r"\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?$")

def parse_date(value) -> str | None:
    """Any common Indian date format, with or without a time after it → "YYYY-MM-DD". Unreadable → None."""
    text = re.sub(r"\s+", " ", str(value or "").strip().replace(",", ", ").replace(" ,", ",")).strip()
    text = TRAILING_TIME_RE.sub("", text)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None

def parse_month(value) -> str | None:
    """"August 2026", "Aug-26", "08/2026" → "2026-08"."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    for fmt in MONTH_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    day = parse_date(text)
    return day[:7] if day else None

def to_date(iso: str) -> date:
    return date.fromisoformat(iso)

def month_of(iso: str) -> str:
    return iso[:7]

def next_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y + m // 12}-{m % 12 + 1:02d}"

def name_key(name) -> str:
    """Lowercase, no titles, no punctuation, single spaces — for comparing names."""
    text = NAME_NOISE_RE.sub(" ", str(name or "").lower())
    return " ".join(re.sub(r"[^a-z ]", " ", text).split())

def names_match(a, b, threshold: int) -> bool:
    """Same person or company despite order, initials and suffixes ("S. Kumar" vs "Kumar Sharma S")."""
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb:
        return False
    return fuzz.token_set_ratio(ka, kb) >= threshold or initials_match(ka, kb)

def initials_match(a: str, b: str) -> bool:
    """"r sharma" vs "rahul sharma": one full word is shared, and every word of one name starts a word of the other."""
    wa, wb = a.split(), b.split()
    if not {w for w in wa if len(w) > 1} & {w for w in wb if len(w) > 1}:
        return False
    fits = lambda short, other: all(any(o.startswith(w) for o in other) for w in short)
    return fits(wa, wb) or fits(wb, wa)

def mask(value, keep: int = 4) -> str:
    text = str(value or "")
    return "X" * max(len(text) - keep, 0) + text[-keep:] if text else ""

def close(a, b, tolerance: float) -> bool:
    return a is not None and b is not None and abs(a - b) <= tolerance

# ── Prompts and pages ────────────────────────────────────────────────────────

def pages_text(pages: List[Dict], context: List[Dict] = ()) -> str:
    """OCR'd pages as one prompt body with explicit page markers; `context` pages are marked as read-only."""
    body = "\n\n=== PAGE BREAK ===\n\n".join(f"PAGE {p['page_number']}:\n{p['markdown']}" for p in pages)
    if context:
        body += "\n\n=== CONTEXT ONLY (do not extract rows that START on this page) ===\n\n" + "\n\n".join(f"PAGE {p['page_number']}:\n{p['markdown']}" for p in context)
    return body

def batch_pages(pages: List[Dict], size: int) -> List[List[Dict]]:
    return [pages[i:i + size] for i in range(0, len(pages), size)]

def appears_in(raw, text: str) -> bool:
    """A value is grounded when its printed form (or its digits, for amounts) occurs in the OCR text."""
    raw = str(raw or "").strip()
    if not raw:
        return False
    if raw.lower() in text.lower():
        return True
    digits = re.sub(r"[^\d.]", "", raw)
    return len(digits) >= 3 and digits in re.sub(r"[^\d.]", "", text)
