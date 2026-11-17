"""Corpus expansion: tops every organisation up to 20 documents (200 in total).

Called by generate_sample_data.py after the 50 hand-written documents are built. Each generated
document has unique identifiers and people (no name or ID is reused anywhere in the corpus), so
every generated benchmark question has exactly one correct source document, while the many
similar documents (invoices, contracts, payslips...) act as realistic retrieval distractors.
Everything is seeded and deterministic.
"""
from __future__ import annotations

import random
from collections import Counter

from generate_sample_data import H1, P, TABLE, UL, ORGS, ORG_OF_FILE, HOSPITAL
from generate_user_documents import FIRST, LAST, MONTHS, money

DOCS_PER_ORG = 20

PROFILES = {
    "helix": dict(city="Bengaluru", industry="software products"),
    "orion": dict(city="Pune", industry="IT services"),
    "brightpath": dict(city="Mumbai", industry="management consulting"),
    "tejas": dict(city="Hyderabad", industry="infrastructure and construction"),
    "meridian": dict(city="Mumbai", industry="investment management"),
    "cobalt": dict(city="Chennai", industry="cloud hosting"),
    "lumen": dict(city="Gurugram", industry="insurance technology"),
    "zenith": dict(city="Delhi", industry="retail"),
    "aster": dict(city="Kolkata", industry="logistics"),
    "silverleaf": dict(city="Bengaluru", industry="healthcare"),
}
CLIENT_NAMES = ["Kestrel", "Bluewater", "Saffron", "Pinecrest", "Monarch", "Riverbend", "Starling", "Coral Bay",
                "Northgate", "Evergreen", "Skyline", "Harbour", "Quill", "Ironwood", "Crescent", "Maple", "Sapphire",
                "Banyan", "Peacock", "Lighthouse", "Copperleaf", "Redstone", "Silverline", "Tamarind"]
CLIENT_TRADES = ["Foods", "Shipping", "Hotels", "Pharma", "Steel", "Textiles", "Agro", "Media", "Motors",
                 "Ceramics", "Developers", "Publishing", "Furniture", "Dairy", "Chemicals", "Electricals"]
CITIES = ["Bengaluru", "Mumbai", "Pune", "Chennai", "Hyderabad", "Delhi", "Kolkata", "Ahmedabad", "Kochi", "Jaipur",
          "Indore", "Lucknow", "Nagpur", "Coimbatore", "Surat"]
PROJECTS = ["Aurora", "Beacon", "Cascade", "Drift", "Ember", "Falcon", "Glacier", "Harbor", "Ion", "Juniper",
            "Kite", "Lantern", "Meteor", "Nova", "Orbit", "Prism", "Quasar", "Radiant", "Summit", "Tundra",
            "Vortex", "Willow", "Zephyr", "Cobra", "Delta", "Echo", "Fusion", "Halo", "Pulse", "Vertex"]


def _date(r, months, year=2026):
    return f"{r.randint(1, 28)} {MONTHS[r.choice(list(months)) - 1]} {year}"


class Registry:
    """Hands out people, clients and project names that are never reused anywhere in the corpus"""

    def __init__(self, r, taken_text):
        self.r, self.used, self.taken = r, set(), taken_text.lower()

    def _fresh(self, make):
        for _ in range(500):
            v = make()
            if v not in self.used and v.lower() not in self.taken:
                self.used.add(v)
                return v
        raise RuntimeError("ran out of unique values")

    def person(self):
        return self._fresh(lambda: f"{self.r.choice(FIRST)} {self.r.choice(LAST)}")

    def client(self):
        return self._fresh(lambda: f"{self.r.choice(CLIENT_NAMES)} {self.r.choice(CLIENT_TRADES)} "
                                   f"{self.r.choice(['Pvt. Ltd.', 'Ltd.'])}")

    def unique(self, value):
        """Reserve an arbitrary value (e.g. company+city) without checking the corpus text"""
        if value in self.used:
            return None
        self.used.add(value)
        return value

    def project(self):
        return self._fresh(lambda: f"Project {self.r.choice(PROJECTS)}")


def spec(filename, domain, title, description, org, **content):
    return dict(filename=filename, domain=domain, format=filename.rsplit(".", 1)[1].lower(), title=title,
                description=description, org=org, **content)


def q(category, question, keywords, reference, page=1):
    return dict(category=category, question=question, answer_keywords=keywords, reference_answer=reference,
                expected_page=page)


# ------------------------------------------------------------------ document templates
# each template: (ctx) -> (spec, question)   ctx has r, reg, org, short, city, code, n (sequence number)

def t_invoice(c):
    r, reg = c["r"], c["reg"]
    client = reg.client()
    num = f"INV-{c['code']}-{4100 + c['n'] * 7}"
    items = r.sample([("Annual support subscription", 90000, 260000), ("Implementation services", 120000, 380000),
                      ("Cloud usage charges", 40000, 150000), ("Training (per batch)", 30000, 80000),
                      ("Hardware supply", 60000, 240000), ("Consulting days", 45000, 120000)], 3)
    rows, sub = [["#", "Description", "Amount (Rs.)"]], 0
    for k, (name, lo, hi) in enumerate(items, start=1):
        amt = r.randrange(lo, hi, 1000)
        sub += amt
        rows.append([str(k), name, money(amt).replace("Rs. ", "")])
    gst = round(sub * 0.18)
    rows += [["", "Subtotal", money(sub).replace("Rs. ", "")], ["", "GST @ 18%", money(gst).replace("Rs. ", "")],
             ["", "Total amount payable", money(sub + gst).replace("Rs. ", "")]]
    due = _date(r, range(10, 12))
    s = spec(f"Invoice_{num}.pdf", "finance", f"Tax Invoice {num}", f"{c['org']} invoice to {client}.", c["org"],
             pages=[[H1("Invoice Details"),
                     TABLE(["Field", "Detail"], ["Invoice number", num], ["Invoice date", _date(r, range(8, 10))],
                           ["Due date", due], ["Bill to", f"{client}, {r.choice(CITIES)}"],
                           ["Supplier", c["org"]]),
                     H1("Line Items"), TABLE(*rows),
                     P(f"Payment is due by {due}. Please quote {num} on all remittances.")]])
    if c["n"] % 2:
        return s, q("exact_id", f"Which customer is billed in invoice {num}?", [client.split()[0]],
                    f"Invoice {num} is billed to {client}.")
    return s, q("exact_id", f"What is the total amount payable on invoice {num}?",
                [money(sub + gst).replace("Rs. ", "")], f"The total payable on {num} is {money(sub + gst)}.")


def t_purchase_order(c):
    r, reg = c["r"], c["reg"]
    num = f"PO-{c['code']}-{5200 + c['n'] * 11}"
    vendor = reg.client()
    item, unit = r.choice([("Laptops", 68000), ("Office chairs", 9500), ("Network switches", 42000),
                           ("Safety helmets", 850), ("Barcode scanners", 7200), ("UPS units", 23000)])
    qty = r.randint(6, 180)
    s = spec(f"Purchase_Order_{num}.docx", "finance", f"Purchase Order {num}", f"{c['org']} order placed with {vendor}.",
             c["org"], blocks=[H1("Order Summary"),
                               TABLE(["Field", "Detail"], ["PO number", num], ["Vendor", vendor],
                                     ["Order date", _date(r, range(7, 10))], ["Requested by", reg.person()]),
                               H1("Items"),
                               TABLE(["Item", "Quantity", "Unit price (Rs.)", "Amount (Rs.)"],
                                     [item, str(qty), money(unit).replace("Rs. ", ""),
                                      money(qty * unit).replace("Rs. ", "")]),
                               P(f"Delivery is required within {r.choice([7, 10, 15, 21])} days at the {c['city']} office.")])
    return s, q("exact_id", f"How many {item.lower()} were ordered under purchase order {num}?", [str(qty)],
                f"Purchase order {num} orders {qty} {item.lower()}.")


def t_offer_letter(c):
    r, reg = c["r"], c["reg"]
    cand = reg.person()
    role = r.choice(["Business Analyst", "Site Engineer", "Account Manager", "Data Engineer", "Operations Lead",
                     "Financial Analyst", "Product Designer", "Supply Chain Planner"])
    ctc = r.randrange(700000, 3400000, 25000)
    notice = r.choice([30, 45, 60, 90])
    fmt = r.choice(["docx", "pdf"])
    blocks = [H1("Offer of Employment"),
              P(f"Dear {cand}, we are pleased to offer you the role of {role} at {c['org']}, {c['city']}."),
              H1("Compensation"),
              TABLE(["Component", "Annual amount"], ["Fixed pay", money(round(ctc * 0.88))],
                    ["Performance bonus (target)", money(ctc - round(ctc * 0.88))], ["Total CTC", money(ctc)]),
              H1("Terms"), UL(f"Joining date: {_date(r, range(11, 13))}.", f"Notice period: {notice} days.",
                              "Probation: 6 months.")]
    s = spec(f"Offer_Letter_{cand.replace(' ', '_')}.{fmt}", "hr", f"Offer Letter - {cand}",
             f"{c['org']} offer to {cand} ({role}).", c["org"],
             **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    if c["n"] % 2:
        return s, q("factual", f"What is the total annual CTC offered to {cand}?", [money(ctc).replace("Rs. ", "")],
                    f"{cand} is offered a total CTC of {money(ctc)}.")
    return s, q("paraphrase", f"How much notice does {cand} have to give before leaving, according to the offer?",
                [f"{notice} days"], f"{cand}'s notice period is {notice} days.")


def t_payslip(c):
    r, reg = c["r"], c["reg"]
    emp = reg.person()
    month = MONTHS[r.randint(5, 8)]
    basic = r.randrange(40000, 160000, 500)
    hra = round(basic * 0.4)
    allow = r.randrange(5000, 25000, 500)
    gross = basic + hra + allow
    pf = round(basic * 0.12)
    tax = round(gross * r.uniform(0.05, 0.16))
    net = gross - pf - tax - 200
    eid = f"{c['code']}-E{3000 + c['n'] * 13}"
    s = spec(f"Payslip_{eid}_{month}_2026.pdf", "hr", f"Payslip - {month} 2026 - {emp}",
             f"Salary slip for {emp} ({eid}).", c["org"],
             pages=[[H1("Employee"), TABLE(["Field", "Detail"], ["Employee", emp], ["Employee ID", eid],
                                          ["Pay period", f"{month} 2026"], ["Location", c["city"]]),
                     H1("Earnings and Deductions"),
                     TABLE(["Component", "Amount (Rs.)"], ["Basic salary", f"{basic:,}"], ["House rent allowance", f"{hra:,}"],
                           ["Special allowance", f"{allow:,}"], ["Provident fund", f"-{pf:,}"],
                           ["Income tax (TDS)", f"-{tax:,}"], ["Professional tax", "-200"],
                           ["Total net pay", f"{net:,}"])]])
    return s, q("tabular", f"What was {emp}'s net pay for {month} 2026?", [f"{net:,}"],
                f"{emp}'s net pay for {month} 2026 was Rs. {net:,}.")


def t_hr_policy(c):
    r = c["r"]
    kind = c["n"] % 3
    if kind == 0:
        days = r.choice([2, 3])
        allowance = r.randrange(1500, 4000, 250)
        blocks = [H1("Eligibility"), P(f"Employees who have completed probation may work from home up to {days} days "
                                         f"per week with their manager's approval."),
                  H1("Equipment"), P(f"{c['short']} pays a monthly internet allowance of {money(allowance)} to "
                                     f"employees on a hybrid schedule."),
                  H1("Core Hours"), P("Employees must be reachable between 11:00 and 16:00 on working days.")]
        name, title = "Hybrid_Work_Policy", "Hybrid Work Policy"
        question = q("paraphrase", f"How many days a week can {c['short']} employees work remotely?", [f"{days} days"],
                     f"{c['short']} employees may work from home up to {days} days per week.")
    elif kind == 1:
        hours = r.choice([24, 32, 40])
        budget = r.randrange(20000, 75000, 5000)
        blocks = [H1("Learning Hours"), P(f"Every employee must complete at least {hours} hours of training per year."),
                  H1("Certification Support"), P(f"{c['short']} reimburses certification fees of up to {money(budget)} "
                                                 f"per employee per year, subject to a 12-month retention clause."),
                  H1("Approval"), P("Requests are approved by the reporting manager and the Learning team.")]
        name, title = "Training_and_Certification_Policy", "Training and Certification Policy"
        question = q("factual", f"How much does {c['short']} reimburse for certification fees per employee per year?",
                     [money(budget).replace("Rs. ", "")], f"Up to {money(budget)} per employee per year.")
    else:
        sla = r.choice([5, 7, 10])
        blocks = [H1("Raising a Grievance"), P("Employees may raise a grievance through the HR portal or by email to the "
                                               "Grievance Committee."),
                  H1("Resolution Timeline"), P(f"The committee acknowledges a grievance within 2 working days and "
                                               f"resolves it within {sla} working days."),
                  H1("Escalation"), P("Unresolved grievances are escalated to the Chief People Officer.")]
        name, title = "Grievance_Redressal_Policy", "Grievance Redressal Policy"
        question = q("factual", f"Within how many working days must {c['short']}'s Grievance Committee resolve a grievance?",
                     [f"{sla} working days"], f"Grievances are resolved within {sla} working days.")
    fmt = r.choice(["html", "md", "docx"])
    s = spec(f"{c['short']}_{name}_{c['n']:02d}.{fmt}", "hr", f"{c['short']} {title}", f"{title} of {c['org']}.", c["org"],
             blocks=[P(f"This policy applies to all employees of {c['org']}.")] + blocks)
    return s, question


def t_nda(c):
    r, reg = c["r"], c["reg"]
    other = reg.client()
    num = f"NDA-{c['code']}-{300 + c['n']}"
    years = r.choice([2, 3, 4, 5])
    fmt = r.choice(["md", "pdf"])
    blocks = [H1("Parties"), P(f"This agreement ({num}) is made on {_date(r, range(1, 9))} between {c['org']} and {other}."),
              H1("Obligations"), P(f"Confidential information must be protected for {years} years from disclosure."),
              H1("Governing Law"), P(f"Courts at {c['city']} have exclusive jurisdiction.")]
    s = spec(f"NDA_{num}.{fmt}", "legal", f"Non-Disclosure Agreement {num}", f"NDA between {c['short']} and {other}.",
             c["org"], **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    return s, q("factual", f"For how many years must confidential information be protected under {num}?",
                [f"{years} years"], f"Under {num}, confidentiality lasts {years} years.")


def t_service_agreement(c):
    r, reg = c["r"], c["reg"]
    client = reg.client()
    num = f"SA-{c['code']}-{700 + c['n']}"
    fee = r.randrange(150000, 950000, 10000)
    term = r.choice([12, 18, 24, 36])
    s = spec(f"Service_Agreement_{num}.docx", "legal", f"Service Agreement {num}",
             f"{c['org']} services for {client}.", c["org"], blocks=[
                 H1("1. Parties and Term"), P(f"{c['org']} (Provider) and {client} (Client) agree to an initial term "
                                              f"of {term} months starting {_date(r, range(1, 9))}."),
                 H1("2. Fees"), P(f"The Client pays a monthly fee of {money(fee)}."),
                 H1("3. Termination"), P("Either party may terminate with 60 days' written notice.")])
    if c["n"] % 2:
        return s, q("exact_id", f"What is the monthly fee under service agreement {num}?",
                    [money(fee).replace("Rs. ", "")], f"The monthly fee under {num} is {money(fee)}.")
    return s, q("paraphrase", f"How long does the initial term of {c['short']}'s agreement with {client} run?",
                [f"{term} months"], f"The initial term is {term} months.")


def t_lease(c):
    r, reg = c["r"], c["reg"]
    city = next(x for x in r.sample(CITIES, len(CITIES)) if reg.unique(f"{c['short']}|lease|{x}"))
    rent = r.randrange(60000, 450000, 5000)
    lessor = reg.client()
    fmt = r.choice(["html", "pdf"])
    blocks = [H1("Premises"), P(f"{lessor} leases {r.randint(4, 40) * 500} sq. ft. of office space in {city} to "
                                f"{c['org']}."),
              H1("Rent"), TABLE(["Item", "Amount"], ["Monthly rent", money(rent)], ["Security deposit", money(rent * 6)]),
              H1("Lock-in"), P(f"Lock-in period: {r.choice([12, 24, 36])} months.")]
    tag = city.replace(" ", "_")
    s = spec(f"{c['short']}_Lease_{tag}.{fmt}", "legal", f"{c['short']} Office Lease - {city}",
             f"Lease of {c['short']}'s {city} premises.", c["org"],
             **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    return s, q("factual", f"What is the monthly rent for {c['short']}'s {city} office?", [money(rent).replace("Rs. ", "")],
                f"The monthly rent is {money(rent)}.")


def t_minutes(c):
    r, reg = c["r"], c["reg"]
    when = _date(r, range(6, 10))
    owner = reg.person()
    budget = r.randrange(300000, 4000000, 50000)
    num = f"MOM-{c['code']}-{40 + c['n']}"
    fmt = r.choice(["md", "txt"])
    s = spec(f"Minutes_{num}.{fmt}", "general", f"Management Meeting Minutes {num}",
             f"{c['short']} management meeting on {when}.", c["org"], blocks=[
                 H1("Meeting"), P(f"Meeting {num} of {c['org']} was held on {when} in {c['city']}."),
                 H1("Decisions"), UL(f"Approved a capital budget of {money(budget)} for warehouse automation.",
                                     f"{owner} will own the vendor evaluation.",
                                     "Quarterly town hall moved to the first Friday of the month."),
                 H1("Action Items"), TABLE(["Action", "Owner", "Due"], ["Vendor shortlist", owner, _date(r, [10])])])
    return s, q("factual", f"What capital budget was approved in meeting {num}?", [money(budget).replace("Rs. ", "")],
                f"{num} approved {money(budget)}.")


def t_project_deck(c):
    r, reg = c["r"], c["reg"]
    proj = reg.project()
    pct = r.randint(30, 95)
    golive = _date(r, range(11, 13))
    budget = r.randrange(2000000, 12000000, 100000)
    s = spec(f"{c['short']}_{proj.replace(' ', '_')}_Status.pptx", "general", f"{proj} - Status Update",
             f"{c['short']} status update for {proj}.", c["org"], slides=[
                 (f"{proj} - Status Update", f"{c['org']} | Steering committee"),
                 ("Progress", [f"Completion: {pct}%", f"Go-live: {golive}", f"Open risks: {r.randint(2, 9)}"]),
                 ("Budget", [f"Approved budget: {money(budget)}", f"Forecast at completion: {money(round(budget * 1.04))}"]),
                 ("Next Steps", ["User acceptance testing", "Data migration rehearsal", "Hypercare plan sign-off"])])
    return s, q("factual", f"What is the go-live date for {c['short']}'s {proj}?", [golive],
                f"{proj} is planned to go live on {golive}.", page=2)


def t_inventory(c):
    r = c["r"]
    items = r.sample(["Laptop", "Monitor", "Pallet jack", "Forklift battery", "Safety vest", "Printer",
                      "Barcode scanner", "Router", "Projector", "Desk phone", "Tablet", "Shelving unit"], 7)
    rows = [["SKU", "Item", "Quantity", "Location"]]
    pick = None
    for k, it in enumerate(items):
        sku = f"{c['code']}-{c['n']:02d}{k:02d}"
        qty = r.randint(3, 260)
        rows.append([sku, it, qty, c["city"]])
        if k == 3:
            pick = (sku, it, qty)
    s = spec(f"{c['short']}_Stock_Register_{c['n']:02d}.csv", "general", f"{c['short']} Stock Register",
             f"{c['short']} stock at {c['city']}.", c["org"], rows=rows)
    return s, q("tabular", f"How many units of SKU {pick[0]} are in stock?", [str(pick[2])],
                f"SKU {pick[0]} ({pick[1]}) has {pick[2]} units.")


def t_incident(c):
    r = c["r"]
    num = f"INC-{c['code']}-{900 + c['n']}"
    cause = r.choice(["an expired TLS certificate on the payment gateway", "a misconfigured firewall rule",
                      "disk exhaustion on the primary database", "a faulty network switch in the data centre",
                      "a failed vendor API deployment"])
    mins = r.randint(25, 300)
    s = spec(f"Incident_Report_{num}.docx", "general", f"Incident Report {num}", f"{c['short']} incident {num}.",
             c["org"], blocks=[H1("Summary"), P(f"On {_date(r, range(6, 10))} {c['short']} services were degraded for "
                                                f"{mins} minutes."),
                               H1("Root Cause"), P(f"The outage was caused by {cause}."),
                               H1("Actions"), UL("Add monitoring alert", "Update runbook", "Review change approvals")])
    key = cause.split()[-2] + " " + cause.split()[-1]
    return s, q("exact_id", f"What caused incident {num}?", [key], f"{num} was caused by {cause}.")


def t_sales(c):
    r = c["r"]
    regions = ["North", "South", "East", "West"]
    rows = [["Region", "Q1 revenue (Rs. lakh)", "Q2 revenue (Rs. lakh)", "Growth %"]]
    vals = {}
    for reg_ in regions:
        a, b = r.randint(80, 900), r.randint(80, 900)
        vals[reg_] = b
        rows.append([reg_, a, b, round((b - a) / a * 100, 1)])
    region = regions[c["n"] % 4]
    unit = ["Enterprise", "Retail", "Government", "SME"][c["n"] % 4]
    s = spec(f"{c['short']}_{unit}_Revenue_FY27.xlsx", "finance", f"{c['short']} {unit} Division - Regional Revenue FY2026-27",
             f"{c['short']} {unit} division revenue by region, Q1-Q2 FY2026-27.", c["org"], sheets={"Revenue": rows})
    return s, q("tabular", f"What was the Q2 revenue of {c['short']}'s {unit} division in the {region} region?",
                [str(vals[region])], f"{region} Q2 revenue of the {unit} division was Rs. {vals[region]} lakh.")


def t_training_deck(c):
    r = c["r"]
    hours = r.choice([6, 8, 10, 12])
    deadline = _date(r, [11, 12])
    track = ["Finance staff", "Field staff", "Managers", "New joiners"][c["n"] % 4]
    s = spec(f"{c['short']}_Compliance_Training_{track.replace(' ', '_')}.pptx", "hr",
             f"{c['short']} Compliance Training 2026 - {track}",
             f"Mandatory compliance training for {track.lower()} at {c['short']}.", c["org"], slides=[
                 (f"Compliance Training 2026 - {track}", f"{c['org']} | {track}"),
                 ("What You Must Complete", [f"Mandatory hours: {hours}", f"Deadline: {deadline}",
                                             "Modules: Anti-bribery, Data privacy, POSH"]),
                 ("Why It Matters", ["Regulatory obligations", "Protecting customers", "Safe workplace"])])
    return s, q("paraphrase", f"By when do {c['short']}'s {track.lower()} have to finish their compliance training?", [deadline],
                f"The deadline is {deadline}.", page=2)


# healthcare (Silverleaf)
def t_discharge(c):
    r, reg = c["r"], c["reg"]
    pid = f"PAT-{61000 + c['n'] * 17}"
    patient = reg.person()
    dx = r.choice(["Community-acquired pneumonia", "Acute appendicitis", "Dengue fever with thrombocytopenia",
                   "Diabetic ketoacidosis", "Fracture of the left radius", "Acute gastroenteritis"])
    days = r.randint(2, 9)
    s = spec(f"Discharge_Summary_{pid}.pdf", "healthcare", f"Discharge Summary - Patient {pid}",
             f"Discharge summary for {pid}.", HOSPITAL, pages=[[
                 H1("Patient"), TABLE(["Field", "Detail"], ["Patient ID", pid], ["Name", patient],
                                      ["Admitted", _date(r, [8])], ["Length of stay", f"{days} days"]),
                 H1("Diagnosis"), P(f"Final diagnosis: {dx}."),
                 H1("Advice"), UL("Review in the outpatient clinic after 7 days", "Complete the prescribed medicines")]])
    return s, q("exact_id", f"What was the final diagnosis for patient {pid}?", [dx.split()[-1]],
                f"{pid} was diagnosed with {dx}.")


def t_lab(c):
    r, reg = c["r"], c["reg"]
    rid = f"LAB-SLH-{7000 + c['n'] * 23}"
    patient = reg.person()
    hb = round(r.uniform(9.5, 16.0), 1)
    crt = round(r.uniform(0.6, 2.4), 2)
    fmt = r.choice(["txt", "md", "pdf"])
    blocks = [H1("Patient"), TABLE(["Field", "Detail"], ["Report ID", rid], ["Patient", patient]),
              H1("Results"), TABLE(["Test", "Result", "Reference"], ["Haemoglobin", f"{hb} g/dL", "12 - 16 g/dL"],
                                   ["Serum creatinine", f"{crt} mg/dL", "0.6 - 1.2 mg/dL"],
                                   ["Platelets", f"{r.randint(90, 420)} x10^3/uL", "150 - 400 x10^3/uL"])]
    s = spec(f"Lab_Report_{rid}.{fmt}", "healthcare", f"Laboratory Report {rid}", f"Lab report {rid}.", HOSPITAL,
             **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    return s, q("tabular", f"What was the serum creatinine in lab report {rid}?", [str(crt)],
                f"Serum creatinine was {crt} mg/dL.")


def t_prescription(c):
    r, reg = c["r"], c["reg"]
    rx = f"RX-SLH-{2400 + c['n'] * 9}"
    patient = reg.person()
    drug = r.choice(["Amoxicillin 500 mg", "Pantoprazole 40 mg", "Metformin 500 mg", "Amlodipine 5 mg",
                     "Cetirizine 10 mg", "Paracetamol 650 mg"])
    days = r.choice([5, 7, 10, 14, 30])
    s = spec(f"Prescription_{rx}.txt", "healthcare", f"Prescription {rx}", f"Outpatient prescription {rx}.", HOSPITAL,
             blocks=[H1("Patient"), P(f"Prescription {rx} for {patient}, issued on {_date(r, [9])}."),
                     H1("Medicines"), TABLE(["Medicine", "Dose", "Duration"], [drug, "As directed", f"{days} days"]),
                     H1("Advice"), P("Return if symptoms persist.")])
    return s, q("factual", f"For how many days was the medicine prescribed in {rx}?", [f"{days} days"],
                f"{drug} was prescribed for {days} days.")


def t_radiology(c):
    r = c["r"]
    rid = f"RAD-SLH-{510 + c['n']}"
    finding = r.choice(["a 6 mm calculus in the right kidney", "mild fatty infiltration of the liver",
                        "a hairline fracture of the fifth metatarsal", "no acute intracranial abnormality",
                        "consolidation in the right lower lobe"])
    s = spec(f"Radiology_Report_{rid}.docx", "healthcare", f"Radiology Report {rid}", f"Imaging report {rid}.", HOSPITAL,
             blocks=[H1("Study"), P(f"Report {rid}: {r.choice(['Ultrasound abdomen', 'X-ray', 'CT scan', 'MRI'])} "
                                    f"performed on {_date(r, [9])}."),
                     H1("Impression"), P(f"The study shows {finding}."),
                     H1("Recommendation"), P("Clinical correlation is advised.")])
    return s, q("exact_id", f"What did radiology report {rid} show?", [finding.split()[-1]], f"It showed {finding}.")


def t_opd(c):
    r, reg = c["r"], c["reg"]
    rows = [["Doctor", "Department", "Days", "Room"]]
    pick = None
    for k, dept in enumerate(r.sample(["Cardiology", "Orthopaedics", "Dermatology", "ENT", "Paediatrics",
                                       "Neurology", "Gastroenterology"], 5)):
        doc = "Dr. " + reg.person()
        room = f"OPD-{c['n']}{k + 1:02d}"
        rows.append([doc, dept, r.choice(["Mon/Wed/Fri", "Tue/Thu", "Mon-Sat", "Wed/Sat"]), room])
        if k == 2:
            pick = (doc, room)
    s = spec(f"OPD_Roster_{c['n']:02d}.csv", "healthcare", "Outpatient Doctor Roster", "OPD consultation roster.",
             HOSPITAL, rows=rows)
    return s, q("tabular", f"In which room does {pick[0]} hold OPD consultations?", [pick[1]],
                f"{pick[0]} consults in {pick[1]}.")


def t_sop(c):
    r = c["r"]
    mins = r.choice([15, 20, 30])
    s = spec(f"SOP_Hand_Hygiene_{c['n']:02d}.html", "healthcare", f"SOP: Hand Hygiene Audit (Ward {c['n']})",
             "Hand hygiene audit procedure.", HOSPITAL, blocks=[
                 H1("Purpose"), P("Ensure compliance with the WHO five moments of hand hygiene."),
                 H1("Procedure"), P(f"The infection control nurse observes each ward for {mins} minutes every week "
                                    f"(Ward {c['n']})."),
                 H1("Target"), P(f"Ward {c['n']} must achieve at least {r.choice([85, 90, 95])}% compliance.")])
    return s, q("factual", f"How long is each weekly hand hygiene observation in Ward {c['n']}?", [f"{mins} minutes"],
                f"Each observation lasts {mins} minutes.")


GENERIC = [t_invoice, t_offer_letter, t_service_agreement, t_minutes, t_payslip, t_project_deck, t_purchase_order,
           t_hr_policy, t_nda, t_inventory, t_incident, t_sales, t_lease, t_training_deck]
HEALTH = [t_discharge, t_lab, t_prescription, t_radiology, t_opd, t_sop]
CODES = {"helix": "HLX", "orion": "ORN", "brightpath": "BPC", "tejas": "TJS", "meridian": "MRD", "cobalt": "CBT",
         "lumen": "LMN", "zenith": "ZNT", "aster": "AST", "silverleaf": "SLH"}

# questions that no document answers (abstention); each must contain a phrase absent from the corpus
UNANSWERABLE = [
    ("What is Zenith Retail's policy on employees bringing pets to work?", "pets"),
    ("How many trucks does Aster Logistics operate in Europe?", "europe"),
    ("What was Cobalt Cloud Services' market capitalisation in 2025?", "market capitalisation"),
    ("How many electric vehicles does Tejas Infrastructure own?", "electric vehicles"),
    ("What is the canteen menu at Meridian Capital on Fridays?", "canteen menu"),
    ("What is the visiting hour policy for the Silverleaf ICU on public holidays?", "visiting hour"),
]


def owner_key(spec_):
    if spec_["org"] == HOSPITAL:
        return "silverleaf"
    for key, (full, _, _) in ORGS.items():
        if spec_["org"] == full:
            return key
    return ORG_OF_FILE.get(spec_["filename"], "helix")


def expand(base_specs, corpus_text):
    """Returns (new_specs, new_questions) so that every organisation has DOCS_PER_ORG documents"""
    counts = Counter(owner_key(s) for s in base_specs)
    reg = Registry(random.Random(2026), corpus_text)
    specs, questions = [], []
    for key in PROFILES:
        need = DOCS_PER_ORG - counts.get(key, 0)
        r = random.Random(f"expand-{key}")
        full, short = (HOSPITAL, "Silverleaf") if key == "silverleaf" else ORGS[key][:2]
        templates = HEALTH if key == "silverleaf" else GENERIC
        offset = list(PROFILES).index(key)
        for n in range(1, need + 1):
            t = templates[(n - 1 + offset) % len(templates)]
            ctx = dict(r=r, reg=reg, org=full, short=short, city=PROFILES[key]["city"], code=CODES[key], n=n)
            s, question = t(ctx)
            specs.append(s)
            questions.append(dict(question, domain=s["domain"], expected_docs=[s["filename"]], history=[]))
    # keep two thirds of the generated questions (alternating) so the benchmark stays tractable on a CPU
    questions = [x for i, x in enumerate(questions) if i % 3 != 2]
    for text, _ in UNANSWERABLE:
        questions.append(dict(category="unanswerable", domain="general", question=text, history=[], expected_docs=[],
                              expected_page=None, answer_keywords=[],
                              reference_answer="Not answerable from the documents; the system should abstain."))
    return specs, questions
