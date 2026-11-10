"""A fake salaried applicant: identity, employer, bank, salary structure and loans. Every name and number is invented."""
import random
import string
from typing import Dict, List
from faker import Faker
from config import ESI_EMPLOYEE_RATE, ESI_GROSS_CEILING, PF_RATE, PF_WAGE_CEILING, PT_SLABS, STANDARD_DEDUCTION

BANKS = [  # fictional banks; IFSC prefixes chosen not to collide with real ones
    {"name": "Ganga National Bank", "ifsc": "GNBX"}, {"name": "Sahyadri Bank Ltd", "ifsc": "SHYX"},
    {"name": "Deccan Commercial Bank", "ifsc": "DECX"}, {"name": "Narmada Bank", "ifsc": "NRMX"},
]
CITIES = {"Maharashtra": ["Mumbai", "Pune"], "Karnataka": ["Bengaluru"], "Telangana": ["Hyderabad"], "West Bengal": ["Kolkata"], "Delhi": ["New Delhi"], "Haryana": ["Gurugram"], "Uttar Pradesh": ["Noida"]}
STATE_CODES = {"Maharashtra": "MH", "Karnataka": "KA", "Telangana": "TG", "West Bengal": "WB", "Delhi": "DL", "Haryana": "HR", "Uttar Pradesh": "UP"}
SUFFIXES = ["Technologies Pvt Ltd", "Solutions Pvt Ltd", "Logistics Pvt Ltd", "Foods Pvt Ltd", "Systems Ltd", "Consulting LLP", "Pharma Pvt Ltd"]
LENDERS = ["SURYA FINANCE LTD", "KAVERI HOME LOANS", "PRAGATI CAPITAL", "METRO AUTO FINANCE"]
TAX_SLABS_NEW = [(2400000, 0.30), (2000000, 0.25), (1600000, 0.20), (1200000, 0.15), (800000, 0.10), (400000, 0.05), (0, 0.0)]

def letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))

def digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))

def make_pan(rng: random.Random, surname: str) -> str:
    """AAAPL1234C shape: 3 letters, P for a person, the surname's initial, 4 digits, a letter."""
    return letters(rng, 3) + "P" + (surname[:1].upper() or "X") + digits(rng, 4) + letters(rng, 1)

def round_to(x: float, step: int = 100) -> int:
    return int(round(x / step) * step)

def professional_tax(state: str, gross: float) -> int:
    slabs = PT_SLABS[state]
    return 0 if slabs is None else next(tax for above, tax in slabs if gross > above)

def annual_tax_new(taxable: float) -> float:
    """New-regime slab tax with the section 87A rebate (no tax up to ₹12 lakh taxable) and 4% cess."""
    if taxable <= 1200000:
        return 0.0
    tax, rest = 0.0, taxable
    for floor, rate in TAX_SLABS_NEW:
        if rest > floor:
            tax += (rest - floor) * rate
            rest = floor
    return tax * 1.04

def salary_structure(rng: random.Random, state: str) -> Dict:
    gross = round_to(rng.choice([rng.uniform(16000, 21000), rng.uniform(25000, 60000), rng.uniform(60000, 150000), rng.uniform(150000, 260000)]), 500)
    basic = round_to(gross * rng.uniform(0.40, 0.50))
    hra = round_to(basic * rng.uniform(0.40, 0.50))
    conveyance = 1600 if gross > 30000 else 0
    special = gross - basic - hra - conveyance
    capped = rng.random() < 0.5
    pf = round(min(basic, PF_WAGE_CEILING) * PF_RATE) if capped else round(basic * PF_RATE)
    esi = -(-gross * ESI_EMPLOYEE_RATE // 1) if gross <= ESI_GROSS_CEILING else 0
    pt = professional_tax(state, gross)
    tds = round(annual_tax_new(12 * gross - STANDARD_DEDUCTION["new"]) / 12)
    earnings = [("Basic Salary", basic), ("House Rent Allowance", hra)] + ([("Conveyance Allowance", conveyance)] if conveyance else []) + [("Special Allowance", special)]
    deductions = [("Provident Fund", pf)] + ([("ESI", int(esi))] if esi else []) + ([("Professional Tax", pt)] if pt else []) + ([("Income Tax (TDS)", tds)] if tds else [])
    return {"earnings": earnings, "deductions": deductions}

def totals(structure: Dict) -> Dict:
    gross = sum(a for _, a in structure["earnings"])
    deducted = sum(a for _, a in structure["deductions"])
    return {"gross": gross, "total_deductions": deducted, "net_pay": gross - deducted}

def make_applicant(rng: random.Random, fake: Faker, index: int) -> Dict:
    first, last = fake.first_name(), fake.last_name()
    state = rng.choice(list(CITIES))
    city = rng.choice(CITIES[state])
    bank = rng.choice(BANKS)
    employer = f"{fake.last_name()} {rng.choice(SUFFIXES)}"
    structure = salary_structure(rng, state)
    net = totals(structure)["net_pay"]
    loans: List[Dict] = [{"lender": l, "emi": round_to(net * rng.uniform(0.06, 0.22), 1), "loan_no": digits(rng, 10)} for l in rng.sample(LENDERS, rng.choice([0, 0, 1, 1, 2]))]
    return {
        "id": f"APP{index:03d}", "name": f"{first} {last}", "first_name": first, "last_name": last, "pan": make_pan(rng, last),
        "address": f"{fake.building_number()}, {fake.street_name()}, {city}", "city": city, "state": state,
        "employer": {"name": employer, "cin": f"U{digits(rng, 5)}{STATE_CODES[state]}{rng.randint(2001, 2022)}PTC{digits(rng, 6)}", "address": f"{fake.building_number()}, {fake.street_name()}, {city} - {digits(rng, 6)}",
                     "tan": f"{letters(rng, 4)}{digits(rng, 5)}{letters(rng, 1)}", "pan": f"{letters(rng, 3)}C{employer[:1].upper()}{digits(rng, 4)}{letters(rng, 1)}"},
        "employee_id": f"EMP{digits(rng, 5)}", "designation": rng.choice(["Software Engineer", "Analyst", "Sales Executive", "Operations Manager", "Accountant", "Team Lead", "Associate"]),
        "bank": {"name": bank["name"], "ifsc": f"{bank['ifsc']}0{digits(rng, 6)}", "account": digits(rng, 12), "branch": f"{city} Main"},
        "salary": structure, "loans": loans, "salary_day": rng.randint(26, 30), "regime": "new",
    }
