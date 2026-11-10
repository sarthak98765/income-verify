import contextvars
from config import OCR_COST_PER_PAGE, PRICES

CURRENT = contextvars.ContextVar("usage", default=None)

class Tally:
    """What one task spent: every LLM call's tokens and dollars, and the pages OCR read."""
    def __init__(self):
        self.calls, self.prompt_tokens, self.completion_tokens, self.llm_cost, self.ocr_pages, self.fallbacks = 0, 0, 0, 0.0, 0, 0
        self.by_model = {}

    def as_doc(self):
        ocr_cost = self.ocr_pages * OCR_COST_PER_PAGE
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens, "llm_cost_usd": round(self.llm_cost, 6), "ocr_pages": self.ocr_pages, "ocr_cost_usd": round(ocr_cost, 6), "cost_usd": round(self.llm_cost + ocr_cost, 6), "by_model": self.by_model, "fallbacks": self.fallbacks}

def start() -> Tally:
    """Begin counting for the task running in this context (and the coroutines it awaits)."""
    tally = Tally()
    CURRENT.set(tally)
    return tally

def cost_of(model: str, usage) -> float:
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    price_in, price_out = PRICES.get(model, (0, 0))
    return (prompt * price_in + completion * price_out) / 1_000_000

def add_llm(model: str, usage) -> None:
    tally = CURRENT.get()
    if tally is None or usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    cost = cost_of(model, usage)
    tally.calls += 1
    tally.prompt_tokens += prompt
    tally.completion_tokens += completion
    tally.llm_cost += cost
    row = tally.by_model.setdefault(model.replace(".", "_"), {"calls": 0, "cost_usd": 0.0})
    row["calls"] += 1
    row["cost_usd"] = round(row["cost_usd"] + cost, 6)

def add_ocr(pages: int) -> None:
    tally = CURRENT.get()
    if tally is not None:
        tally.ocr_pages += pages

def add_fallback() -> None:
    tally = CURRENT.get()
    if tally is not None:
        tally.fallbacks += 1
