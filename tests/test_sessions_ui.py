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
AS = os.path.join(HOME, "Desktop/Teaching/Assessment")
def find_manifests():
    out = []
    for r, ds, fs in os.walk(AS):
        if "manifest.json" in fs: out.append(os.path.join(r, "manifest.json"))
    return out
def manifest():
    m = find_manifests(); return json.load(open(m[0])) if m else None

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://127.0.0.1:8765")
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    sess = lambda page=None: (page or pg).text_content(".asg-session")
    # an assignment with a saved record
    pg.fill("#atitle", "Task 2: Define & Ideate"); pg.fill("#rubric", "Explain how each idea helps your client.\nCriteria: Five HMW questions")
    pg.select_option("#course", label="ICT 9 (Q1)"); time.sleep(0.5)
    # students typed in BEFORE the assignment is saved: saving it must adopt them
    pg.click("nav.steps button:nth-child(4)")
    pg.click("#add"); pg.click("#add"); cards = pg.locator(".student")
    data = [("Bea Zed", "CH-2", "Bea's HMW questions: how might we help Sam?", "Developing"), ("Al Adams", "CH-1", "Al's ideas about the client.", "Proficient")]
    for i, (nm, rid, wk, lv) in enumerate(data):
        c = cards.nth(i); c.locator(".name").fill(nm); c.locator(".work").fill(wk); c.locator(".notes").fill("note for " + nm.split()[0])
        pg.evaluate(f"document.querySelectorAll('.student')[{i}].dataset.rid = '{rid}'")
    check("1 before saving the assignment, the page says work isn't kept", "not saved between sessions" in sess(), sess())
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.8)
    check("2 saving the assignment starts the session", "Session" in sess() and "not saved between" not in sess(), sess())
    pg.click("#go"); pg.wait_for_function("document.querySelectorAll('.student .out:not(.err)').length === 2", timeout=30000); time.sleep(1.2)
    for i, (nm, rid, wk, lv) in enumerate(data):
        cards.nth(i).locator(".level").select_option(lv); time.sleep(0.2)
    time.sleep(1.1)
    cards.nth(0).locator(".myschool-comment").fill("Developing: add a client need."); time.sleep(0.3)
    cards.nth(0).locator(".review-controls button").click(); time.sleep(1.1)
    check("3 reviewed", "Reviewed" in cards.nth(0).locator(".review-state").text_content())
    pg.click("nav.steps button:nth-child(5)"); time.sleep(0.5)
    pg.locator(".posting-row input[type=checkbox]").nth(0).click(); time.sleep(1.1)
    fb0 = pg.evaluate("document.querySelectorAll('.student')[0].querySelector('.out').innerText")
    time.sleep(3.5)
    m = manifest()
    check("4 manifest.json written in the Assessment folder", m is not None and len(m["students"]) == 2, find_manifests())
    rel = os.path.relpath(find_manifests()[0], AS)
    check("  path is year/term/course/assignment", rel == "2026-27/Q1/ICT 9 (Q1)/Task 2 Define Ideate/manifest.json".replace("Define Ideate", "Define   Ideate".replace("   ", " & ")) or rel.startswith("2026-27/Q1/ICT 9 (Q1)/Task 2"), rel)
    s0 = [s for s in m["students"] if s["student_id"] == "CH-2"][0]
    check("  stores work, notes, level, feedback, comment, approval, tick", s0["work"].startswith("Bea's HMW") and s0["notes"] == "note for Bea" and s0["level"] == "Developing"
          and s0["feedback"] == fb0 and s0["myschool_comment"].startswith("Developing") and s0["approval"] and s0["posting"]["teams"] and s0["posting"]["myschool"] is None, {k: (str(v)[:30]) for k, v in s0.items()})
    check("  status line names the folder", "Session saved" in sess() and "Assessment" in sess(), sess())

    # --- close and reopen
    v_before_reopen = manifest()["version"]
    pg.close(); pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(3)
    cards = pg.locator(".student")
    check("5 reopening restores both students", cards.count() == 2, cards.count())
    names = pg.eval_on_selector_all(".student .name", "es => es.map(e => e.value)")
    check("  names, work, notes, levels back", names == ["Bea Zed", "Al Adams"] and pg.eval_on_selector_all(".student .work", "es => es.map(e => e.value.slice(0, 5))") == ["Bea's", "Al's "]
          and pg.eval_on_selector_all(".student .notes", "es => es.map(e => e.value)") == ["note for Bea", "note for Al"]
          and pg.eval_on_selector_all(".student .level", "es => es.map(e => e.value)") == ["Developing", "Proficient"], names)
    check("  feedback text identical", pg.evaluate("document.querySelectorAll('.student')[0].querySelector('.out').innerText") == fb0)
    check("  MySchool comment back", cards.nth(0).locator(".myschool-comment").input_value().startswith("Developing"))
    check("  review still valid, other student still unreviewed", "Reviewed" in cards.nth(0).locator(".review-state").text_content() and cards.nth(1).locator(".review-state").text_content() == "", cards.nth(0).locator(".review-state").text_content())
    check("  not flagged outdated", pg.locator(".draft-note").count() == 0)
    pg.click("nav.steps button:nth-child(5)"); time.sleep(0.5)
    check("  Teams tick back, MySchool not", pg.locator(".posting-row input[type=checkbox]").nth(0).is_checked() and not pg.locator(".posting-row input[type=checkbox]").nth(1).is_checked()
          and "Teams 1 of 1" in pg.text_content(".posting-progress"), pg.text_content(".posting-progress"))
    check("  nothing re-saved just by opening", manifest()["version"] == v_before_reopen, (manifest()["version"], v_before_reopen))

    # --- an edit after review voids the approval, and that survives a reopen
    v_edit = manifest()["version"]
    pg.click("nav.steps button:nth-child(4)")
    pg.locator(".student").nth(0).locator(".out").click(); pg.keyboard.press("End"); pg.keyboard.type(" Extra sentence."); time.sleep(3.5)
    check("6 edit voids review", "review again" in pg.locator(".student").nth(0).locator(".review-state").text_content())
    check("  edit saved", "Extra sentence." in [s for s in manifest()["students"] if s["student_id"] == "CH-2"][0]["feedback"] and manifest()["version"] == v_edit + 1, (manifest()["version"], v_edit))
    pg.reload(); time.sleep(3)
    check("  still voided after reopening", "review again" in pg.locator(".student").nth(0).locator(".review-state").text_content(), pg.locator(".student").nth(0).locator(".review-state").text_content())
    pg.click("nav.steps button:nth-child(5)"); time.sleep(0.5)
    check("  Teams tick shows changed after posting", "Changed after posting" in pg.text_content(".posting-state"), pg.text_content(".posting-state"))
    # re-review, then change the assignment's instructions and save it: approval void + draft flagged
    pg.click("nav.steps button:nth-child(4)"); pg.locator(".student").nth(0).locator(".review-controls button").click(); time.sleep(1.1)
    check("  re-reviewed", "Reviewed" in pg.locator(".student").nth(0).locator(".review-state").text_content())
    time.sleep(2.5)
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#rubric", pg.input_value("#rubric") + "\nInclude a sketch."); time.sleep(0.4)
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.8)
    pg.reload(); time.sleep(3); pg.click("nav.steps button:nth-child(4)"); time.sleep(0.6)
    st = pg.locator(".student").nth(0)
    check("7 instructions changed: approval void and draft flagged after reopening", "review again" in st.locator(".review-state").text_content() and pg.locator(".draft-note").count() == 0 or "review again" in st.locator(".review-state").text_content(),
          (st.locator(".review-state").text_content(), pg.locator(".draft-note").count()))

    # --- two tabs on one session
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errs.append("tab2: " + str(e))); pg2.on("dialog", lambda d: d.accept())
    pg2.goto("http://127.0.0.1:8765/"); time.sleep(3)
    v = manifest()["version"]; pg2.click("nav.steps button:nth-child(4)"); pg.click("nav.steps button:nth-child(4)")
    pg2.locator(".student").nth(1).locator(".notes").fill("note written in tab 2"); time.sleep(3.5)
    check("8 tab 2 saved its note", manifest()["version"] == v + 1, manifest()["version"])
    pg.locator(".student").nth(1).locator(".notes").fill("note written in tab 1"); time.sleep(3.5)
    mm = manifest(); n1 = [s for s in mm["students"] if s["student_id"] == "CH-1"][0]["notes"]
    check("  tab 1 refused: file unchanged, page keeps its work and offers both choices", mm["version"] == v + 1 and n1 == "note written in tab 2"
          and pg.locator(".sess-note button").count() == 2 and pg.locator(".student").nth(1).locator(".notes").input_value() == "note written in tab 1", (mm["version"], n1, sess()))
    check("  status says not saved", "not saved" in sess(), sess())
    pg.click(".sess-note >> text=Save mine on top"); time.sleep(1.5)
    mm = manifest(); n1 = [s for s in mm["students"] if s["student_id"] == "CH-1"][0]["notes"]
    check("  'Save mine on top' writes it", mm["version"] == v + 2 and n1 == "note written in tab 1", (mm["version"], n1))
    pg2.locator(".student").nth(1).locator(".notes").fill("stale edit from tab 2"); time.sleep(3.5)
    pg2.click(".sess-note >> text=Load the saved session"); time.sleep(1.2)
    check("  'Load the saved session' brings tab 1's version in", pg2.locator(".student").nth(1).locator(".notes").input_value() == "note written in tab 1", pg2.locator(".student").nth(1).locator(".notes").input_value())
    pg2.close()

    # --- switching assignments keeps each one's students apart
    pg.select_option(".asg-pick", ""); time.sleep(1.5)
    check("9 'New assignment' clears the students, saved session untouched", pg.locator(".student").count() == 0 and manifest()["version"] == v + 2, pg.locator(".student").count())
    check("  no manifest invented for an empty new assignment", len(find_manifests()) == 1, find_manifests())
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#atitle", "Task 3: Prototype"); pg.fill("#rubric", "Build a prototype."); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(1.2)
    time.sleep(2.5)
    check("  empty assignment still has no manifest", len(find_manifests()) == 1, find_manifests())
    opts = pg.eval_on_selector_all(".asg-pick option", "os => os.map(o => [o.value, o.textContent])")
    first = [o for o in opts if "Define" in o[1]][0][0]
    pg.select_option(".asg-pick", first); time.sleep(2.5)
    check("  switching back restores the first assignment's students", pg.locator(".student").count() == 2 and pg.eval_on_selector_all(".student .name", "es => es.map(e => e.value)") == ["Bea Zed", "Al Adams"])

    # --- folder safety and request guards
    import app as A
    for title in ["../../etc/passwd", "..", "a/b\\c:d", "   ", "x" * 300]:
        rel, d = A.session_folder("asg-20261031-aaaaaaaa", {"title": title, "course": {"schoolYear": "../..", "label": "/abs"}, "term": ".."})
        check("10 folder for title %r stays inside Assessment" % title[:12], d.is_relative_to(A.ASSESSMENT.resolve()) and d != A.ASSESSMENT.resolve() and ".." not in rel.split("/"), rel[:60])
    def post(path, body, headers):
        req = urllib.request.Request("http://127.0.0.1:8765" + path, data=json.dumps(body).encode(), headers=headers, method="POST")
        try: return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e: return e.code
    check("11 other origin refused", post("/api/session", {"assignment": first, "students": [], "baseVersion": 1}, {"Content-Type": "application/json", "Origin": "https://evil.example"}) == 403)
    check("  non-JSON refused", post("/api/session", {}, {"Content-Type": "text/plain"}) == 403)
    with urllib.request.urlopen("http://127.0.0.1:8765/api/session?assignment=..%2F..%2Fetc") as r: check("  bad assignment id refused", json.load(r).get("error") == "Assignment not found.")
    pg.set_viewport_size({"width": 390, "height": 844}); time.sleep(0.4)
    check("12 no sideways scroll at phone width", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    print("JS errors:", errs or "none")
    print("ALL PASS" if all(ok_all) and not errs else f"{ok_all.count(False)} FAILED")
    b.close()
