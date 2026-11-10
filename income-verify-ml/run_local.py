"""Run the pipeline on one applicant's folder, without the queue or the database.

  python run_local.py data/dev/APP1003            # every file in the folder; application from truth.json if present
  python run_local.py some/folder --name "A Kumar" --employer "X Pvt Ltd" --income 52000

Writes out/<folder name>.json and prints the verdict, checks and cost.
"""
import argparse
import asyncio
import json
import os
import tracing
import usage
from pipeline import analyze_application, process_document

OUT = "out"
FILE_TYPES = (".pdf", ".jpg", ".jpeg", ".png", ".webp")

def application_for(folder: str, args) -> dict:
    truth = os.path.join(folder, "truth.json")
    if os.path.exists(truth) and not args.name:
        with open(truth) as f:
            return json.load(f)["application"]
    return {"applicant_name": args.name or "", "declared_employer": args.employer or "", "declared_monthly_income": args.income}

async def run_folder(folder: str, application: dict) -> dict:
    docs = []
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(FILE_TYPES):
            with open(os.path.join(folder, name), "rb") as f:
                docs.append(await process_document(f.read(), name))
    return {"application": application, "documents": docs, "result": await analyze_application(application, docs)}

def show(out: dict) -> None:
    r = out["result"]
    print(f"\n{out['application']['applicant_name']}: {r['status'].upper()}  authenticity {r['authenticity_score']}/100")
    for d in out["documents"]:
        bad = [c for c in d["checks"] if c["status"] != "pass"]
        print(f"  {d['filename']:24} {d['doc_type']:15} checks not passed: {len(bad)}  low fields: {len(d['confidence']['low'])}")
        for c in bad:
            print(f"      {c['status']:4} {c['key']}: {c['message']}")
    print("  cross-checks:")
    for c in r["cross_checks"]:
        print(f"      {c['status']:4} {c['key']}: {c['message']}")
    print(f"  signals: {[s['key'] for s in r['signals']] or 'none'}")
    m = r["metrics"]
    print(f"  income {m.get('verified_monthly_income')}  emi {m.get('emi_total')}  foir {m.get('foir')}  bounces {len(m.get('bounces') or [])}  avg bal {m.get('average_balance')}")
    print(f"  summary ({r.get('summary_by')}): {r.get('summary')}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--name")
    parser.add_argument("--employer")
    parser.add_argument("--income", type=float)
    args = parser.parse_args()
    tally = usage.start()
    tracing.start("run_local", os.path.basename(os.path.normpath(args.folder)))
    out = await run_folder(args.folder, application_for(args.folder, args))
    await tracing.flush()
    out["usage"] = tally.as_doc()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, os.path.basename(os.path.normpath(args.folder)) + ".json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    show(out)
    print(f"\nspent: ${out['usage']['cost_usd']} ({out['usage']['calls']} LLM calls, {out['usage']['ocr_pages']} OCR pages) → {path}")

if __name__ == "__main__":
    asyncio.run(main())
