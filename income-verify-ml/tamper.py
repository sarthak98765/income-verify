"""Fraud and tamper signals. Each is {"key", "message", "page", "weight"} — evidence for a human, never a rejection."""
from collections import Counter
from datetime import timedelta
from typing import Dict, List
import re
import pymupdf
from config import PDF_EDITORS, SIGNAL_WEIGHTS
from utils import to_date

ODD_FONT_MAX_SPANS = 2
COMMON_FONT_MIN_SPANS = 10
ROUND_SHARE = 0.5
ROUND_MIN_CREDITS = 6
LARGE_CREDIT_MIN = 50000
WINDOW_DAYS = 7
CIRCULAR_DAYS = 3
CIRCULAR_MIN = 10000
AMOUNT_TEXT_RE = re.compile(r"\d[\d,]*\.\d{2}\b")

def signal(key: str, message: str, page=None) -> Dict:
    return {"key": key, "message": message, "page": page, "weight": SIGNAL_WEIGHTS[key]}

# ── The file itself ──────────────────────────────────────────────────────────

def pdf_date(value: str) -> str:
    """"D:20260814103000+05'30'" → "20260814103000" (comparable as text)."""
    return (value or "").replace("D:", "")[:14]

def metadata_signals(pdf: bytes) -> List[Dict]:
    """An editor named as producer/creator, a modified date after the created date, or incremental saves (edits appended)."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        meta = doc.metadata or {}
    found = []
    tool = " ".join([meta.get("producer") or "", meta.get("creator") or ""]).lower()
    editor = next((e for e in PDF_EDITORS if e in tool), None)
    if editor:
        found.append(signal("pdf_edited", f"PDF was produced or saved by an editing tool ({editor})"))
    created, modified = pdf_date(meta.get("creationDate")), pdf_date(meta.get("modDate"))
    if created and modified and modified > created:
        found.append(signal("pdf_edited", f"PDF modified after it was created ({modified[:8]} > {created[:8]})"))
    if pdf.count(b"%%EOF") > 1:
        found.append(signal("pdf_edited", f"PDF has {pdf.count(b'%%EOF') - 1} incremental save(s) appended after the original"))
    return found

def font_signals(pdf: bytes) -> List[Dict]:
    """A font used for a couple of amounts (e.g. "25,078.00") while the rest of the document uses others — typical of an edited figure.
    Scans have no text layer and yield nothing."""
    spans = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    spans += [(page.number + 1, s["font"], s["text"].strip()) for s in line["spans"] if s["text"].strip()]
    counts = Counter(font for _, font, _ in spans)
    if not counts or max(counts.values()) < COMMON_FONT_MIN_SPANS:
        return []
    odd = [(page, font, text) for page, font, text in spans if counts[font] <= ODD_FONT_MAX_SPANS and AMOUNT_TEXT_RE.search(text)]
    return [signal("odd_font", f"'{text[:40]}' is set in {font}, a font used nowhere else in the document", page) for page, font, text in odd]

# ── The transactions ─────────────────────────────────────────────────────────

def round_amount_signals(transactions: List[Dict]) -> List[Dict]:
    """Real statements rarely have most credits ending in 000 (salary excluded)."""
    credits = [t for t in transactions if t["credit"] and t["credit"] >= 1000 and t.get("category") not in ("salary", "bounce", "refund")]
    if len(credits) < ROUND_MIN_CREDITS:
        return []
    share = sum(1 for t in credits if t["credit"] % 1000 == 0) / len(credits)
    return [signal("round_amounts", f"{share:.0%} of {len(credits)} non-salary credits are round thousands")] if share > ROUND_SHARE else []

def window_dressing_signals(transactions: List[Dict], period_to: str | None) -> List[Dict]:
    """A large non-salary credit (vs other non-salary credits) in the last days of the statement — it inflates the closing and average balance."""
    dated = [t for t in transactions if t["date"]]
    if not dated:
        return []
    end = to_date(period_to or dated[-1]["date"])
    credits = sorted(t["credit"] for t in dated if t["credit"] and t["credit"] < LARGE_CREDIT_MIN and t.get("category") != "salary")
    median = credits[len(credits) // 2] if credits else 0
    late = [t for t in dated if t["credit"] and t.get("category") != "salary" and t["credit"] >= max(LARGE_CREDIT_MIN, 3 * median) and to_date(t["date"]) > end - timedelta(days=WINDOW_DAYS)]
    return [signal("window_dressing", f"Large credit ₹{t['credit']:,.0f} on {t['date']}, {(end - to_date(t['date'])).days} day(s) before the statement ends", t["page"]) for t in late]

def circular_signals(transactions: List[Dict]) -> List[Dict]:
    """A credit that leaves again for the same amount within a few days: money passed through to look like income."""
    found = []
    dated = [t for t in transactions if t["date"]]
    for i, c in enumerate(dated):
        if not c["credit"] or c["credit"] < CIRCULAR_MIN or c.get("category") in ("salary", "bounce", "refund"):
            continue
        for d in dated[i + 1:]:
            gap = (to_date(d["date"]) - to_date(c["date"])).days
            if gap > CIRCULAR_DAYS:
                break
            if d["debit"] and abs(d["debit"] - c["credit"]) < 1:
                found.append(signal("circular_money", f"₹{c['credit']:,.0f} credited on {c['date']} and debited again on {d['date']}", c["page"]))
                break
    return found

def transaction_signals(transactions: List[Dict], period_to: str | None) -> List[Dict]:
    return round_amount_signals(transactions) + window_dressing_signals(transactions, period_to) + circular_signals(transactions)

def authenticity(signals: List[Dict]) -> int:
    """100 minus the weight of each distinct kind of signal (repeats of one kind count once)."""
    return max(0, 100 - sum(SIGNAL_WEIGHTS[k] for k in {s["key"] for s in signals}))
