"""Generate a unique 5-document library for every sample account (user01..user49).

Usage (from the project root):

    .venv/Scripts/python.exe scripts/generate_user_documents.py

Each account gets its own invoice (finance), offer letter (HR), lab report (healthcare),
contract (legal) and a general business document, with names, amounts, dates and IDs drawn
from a per-user random seed - so no two accounts see the same documents or insights.
Output: data/user_documents/userNN/<domain>/<file> plus data/user_documents/manifest.json,
which also lists questions that each user's documents can answer (used by seed_demo.py).
Everything is fictional and deterministic (re-running produces identical files).
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_sample_data import H1, H2, P, TABLE, UL, _render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "user_documents"
USERS = 49

FIRST = ["Aarav", "Diya", "Rohan", "Meera", "Kabir", "Ananya", "Vikram", "Isha", "Arjun", "Nisha", "Karan",
         "Pooja", "Siddharth", "Riya", "Aditya", "Sneha", "Rahul", "Tanvi", "Nikhil", "Priya", "Varun",
         "Kavya", "Manish", "Shreya", "Harsh", "Neha", "Yash", "Aditi", "Gaurav", "Simran"]
LAST = ["Sharma", "Iyer", "Reddy", "Patel", "Menon", "Gupta", "Nair", "Joshi", "Rao", "Kulkarni", "Singh",
        "Bose", "Desai", "Pillai", "Chopra", "Verma", "Kapoor", "Mehta", "Banerjee", "Shetty"]
COMPANIES = ["Aurora Analytics", "BlueRiver Logistics", "Cedarwood Foods", "Deltawave Telecom", "Evergreen Agro",
             "Falcon Robotics", "Granite Infra", "Horizon Health Tech", "Indigo Retail", "Juniper Fintech",
             "Kestrel Aerospace", "Lotus Textiles", "Monsoon Media", "Northstar Pharma", "Orchid Hotels",
             "Pinnacle Motors", "Quartz Semiconductors", "Redwood Realty", "Saffron Foods", "Tidal Energy"]
CITIES = ["Bengaluru", "Mumbai", "Pune", "Chennai", "Hyderabad", "Delhi", "Kolkata", "Ahmedabad", "Kochi", "Jaipur"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
SERVICES = [("Cloud hosting (monthly)", 18000, 65000), ("Software licences", 1200, 4800),
            ("Data migration services", 40000, 120000), ("Security audit", 60000, 180000),
            ("Support retainer", 25000, 90000), ("Training workshop (per day)", 15000, 45000),
            ("API integration", 30000, 110000), ("Hardware - laptops", 55000, 95000)]
ROLES = [("Software Engineer", "Engineering"), ("Data Analyst", "Analytics"), ("Product Manager", "Product"),
         ("UX Designer", "Design"), ("DevOps Engineer", "Platform"), ("Sales Executive", "Sales"),
         ("HR Business Partner", "People Operations"), ("Finance Associate", "Finance"),
         ("QA Engineer", "Engineering"), ("Customer Success Manager", "Customer Success")]
DOCTORS = ["Dr. Ramesh Kulkarni", "Dr. Farah Siddiqui", "Dr. Prakash Menon", "Dr. Leela Krishnan",
           "Dr. Imran Qureshi", "Dr. Sunita Deshpande"]
HOSPITALS = ["Silverleaf Multispeciality Hospital", "CarePoint Diagnostics", "Sunrise Clinic & Labs",
             "Greenfield Health Centre"]


def money(n: int) -> str:
    """Indian digit grouping: 1234567 -> Rs. 12,34,567"""
    s = str(int(n))
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "Rs. " + (",".join(parts + [tail]) if parts else tail)


def date(r: random.Random, year: int = 2026, months=range(1, 10)) -> str:
    return f"{r.randint(1, 28)} {MONTHS[r.choice(list(months)) - 1]} {year}"


def spec(filename, domain, title, description, org, **content):
    fmt = filename.rsplit(".", 1)[1].lower()
    return dict(filename=filename, domain=domain, format=fmt, title=title, description=description, org=org,
                **content)


# ------------------------------------------------------------------ generators
def invoice(i, r, me, company, city):
    client = r.choice([c for c in COMPANIES if c != company])
    num = f"INV-2026-{1000 + i * 37 + r.randint(0, 30)}"
    items = r.sample(SERVICES, 3)
    rows, subtotal = [["Description", "Qty", "Rate", "Amount"]], 0
    for name, lo, hi in items:
        qty = r.randint(1, 4)
        rate = r.randrange(lo, hi, 500)
        subtotal += qty * rate
        rows.append([name, qty, money(rate), money(qty * rate)])
    gst = round(subtotal * 0.18)
    total = subtotal + gst
    issued, due = date(r, months=range(6, 9)), date(r, months=range(9, 11))
    po = f"PO-{r.randint(40000, 99999)}"
    s = spec(f"Invoice_{num}.pdf", "finance", f"Tax Invoice {num}", f"Invoice from {company} to {client}.",
             company, pages=[[
                 H1("Invoice Details"),
                 TABLE(["Field", "Detail"], ["Invoice number", num], ["Invoice date", issued], ["Due date", due],
                       ["Purchase order", po], ["Billed to", f"{client}, {r.choice(CITIES)}"],
                       ["Prepared by", me]),
                 H1("Line Items"), TABLE(*rows),
                 H1("Totals"),
                 TABLE(["Item", "Amount"], ["Subtotal", money(subtotal)], ["GST @ 18%", money(gst)],
                       ["Total amount payable", money(total)]),
                 P(f"Payment is due by {due}. Late payments attract interest of 1.5% per month. "
                   f"Please quote {num} and {po} on all remittances."),
             ]])
    qs = [(f"What is the total amount payable on invoice {num}?", money(total).replace("Rs. ", "")),
          (f"When is payment due for invoice {num}?", due)]
    return s, qs


def offer_letter(i, r, me, company, city):
    cand = f"{r.choice(FIRST)} {r.choice(LAST)}"
    role, dept = r.choice(ROLES)
    ctc = r.randrange(600000, 3200000, 25000)
    join = date(r, months=range(10, 13))
    probation = r.choice([3, 6])
    notice = r.choice([30, 60, 90])
    fmt = "docx" if i % 2 else "pdf"
    blocks = [
        H1("Offer of Employment"),
        P(f"Dear {cand},", f"We are pleased to offer you the position of {role} in the {dept} department of "
          f"{company}, based in our {city} office. Your reporting manager will be {me}."),
        H1("Compensation"),
        TABLE(["Component", "Annual amount"], ["Fixed pay", money(round(ctc * 0.85))],
              ["Variable pay (target)", money(ctc - round(ctc * 0.85))], ["Total CTC", money(ctc)]),
        H1("Terms"),
        UL(f"Date of joining: {join}.", f"Probation period: {probation} months.",
           f"Notice period after confirmation: {notice} days.", "Working days: Monday to Friday."),
        P(f"Please sign and return this letter within 7 days to confirm acceptance. We look forward to welcoming "
          f"you to {company}."),
    ]
    name = f"Offer_Letter_{cand.replace(' ', '_')}.{fmt}"
    s = spec(name, "hr", f"Offer Letter - {cand}", f"Employment offer for {cand} as {role}.", company,
             **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    qs = [(f"What is the total annual CTC offered to {cand}?", money(ctc).replace("Rs. ", "")),
          (f"What is the notice period in {cand}'s offer letter?", f"{notice} days")]
    return s, qs


def lab_report(i, r, me, company, city):
    patient = f"{r.choice(FIRST)} {r.choice(LAST)}"
    age = r.randint(24, 72)
    doctor, hospital = r.choice(DOCTORS), r.choice(HOSPITALS)
    hba1c = round(r.uniform(5.0, 9.4), 1)
    fasting = r.randint(82, 190)
    ldl = r.randint(70, 190)
    hb = round(r.uniform(10.5, 16.5), 1)
    tsh = round(r.uniform(0.6, 6.8), 2)
    diabetic = hba1c >= 6.5
    impression = ("Findings are consistent with type 2 diabetes mellitus; glycaemic control needs improvement."
                  if diabetic else "Glycaemic markers are within the non-diabetic range.")
    meds = (["Metformin 500 mg twice daily after meals"] if diabetic else []) + \
           (["Atorvastatin 10 mg once daily at night"] if ldl >= 130 else []) or ["No new medication advised"]
    rid = f"LAB-{city[:3].upper()}-{20000 + i * 113 + r.randint(0, 99)}"
    fmt = ["txt", "pdf", "md"][i % 3]
    blocks = [
        H1("Patient Information"),
        TABLE(["Field", "Detail"], ["Patient name", patient], ["Age", f"{age} years"], ["Report ID", rid],
              ["Referring doctor", doctor], ["Collected on", date(r, months=range(7, 10))]),
        H1("Test Results"),
        TABLE(["Test", "Result", "Reference range"], ["HbA1c", f"{hba1c} %", "below 5.7 %"],
              ["Fasting blood glucose", f"{fasting} mg/dL", "70 - 100 mg/dL"],
              ["LDL cholesterol", f"{ldl} mg/dL", "below 100 mg/dL"], ["Haemoglobin", f"{hb} g/dL", "12 - 16 g/dL"],
              ["TSH", f"{tsh} mIU/L", "0.4 - 4.0 mIU/L"]),
        H1("Impression"), P(impression),
        H1("Advice"), UL(*meds, "Repeat HbA1c after 3 months."),
    ]
    s = spec(f"Lab_Report_{patient.replace(' ', '_')}.{fmt}", "healthcare", f"Laboratory Report - {patient}",
             f"Blood test report for {patient} ({rid}).", hospital,
             **({"pages": [blocks]} if fmt == "pdf" else {"blocks": blocks}))
    qs = [(f"What was {patient}'s HbA1c result?", f"{hba1c}"),
          (f"What is the LDL cholesterol value in {patient}'s lab report?", f"{ldl}")]
    return s, qs


def contract(i, r, me, company, city):
    kind = i % 3
    other = r.choice([c for c in COMPANIES if c != company])
    eff = date(r, months=range(1, 9))
    law = r.choice(CITIES)
    if kind == 0:
        term = r.choice([2, 3, 5])
        s = spec(f"NDA_{company.split()[0]}_{other.split()[0]}.md", "legal",
                 f"Mutual Non-Disclosure Agreement - {company} and {other}",
                 f"Mutual NDA between {company} and {other}.", company, blocks=[
                     H1("Parties"), P(f"This Mutual Non-Disclosure Agreement is made on {eff} between {company} "
                                      f"and {other}."),
                     H1("Confidentiality Obligations"),
                     P(f"Each party shall keep the other party's Confidential Information secret for {term} years "
                       f"from the date of disclosure and use it only to evaluate a potential business relationship."),
                     H1("Remedies"), P(f"Breach entitles the disclosing party to injunctive relief and damages of up "
                                       f"to {money(r.randrange(500000, 5000000, 100000))}."),
                     H1("Governing Law"), P(f"This Agreement is governed by Indian law; courts at {law} have "
                                            f"exclusive jurisdiction."),
                 ])
        return s, [(f"How long must confidential information be protected under the NDA with {other}?",
                    f"{term} years")]
    if kind == 1:
        fee = r.randrange(150000, 900000, 10000)
        months = r.choice([12, 18, 24, 36])
        cap = r.choice([6, 12])
        s = spec(f"Service_Agreement_{other.split()[0]}.docx", "legal",
                 f"Master Service Agreement - {other}", f"Service agreement between {company} and {other}.",
                 company, blocks=[
                     H1("1. Parties and Term"),
                     P(f"{company} (the Provider) and {other} (the Client) enter this Agreement effective {eff} "
                       f"for an initial term of {months} months."),
                     H1("2. Fees"),
                     P(f"The Client shall pay a monthly fee of {money(fee)} within 30 days of each invoice."),
                     H1("3. Limitation of Liability"),
                     P(f"Each party's aggregate liability is capped at the fees paid in the preceding {cap} months."),
                     H1("4. Termination"), P("Either party may terminate for convenience with 60 days' written notice."),
                     H1("5. Governing Law"), P(f"Courts at {law} have exclusive jurisdiction."),
                 ])
        return s, [(f"What is the monthly fee in the service agreement with {other}?",
                    money(fee).replace("Rs. ", ""))]
    rent = r.randrange(45000, 400000, 5000)
    deposit = rent * r.choice([3, 6, 10])
    s = spec(f"Lease_Agreement_{city}_Office.html", "legal", f"Office Lease Agreement - {city}",
             f"Lease of {company}'s {city} office premises.", company, blocks=[
                 H1("Premises"), P(f"{other} (the Lessor) leases office space of {r.randint(2, 30) * 500} sq. ft. in "
                                   f"{city} to {company} (the Lessee) from {eff}."),
                 H1("Rent and Deposit"),
                 TABLE(["Item", "Amount"], ["Monthly rent", money(rent)], ["Security deposit", money(deposit)],
                       ["Annual escalation", f"{r.choice([5, 7, 10])}%"]),
                 H1("Lock-in"), P(f"The lease has a lock-in period of {r.choice([12, 24, 36])} months."),
                 H1("Governing Law"), P(f"Disputes are subject to the courts at {law}."),
             ])
    return s, [(f"What is the monthly rent for the {city} office lease?", money(rent).replace("Rs. ", ""))]


def business_doc(i, r, me, company, city):
    kind = i % 4
    if kind == 0:  # expense sheet
        cats = ["Travel", "Meals", "Accommodation", "Software", "Training", "Office supplies"]
        rows = [["Date", "Employee", "Category", "Amount (Rs.)"]]
        totals = {}
        for _ in range(14):
            c = r.choice(cats)
            amt = r.randrange(800, 42000, 50)
            totals[c] = totals.get(c, 0) + amt
            rows.append([date(r, months=[9]), f"{r.choice(FIRST)} {r.choice(LAST)}", c, amt])
        summary = [["Category", "Total (Rs.)"]] + [[c, v] for c, v in sorted(totals.items())]
        top = max(totals, key=totals.get)
        s = spec(f"Expenses_September_2026_{company.split()[0]}.xlsx", "finance" if i % 8 else "general",
                 f"Team Expense Register - September 2026", f"{company} expense claims for September 2026.",
                 company, sheets={"Claims": rows, "Summary": summary})
        return s, [(f"Which expense category had the highest total in September 2026?", top)]
    if kind == 1:  # project status deck
        proj = f"Project {r.choice(['Atlas', 'Beacon', 'Comet', 'Drift', 'Ember', 'Fable', 'Glide', 'Helix'])}"
        pct = r.randint(35, 95)
        budget = r.randrange(1500000, 9000000, 100000)
        golive = date(r, months=range(11, 13))
        s = spec(f"{proj.replace(' ', '_')}_Status_Report.pptx", "general", f"{proj} - Status Report",
                 f"Status update for {proj} at {company}.", company, slides=[
                     (f"{proj} - Status Report", f"{company} | Prepared by {me}"),
                     ("Progress", [f"Overall completion: {pct}%", f"Planned go-live: {golive}",
                                   f"Sprint velocity: {r.randint(18, 46)} story points"]),
                     ("Budget", [f"Approved budget: {money(budget)}",
                                 f"Spent to date: {money(round(budget * pct / 100 * r.uniform(0.85, 1.1)))}"]),
                     ("Risks", [r.choice(["Vendor API delays", "Key engineer attrition", "Scope creep from sales",
                                          "Data quality issues in legacy system"]), "Mitigation plan agreed with sponsor"]),
                 ])
        return s, [(f"What is the planned go-live date for {proj}?", golive)]
    if kind == 2:  # meeting minutes
        when = date(r, months=range(8, 10))
        owner = f"{r.choice(FIRST)} {r.choice(LAST)}"
        budget = r.randrange(200000, 2500000, 50000)
        s = spec(f"Meeting_Minutes_{when.replace(' ', '_')}.md", "general", f"Leadership Meeting Minutes - {when}",
                 f"Minutes of the {company} leadership meeting held on {when}.", company, blocks=[
                     H1("Attendees"), P(f"{me} (chair), {owner}, {r.choice(FIRST)} {r.choice(LAST)}, "
                                        f"{r.choice(FIRST)} {r.choice(LAST)}."),
                     H1("Decisions"),
                     UL(f"Approved a marketing budget of {money(budget)} for Q4 2026.",
                        f"{owner} will lead the {city} office expansion.",
                        f"Hiring freeze lifted for {r.choice(['Engineering', 'Sales', 'Support'])}."),
                     H1("Action Items"),
                     TABLE(["Action", "Owner", "Due"], ["Share revised Q4 forecast", me, date(r, months=[10])],
                           ["Shortlist office spaces", owner, date(r, months=[11])]),
                 ])
        return s, [(f"What marketing budget was approved for Q4 2026?", money(budget).replace("Rs. ", ""))]
    items = ["Laptop", "Monitor", "Keyboard", "Mouse", "Docking station", "Headset", "Webcam", "Router",
             "Printer", "Projector"]
    rows = [["SKU", "Item", "Quantity", "Unit cost (Rs.)", "Location"]]
    low = None
    for k, it in enumerate(r.sample(items, 8)):
        qty = r.randint(2, 140)
        rows.append([f"SKU-{i:02d}{k:02d}", it, qty, r.randrange(500, 90000, 100), city])
        if low is None or qty < low[1]:
            low = (it, qty)
    s = spec(f"IT_Asset_Inventory_{city}.csv", "general", f"IT Asset Inventory - {city}",
             f"IT asset stock at the {company} {city} office.", company, rows=rows)
    return s, [(f"Which IT asset has the lowest quantity in the {city} inventory?", low[0])]


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    manifest = {}
    for i in range(1, USERS + 1):
        r = random.Random(1000 + i)
        me = f"{FIRST[(i * 7) % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"
        company = COMPANIES[i % len(COMPANIES)] + " Pvt. Ltd."
        city = CITIES[i % len(CITIES)]
        user = f"user{i:02d}"
        docs, questions = [], []
        for gen in (invoice, offer_letter, lab_report, contract, business_doc):
            s, qs = gen(i, r, me, company, city)
            path = OUT_DIR / user / s["domain"] / s["filename"]
            path.parent.mkdir(parents=True, exist_ok=True)
            _render(s, path)
            docs.append({k: s[k] for k in ("filename", "domain", "format", "title", "description")})
            questions += [{"question": q, "expected": a, "doc": s["filename"]} for q, a in qs]
        manifest[user] = {"persona": me, "company": company, "city": city, "documents": docs, "questions": questions}
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    names = [d["filename"] for u in manifest.values() for d in u["documents"]]
    print(f"Wrote {len(names)} documents for {len(manifest)} users to {OUT_DIR} ({len(set(names))} unique names)")


if __name__ == "__main__":
    main()
