"""Per-student Teams statuses (read-only): the roster parser, the job (names stay in the assignment's own folder, never in
the journal), and the status line on each student card. Synthetic roster text, stand-in runner; nothing contacts Teams."""
import json, os, sys, tempfile, threading, time, urllib.request, urllib.error
from _common import APPDIR, LAUNCH, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class O(BaseHTTPRequestHandler):
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self): self.rfile.read(int(self.headers.get("Content-Length", 0))); self._j({"message": {"content": "x"}})
    def log_message(self, *a): pass
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 11434), O).serve_forever, daemon=True).start()
import app, teams_read as T
guard_app(app, HOME); block_live_browser(T)
from teams_fixtures import roster, names, sts
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))

# ---- A. the parser
rows = list(zip(names, sts))
r = T.parse_roster_students(roster(rows, 6, 6))
check("A1 a complete roster gives each student's name and status in order", r["complete"] and [(x["name"], x["status"]) for x in r["students"]] == [(n, s) for (a, n), s in rows], r)
check("  the aggregate parser still returns counts and no names", "Test" not in json.dumps(T.parse_roster(roster(rows, 6, 6))))
r = T.parse_roster_students(roster(rows, 7, 6))
check("A2 a roster whose rows don't add up to 'N results found' is NOT returned (a partly loaded list)", not r["complete"] and r["students"] == [] and "7" in r["why"], r)
r = T.parse_roster_students(roster(rows, 6, 6).replace("TA\nTest, Alpha\n", "Test, Alpha\n", 1))
check("A3 rows that don't come in groups of three are not returned", not r["complete"] and r["students"] == [], r)
check("A4 two students with the same name are not returned (they could not be told apart)", not T.parse_roster_students(roster([(("TA", "Test, Alpha"), "Viewed"), (("TB", "Test, Alpha"), "Turned in")], 2, 2))["complete"])
check("A5 text without the roster headings is not returned", not T.parse_roster_students("Something else entirely")["complete"])
check("A6 an unfamiliar status word is kept as Teams shows it", T.parse_roster_students(roster([(("TA", "Test, Alpha"), "Needs review")], 1, 1))["students"][0]["status"] == "Needs review")

# ---- B. the job
app.course_data = lambda: {"source": "live", "note": "", "school_year": "2026-27", "quarters": [], "courses": [{"name": "ICT 9 (Q1)", "grades": [9], "quarters": [1], "sections": [{"id": "S1", "block": "A", "quarters": [1]}], "department": "ADST"}]}
app.load_standards = lambda: {}
app.start_worker()
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler).serve_forever, daemon=True).start()
mode = ["ok"]; calls = []
def fake(cls, title):
    calls.append((cls, title)); time.sleep(0.3)
    if mode[0] == "busy": return {"ok": False, "kind": "busy", "error": "Browser profile in use: another browser job is using Chrome."}
    if mode[0] == "signin" and "signed" not in [c[0] for c in calls]:
        calls.append(("signed",)); return {"ok": False, "kind": "sign_in", "error": "Sign in to Microsoft in the Chrome window that opened, then resume the job."}
    if mode[0] == "differs": return {"ok": False, "kind": "differs", "error": "no assignment matches that class and title"}
    text = roster(rows, 7 if mode[0] == "partial" else 6, 6)
    return {"ok": True, "op": "read", "read_at": "2026-11-01T10:00:00-07:00", "source": {"teams_class": cls}, "list_row": {"title": title}, "student_view": {"due": "Nov 4, 3:00 PM"},
            "roster_counts": T.parse_roster(text), "roster_students": T.parse_roster_students(text), "log": []}
app.TEAMS_STUDENTS_RUNNER = fake
def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=None if body is None else json.dumps(body).encode(), headers=h if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r_: return r_.status, json.load(r_)
    except urllib.error.HTTPError as e: return e.code, {}
def wait(fn, secs=20):
    end = time.time() + secs
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.2)
def job(jid): return call("GET", "/api/jobs/" + jid)[1]["job"]
CLS = "RCS - H - Q1 ICT 9 [2026-27]"
rec = call("POST", "/api/assignments", {"assignment": {"title": "Task A: Build & Share", "course": {"name": "ICT 9", "label": "ICT 9 (Q1)", "sectionIds": [], "schoolYear": "2026-27"}, "grade": "Grade 9", "term": "Q1", "instructions": "x",
           "teams": {"className": CLS, "title": "Task A: Build & Share"}}})[1]["assignment"]; aid = rec["id"]
check("B0 the saved assignment keeps its Teams class and title", (rec.get("teams") or {}).get("className") == CLS and (rec.get("teams") or {}).get("title") == "Task A: Build & Share", rec.get("teams"))
st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": "asg-20260101-deadbeef", "class": CLS, "title": "T"}); check("B1 an assignment that isn't saved is refused", "error" in r)
st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": "", "title": "T"}); check("  no class or title is refused with what to do", "Read this assignment from Teams first" in r.get("error", ""), r)
st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}, {"Origin": "http://evil.example"}); check("  another origin is refused", st == 403)
st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); jid = r["job"]["id"]
st, r2 = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); check("  a second status read while one runs is refused", "already queued" in r2.get("error", ""), r2)
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
res = j and j["drafts"][0].get("teams_students")
check("B2 the job returns six students with their statuses, split into first and last name", res and len(res["students"]) == 6 and res["students"][0] == {"name": "Test, Alpha", "first": "Alpha", "last": "Test", "status": "Viewed", "has_feedback": False}, res and res["students"][:1])
check("  the reader was asked for the saved class and title", calls[0] == (CLS, "Task A: Build & Share"))
side = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if r_.endswith(".jobs") and "Test, Alpha" in open(os.path.join(r_, f)).read()]
elsewhere = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if b"Test, Alpha" in open(os.path.join(r_, f), "rb").read() and "Assessment" not in os.path.join(r_, f)]
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("  names are only in the assignment's own Assessment folder; the journal and App Support hold none", len(side) == 1 and "Assessment" in side[0] and not elsewhere and b"Alpha" not in db and b"Test," not in db, (side, elsewhere))
check("  the job list (no results) carries no names", "Alpha" not in json.dumps(call("GET", "/api/jobs?assignment=" + aid)[1]))
call("POST", f"/api/jobs/{jid}/delivered", {"keys": ["students"]})
mode[0] = "partial"; st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("B3 a roster that wasn't read completely is a failed item with the reason, and no names are kept", j and j["counts"]["failed"] == 1 and "wasn't read completely" in j["items"][0]["error"] and not j["drafts"] and "Alpha" not in json.dumps(j), j and j["items"])
mode[0] = "differs"; st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("B4 a page that differs is a failed item and offers nothing", j and j["counts"]["failed"] == 1 and not j["drafts"])
mode[0] = "busy"; st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "failed" else None)(job(jid))); check("B5 browser profile in use stops the job with that message", j and "profile in use" in j["error"].lower(), j and j["error"])
call("POST", f"/api/jobs/{jid}/cancel", {})
mode[0] = "signin"; calls.clear(); st, r = call("POST", "/api/jobs", {"type": "teams_students", "assignment": aid, "class": CLS, "title": "Task A: Build & Share"}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "waiting_for_sign_in" else None)(job(jid))); check("B6 a sign-in page leaves the job waiting for the teacher", j is not None)
call("POST", f"/api/jobs/{jid}/resume", {}); j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid))); check("  resume reads the statuses", j and j["drafts"] and len(j["drafts"][0]["teams_students"]["students"]) == 6)
call("POST", f"/api/jobs/{jid}/delivered", {"keys": ["students"]})

rec2 = call("POST", "/api/assignments", {"assignment": {"title": "No Teams here", "instructions": "x"}})[1]["assignment"]

# ---- C. the page
mode[0] = "ok"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 1000}); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    pg.click("nav.steps button:nth-child(3)")
    pg.click("#teams-status-read")
    check("C1 with no assignment open it asks for one (nothing starts)", "Open or save an assignment" in pg.locator(".teams-status-msg").inner_text())
    pg.select_option(".asg-pick", aid); time.sleep(2)
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())")
    pg.evaluate("addStudent('Alpha Test', 'My notes.'); addStudent('Echo Test', 'My notes.'); addStudent('Nobody Here', 'My notes.')")
    pg.click("#teams-status-read")
    pg.wait_for_function("/Read 6 students/.test(document.querySelector('.teams-status-msg').textContent)", timeout=20000)
    t = pg.evaluate("[...document.querySelectorAll('.student')].map(c => c.querySelector('.tstatus').textContent)")
    check("C2 each card shows its own Teams status; a student not on the roster says so", t == ["Teams: viewed, not turned in", "Teams: turned in", "Teams: not found in this export"], t)
    check("  the summary line counts the statuses and says nothing was changed in Teams", "4 viewed" in pg.locator(".teams-status-msg").inner_text() and "nothing was changed in Teams" in pg.locator(".teams-status-msg").inner_text())
    check("  the page's own Teams note summarises the class", "turned in" in pg.locator("#teamsnote").inner_text().lower() and "Task A" in pg.locator("#teamsnote").inner_text(), pg.locator("#teamsnote").inner_text()[:160])
    check("  the job's names are marked delivered (not offered again)", not any(i for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"] if x["type"] == "teams_students" for i in x["items"] if i["state"] == "done" and not i["delivered"]))
    pg.evaluate("TEAMS.students[0].status='Returned'; applyTeams()")
    pg.select_option(".asg-pick", rec2["id"]); time.sleep(2)
    pg.evaluate("addStudent('Alpha Test','Other assignment work.'); applyTeams()")
    check("  switching assignments clears old Returned statuses and summary", pg.evaluate("TEAMS === null && [...document.querySelectorAll('.student')].every(c=>!c.dataset.tstatus) && !document.querySelector('#teamsnote').textContent"))
    pg.reload(); time.sleep(2); pg.select_option(".asg-pick", rec2["id"]); time.sleep(2); pg.click("nav.steps button:nth-child(3)"); pg.click("#teams-status-read"); time.sleep(0.8)
    check("C3 an assignment with no saved Teams class and title says to read it from Teams first", "no saved Teams class and title" in pg.locator(".teams-status-msg").inner_text())
    check("C4 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed")
sys.exit(0 if all(ok_all) else 1)
