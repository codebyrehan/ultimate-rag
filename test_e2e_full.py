"""End-to-end test against running server with real HF LLM."""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
results = []

def req(method, path, data=None, headers=None, token=None):
    url = BASE + path
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(r)
        content = resp.read()
        try:
            return resp.status, json.loads(content)
        except json.JSONDecodeError:
            lines = content.decode("utf-8", errors="replace").strip().splitlines()
            if lines:
                try:
                    return resp.status, json.loads(lines[-1])
                except json.JSONDecodeError:
                    pass
            return resp.status, {}
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return e.code, {}

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        results.append(name)


# 1. Health
s, d = req("GET", "/health")
check("health", s == 200, str(d.get("status")))

# 2. Register User A (or login if already exists)
s, d = req("POST", "/auth/register", {
    "email": "alice@example.com",
    "password": "TestPass123!",
    "tenant_name": "tenant_a",
    "full_name": "Alice"
})
if s == 409:
    s, d = req("POST", "/auth/login", {
        "email": "alice@example.com",
        "password": "TestPass123!",
        "tenant_name": "tenant_a"
    })
check("register/login Alice", s == 200, str(s))
alice_token = d.get("access_token", "")
alice_refresh = d.get("refresh_token", "")

# 3. Register User B (or login if already exists)
s, d = req("POST", "/auth/register", {
    "email": "bob@example.com",
    "password": "TestPass456!",
    "tenant_name": "tenant_b",
    "full_name": "Bob"
})
if s == 409:
    s, d = req("POST", "/auth/login", {
        "email": "bob@example.com",
        "password": "TestPass456!",
        "tenant_name": "tenant_b"
    })
check("register/login Bob", s == 200, str(s))
bob_token = d.get("access_token", "")

# Clean up any existing documents from previous runs
for token_name, token in [("alice", alice_token), ("bob", bob_token)]:
    s, existing_docs = req("GET", "/documents/", token=token)
    if s == 200 and existing_docs:
        for doc in existing_docs:
            req("DELETE", f"/documents/{doc['id']}", token=token)

# 4. Token refresh
s, d = req("POST", "/auth/refresh", {"refresh_token": alice_refresh})
check("token refresh", s == 200, str(s))
alice_token = d.get("access_token", "")

# 6. Upload PDF as Alice
pdf_path = "E:/ultimate rag p1/test_handbook.pdf"
if not os.path.exists(pdf_path):
    from ultimate_rag.tests._fixtures import make_sample_pdf
    pdf_data = make_sample_pdf()
    with open(pdf_path, "wb") as f:
        f.write(pdf_data)

with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="handbook.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()

r = urllib.request.Request(BASE + "/documents/upload", data=body, headers={
    "Authorization": f"Bearer {alice_token}",
    "Content-Type": f"multipart/form-data; boundary={boundary}",
}, method="POST")
try:
    resp = urllib.request.urlopen(r)
    s = resp.status
    d = json.loads(resp.read())
except urllib.error.HTTPError as e:
    s = e.code
    content = e.read()
    d = json.loads(content) if content else {}
check("PDF upload (Alice)", s == 201, str(s))
doc_id_alice = d.get("id", "")
check("document ID returned", bool(doc_id_alice), doc_id_alice)

# 6b. Duplicate upload rejected
r = urllib.request.Request(BASE + "/documents/upload", data=body, headers={
    "Authorization": f"Bearer {alice_token}",
    "Content-Type": f"multipart/form-data; boundary={boundary}",
}, method="POST")
try:
    resp = urllib.request.urlopen(r)
    s = resp.status
except urllib.error.HTTPError as e:
    s = e.code
check("duplicate upload rejected", s == 409, str(s))

# 7. List documents (Alice should see 1)
s, docs = req("GET", "/documents/", token=alice_token)
check("Alice sees 1 document", s == 200 and len(docs) == 1, f"got {len(docs) if docs else 0}")

# 8. Bob should NOT see Alice's documents
s, docs_bob = req("GET", "/documents/", token=bob_token)
check("Bob sees 0 documents (tenant isolation)", s == 200 and len(docs_bob) == 0, f"got {len(docs_bob) if docs_bob else 0}")

# 9. Bob tries to access Alice's document (IDOR)
s, d = req("GET", f"/documents/{doc_id_alice}", token=bob_token)
check("Bob cannot access Alice's document (IDOR)", s == 404, str(s))

# 10. Alice gets document detail
s, d = req("GET", f"/documents/{doc_id_alice}", token=alice_token)
check("Alice gets document detail", s == 200, str(s))
check("version field present", "version" in d, str(d.get("version")))

# 11. Upload different PDF as Bob
pdf_path2 = "E:/ultimate rag p1/test_manual.pdf"
if not os.path.exists(pdf_path2):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "BOB'S MANUAL\n\nThis is Bob's unique document content.\nIt should not match Alice's handbook.", fontsize=11)
    pdf_data2 = doc.write()
    doc.close()
    with open(pdf_path2, "wb") as f:
        f.write(pdf_data2)

with open(pdf_path2, "rb") as f:
    pdf_bytes2 = f.read()

boundary2 = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body2 = (
    f"--{boundary2}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="manual.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode() + pdf_bytes2 + f"\r\n--{boundary2}--\r\n".encode()

r = urllib.request.Request(BASE + "/documents/upload", data=body2, headers={
    "Authorization": f"Bearer {bob_token}",
    "Content-Type": f"multipart/form-data; boundary={boundary2}",
}, method="POST")
try:
    resp = urllib.request.urlopen(r)
    s = resp.status
    d = json.loads(resp.read())
except urllib.error.HTTPError as e:
    s = e.code
    content = e.read()
    d = json.loads(content) if content else {}
check("PDF upload (Bob)", s == 201, str(s))
doc_id_bob = d.get("id", "")
check("Bob's document ID returned", bool(doc_id_bob), str(doc_id_bob))

# 12. Chat - factual question
s, d = req("POST", "/chat/stream", {"query": "What is the annual leave policy?", "conversation_id": None}, token=alice_token)
check("chat factual question", s == 200, str(s))
if s == 200:
    check("response has query_id", bool(d.get("query_id")))

# 13. Chat - keyword question
s, d = req("POST", "/chat/stream", {"query": "What does the handbook say about leave?", "conversation_id": None}, token=alice_token)
check("chat keyword question", s == 200, str(s))

# 14. Chat - semantic question
s, d = req("POST", "/chat/stream", {"query": "Can I take time off?", "conversation_id": None}, token=alice_token)
check("chat semantic question", s == 200, str(s))

# 15. Chat - follow-up
s, d = req("POST", "/chat/stream", {"query": "How many days?", "conversation_id": None}, token=alice_token)
check("chat follow-up question", s == 200, str(s))

# 16. Chat - unsupported question
s, d = req("POST", "/chat/stream", {"query": "What is the meaning of life?", "conversation_id": None}, token=alice_token)
check("chat unsupported question", s == 200, str(s))

# 17. Non-tenant document access
s, d = req("GET", f"/documents/{doc_id_bob}", token=alice_token)
check("Alice cannot access Bob's document", s == 404, str(s))

# 18. Non-tenant conversation access
s, d = req("GET", "/conversations/", token=bob_token)
check("Bob can list conversations", s == 200, str(s))

# 19. Delete document
s, d = req("DELETE", f"/documents/{doc_id_alice}", token=alice_token)
check("delete document", s == 200, str(s))

# 20. Verify deleted
s, d = req("GET", f"/documents/{doc_id_alice}", token=alice_token)
check("deleted document not accessible", s == 404, str(s))

# 21. Metrics
s, d = req("GET", "/metrics")
check("metrics endpoint", s == 200, str(s))

# 22. Search endpoint
s, d = req("POST", "/search/query", {"query": "leave policy"}, token=alice_token)
check("search endpoint", s == 200, str(s))

print(f"\n{'='*60}")
if results:
    print(f"FAILs: {results}")
    sys.exit(1)
else:
    print("ALL E2E CHECKS PASSED")
