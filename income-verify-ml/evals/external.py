"""Bank extraction on statements we did not design: AgamiAI Indian-Bank-Statements (Hugging Face, Apache-2.0).

  python -m evals.external --count 15 --version v1      # 15 scanned statements of each layout → 30

Downloads to data/external/ (gitignored), caches each output in evals/results/external/<version>/, writes
evals/results/external-<version>.md and .json. Business current accounts with no fraud, so this scores reading
only: document type, header fields, transactions, and whether the balance check flags the right rows. (Some of
these statements' printed balances genuinely don't add up around reversals and failed debits, so "reconciles" is
the wrong target; the check should flag exactly the rows where the truth itself breaks.)
"""
import argparse
import asyncio
import json
import os
import time
from statistics import median
import httpx
import usage
from config import MODEL_POLICY
from evals.score import percentile, same, share, transaction_counts
from logger import custom_logger
from pipeline import process_document

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data", "external")
BASE_URL = "https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements/resolve/main/train"
LAYOUTS = {"type1": "India_Bank_Statement_Scanned_Type1", "type2": "India_Bank_Statement_Scanned_Type2"}
HEADER_FIELDS = ["account_holder", "opening_balance", "closing_balance"]

async def download(client: httpx.AsyncClient, layout: str, n: int) -> str:
    """Fetch statement n of a layout (pdf + json) unless it is already on disk."""
    stem = os.path.join(DATA, layout, f"{n:05d}")
    for ext in ("pdf", "json"):
        if not os.path.exists(f"{stem}.{ext}"):
            r = await client.get(f"{BASE_URL}/{LAYOUTS[layout]}/{n:05d}.{ext}", follow_redirects=True)
            r.raise_for_status()
            with open(f"{stem}.{ext}", "wb") as f:
                f.write(r.content)
    return stem

def iso(d: str) -> str:
    """'2024-01-01 12:40:40' or '01/01/2024' → '2024-01-01'."""
    d = d.split(" ")[0]
    if "/" in d:
        day, month, year = d.split("/")
        return f"{year}-{month}-{day}"
    return d

def truth_rows(j: dict) -> list:
    """Both layouts as date / debit / credit / balance, the shape our extractor returns."""
    rows = []
    for t in j["transactions"]:
        if "transaction_amount" in t:   # type 2: one signed column
            amount = t["transaction_amount"]
            debit, credit = (amount, None) if t["cr_dr"] == "DR" else (None, amount)
            rows.append({"date": iso(t["date"]), "debit": debit, "credit": credit, "balance": t["available_balance"]})
        else:
            rows.append({"date": iso(t["date"]), "debit": t["debit"], "credit": t["credit"], "balance": t["balance"]})
    return rows

async def run_one(stem: str, out_dir: str, sem: asyncio.Semaphore) -> dict:
    name = "-".join(stem.split(os.sep)[-2:])
    path = os.path.join(out_dir, f"{name}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    async with sem:
        tally, started = usage.start(), time.monotonic()
        try:
            with open(f"{stem}.pdf", "rb") as f:
                doc = await process_document(f.read(), os.path.basename(stem) + ".pdf")
        except Exception as e:
            custom_logger.exception(f"external | {name} failed: {e}")
            return {"name": name, "error": str(e)}
        out = {"name": name, "doc": doc, "usage": tally.as_doc(), "seconds": round(time.monotonic() - started, 1)}
    with open(path, "w") as f:
        json.dump(out, f, default=str)
    return out

def chain_breaks(opening: float, rows: list) -> set:
    """Rows whose balance is not the previous balance + credit − debit (the same rule as checks.balance_chain)."""
    breaks, prev = set(), opening
    for i, r in enumerate(rows):
        if prev is not None and r["balance"] is not None and abs(prev + (r["credit"] or 0) - (r["debit"] or 0) - r["balance"]) > 0.5:
            breaks.add(i)
        prev = r["balance"]
    return breaks

def score(stem: str, out: dict) -> dict:
    with open(f"{stem}.json") as f:
        j = json.load(f)
    doc = out["doc"]
    row = {"name": out["name"], "layout": out["name"].split("-")[0], "classified": doc["doc_type"] == "bank_statement",
           "seconds": out["seconds"], "cost": out["usage"]["cost_usd"], "pages": doc["pages"], "rows": len(j["transactions"])}
    if not row["classified"]:
        return {**row, "fields": {n: False for n in HEADER_FIELDS}, "transactions": {"tp": 0, "fp": 0, "fn": len(j["transactions"])}, "truth_breaks": 0, "chain_agrees": False}
    account = doc["fields"].get("account") or {}
    row["fields"] = {n: same(j.get(n), account.get(n), n) for n in HEADER_FIELDS}
    row["transactions"] = transaction_counts(truth_rows(j), doc["fields"].get("transactions") or [])
    chain = next((c for c in doc["checks"] if c["key"] == "balance_chain"), None)
    flagged = {int(f.split(".")[1]) for f in (chain or {}).get("fields", []) if f.startswith("transactions.")}
    truth = chain_breaks(j["opening_balance"], truth_rows(j))
    row["truth_breaks"] = len(truth)
    row["chain_agrees"] = flagged == truth and bool(chain) and (chain["status"] == "pass") == (not truth)
    return row

def summarize(rows: list) -> dict:
    def block(rs):
        tp, fp, fn = (sum(r["transactions"][k] for r in rs) for k in ("tp", "fp", "fn"))
        p, rc = (tp / (tp + fp) if tp + fp else 0), (tp / (tp + fn) if tp + fn else 0)
        return {"statements": len(rs), "pages": sum(r["pages"] for r in rs), "rows": sum(r["rows"] for r in rs),
                "classification": share([r["classified"] for r in rs]),
                "fields": {n: share([r["fields"][n] for r in rs]) for n in HEADER_FIELDS},
                "transactions": {"precision": p, "recall": rc, "f1": 2 * p * rc / (p + rc) if p + rc else 0},
                "exact": share([all(r["fields"].values()) and r["transactions"]["fp"] == 0 and r["transactions"]["fn"] == 0 for r in rs]),
                "truth_breaking": sum(1 for r in rs if r["truth_breaks"]), "chain_agrees": share([r["chain_agrees"] for r in rs]),
                "seconds_p50": median([r["seconds"] for r in rs]) if rs else 0, "seconds_p95": percentile([r["seconds"] for r in rs], 0.95),
                "cost": sum(r["cost"] for r in rs) / len(rs) if rs else 0}
    return {"all": block(rows), **{k: block([r for r in rows if r["layout"] == k]) for k in LAYOUTS}}

def to_markdown(name: str, s: dict) -> str:
    pct = lambda x: "—" if x is None else f"{x * 100:.1f}%"
    cols = ["all", *LAYOUTS]
    line = lambda label, f: f"| {label} | " + " | ".join(f(s[c]) for c in cols) + " |"
    rows = [
        line("Statements / pages / rows", lambda b: f"{b['statements']} / {b['pages']} / {b['rows']}"),
        line("Classified as bank statement", lambda b: pct(b["classification"])),
        *[line(f"Header: {n}", lambda b, n=n: pct(b["fields"][n])) for n in HEADER_FIELDS],
        line("Transaction precision", lambda b: pct(b["transactions"]["precision"])),
        line("Transaction recall", lambda b: pct(b["transactions"]["recall"])),
        line("Transaction F1", lambda b: pct(b["transactions"]["f1"])),
        line("Statement exact (header + every row)", lambda b: pct(b["exact"])),
        line("Statements whose printed balances truly break", lambda b: f"{b['truth_breaking']} of {b['statements']}"),
        line("Balance check flags exactly the breaking rows", lambda b: pct(b["chain_agrees"])),
        line("Time per statement p50 / p95", lambda b: f"{b['seconds_p50']}s / {b['seconds_p95']}s"),
        line("Cost per statement", lambda b: f"${b['cost']:.4f}"),
    ]
    head = "| Metric | All | Type 1 (debit/credit columns) | Type 2 (signed amount column) |\n|---|---:|---:|---:|"
    return f"### {name}\n\n{head}\n" + "\n".join(rows) + "\n\nRows match on (date, debit, credit, balance).\n"

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=15, help="statements per layout")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    for layout in LAYOUTS:
        os.makedirs(os.path.join(DATA, layout), exist_ok=True)
    async with httpx.AsyncClient(timeout=180) as client:
        stems = [await download(client, layout, n) for layout in LAYOUTS for n in range(1, args.count + 1)]
    out_dir = os.path.join(HERE, "results", "external", args.version)
    os.makedirs(out_dir, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    outputs = await asyncio.gather(*(run_one(s, out_dir, sem) for s in stems))
    rows = [score(s, o) for s, o in zip(stems, outputs) if "error" not in o]
    summary = summarize(rows)
    name = f"IncomeVerify {args.version} (external AgamiAI scanned statements, extract={MODEL_POLICY['extract']}) · n={len(rows)}"
    md = to_markdown(name, summary)
    stem = os.path.join(HERE, "results", f"external-{args.version}")
    with open(stem + ".md", "w") as f:
        f.write(md)
    with open(stem + ".json", "w") as f:
        json.dump({"name": name, "summary": summary, "statements": rows}, f, indent=1, default=str)
    print(md)
    failed = [o["name"] for o in outputs if "error" in o]
    if failed:
        print(f"failed: {failed}")

if __name__ == "__main__":
    asyncio.run(main())
