"""HTML templates → PDF with PyMuPDF's Story. Three payslip layouts, four bank statement layouts, one Form 16.
Every page carries a SYNTHETIC SPECIMEN footer so these files can't pass as real documents."""
import io
from datetime import date
from typing import Dict, List
import pymupdf

FOOTER = "SYNTHETIC SPECIMEN - generated test data, not a real document"
CSS = """body{font-family:sans-serif;font-size:8.5pt;color:#111} h1{font-size:14pt;margin:0} h2{font-size:11pt;margin:4px 0}
table{border-collapse:collapse;width:100%} td,th{padding:2px 4px;border:0.5px solid #888;vertical-align:top} th{background:#e6e6e6;text-align:left}
.r{text-align:right} .muted{color:#555} .noborder td{border:none;padding:1px 4px} .total td{font-weight:bold;background:#f2f2f2}"""
PRODUCERS = {"payslip": ["greytHR Payroll 7.2", "Zing HR Reports", "PayEase Engine 3.1"], "bank_statement": ["Oracle BI Publisher 12.2", "Finacle Statement Service", "JasperReports Library 6.20"], "form16": ["TRACES PDF Generator"]}

def inr(x) -> str:
    """Indian digit grouping: 123456.5 → "1,23,456.50"."""
    if x is None:
        return ""
    sign = "-" if x < 0 else ""
    whole, frac = f"{abs(x):.2f}".split(".")
    head, groups = whole[:-3], [whole[-3:]]
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return sign + ",".join(groups) + "." + frac

def html_to_pdf(html: str, producer: str, created: str) -> bytes:
    story = pymupdf.Story(html=html, user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    box = pymupdf.paper_rect("a4")
    more = 1
    while more:
        device = writer.begin_page(box)
        more, _ = story.place(box + (36, 36, -36, -48))
        story.draw(device)
        writer.end_page()
    writer.close()
    with pymupdf.open(stream=buf.getvalue(), filetype="pdf") as doc:
        for page in doc:
            page.insert_text((36, page.rect.height - 24), f"{FOOTER}  |  page {page.number + 1} of {doc.page_count}", fontsize=6.5, color=(0.45, 0.45, 0.45))
        doc.set_metadata({"producer": producer, "creator": producer, "creationDate": created, "modDate": created, "title": ""})
        return doc.tobytes(garbage=3, deflate=True)

def pdf_date(day: date) -> str:
    return f"D:{day:%Y%m%d}101500+05'30'"

# ── Payslips ─────────────────────────────────────────────────────────────────

def payslip_header(app: Dict, month_label: str) -> str:
    e = app["employer"]
    return f"<h1>{e['name']}</h1><p class='muted'>{e['address']}<br/>CIN: {e['cin']}</p><h2>Payslip for the month of {month_label}</h2>"

def employee_block(app: Dict, days: int) -> str:
    rows = [("Employee Name", app["name"]), ("Employee ID", app["employee_id"]), ("Designation", app["designation"]), ("PAN", app["pan"]),
            ("Work Location", f"{app['city']}, {app['state']}"), ("Bank A/c", "XXXXXXXX" + app["bank"]["account"][-4:]), ("Days Paid", str(days))]
    return "<table class='noborder'>" + "".join(f"<tr><td class='muted'>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table><br/>"

def payslip_side_by_side(app, slip, month_label, days) -> str:
    e, d = slip["earnings"], slip["deductions"]
    n = max(len(e), len(d))
    pad = lambda rows: rows + [("", None)] * (n - len(rows))
    body = "".join(f"<tr><td>{en}</td><td class='r'>{inr(ea)}</td><td>{dn}</td><td class='r'>{inr(da)}</td></tr>" for (en, ea), (dn, da) in zip(pad(e), pad(d)))
    return (payslip_header(app, month_label) + employee_block(app, days) + "<table><tr><th>Earnings</th><th class='r'>Amount (Rs.)</th><th>Deductions</th><th class='r'>Amount (Rs.)</th></tr>" + body
            + f"<tr class='total'><td>Gross Earnings</td><td class='r'>{inr(slip['gross'])}</td><td>Total Deductions</td><td class='r'>{inr(slip['total_deductions'])}</td></tr></table>"
            + f"<h2>Net Pay: Rs. {inr(slip['net_pay'])}</h2>")

def payslip_stacked(app, slip, month_label, days) -> str:
    table = lambda title, rows, total_label, total: f"<table><tr><th>{title}</th><th class='r'>INR</th></tr>" + "".join(f"<tr><td>{n}</td><td class='r'>{inr(a)}</td></tr>" for n, a in rows) + f"<tr class='total'><td>{total_label}</td><td class='r'>{inr(total)}</td></tr></table><br/>"
    return (payslip_header(app, month_label) + employee_block(app, days) + table("Earnings", slip["earnings"], "Gross Earnings", slip["gross"])
            + table("Deductions", slip["deductions"], "Total Deductions", slip["total_deductions"]) + f"<table><tr class='total'><td>Net Pay (Take Home)</td><td class='r'>{inr(slip['net_pay'])}</td></tr></table>")

def payslip_compact(app, slip, month_label, days) -> str:
    rows = "".join(f"<tr><td>{n}</td><td class='r'>{inr(a)}</td><td></td></tr>" for n, a in slip["earnings"]) + "".join(f"<tr><td>{n}</td><td></td><td class='r'>{inr(a)}</td></tr>" for n, a in slip["deductions"])
    return (f"<h1>{app['employer']['name']}</h1><p class='muted'>Salary Slip - {month_label} | CIN {app['employer']['cin']}</p>"
            + f"<p>{app['name']} ({app['employee_id']}) | {app['designation']} | PAN {app['pan']} | {app['city']}, {app['state']} | Paid days {days}</p>"
            + f"<table><tr><th>Component</th><th class='r'>Earnings</th><th class='r'>Deductions</th></tr>{rows}<tr class='total'><td>Total</td><td class='r'>{inr(slip['gross'])}</td><td class='r'>{inr(slip['total_deductions'])}</td></tr></table>"
            + f"<p><b>Take Home Pay: INR {inr(slip['net_pay'])}</b></p><p class='muted'>Bank: {app['bank']['name']} A/c XXXX{app['bank']['account'][-4:]}</p>")

PAYSLIP_LAYOUTS = [payslip_side_by_side, payslip_stacked, payslip_compact]

def render_payslip(app: Dict, slip: Dict, layout: int, month_label: str, days: int, created: date) -> bytes:
    return html_to_pdf(PAYSLIP_LAYOUTS[layout](app, slip, month_label, days), PRODUCERS["payslip"][layout], pdf_date(created))

# ── Bank statements ──────────────────────────────────────────────────────────

def statement_header(app: Dict, st: Dict, fmt) -> str:
    b = app["bank"]
    return (f"<h1>{b['name']}</h1><p class='muted'>{b['branch']} Branch | IFSC: {b['ifsc']}</p><h2>Statement of Account</h2>"
            + f"<table class='noborder'><tr><td class='muted'>Account Holder</td><td>{app['name'].upper()}</td><td class='muted'>Account No.</td><td>{b['account']}</td></tr>"
            + f"<tr><td class='muted'>Address</td><td>{app['address']}</td><td class='muted'>Period</td><td>{fmt(st['period_from'])} to {fmt(st['period_to'])}</td></tr>"
            + f"<tr><td class='muted'>Opening Balance</td><td>{inr(st['opening_balance'])}</td><td class='muted'>Closing Balance</td><td>{inr(st['closing_balance'])}</td></tr></table><br/>")

def statement_separate(app, st) -> str:
    fmt = lambda d: f"{d:%d/%m/%Y}"
    rows = "".join(f"<tr><td>{fmt(t['date'])}</td><td>{t['description']}</td><td>{t['ref']}</td><td class='r'>{inr(-t['amount']) if t['amount'] < 0 else ''}</td><td class='r'>{inr(t['amount']) if t['amount'] > 0 else ''}</td><td class='r'>{inr(t['balance'])}</td></tr>" for t in st["transactions"])
    return statement_header(app, st, fmt) + f"<table><tr><th>Date</th><th>Narration</th><th>Ref No.</th><th class='r'>Withdrawal</th><th class='r'>Deposit</th><th class='r'>Balance</th></tr>{rows}</table>"

def statement_drcr(app, st) -> str:
    fmt = lambda d: f"{d:%d-%b-%Y}"
    rows = "".join(f"<tr><td>{fmt(t['date'])}</td><td>{t['description']}</td><td class='r'>{inr(abs(t['amount']))} {'Dr' if t['amount'] < 0 else 'Cr'}</td><td class='r'>{inr(t['balance'])} Cr</td></tr>" for t in st["transactions"])
    return statement_header(app, st, fmt) + f"<table><tr><th>Txn Date</th><th>Description</th><th class='r'>Amount</th><th class='r'>Balance</th></tr>{rows}</table>"

def statement_value_date(app, st) -> str:
    fmt = lambda d: f"{d:%d-%m-%y}"
    rows = "".join(f"<tr><td>{fmt(t['date'])}</td><td>{fmt(t['date'])}</td><td>{t['description']}</td><td class='r'>{inr(-t['amount']) if t['amount'] < 0 else '-'}</td><td class='r'>{inr(t['amount']) if t['amount'] > 0 else '-'}</td><td class='r'>{inr(t['balance'])}</td></tr>" for t in st["transactions"])
    return statement_header(app, st, fmt) + f"<table><tr><th>Txn Date</th><th>Value Date</th><th>Particulars</th><th class='r'>Debit</th><th class='r'>Credit</th><th class='r'>Balance</th></tr>{rows}</table>"

def statement_closing_col(app, st) -> str:
    fmt = lambda d: f"{d:%d/%m/%y}"
    rows = "".join(f"<tr><td>{fmt(t['date'])}</td><td>{t['description']}</td><td>{t['ref'][-8:]}</td><td class='r'>{inr(-t['amount']) if t['amount'] < 0 else ''}</td><td class='r'>{inr(t['amount']) if t['amount'] > 0 else ''}</td><td class='r'>{inr(t['balance'])}</td></tr>" for t in st["transactions"])
    return statement_header(app, st, fmt) + f"<table><tr><th>Date</th><th>Narration</th><th>Chq./Ref.No.</th><th class='r'>Withdrawal Amt.</th><th class='r'>Deposit Amt.</th><th class='r'>Closing Balance</th></tr>{rows}</table>"

STATEMENT_LAYOUTS = [statement_separate, statement_drcr, statement_value_date, statement_closing_col]

def render_statement(app: Dict, st: Dict, layout: int, created: date) -> bytes:
    return html_to_pdf(STATEMENT_LAYOUTS[layout](app, st), PRODUCERS["bank_statement"][layout % 3], pdf_date(created))

# ── Form 16 ──────────────────────────────────────────────────────────────────

def render_form16(app: Dict, f: Dict, created: date) -> bytes:
    e = app["employer"]
    part_a = (f"<h1>FORM NO. 16</h1><p class='muted'>[See rule 31(1)(a)] Certificate under section 203 of the Income-tax Act for tax deducted at source on salary</p><h2>PART A</h2>"
              + f"<table><tr><th>Name and address of the Employer</th><th>Name and address of the Employee</th></tr><tr><td>{e['name']}<br/>{e['address']}</td><td>{app['name']}<br/>{app['address']}</td></tr></table><br/>"
              + f"<table><tr><th>PAN of the Deductor</th><th>TAN of the Deductor</th><th>PAN of the Employee</th><th>Assessment Year</th><th>Period</th></tr><tr><td>{e['pan']}</td><td>{e['tan']}</td><td>{app['pan']}</td><td>{f['assessment_year']}</td><td>01-Apr-{f['fy_start']} to 31-Mar-{f['fy_start'] + 1}</td></tr></table><br/>"
              + f"<p>Total tax deducted and deposited: Rs. {inr(f['tax_deducted'])}</p>")
    rows = [("1. Gross Salary (a) Salary as per provisions contained in section 17(1)", f["gross_salary"]), ("(d) Total", f["gross_salary"]),
            ("2. Less: Allowances to the extent exempt under section 10", f["exemptions_section_10"]), ("4. Deductions under section 16: (a) Standard deduction under section 16(ia)", f["standard_deduction"]),
            ("(c) Tax on employment under section 16(iii)", f["professional_tax"]), ("10. Deductions under Chapter VI-A (total)", f["chapter_via_deductions"]),
            ("12. Total taxable income", f["taxable_income"]), ("19. Net tax payable / Tax deducted", f["tax_deducted"])]
    regime = "Yes" if f["regime"] == "new" else "No"
    part_b = (f"<h2>PART B (Annexure) - Details of Salary Paid and any other income and tax deducted</h2><p>Whether opting out of taxation u/s 115BAC (new tax regime): {'No' if regime == 'Yes' else 'Yes'}</p>"
              + "<table><tr><th>Particulars</th><th class='r'>Rs.</th></tr>" + "".join(f"<tr><td>{k}</td><td class='r'>{inr(v)}</td></tr>" for k, v in rows) + "</table>")
    return html_to_pdf(part_a + part_b, PRODUCERS["form16"][0], pdf_date(created))
