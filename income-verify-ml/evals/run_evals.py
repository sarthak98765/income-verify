"""Score the pipeline against the synthetic ground truth.

  python -m evals.run_evals --split dev --version v1
  python -m evals.run_evals --split test --version v1 --extract-model gpt-6-luna    # ablation
  python -m evals.run_evals --split test --version v1-noreread --no-reread         # ablation
  python -m evals.run_evals --split test --version v1-textlayer --reader textlayer  # ablation: PDF text layer, no OCR

Each applicant's output is cached in evals/results/<split>/<version>/<id>.json (delete it to re-run).
The table goes to evals/results/<split>-<version>.md and .json.
"""
import argparse
import asyncio
import json
import os
import time
from collections import Counter
from statistics import median
import pymupdf
import ocr
import tracing
import usage
from config import MODEL_POLICY
from evals.score import score_applicant, summarize
from logger import custom_logger
from pipeline import analyze_application, process_document

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
FILE_TYPES = (".pdf", ".jpg", ".jpeg", ".png")

async def text_layer_read(data: bytes, filename: str) -> dict:
    """Ablation reader: the PDF's own text layer instead of OCR. Free, but a scan or photo has no text layer."""
    with pymupdf.open(stream=ocr.as_pdf(data, filename), filetype="pdf") as pdf:
        pages = [{"page_number": i + 1, "markdown": page.get_text()} for i, page in enumerate(pdf)]
    return {"pages": pages, "low_quality_pages": [p["page_number"] for p in pages if ocr.is_bad(p["markdown"])]}

async def timed(call, *args, **kwargs):
    """Run one step under its own cost tally; returns (result, usage, seconds)."""
    tally, started = usage.start(), time.monotonic()
    out = await call(*args, **kwargs)
    return out, tally.as_doc(), round(time.monotonic() - started, 1)

def add_usage(parts: list) -> dict:
    keys = ("calls", "prompt_tokens", "completion_tokens", "llm_cost_usd", "ocr_pages", "ocr_cost_usd", "cost_usd")
    return {k: round(sum(p[k] for p in parts), 6) for k in keys}

async def run_applicant(folder: str, truth: dict, use_reread: bool) -> dict:
    """One applicant end to end. Each document gets its own cost and time, so per-document numbers can be reported."""
    tracing.start("eval", truth["id"], {"issue": truth.get("issue")})
    docs, parts, total_s = [], [], 0.0
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(FILE_TYPES):
            with open(os.path.join(folder, name), "rb") as f:
                doc, spent, secs = await timed(process_document, f.read(), name, use_reread=use_reread)
            docs.append({**doc, "eval_usage": spent, "eval_seconds": secs})
            parts.append(spent)
            total_s += secs
    result, spent, secs = await timed(analyze_application, truth["application"], docs, use_summary=False)
    return {"documents": docs, "result": result, "usage": add_usage(parts + [spent]), "seconds": round(total_s + secs, 1)}

async def cached_run(folder: str, truth: dict, out_dir: str, use_reread: bool, sem: asyncio.Semaphore) -> dict:
    path = os.path.join(out_dir, f"{truth['id']}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    async with sem:
        try:
            out = await run_applicant(folder, truth, use_reread)
        except Exception as e:
            custom_logger.exception(f"evals | {truth['id']} failed: {e}")
            return {"error": str(e)}
    with open(path, "w") as f:
        json.dump(out, f, default=str)
    return out

def to_markdown(name: str, s: dict) -> str:
    pct = lambda x: "—" if x is None else f"{x * 100:.1f}%"
    rows = [
        ("Document classification", pct(s["classification_accuracy"])), ("Payslip field accuracy", pct(s["field_accuracy"]["payslip"])),
        ("Bank header field accuracy", pct(s["field_accuracy"]["bank_statement"])), ("Form 16 field accuracy", pct(s["field_accuracy"]["form16"])),
        ("Transaction P / R / F1", f"{pct(s['transactions']['precision'])} / {pct(s['transactions']['recall'])} / {pct(s['transactions']['f1'])}"),
        ("Balance chain reconciles (unedited statements)", pct(s["balance_reconciled"])), ("Document exact match (every field right)", pct(s["document_perf"]["all"]["exact"])),
        ("Cross-check accuracy", pct(s["cross_check_accuracy"])), ("Verdict accuracy", pct(s["verdict_accuracy"])),
        ("Issue catch rate", f"{pct(s['issue_catch_rate'])} ({s['issues_caught']}/{s['issues_total']})"), ("False alarms on clean applicants (flagged)", pct(s["false_alarm_rate"])),
        ("Straight-through (clean → verified)", pct(s["straight_through"])), ("Auto-verified that were truly clean", pct(s["auto_verified_precision"])),
        ("Verified income exact", pct(s["income_exact"])), ("EMI total exact", pct(s["emi_exact"])), ("Bounce count exact", pct(s["bounces_exact"])),
        ("Time per applicant p50 / p95", f"{s['seconds_p50']}s / {s['seconds_p95']}s"), ("Cost per applicant", f"${s['cost_per_applicant']:.4f}"),
    ]
    issues = "\n".join(f"| {k} | {v['caught']}/{v['total']} |" for k, v in sorted(s["by_issue"].items()))
    secs = lambda x: "—" if x is None else f"{x:.1f}s"
    usd = lambda x: "—" if x is None else f"${x:.4f}"
    perf = "\n".join(f"| {k} | {v['n']} | {pct(v['exact'])} | {secs(v['seconds_p50'])} / {secs(v['seconds_p95'])} | {usd(v['cost'])} |" for k, v in s["document_perf"].items())
    fields = "\n".join(f"| {kind} | {name} | {pct(v)} |" for kind, row in s["per_field"].items() for name, v in row.items())
    return (f"### {name} · n={s['applicants']} applicants, {s['documents']} documents\n\n| Metric | Value |\n|---|---:|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)
            + f"\n\n**Catch rate by planted issue**\n\n| Issue | Caught |\n|---|---:|\n{issues}\n\nVerdicts (expected → got): {dict(s['confusion'])}\n"
            + f"\n**Per document** (time is sequential processing of one document)\n\n| Type | n | Exact match | Time p50 / p95 | Cost |\n|---|---:|---:|---:|---:|\n{perf}\n"
            + f"\n**Per field**\n\n| Document | Field | Accuracy |\n|---|---|---:|\n{fields}\n")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--version", default="dev")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--extract-model")
    parser.add_argument("--no-reread", action="store_true")
    parser.add_argument("--reader", choices=["ocr", "textlayer"], default="ocr")
    args = parser.parse_args()
    if args.reader == "textlayer":
        ocr.read = text_layer_read
    if args.extract_model:
        MODEL_POLICY["extract"] = args.extract_model
    base = os.path.join(DATA, args.split)
    out_dir = os.path.join(HERE, "results", args.split, args.version)
    os.makedirs(out_dir, exist_ok=True)
    folders = sorted(f for f in os.listdir(base) if os.path.isdir(os.path.join(base, f)))[: args.limit]
    truths = [json.load(open(os.path.join(base, f, "truth.json"))) for f in folders]
    sem = asyncio.Semaphore(args.concurrency)
    outputs = await asyncio.gather(*(cached_run(os.path.join(base, f), t, out_dir, not args.no_reread, sem) for f, t in zip(folders, truths)))
    await tracing.flush()
    scored = [score_applicant(t, o) for t, o in zip(truths, outputs) if "error" not in o]
    summary = summarize(scored)
    name = f"IncomeVerify {args.version} ({args.split}, extract={MODEL_POLICY['extract']}{', no re-read' if args.no_reread else ''}{', PDF text layer' if args.reader == 'textlayer' else ''})"
    md = to_markdown(name, summary)
    stem = os.path.join(HERE, "results", f"{args.split}-{args.version}")
    with open(stem + ".md", "w") as f:
        f.write(md)
    with open(stem + ".json", "w") as f:
        json.dump({"name": name, "summary": summary, "applicants": scored}, f, indent=1, default=str)
    print(md)
    failed = [t["id"] for t, o in zip(truths, outputs) if "error" in o]
    if failed:
        print(f"failed: {failed}")

if __name__ == "__main__":
    asyncio.run(main())
