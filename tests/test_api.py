"""End-to-end API tests: auth, isolation, ingestion of every format, RAG, streaming, intelligence"""
import io
import json

import pytest

LEAVE_2025 = """Leave Policy 2025

Annual Leave
Employees are entitled to 18 days of annual leave per calendar year.

Sick Leave
Employees receive 10 days of paid sick leave per year.
"""
LEAVE_2026 = LEAVE_2025.replace("18 days", "20 days").replace("10 days", "12 days").replace("2025", "2026")
INVOICE = """Tax Invoice

Invoice Number: INV-2026-8842
Vendor: Northern Star Cloud Services Ltd
Invoice Date: 15 February 2026
Due Date: 15 March 2026
Grand Total: ₹5,31,000
"""


def upload(client, headers, name, data, domain="hr"):
    return client.post("/api/documents/upload", headers=headers, data={"domain": domain},
                       files=[("files", (name, io.BytesIO(data), "application/octet-stream"))])


def docx_bytes():
    from docx import Document
    d = Document()
    d.add_heading("Master Services Agreement", 1)
    d.add_paragraph("This Agreement is made between Nimbus Technologies Pvt. Ltd. and Orion Retail Ltd.")
    d.add_heading("Fees", 2)
    d.add_paragraph("The annual fee of ₹12,00,000 is payable quarterly.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "Milestone", "Date", "Go-live", "1 June 2026"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def pdf_bytes():
    from fpdf import FPDF
    pdf = FPDF()
    for page, text in enumerate(["Travel Policy\nDomestic travel requires manager approval.",
                                 "Hotel Limits\nThe hotel limit in metro cities is 6500 rupees per night."], 1):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


def pptx_bytes():
    from pptx import Presentation
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Quarterly Roadmap"
    s.placeholders[1].text = "Launch the mobile app in Q3 2026"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def xlsx_bytes():
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"Item": ["Laptops", "Monitors"], "Budget": [4500000, 900000]}).to_excel(w, sheet_name="Budget", index=False)
    return buf.getvalue()


def png_bytes():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (900, 200), "white")
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((20, 70), "Visitor badge code ZETA-7731", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- auth
def test_requires_authentication(client):
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/documents", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_register_validation_and_login_logout(client):
    assert client.post("/api/auth/register", json={"username": "x", "email": "bad", "password": "1"}).status_code == 400
    r = client.post("/api/auth/register", json={"username": "carol", "email": "carol@test.io", "password": "secret123"})
    assert r.status_code == 200
    assert client.post("/api/auth/register",
                       json={"username": "carol", "email": "c2@test.io", "password": "secret123"}).status_code == 400
    assert client.post("/api/auth/login", json={"username": "carol", "password": "nope"}).status_code == 401
    token = client.post("/api/auth/login", json={"username": "carol@test.io", "password": "secret123"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).json()["user"]["username"] == "carol"
    client.post("/api/auth/logout", headers=h)
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_demo_account_needs_password(client):
    # there is no password-less shortcut: the demo account logs in like any other
    assert client.post("/api/auth/demo").status_code in (404, 405)
    assert client.post("/api/auth/login", json={"username": "demo", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "demo", "password": "Demo-Test-Pass-1"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "demo"


# ---------------------------------------------------------------- ingestion
@pytest.fixture(scope="module")
def alice_docs(client, alice):
    files = {
        "Leave_Policy.txt": LEAVE_2025.encode(),
        "Invoice_8842.txt": INVOICE.encode(),
        "MSA.docx": docx_bytes(),
        "Travel.pdf": pdf_bytes(),
        "Roadmap.pptx": pptx_bytes(),
        "Budget.xlsx": xlsx_bytes(),
        "Directory.csv": b"EMP_ID,Name,Department,Salary\nEMP-2026-00101,Rahul Sharma,Engineering,2400000\n"
                         b"EMP-2026-00102,Priya Nair,Finance,1800000\n",
        "Handbook.html": b"<html><body><h1>Code of Conduct</h1><p>Gifts above 5000 rupees must be declared.</p>"
                         b"<ul><li>Be respectful</li></ul></body></html>",
        "Badge.png": png_bytes(),
    }
    docs = {}
    for name, data in files.items():
        r = upload(client, alice, name, data)
        assert r.status_code == 200, r.text
        body = r.json()
        assert not body["errors"], body["errors"]
        docs[name] = body["processed"][0]
    return docs


def test_every_format_is_indexed(alice_docs):
    for name, doc in alice_docs.items():
        assert doc["chunk_count"] > 0, name
    assert alice_docs["Travel.pdf"]["page_count"] == 2
    assert alice_docs["Budget.xlsx"]["tables_count"] >= 1
    assert alice_docs["Badge.png"]["ocr_pages"] == 1


def test_ocr_extracts_image_text(client, alice, alice_docs):
    chunks = client.get(f"/api/documents/{alice_docs['Badge.png']['doc_id']}", headers=alice).json()["chunks"]
    assert "ZETA-7731" in " ".join(c["content"] for c in chunks).replace(" -", "-")


def test_pdf_pages_and_sections(client, alice, alice_docs):
    chunks = client.get(f"/api/documents/{alice_docs['Travel.pdf']['doc_id']}", headers=alice).json()["chunks"]
    hotel = [c for c in chunks if "6500" in c["content"]][0]
    assert hotel["page_number"] == 2 and hotel["section"] == "Hotel Limits"


def test_duplicate_and_bad_uploads(client, alice, alice_docs):
    r = upload(client, alice, "copy.txt", LEAVE_2025.encode()).json()
    assert r["duplicates"] and r["duplicates"][0]["existing_doc_id"] == alice_docs["Leave_Policy.txt"]["doc_id"]
    assert upload(client, alice, "virus.exe", b"MZ").json()["errors"]
    assert upload(client, alice, "empty.txt", b"").json()["errors"]
    assert upload(client, alice, "broken.pdf", b"not really a pdf").json()["errors"]


def test_versioning_same_filename(client, alice, alice_docs):
    v2 = upload(client, alice, "Leave_Policy.txt", LEAVE_2026.encode()).json()["processed"][0]
    assert v2["version"] == 2 and v2["parent_doc_id"] == alice_docs["Leave_Policy.txt"]["doc_id"]
    versions = client.get(f"/api/documents/{v2['doc_id']}/versions", headers=alice).json()["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    comp = client.post("/api/documents/compare", headers=alice,
                       json={"doc_id_a": versions[0]["doc_id"], "doc_id_b": v2["doc_id"]}).json()
    assert comp["modified_count"] >= 2
    assert any(d["original_value"] == "18" and d["new_value"] == "20"
               for m in comp["modified_clauses"] for d in m["deltas"])


# ---------------------------------------------------------------- RAG
def test_query_cites_correct_document_and_rewrites_followup(client, alice, alice_docs):
    r = client.post("/api/query", headers=alice, json={"question": "What is the grand total of invoice INV-2026-8842?"})
    assert r.status_code == 200
    msg = r.json()["assistant_message"]
    assert not msg["abstained"] and "5,31,000" in msg["content"]
    assert msg["citations"][0]["filename"] == "Invoice_8842.txt"
    assert 0 <= msg["confidence_score"] <= 1

    cid = r.json()["conversation_id"]
    r2 = client.post("/api/query", headers=alice, json={"question": "What about the due date?", "conversation_id": cid})
    m2 = r2.json()["assistant_message"]
    assert m2["rewritten_query"] and "due date" in m2["rewritten_query"].lower()
    assert "15 March 2026" in m2["content"]
    conv = client.get(f"/api/conversations/{cid}", headers=alice).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]


def test_source_view_highlights_cited_sentence_in_pdf(client, alice, bob, alice_docs):
    msg = client.post("/api/query", headers=alice, json={"question": "What is the hotel limit in metro cities?",
                                                          "answer_style": "quote"}).json()["assistant_message"]
    cite = next(c for c in msg["citations"] if c["filename"] == "Travel.pdf")
    body = {"chunk_id": cite["chunk_id"], "page_number": cite["page_number"], "focus": msg["content"]}
    view = client.post(f"/api/documents/{cite['doc_id']}/source-view", headers=alice, json=body).json()
    assert view["kind"] == "pdf" and view["page_number"] == 2 and view["found"]
    assert view["image"].startswith("data:image/png;base64,") and view["boxes"]
    assert any("6500" in h for h in view["highlights"])
    # another user's document cannot be viewed
    r = client.post(f"/api/documents/{cite['doc_id']}/source-view", headers=bob, json=body)
    assert r.status_code == 404


def test_source_view_text_formats(client, alice, alice_docs):
    doc = alice_docs["Invoice_8842.txt"]
    chunks = client.get(f"/api/documents/{doc['doc_id']}", headers=alice).json()["chunks"]
    view = client.post(f"/api/documents/{doc['doc_id']}/source-view", headers=alice,
                       json={"chunk_id": chunks[0]["chunk_id"], "focus": "The due date is 15 March 2026."}).json()
    assert view["kind"] == "text" and any(c["cited"] for c in view["chunks"])
    assert any("15 March 2026" in h for h in view["highlights"])


def test_feedback_is_recorded_and_owner_only(client, alice, bob, alice_docs):
    r = client.post("/api/query", headers=alice, json={"question": "What is the grand total of invoice INV-2026-8842?",
                                                      "answer_style": "detailed"}).json()
    mid = r["assistant_message"]["message_id"]
    assert r["assistant_message"]["answer_style"] == "detailed"
    assert client.post(f"/api/messages/{mid}/feedback", headers=bob, json={"rating": 1}).status_code == 404
    ok = client.post(f"/api/messages/{mid}/feedback", headers=alice, json={"rating": -1})
    assert ok.status_code == 200 and ok.json()["message"]["feedback"] == -1
    fb = client.get("/api/analytics", headers=alice).json()["feedback"]
    assert fb["not_helpful"] >= 1 and any(s["style"] == "detailed" and s["not_helpful"] >= 1 for s in fb["by_style"])
    cleared = client.post(f"/api/messages/{mid}/feedback", headers=alice, json={"rating": 0}).json()["message"]
    assert cleared["feedback"] is None
    assert client.post(f"/api/messages/{mid}/feedback", headers=alice, json={"rating": 5}).status_code == 422


def test_tabular_question(client, alice, alice_docs):
    msg = client.post("/api/query", headers=alice, json={"question": "What is Rahul Sharma's salary?"}).json()["assistant_message"]
    assert "2400000" in msg["content"] and msg["citations"][0]["filename"] == "Directory.csv"


def test_unanswerable_question_abstains(client, alice, alice_docs):
    msg = client.post("/api/query", headers=alice, json={"question": "Who won the FIFA world cup in 1998?"}).json()["assistant_message"]
    assert msg["abstained"] and msg["citations"] == []


def test_document_scoped_query(client, alice, alice_docs):
    msg = client.post("/api/query", headers=alice, json={
        "question": "What is the hotel limit?", "doc_id": alice_docs["Travel.pdf"]["doc_id"]}).json()["assistant_message"]
    assert all(c["filename"] == "Travel.pdf" for c in msg["citations"]) and "6500" in msg["content"]


def test_streaming_endpoint(client, alice, alice_docs):
    with client.stream("POST", "/api/query/stream", headers=alice,
                       json={"question": "How many days of sick leave do employees receive?"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    events = [line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("event: ")]
    assert events[0] == "meta" and "token" in events and events[-1] == "done"
    done = json.loads([l for l in body.split("\n\n") if l.startswith("event: done")][0].split("data: ", 1)[1])
    assert done["assistant_message"]["role"] == "assistant"


# ---------------------------------------------------------------- isolation & deletion
def test_users_are_isolated(client, alice, bob, alice_docs):
    assert client.get("/api/documents", headers=bob).json()["total"] == 0
    doc_id = alice_docs["Invoice_8842.txt"]["doc_id"]
    assert client.get(f"/api/documents/{doc_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=bob).status_code == 404
    msg = client.post("/api/query", headers=bob, json={"question": "What is the total of invoice INV-2026-8842?"}).json()
    assert msg["assistant_message"]["abstained"] and not msg["assistant_message"]["citations"]
    alice_conv = client.get("/api/conversations", headers=alice).json()["conversations"][0]["conversation_id"]
    assert client.get(f"/api/conversations/{alice_conv}", headers=bob).status_code == 404


def test_delete_removes_from_search(client, alice, alice_docs):
    doc_id = alice_docs["Handbook.html"]["doc_id"]
    q = {"question": "What is the threshold for declaring gifts?"}
    before = client.post("/api/query", headers=alice, json=q).json()["assistant_message"]
    assert any(c["doc_id"] == doc_id for c in before["citations"])
    assert client.delete(f"/api/documents/{doc_id}", headers=alice).status_code == 200
    after = client.post("/api/query", headers=alice, json=q).json()["assistant_message"]
    assert all(c["doc_id"] != doc_id for c in after["citations"])
    assert client.get(f"/api/documents/{doc_id}", headers=alice).status_code == 404


# ---------------------------------------------------------------- intelligence & dashboards
def test_intelligence_endpoints(client, alice, alice_docs):
    doc_id = alice_docs["MSA.docx"]["doc_id"]
    s = client.post(f"/api/documents/{doc_id}/summarize", headers=alice, json={"summary_type": "short"}).json()
    assert s["summary"]["overview"] and s["summary"]["method"]
    e = client.post(f"/api/documents/{doc_id}/entities", headers=alice).json()
    assert "₹12,00,000" in e["entities"]["Money"]
    x = client.post(f"/api/documents/{doc_id}/extract", headers=alice, json={"document_type": "auto"}).json()
    assert x["structured_data"]["document_type"] == "contract"
    assert x["structured_data"]["fields"]["contract_value"] == "₹12,00,000"


def test_statistics_and_analytics(client, alice, alice_docs):
    st = client.get("/api/statistics", headers=alice).json()
    assert st["total_documents"] >= 8 and st["total_questions"] >= 1 and ".pdf" in st["by_format"]
    an = client.get("/api/analytics", headers=alice).json()
    assert an["queries_per_day"] and an["top_documents"]
    assert client.get("/api/system/status").json()["vector_index"] in ("faiss", "numpy")
    assert isinstance(client.get("/api/suggestions", headers=alice).json()["questions"], list)


# ---------------------------------------------------------------- administration
def test_admin_overview_requires_admin_role(client, alice, alice_docs):
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers=alice).status_code == 403
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin-Test-Pass-1"}).json()["token"]
    data = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"}).json()
    names = {u["username"] for u in data["users"]}
    assert {"admin", "demo", "alice"} <= names
    assert data["totals"]["documents"] >= len(alice_docs) - 1
    assert any(d["owner"] == "alice" for d in data["documents"])
    assert any(q["username"] == "alice" and q["question"] for q in data["recent_questions"])


def test_admin_controls(client, alice, alice_docs):
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin-Test-Pass-1"}).json()["token"]
    adm = {"Authorization": f"Bearer {token}"}
    # dashboard numbers are system-wide for administrators
    stats = client.get("/api/statistics", headers=adm).json()
    assert stats["scope"] == "system" and stats["total_documents"] >= 1
    assert client.get("/api/statistics", headers=alice).json()["scope"] == "user"
    # non-admins cannot use management endpoints
    assert client.post("/api/admin/users", headers=alice,
                       json={"username": "eve", "email": "eve@x.io", "password": "secret12"}).status_code == 403
    bob = client.post("/api/admin/users", headers=adm,
                      json={"username": "mallory", "email": "mallory@x.io", "password": "secret12"}).json()
    assert bob["role"] == "user"
    bob_token = client.post("/api/auth/login", json={"username": "mallory", "password": "secret12"}).json()["token"]
    bob_h = {"Authorization": f"Bearer {bob_token}"}
    # suspend: existing session dies and login is refused
    assert client.patch(f"/api/admin/users/{bob['user_id']}", headers=adm, json={"disabled": True}).json()["disabled"]
    assert client.get("/api/auth/me", headers=bob_h).status_code == 401
    assert client.post("/api/auth/login", json={"username": "mallory", "password": "secret12"}).status_code == 403
    client.patch(f"/api/admin/users/{bob['user_id']}", headers=adm, json={"disabled": False, "password": "newpass1"})
    assert client.post("/api/auth/login", json={"username": "mallory", "password": "newpass1"}).status_code == 200
    # admin cannot lock themselves out
    me = client.get("/api/auth/me", headers=adm).json()["user"]
    assert client.patch(f"/api/admin/users/{me['user_id']}", headers=adm, json={"role": "user"}).status_code == 400
    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=adm).status_code == 400
    # read any conversation, delete any document, delete a user
    recent = client.get("/api/admin/overview", headers=adm).json()["recent_questions"]
    conv = client.get(f"/api/admin/conversations/{recent[0]['conversation_id']}", headers=adm).json()
    assert conv["messages"] and conv["conversation"]["username"]
    doc_id = client.get("/api/documents", headers=alice).json()["documents"][0]["doc_id"]
    assert client.delete(f"/api/admin/documents/{doc_id}", headers=adm).status_code == 200
    assert client.get(f"/api/documents/{doc_id}", headers=alice).status_code == 404
    assert client.delete(f"/api/admin/users/{bob['user_id']}", headers=adm).status_code == 200
    assert client.post("/api/auth/login", json={"username": "mallory", "password": "newpass1"}).status_code == 401


def test_admin_sees_all_documents_and_chats(client, alice, alice_docs):
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin-Test-Pass-1"}).json()["token"]
    adm = {"Authorization": f"Bearer {token}"}
    docs = client.get("/api/documents", headers=adm).json()["documents"]
    alice_doc = next(d for d in docs if d["owner"] == "alice")
    # filter by owner, open another user's document and run insights on it
    assert {d["owner"] for d in client.get("/api/documents?owner=alice", headers=adm).json()["documents"]} == {"alice"}
    assert client.get(f"/api/documents/{alice_doc['doc_id']}", headers=adm).status_code == 200
    assert client.post(f"/api/documents/{alice_doc['doc_id']}/summarize", headers=adm,
                       json={"summary_type": "short"}).status_code == 200
    # every user's conversations are listed with their owner and can be read, but not written to
    convs = client.get("/api/conversations", headers=adm).json()["conversations"]
    alice_conv = next(c for c in convs if c["owner"] == "alice")
    assert client.get(f"/api/conversations/{alice_conv['conversation_id']}", headers=adm).status_code == 200
    assert client.post("/api/query", headers=adm, json={"question": "hello?",
                       "conversation_id": alice_conv["conversation_id"]}).status_code == 404
    # admin questions search across all users' documents
    res = client.post("/api/query", headers=adm, json={"question": "How many days of annual leave?"}).json()
    assert res["assistant_message"]["citations"]
    # regular users still only see their own data
    assert all(d["owner"] == "alice" for d in client.get("/api/documents", headers=alice).json()["documents"])


def test_admin_user_detail(client, alice, alice_docs):
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin-Test-Pass-1"}).json()["token"]
    adm = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=alice).json()["user"]
    assert client.get(f"/api/admin/users/{me['user_id']}", headers=alice).status_code == 403
    detail = client.get(f"/api/admin/users/{me['user_id']}", headers=adm).json()
    assert detail["user"]["username"] == "alice"
    assert len(detail["activity"]) == 14 and {"date", "count"} <= set(detail["activity"][0])
    assert detail["documents"] and detail["conversations"]
    assert set(detail["stats"]) == {"avg_confidence", "avg_latency", "abstained", "grounded_rate"}
    assert client.get("/api/admin/users/usr_missing", headers=adm).status_code == 404


def test_insights_are_remembered_and_regenerate_recomputes(client, alice, alice_docs, monkeypatch):
    from backend.services import get_services
    s = get_services()
    doc_id = client.get("/api/documents", headers=alice).json()["documents"][0]["doc_id"]
    calls = {"n": 0}
    real = s.intelligence.generate_summary

    def counting(chunks, kind="detailed"):
        calls["n"] += 1
        return real(chunks, kind)

    monkeypatch.setattr(s.intelligence, "generate_summary", counting)
    url = f"/api/documents/{doc_id}/summarize"
    first = client.post(url, headers=alice, json={"summary_type": "short", "refresh": True}).json()
    assert calls["n"] == 1                                      # Regenerate always recomputes
    again = client.post(url, headers=alice, json={"summary_type": "short"}).json()
    assert calls["n"] == 1 and first == again                  # a normal view is served from memory
    client.delete(f"/api/documents/{doc_id}", headers=alice)
    assert not any(k[0] == doc_id for k in s._insights)         # deleting a document forgets its insights


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"


def test_short_passwords_rejected(client):
    r = client.post("/api/auth/register", json={"username": "shorty", "email": "shorty@x.io", "password": "abc1234"})
    assert r.status_code == 400 and "8 characters" in r.json()["detail"]


def test_account_locks_after_repeated_wrong_passwords(client):
    client.post("/api/auth/register", json={"username": "lockme", "email": "lockme@x.io", "password": "right-pass-1"})
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "lockme", "password": "wrong-pass"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "lockme", "password": "right-pass-1"})
    assert r.status_code == 429 and "Retry-After" in r.headers   # even the right password waits out the lock
    # other accounts are unaffected
    assert client.post("/api/auth/login", json={"username": "demo", "password": "Demo-Test-Pass-1"}).status_code == 200


def test_only_admins_can_start_the_benchmark(client, alice):
    assert client.post("/api/evaluation/run", headers=alice).status_code == 403


def test_random_initial_password_is_never_hard_coded(tmp_path, monkeypatch):
    from backend import auth
    monkeypatch.setattr(auth.Config, "DATA_DIR", tmp_path)
    a = auth.initial_password("administrator", "admin", "")
    b = auth.initial_password("demo", "demo", "")
    assert a != b and len(a) >= 12
    text = (tmp_path / "initial_credentials.txt").read_text(encoding="utf-8")
    assert a in text and b in text
    assert auth.initial_password("administrator", "admin", "Chosen-Pass-9") == "Chosen-Pass-9"
