"""Six months of a salaried person's bank account, with a correct running balance on every row."""
import calendar
import random
from datetime import date, timedelta
from typing import Dict, List
from faker import Faker

MERCHANTS = ["SWIGGY", "ZOMATO", "BIGBASKET", "BLINKIT", "AMAZON PAY", "FLIPKART", "UBER INDIA", "OLA CABS", "DMART", "APOLLO PHARMACY", "BOOKMYSHOW", "IRCTC", "RELIANCE FRESH", "CHAI POINT"]
UTILITIES = ["BILLPAY ELECTRICITY", "BILLPAY BROADBAND", "BILLPAY GAS", "MOBILE RECHARGE"]

def month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

def ref(rng: random.Random, n: int = 12) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))

def events_for_month(rng: random.Random, fake: Faker, app: Dict, year: int, month: int, net_pay: float) -> List[Dict]:
    """Every credit and debit of one month as {date, description, ref, amount (+ credit / − debit)}, unordered."""
    last = month_days(year, month)
    day = lambda d: date(year, month, min(d, last))
    employer = app["employer"]["name"].upper()
    out = [{"date": day(app["salary_day"]), "description": f"NEFT-SAL-{employer[:22]}-{month:02d}{year % 100}", "ref": f"N{ref(rng, 11)}", "amount": net_pay}]
    for loan in app["loans"]:
        out.append({"date": day(5), "description": f"NACH-DR-{loan['lender']}-{loan['loan_no']}", "ref": f"ACH{ref(rng, 9)}", "amount": -loan["emi"]})
    rent = app.setdefault("rent", round(rng.uniform(0.15, 0.30) * net_pay / 100) * 100 if rng.random() < 0.7 else 0)
    if rent:
        out.append({"date": day(rng.randint(1, 7)), "description": f"UPI/RENT/{fake.first_name().upper()}/{ref(rng)}", "ref": ref(rng), "amount": -rent})
    for name in rng.sample(UTILITIES, rng.randint(1, 3)):
        out.append({"date": day(rng.randint(8, 20)), "description": f"{name}/{ref(rng, 8)}", "ref": ref(rng), "amount": -round(rng.uniform(250, 3500), 2)})
    for _ in range(rng.randint(8, 18)):
        out.append({"date": day(rng.randint(1, last)), "description": f"UPI/{rng.choice(MERCHANTS)}/{ref(rng)}/Payment", "ref": ref(rng), "amount": -round(rng.uniform(80, 4500), 2)})
    for _ in range(rng.randint(0, 2)):
        out.append({"date": day(rng.randint(1, last)), "description": f"ATM CASH WDL {fake.city().upper()[:12]} {ref(rng, 6)}", "ref": ref(rng, 6), "amount": -float(rng.choice([2000, 3000, 5000, 10000]))})
    if rng.random() < 0.4:
        out.append({"date": day(rng.randint(1, last)), "description": f"UPI/{fake.first_name().upper()} {fake.last_name().upper()}/{ref(rng)}/Sent", "ref": ref(rng), "amount": -round(rng.uniform(500, 8000), 2)})
    if rng.random() < 0.3:
        out.append({"date": day(rng.randint(1, last)), "description": f"IMPS-{ref(rng)}-{fake.first_name().upper()} {fake.last_name().upper()}", "ref": ref(rng), "amount": round(rng.uniform(500, 6000), 2)})
    if month in (3, 6, 9, 12):
        out.append({"date": day(last), "description": "INT.PD SB A/C", "ref": "", "amount": round(rng.uniform(40, 900), 2)})
    if rng.random() < 0.3:
        out.append({"date": day(last), "description": "SMS ALERT CHGS", "ref": "", "amount": -17.70})
    return out

def with_balances(events: List[Dict], opening: float) -> List[Dict]:
    """Sort by date and add the running balance. A debit that would overdraw the account is dropped, like a declined payment."""
    rows, balance = [], opening
    for e in sorted(events, key=lambda e: (e["date"], -e["amount"])):
        if balance + e["amount"] < 0:
            continue
        balance = round(balance + e["amount"], 2)
        rows.append({**e, "balance": balance})
    return rows

def add_bounce(rng: random.Random, app: Dict, events: List[Dict], year: int, month: int) -> None:
    """A NACH EMI that came back unpaid: the debit, its reversal, and the return charge."""
    loan = app["loans"][0]
    when = date(year, month, 5)
    events += [{"date": when + timedelta(days=1), "description": f"NACH RTN INSUFF BAL-{loan['lender']}", "ref": f"ACH{ref(rng, 9)}", "amount": loan["emi"]},
               {"date": when + timedelta(days=1), "description": "NACH RTN CHGS INCL GST", "ref": "", "amount": -590.0}]

def simulate(rng: random.Random, fake: Faker, app: Dict, months: List[tuple], net_pay: float, bounce_months: List[tuple] = ()) -> Dict:
    """{opening_balance, closing_balance, period_from, period_to, transactions[{date, description, ref, amount, balance}]}."""
    events = []
    for year, month in months:
        events += events_for_month(rng, fake, app, year, month, net_pay)
        if (year, month) in bounce_months and app["loans"]:
            add_bounce(rng, app, events, year, month)
    opening = round(rng.uniform(15000, 250000), 2)
    rows = with_balances(events, opening)
    start = date(months[0][0], months[0][1], 1)
    end = date(months[-1][0], months[-1][1], month_days(*months[-1]))
    return {"opening_balance": opening, "closing_balance": rows[-1]["balance"] if rows else opening, "period_from": start, "period_to": end, "transactions": rows}

def rebalance(statement: Dict, start_index: int = 0) -> None:
    """Recompute balances from `start_index` on (a fraudster who inserts a row and fixes the later balances)."""
    rows = statement["transactions"]
    balance = rows[start_index - 1]["balance"] if start_index else statement["opening_balance"]
    for r in rows[start_index:]:
        balance = round(balance + r["amount"], 2)
        r["balance"] = balance
    statement["closing_balance"] = rows[-1]["balance"]
