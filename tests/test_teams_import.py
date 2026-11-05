"""Milestone test: import from (pasted) Teams -> confirm Course Hub match -> save -> reopen; versions; design tab."""
import json, os, sys, tempfile, threading, time, urllib.request
from _common import APPDIR, SHOTS, LAUNCH, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class O(BaseHTTPRequestHandler):  # stand-in Ollama
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._j({"message": {"content": "You wrote five how-might-we questions and linked each idea to a client need. Next, explain why the idea fits."}})
    def log_message(self, *a): pass
model = ThreadingHTTPServer(("127.0.0.1", 0), O)
os.environ['OLLAMA_URL'] = os.environ['LMSTUDIO_URL'] = f'http://127.0.0.1:{model.server_port}'
threading.Thread(target=model.serve_forever, daemon=True).start()

import app, teams_read as T
guard_app(app, HOME); block_live_browser(T)
COURSES = {"source": "live", "note": "Courses from Course Hub (live), 2026-27.", "school_year": "2026-27",
  "quarters": [{"label": "Q1", "start": "2026-09-02", "end": "2026-11-06"}, {"label": "Q2", "start": "2026-11-09", "end": "2027-01-29"}],
  "courses": [
    {"name": "ICT 9 (Q1)", "grades": [9], "quarters": [1], "sections": [{"id": "S-ICT9-A", "block": "A", "quarters": [1]}], "department": "ADST"},
    {"name": "ICT 9 (Q2)", "grades": [9], "quarters": [2], "sections": [{"id": "S-ICT9-B", "block": "B", "quarters": [2]}], "department": "ADST"},
    {"name": "Computer Studies 10", "grades": [10], "sections": [{"id": "S-CS10", "block": "C", "quarters": []}], "department": "ADST"},
    {"name": "Senior Band", "grades": [10, 11, 12], "sections": [{"id": "S-BAND", "block": "D", "quarters": []}], "department": "Fine Arts"}]}
STD = {"ADST 9-12": [{"id": "0", "label": "ADST 9 - Learning Standard 1: Defining", "text": "Defining\nIdentify needs."},
                     {"id": "1", "label": "ADST 9 - Learning Standard 2: Ideating", "text": "Ideating\nGenerate ideas."}],
       "Fine Arts 10-12": [{"id": "0", "label": "Music 10 - Learning Standard 1: Performing", "text": "Performing"}]}
app.course_data = lambda: json.loads(json.dumps(COURSES))
app.load_standards = lambda: STD
app.start_worker()
server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
app.PORT = server.server_port
app.ALLOWED_HOSTS = {f'127.0.0.1:{app.PORT}', f'localhost:{app.PORT}'}
BASE = f'http://127.0.0.1:{app.PORT}'
threading.Thread(target=server.serve_forever, daemon=True).start()


from teams_fixtures import LIST, names, sts, roster, SV, SV_RUBRIC, CLASS_ID, ASSIGNMENT_ID

ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))
mode = ["ok"]; calls = []
def fake(op, cls="", title=""):
    calls.append((op, cls, title)); time.sleep(0.4)
    now = "2026-11-01T10:00:00-07:00"
    if mode[0] == "busy": return {"ok": False, "kind": "busy", "error": "Browser profile in use: another browser job is using Chrome."}
    if mode[0] == "sign_in" and not [c for c in calls if c[0] == "signed"]:
        calls.append(("signed",)); return {"ok": False, "kind": "sign_in", "error": "Sign in to Microsoft in the Chrome window that opened, then resume the job."}
    if mode[0] == "differs": return {"ok": False, "kind": "differs", "error": "no assignment matches that class and title", "candidates": []}
    if op == "list": return {"ok": True, "op": "list", "read_at": now, "assignments": T.parse_list(LIST), "log": []}
    return {"ok": True, "op": "read", "read_at": now, "source": {"class_id": "11111111-2222-4333-8444-555555555555", "assignment_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "url": "https://assignments.example.test/classes/11111111/assignment-review/aaaaaaaa", "teams_class": cls, "list_title": title, "read_at": now},
            "student_view": {**T.parse_student_view(SV_RUBRIC if mode[0] in ("rubric", "rubric_read") else SV), **({"rubric_read": True, "rubric": T.validate_rubric({"title": "Sample Design Rubric (Gr 9 Test)", "criteria": [{"name": n, "heading": n, "levels": [{"level": l, "descriptor": f"{n} at {l}."} for l in ("Extending", "Proficient", "Developing", "Emerging")]} for n in ("Planning", "Building")]})[0]} if mode[0] == "rubric_read" else {}), **({"rubric_note": "Teams' page had 1 control(s) and 0 text line(s) mentioning \u201crubric\u201d, but none was exactly \u201cView rubric\u201d: Open grading rubric guide"} if mode[0] == "note" else {})}, "roster_counts": T.parse_roster(roster(list(zip(names, sts)), 6, 6)), "list_row": {}, "log": []}
app.TEAMS_RUNNER = fake
def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=h if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, {}
def wait(fn, secs=20):
    end = time.time() + secs
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.2)
# ---- over HTTP
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "read", "class": "x"}); check("1 read without a title is refused", "needs the Teams class" in r.get("error", ""), r)
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "delete"}); check("  unknown op refused", "op must be" in r.get("error", ""), r)
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "list"}, {"Origin": "http://evil.example"}); check("  other origin refused", st == 403)
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "list"}); jid = r["job"]["id"]
st, r2 = call("POST", "/api/jobs", {"type": "teams_read", "op": "list"}); check("  a second Teams read while one runs is refused", "already queued" in r2.get("error", ""), r2)
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(call("GET", "/api/jobs/" + jid)[1]["job"]))
check("2 list job completes and returns the rows", j and len(j["drafts"][0]["teams"]["assignments"]) == 7, j and j["state"])
sc = [os.path.join(r, f) for r, d, fs in os.walk(os.path.join(HOME, "Library/Application Support/student-feedback/teams-reads")) for f in fs]
check("  result kept under App Support, not in Assessment", len(sc) == 1 and all("Assessment" not in x for x in sc), sc)
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("  journal holds no assignment text", b"Task A" not in db and b"ICT 9" not in db)
mode[0] = "sign_in"; calls.clear()
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "read", "class": "RCS - H - Q1 ICT 9 [2026-27]", "title": "Task A: Build & Share"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "waiting_for_sign_in" else None)(call("GET", "/api/jobs/" + jid)[1]["job"]))
check("3 sign-in page: job waits for the teacher (not failed)", j and "Sign in" in j["error"], j and j["state"])
st, r = call("POST", "/api/jobs/" + jid + "/resume", {}); check("  resume accepted", st == 200 and r["job"]["state"] in ("queued", "running"), r)
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(call("GET", "/api/jobs/" + jid)[1]["job"]))
tv = j["drafts"][0]["teams"] if j else {}
check("  after resume the read completes", bool(tv) and tv["student_view"]["title"] == "Task A: Build & Share")
mode[0] = "busy"
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "list"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "failed" else None)(call("GET", "/api/jobs/" + jid)[1]["job"]))
check("4 browser profile in use: job fails with the plain message, can be resumed", j and "Browser profile in use" in j["error"], j and j["state"])
call("POST", "/api/jobs/" + jid + "/cancel", {})
mode[0] = "differs"
st, r = call("POST", "/api/jobs", {"type": "teams_read", "op": "read", "class": "c", "title": "t"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(call("GET", "/api/jobs/" + jid)[1]["job"]))
check("5 page differs / no single match: item failed with the reason, nothing imported", j and j["items"][0]["state"] == "failed" and "no assignment matches" in j["items"][0]["error"], j and j["items"])
mode[0] = "ok"

# ---- in the page
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto(BASE + "/"); time.sleep(2)
    pg.click("text=Choose from Teams…"); time.sleep(0.3)
    check("6 dialog offers the reader and keeps the paste route", pg.locator(".teams-list-btn").count() == 1 and pg.locator(".teams-paste").count() == 1)
    pg.click(".teams-list-btn")
    pg.wait_for_selector(".teams-item", timeout=15000)
    check("  list shows rows with class and due", pg.locator(".teams-item").count() == 7 and "RCS - H - Q1 ICT 9 [2026-27] · Nov 4th" in pg.locator(".teams-list").inner_text())
    check("  fractions shown as unlabelled", "not labelled by Teams" in pg.locator(".teams-list").inner_text())
    pg.fill(".teams-filter", "task a"); check("  filter narrows the list", pg.locator(".teams-item").count() == 2, pg.locator(".teams-item").count())
    row = pg.locator(".teams-item", has_text="Q1 ICT 9").first
    row.locator("text=Use assignment details").click()
    pg.wait_for_selector(".teams-row[data-key=source]", timeout=15000)
    rows = pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    read_count = len(calls)
    row.locator("text=Use assignment details").click()
    check("  repeated discovery reuses the read and says so", len(calls) == read_count and 'Reusing this page' in pg.locator('.teams-job-msg').inner_text())
    check("7 preview: name, instructions, counts, source", any("Assignment name Task A: Build & Share" in x for x in rows) and any("Status counts 6 students: 4 viewed" in x for x in rows) and any("Source Class 11111111" in x for x in rows), rows)
    check("  reference materials listed by name, marked not read", any("listed by name only (not opened or read" in x and "Sample deck.pptx" in x for x in rows))
    check("  instructions exclude the reference material and the AI widget", "flashcards" not in pg.evaluate("document.querySelector('.teams-row[data-key=instructions]').innerText"))
    tog = pg.locator(".teams-row[data-key=instructions] button[aria-expanded]")
    full = T.parse_student_view(SV)["instructions"]
    check("  long instructions get a show-full control (collapsed by default)", tog.count() == 1 and tog.get_attribute("aria-expanded") == "false" and "…" in pg.inner_text(".teams-row[data-key=instructions] .teams-val > span"))
    tog.click()
    check("  expanded view shows the complete instructions", pg.inner_text(".teams-row[data-key=instructions] .teams-val > span") == full and tog.get_attribute("aria-expanded") == "true")
    tog.click()
    check("  and collapses again", "…" in pg.inner_text(".teams-row[data-key=instructions] .teams-val > span"))
    check("  no student names in the preview", not any("Test, " in x or "Alpha" in x for x in rows))
    check("  class filled in; no rubric invented", pg.input_value(".teams-class") == "RCS - H - Q1 ICT 9 [2026-27]" and any("no rubric button was shown" in x for x in rows))
    check("  read-only: the runner was asked only to list and read", {c[0] for c in calls if c[0] != "signed"} <= {"list", "read"} and ("read", "RCS - H - Q1 ICT 9 [2026-27]", "Task A: Build & Share") in calls, calls[-3:])
    pg.click("text=Confirm match"); time.sleep(0.6)
    pg.click(".teams-all"); time.sleep(0.5)
    check("8 import fills title and instructions, labelled as read by the app", pg.input_value("#atitle") == "Task A: Build & Share" and pg.input_value("#rubric").startswith("Instructions:"))
    src = pg.evaluate("document.querySelector('.asg-src, .field-source') ? [...document.querySelectorAll('.field-source')].map(e=>e.textContent).join('|') : ''")
    check("  field source says it was read from Teams", "read by the app" in src, src)
    pg.click(".teams-save"); time.sleep(1)
    recs = [json.load(open(os.path.join(HOME, "Library/Application Support/student-feedback/assignments", f))) for f in os.listdir(os.path.join(HOME, "Library/Application Support/student-feedback/assignments"))]
    t = recs[0]["teams"] if recs else {}
    check("  saved record keeps the source ids, read time, counts and 'reference materials not read'",
          t.get("source", {}).get("assignment_id", "").startswith("aaaaaaaa") and t["source"].get("read_at") and t.get("statusCounts", {}).get("rows_read") == 6 and t.get("referenceMaterialsRead") is False and t.get("rubricState") == "absent", {k: str(v)[:60] for k, v in t.items()})
    check("  record has no student names", "Test, Alpha" not in json.dumps(recs))
    time.sleep(1.8)
    check("8b with no rubric read, the drafting checkbox 'Use the Teams rubric' is off and unavailable", pg.is_disabled("#use-rubric") and not pg.is_checked("#use-rubric"))
    # paste route still works
    pg.click(".teams-close"); time.sleep(0.3); pg.click("text=Choose from Teams…"); time.sleep(0.3)
    pg.fill(".teams-paste", "Back\nTask 9: Pasted\nDue Nov 9\nInstructions\nDo the thing.\nPoints\nNo points"); pg.click(".teams-read"); time.sleep(0.3)
    rows = pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    check("9 paste fallback still works", any("Task 9: Pasted" in x for x in rows) and not any("Status counts" in x for x in rows), rows[:2])
    # a rubric marker in Student view: shown as present and not read, never mixed into the instructions
    mode[0] = "rubric"; pg.click(".teams-close"); time.sleep(0.3); pg.click("text=Choose from Teams…"); time.sleep(0.3)
    pg.fill(".teams-filter", "") if pg.locator(".teams-filter").is_visible() else None
    n0 = len(calls); pg.click(".teams-list-btn")
    wait(lambda: len(calls) > n0 and calls[-1][0] == "list"); pg.wait_for_function("document.querySelector('.teams-job-msg') && /Choose one to read/.test(document.querySelector('.teams-job-msg').textContent)", timeout=15000); time.sleep(2)
    pg.locator(".teams-item", has_text="Q1 ICT 9").first.locator("text=Refresh details from Teams").click()
    pg.wait_for_selector(".teams-row[data-key=source]", timeout=15000)
    rows = pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    check("10a rubric marker shown as present, not read", any("present in Teams" in x and "not read" in x for x in rows), rows[-3:])
    check("  and kept out of the instructions", not any("View rubric" in x for x in rows if x.startswith("Instructions")))
    if pg.locator("text=Confirm match").count(): pg.click("text=Confirm match"); time.sleep(0.5)
    pg.click(".teams-all"); time.sleep(0.5); pg.click(".teams-save"); time.sleep(1)
    adir = os.path.join(HOME, "Library/Application Support/student-feedback/assignments")
    t2 = json.load(open(os.path.join(adir, os.listdir(adir)[0])))["teams"]
    check("10b saved record says the rubric is present and unread", t2.get("rubricState") == "present_unread", t2.get("rubricState"))
    check("  imported instructions contain no rubric marker", "View rubric" not in pg.input_value("#rubric"))
    pg.reload(); time.sleep(2.5); pg.click("text=Choose from Teams…"); time.sleep(0.5)
    rows = pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    check("10c after reload and reopen, the saved state is still present-but-unread", any(x.startswith("Last read from Teams") and "present in Teams" in x and "not read" in x for x in rows), rows[:3])
    # a rubric that was actually read is a third, distinct state
    mode[0] = "rubric_read"; pg.click(".teams-close"); time.sleep(0.3); pg.click("text=Choose from Teams…"); time.sleep(0.3)
    n0 = len(calls); pg.click(".teams-list-btn")
    wait(lambda: len(calls) > n0 and calls[-1][0] == "list"); pg.wait_for_function("document.querySelector('.teams-job-msg') && /Choose one to read/.test(document.querySelector('.teams-job-msg').textContent)", timeout=15000); time.sleep(2)
    pg.locator(".teams-item", has_text="Q1 ICT 9").first.locator("text=Refresh details from Teams").click()
    pg.wait_for_selector(".teams-row[data-key=source]", timeout=15000)
    rows = pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    src_row = next(x for x in rows if x.startswith("Source"))
    check("10d read rubric is reported as read, not as unread or absent", "present and read from Teams" in src_row and "not read" not in src_row.split("Rubric:")[1], src_row[-160:])
    rr = next(x for x in rows if x.startswith("Rubric"))
    check("10d2 the rubric has its own row, separate from the instructions, collapsed by default", "Sample Design Rubric" in rr and "2 criteria: Planning, Building; 8 descriptors" in rr and "Planning at Extending" not in rr, rr[:200])
    ins_row = next(x for x in rows if x.startswith("Instructions"))
    check("  nothing from the rubric is in the instructions row", "Planning at" not in ins_row and "Sample Design Rubric" not in ins_row)
    pg.locator(".teams-row[data-key=rubric] button[aria-expanded]").click()
    full = pg.inner_text(".teams-row[data-key=rubric] .teams-val > span")
    check("  expanded: every criterion with its four levels in Teams' order", full.index("Planning at Extending") < full.index("Planning at Proficient") < full.index("Planning at Developing") < full.index("Planning at Emerging") < full.index("Building at Extending") < full.index("Building at Proficient") < full.index("Building at Developing") < full.index("Building at Emerging") and full.count(" at ") == 8, full[:160])
    check("  the Setup fields were not changed by reading the rubric", "Planning at" not in pg.input_value("#rubric") and "Planning at" not in pg.input_value("#atitle"))
    if pg.locator("text=Confirm match").count(): pg.click("text=Confirm match"); time.sleep(0.5)
    pg.click(".teams-all"); time.sleep(0.5); pg.click(".teams-save"); time.sleep(1)
    t3 = json.load(open(os.path.join(adir, os.listdir(adir)[0])))["teams"]
    check("10d3 saved record keeps the rubric as read, apart from the instructions", t3.get("rubricState") == "read" and len(t3.get("rubric", {}).get("criteria", [])) == 2 and "Planning at" not in json.dumps(json.load(open(os.path.join(adir, os.listdir(adir)[0])))["instructions"]), str(t3.get("rubricState")))
    time.sleep(1.8)
    check("10d4 once a rubric was read, the drafting checkbox is available and names the criteria (default off)", not pg.is_disabled("#use-rubric") and not pg.is_checked("#use-rubric") and "Planning, Building" in pg.inner_text("#use-rubric >> xpath=../following-sibling::span[1]"))
    b0 = pg.evaluate("window.feedbackWorkspace.basisNow()")
    pg.evaluate("document.querySelector('#use-rubric').click()"); time.sleep(0.4)   # the box sits on the drafting step; click it in place
    b1 = pg.evaluate("window.feedbackWorkspace.basisNow()")
    check("10e ticking the box marks the assignment unsaved and changes what drafts are judged against (outdated warning)", "Unsaved changes" in pg.inner_text(".assignment-bar") and b0 != b1 and "Planning|Extending|" in b1 and "Planning|Extending|" not in b0)
    pg.click(".teams-save"); time.sleep(0.8)
    aid_ = os.listdir(adir)[0][:-5]
    check("  saved in the assignment record (per assignment)", json.load(open(os.path.join(adir, aid_ + ".json")))["teams"].get("useRubric") is True)
    pg.reload(); time.sleep(2.5); time.sleep(1.8)
    check("10f after reload the box is still ticked for that assignment", pg.is_checked("#use-rubric") and not pg.is_disabled("#use-rubric"))
    pg.select_option(".asg-pick", ""); time.sleep(2)
    check("10g switching to another (new) assignment: the box is unticked and unavailable", not pg.is_checked("#use-rubric") and pg.is_disabled("#use-rubric"))
    pg.select_option(".asg-pick", aid_); time.sleep(2)
    check("  switching back restores it", pg.is_checked("#use-rubric"))
    pg.evaluate("document.querySelector('#use-rubric').click()"); time.sleep(0.4)
    check("  unticking marks it unsaved and changes the draft basis again", "Unsaved changes" in pg.inner_text(".assignment-bar") and pg.evaluate("window.feedbackWorkspace.basisNow()") == b0)
    # the reader's diagnostic note is shown when it saw something rubric-like that wasn't the marker
    mode[0] = "note"; pg.click(".teams-close") if pg.locator(".teams-close").is_visible() else None; time.sleep(0.3); pg.click("text=Choose from Teams…"); time.sleep(0.3)
    n0 = len(calls); pg.click(".teams-list-btn")
    wait(lambda: len(calls) > n0 and calls[-1][0] == "list"); pg.wait_for_function("document.querySelector('.teams-job-msg') && /Choose one to read/.test(document.querySelector('.teams-job-msg').textContent)", timeout=15000); time.sleep(2)
    pg.locator(".teams-item", has_text="Q1 ICT 9").first.locator("text=Refresh details from Teams").click()
    pg.wait_for_selector(".teams-row[data-key=source]", timeout=15000)
    src_row = next(x for x in pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())") if x.startswith("Source"))
    check("10e absent plus a diagnostic note: both shown, nothing claimed present", "no rubric button was shown" in src_row and "Open grading rubric guide" in src_row, src_row[-200:])
    mode[0] = "ok"
    # sign-in path in the page
    mode[0] = "sign_in"; calls.clear(); pg.fill(".teams-filter", ""); pg.click(".teams-list-btn")
    pg.wait_for_selector("text=I’ve signed in: resume", timeout=15000)
    check("10 sign-in wait is shown with a resume button", "Waiting for you to sign in" in pg.text_content(".teams-job-msg"))
    pg.click("text=I’ve signed in: resume"); pg.wait_for_selector(".teams-item", timeout=15000)
    check("  resuming finishes the list", pg.locator(".teams-item").count() >= 1)
    check("11 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} passed"); sys.exit(0 if all(ok_all) else 1)
