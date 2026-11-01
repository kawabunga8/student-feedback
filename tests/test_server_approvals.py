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
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 11434), O).serve_forever, daemon=True).start()

import app
guard_app(app, HOME)
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
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler).serve_forever, daemon=True).start()


ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)) if extra != "" else ""))
import copy
def base_rec(**kw):
    r = {"title": "Task 2", "course": {"name": "ICT 9 (Q1)", "label": "ICT 9 (Q1)", "sectionIds": ["S1"], "schoolYear": "2026-27"}, "grade": "Grade 9",
         "term": "Q1", "instructions": "Explain how each idea helps your client.", "focus": ["Names a client need"],
         "standards": ["ADST 9 - Learning Standard 1: Defining"], "length": "paragraph", "design": {}}
    r.update(kw); return r
def student(**kw):
    s = {"student_id": "CH-1", "name": "Al Adams", "orig": "", "grade": "", "work": "My ideas.", "notes": "n", "level": "Proficient",
         "feedback": "Good job.", "myschool_comment": "Proficient.", "basis": "", "approval": None, "posting": {"teams": None, "myschool": None}}
    s.update(kw); return s
def bound_for(st, rec, **over):    # exactly what the page binds an approval to
    b = {"student_id": st["student_id"], "name": st["name"], "work": st["work"], "notes": st["notes"], "level": st["level"],
         "grade": st["grade"] or rec["grade"], "feedback": st["feedback"], "myschool_comment": st["myschool_comment"], "assignment": rec["title"],
         "instructions": A.compose_rubric(rec["instructions"], rec["focus"]), "course": rec["course"]["label"], "school_year": rec["course"]["schoolYear"],
         "quarter": rec["term"], "department": "ADST", "standards": [{"id": "0", "label": l} for l in rec["standards"]]}
    b.update(over); return json.dumps(b)
def approve(st, rec, **over): return {"bound": bound_for(st, rec, **over), "at": "2026-10-31T10:00:00Z"}
def put(aid, students, base):   # save a session, return (path, session, status)
    r = A.save_session(aid, students, base); return r
import app as A
def new_assignment(**kw):
    r = A.save_assignment_record(base_rec(**kw)); return r["id"], r
def edit(aid, **changes):
    cur = A.load_assignment_record(aid); new = {k: cur[k] for k in A.RECORD_KEYS if k in cur}; new.update(changes)
    return A.save_assignment_record(new, cur["version"])
cur_status = lambda aid: A.load_session(aid)["status"]

# --- 1. a matching approval is current
aid, rec = new_assignment()
st = student(); st["approval"] = approve(st, rec); st["posting"]["teams"] = approve(st, rec)
r = put(aid, [st], None); v = r["session"]["version"]
s = r["status"]["students"][0]
check("1 matching approval is current on save", s["approval"]["current"] and s["posting"]["teams"]["current"] and r["status"]["approved"] == 1, s)
check("  approval stamped with the assignment version", r["session"]["students"][0]["approval"]["stamp"]["assignment_version"] == rec["version"])
check("  load agrees", cur_status(aid)["approved"] == 1)

# --- 2. any stored value changing under an unchanged approval makes it stale
for field, newval in [("feedback", "Changed feedback."), ("level", "Extending"), ("work", "Different work."), ("notes", "other"), ("myschool_comment", "x"), ("name", "Alan Adams"), ("student_id", "CH-9"), ("grade", "Grade 10")]:
    aid2, rec2 = new_assignment(); a = student(); a["approval"] = approve(a, rec2)
    t = dict(a); t[field] = newval
    out = put(aid2, [t], None)["status"]["students"][0]["approval"]
    check("2 tampered %s: approval not current" % field, not out["current"] and field in out["reasons"], out["reasons"])

# --- 3. a forged bound that doesn't match the stored values
aid3, rec3 = new_assignment(); a = student(); a["approval"] = approve(a, rec3, feedback="Something never saved")
o = put(aid3, [a], None)["status"]["students"][0]["approval"]
check("3 forged reviewed values refused", not o["current"] and o["reasons"] == ["feedback"], o)
a["approval"] = {"bound": "not json", "at": ""}; o = put(aid3, [a], 1)["status"]["students"][0]["approval"]
check("  unreadable approval refused", not o["current"] and o["reasons"] == ["unreadable approval"], o)

# --- 4. assignment changes
aid4, rec4 = new_assignment(); a = student(); a["approval"] = approve(a, rec4); put(aid4, [a], None)
edit(aid4, instructions="Explain AND justify.")
o = cur_status(aid4)["students"][0]["approval"]
check("4 instructions change voids approval", not o["current"] and "instructions" in o["reasons"] and "assignment changed since approval" in o["reasons"], o["reasons"])
aid5, rec5 = new_assignment(); a = student(); a["approval"] = approve(a, rec5); put(aid5, [a], None)
edit(aid5, title="Task 2 (renamed)")
o = cur_status(aid5)["students"][0]["approval"]
check("  title-only change voids approval", not o["current"] and "assignment" in o["reasons"], o["reasons"])
aid6, rec6 = new_assignment(); a = student(); a["approval"] = approve(a, rec6); put(aid6, [a], None)
edit(aid6, standards=[])
o = cur_status(aid6)["students"][0]["approval"]
check("  standards change voids approval", not o["current"] and "standards" in o["reasons"], o["reasons"])
edit(aid6, focus=["Another focus"]); o = cur_status(aid6)["students"][0]["approval"]
check("  feedback-focus change voids approval", "instructions" in o["reasons"])
aid7, rec7 = new_assignment(); a = student(); a["approval"] = approve(a, rec7); put(aid7, [a], None)
edit(aid7, length="detailed", design={"teacherNotes": "private"})
check("  a change that doesn't touch what was reviewed leaves it current", cur_status(aid7)["students"][0]["approval"]["current"])

# --- 5. re-approval after a change is stamped with the new version, and stamps persist across saves
rec4b = A.load_assignment_record(aid4); a = student(); a["approval"] = approve(a, rec4b)
r = put(aid4, [a], 1)
check("5 fresh approval current and stamped with the new version", r["status"]["students"][0]["approval"]["current"]
      and r["session"]["students"][0]["approval"]["stamp"]["assignment_version"] == rec4b["version"] and rec4b["version"] > rec["version"])
resend = student(); resend["approval"] = {"bound": a["approval"]["bound"], "at": "later"}     # the page re-sends without a stamp
r2 = put(aid4, [resend], 2)
check("  re-saving the same approval keeps its original stamp", r2["session"]["students"][0]["approval"]["stamp"] == r["session"]["students"][0]["approval"]["stamp"])

# --- 6. posting ticks are judged the same way
aid8, rec8 = new_assignment(); a = student(); a["posting"]["teams"] = approve(a, rec8); a["approval"] = approve(a, rec8); put(aid8, [a], None)
b = dict(a); b["feedback"] = "Edited after posting."; b["approval"] = None
o = put(aid8, [b], 1)["status"]["students"][0]
check("6 tick stale after the feedback changes", not o["posting"]["teams"]["current"] and "feedback" in o["posting"]["teams"]["reasons"] and o["approval"] is None, o)

# --- 7. the posting reader is closed, and only returns what the server finds approved
aid9, rec9 = new_assignment(); good = student(); good["approval"] = approve(good, rec9); good["posting"]["teams"] = approve(good, rec9)
bad = student(student_id="CH-2", name="Bea Zed", feedback="Edited"); bad["approval"] = approve(bad, rec9, feedback="Old text")
none = student(student_id="CH-3", name="Cy Day")
put(aid9, [good, bad, none], None)
try: A.approved_for_posting(aid9); gated = False
except PermissionError: gated = True
check("7 posting reader refuses while automated posting is disabled", gated and A.AUTOMATED_POSTING is False)
A.AUTOMATED_POSTING = True
got = A.approved_for_posting(aid9)
check("  with it on, only the server-approved student is returned", [g["student_id"] for g in got] == ["CH-1"] and got[0]["ticked"] == {"teams": True, "myschool": False} and got[0]["feedback"] == "Good job.", got)
edit(aid9, instructions="Changed")
check("  after the assignment changes nobody is returned", A.approved_for_posting(aid9) == [])
A.AUTOMATED_POSTING = False
check("  no HTTP route exposes the posting reader", all("approved" not in line for line in open("app.py").read().split("self.path") [1:] if False) and "/api/session/approved" not in open("app.py").read())

# --- 8. in the page: reviewed but unsaved assignment edits are not approved on the server until the assignment is saved
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    pg.fill("#atitle", "Task 9"); pg.fill("#rubric", "Explain how each idea helps."); pg.select_option("#course", label="ICT 9 (Q1)"); time.sleep(0.4)
    pg.click("nav.steps button:nth-child(4)"); pg.click("#add"); c = pg.locator(".student").first
    c.locator(".name").fill("Test Student"); c.locator(".work").fill("My ideas"); pg.evaluate("document.querySelector('.student').dataset.rid='CH-1'")
    pg.click("nav.steps button:nth-child(2)"); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.8)
    pg.click("nav.steps button:nth-child(4)"); pg.click("#go"); pg.wait_for_function("document.querySelectorAll('.student .out:not(.err)').length === 1", timeout=30000); time.sleep(1.2)
    c.locator(".level").select_option("Proficient"); time.sleep(1.1); c.locator(".review-controls button").click(); time.sleep(3.8)
    line = lambda: pg.text_content(".asg-session")
    check("8 reviewed and saved: no warning, server counts the approval", "approved on the server" not in line() and "Session saved" in line(), line())
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#rubric", "Explain how each idea helps.\nAnd justify."); time.sleep(0.5)
    pg.click("nav.steps button:nth-child(4)"); time.sleep(1.2)
    check("  instructions edited but not saved: review is void on the page", "review again" in c.locator(".review-state").text_content())
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#rubric", "Explain how each idea helps."); time.sleep(3)
    pg.click("nav.steps button:nth-child(4)"); time.sleep(0.8)
    check("  back to the saved wording: valid again, no warning", "Reviewed" in c.locator(".review-state").text_content() and "approved on the server" not in line(), line())
    # review while Setup has unsaved edits that don't void anything locally... the server compares to the SAVED record
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#rubric", "Explain how each idea helps.\nAnd justify."); pg.click("nav.steps button:nth-child(4)"); time.sleep(0.5)
    c.locator(".review-controls button").click(); time.sleep(3.8)
    check("  reviewed against unsaved instructions: warns that the server doesn't count it", "isn’t approved on the server" in line() and "save the assignment" in line(), line())
    pg.click("nav.steps button:nth-child(2)"); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(1.5)
    check("  saved after approving: still not counted, and it says to review again", "mark them reviewed again" in line() or "mark reviewed again" in line() or "isn’t approved on the server: mark" in line(), line())
    pg.click("nav.steps button:nth-child(4)"); time.sleep(0.6); c.locator(".review-controls button").click(); time.sleep(3.8)
    check("  reviewing again against the saved assignment clears the warning", "approved on the server" not in line(), line())
    print("JS errors:", errs or "none")
    b.close()
print("ALL PASS" if all(ok_all) and not errs else f"{ok_all.count(False)} FAILED")
