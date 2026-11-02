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

TEAMS_TEXT = """Back
Student view
This is a preview of what this assignment will look like for students.
Task 2: Define & Ideate
Due November 6, 2026 11:59 PM
Instructions
Stage 2 of the design cycle.

Write at least five "How might we" questions for your client.
Explain how each idea could help your client.
Success criteria:
- Five or more HMW questions
- Each idea linked to client need
Reference materials
Task 2 template.docx
Design cycle overview.pdf
My work
Add work
Points
No points
Turn in"""

ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)) if extra != "" else ""))

def rec_files():
    d = os.path.join(HOME, "Library/Application Support/student-feedback/assignments")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []
def read_rec(aid):
    return json.load(open(os.path.join(HOME, "Library/Application Support/student-feedback/assignments", aid + ".json")))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://127.0.0.1:8765")
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    bar = lambda: pg.text_content(".asg-status"); note = lambda: pg.text_content(".asg-note")
    check("1 starts as a new assignment", "New assignment" in bar(), bar())
    check("  field buttons present", pg.locator(".from-teams").count() == 4, pg.eval_on_selector_all(".from-teams", "bs => bs.map(b => b.textContent)"))

    # --- Choose from Teams: paste, read, type class, confirm match, import all
    pg.click("text=Choose from Teams…"); time.sleep(0.3)
    pg.fill(".teams-paste", TEAMS_TEXT); pg.click(".teams-read"); time.sleep(0.3)
    rows = lambda: pg.eval_on_selector_all(".teams-row", "rs => rs.map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    r = rows()
    check("2 title read", any("Task 2: Define & Ideate" in x for x in r), r[0])
    check("  instructions exclude reference materials", "template.docx" not in pg.evaluate("document.querySelector('.teams-row[data-key=instructions] .teams-val > span').textContent"))
    check("  reference materials listed separately", any("Reference materials" in x and "Task 2 template.docx" in x for x in r))
    check("  course row asks for class", any("Add the Teams class name" in x for x in r))
    pg.fill(".teams-class", "RCS - H - Q1 ICT 9 [2026-27]"); time.sleep(0.3)
    check("3 course suggested (ICT 9 Q1)", pg.eval_on_selector(".teams-course", "s => s.selectedOptions[0].textContent").startswith("ICT 9 (Q1)"))
    check("  grade waits for the course", any("Match the course first" in x for x in rows()))
    pg.click("text=Confirm match"); time.sleep(0.6)
    cm = json.load(open(os.path.join(HOME, "Library/Application Support/student-feedback/class-map.json")))
    m = cm.get("2026-27", {}).get("RCS - H - Q1 ICT 9 [2026-27]", {})
    check("4 class map saved per school year with Course Hub section IDs", m.get("name") == "ICT 9 (Q1)" and m.get("sectionIds") == ["S-ICT9-A"], m)
    check("  Setup course set", pg.eval_on_selector("#course", "s => s.selectedOptions[0].textContent").startswith("ICT 9 (Q1)"))
    check("  grade from Course Hub", pg.input_value("#grade") == "Grade 9")
    pg.click(".teams-all"); time.sleep(0.5)
    check("5 import all message", "Imported the name and instructions and the course" in pg.text_content(".teams-msg"), pg.text_content(".teams-msg"))
    check("  title filled", pg.input_value("#atitle") == "Task 2: Define & Ideate")
    ins = pg.input_value("#rubric")
    check("  instructions filled without UI lines", ins.startswith("Stage 2 of the design cycle.") and "Turn in" not in ins and "template.docx" not in ins)
    pg.screenshot(path=SHOTS + "/dialog.png")
    pg.click(".teams-close")
    src = pg.eval_on_selector_all(".field-source", "es => es.map(e => e.textContent)")
    check("  every field shows its source", all(s.startswith("Source:") for s in src) and "Teams" in src[0], src)

    # --- save -> v1, title-only -> title, instructions -> content
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    files = rec_files(); aid = files[0][:-5] if files else ""
    rec = read_rec(aid) if aid else {}
    check("6 saved v1 on disk", rec.get("version") == 1 and rec["history"][-1]["kind"] == "created", note())
    check("  record parts", rec.get("course", {}).get("sectionIds") == ["S-ICT9-A"] and rec["course"]["schoolYear"] == "2026-27"
          and rec["teams"]["className"] == "RCS - H - Q1 ICT 9 [2026-27]" and rec["teams"]["referenceMaterials"] == ["Task 2 template.docx", "Design cycle overview.pdf"]
          and rec["grade"] == "Grade 9" and rec["term"] == "Q1", {k: rec.get(k) for k in ("grade", "term", "teams")})
    check("  bar says saved", "Saved · version 1" in bar(), bar())
    pg.fill("#atitle", "Task 2: Define and Ideate"); time.sleep(0.3)
    check("  edit shows unsaved", "Unsaved changes" in bar())
    check("  manual edit source", pg.text_content(".field-source") .startswith("Source: Edited here"))
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    rec = read_rec(aid)
    check("7 title-only change recorded as 'title'", rec["version"] == 2 and rec["history"][-1] == {**rec["history"][-1], "kind": "title", "changed": ["title"]}, rec["history"][-1])

    # draft a student, then change the instructions -> draft flagged, review mark voided
    pg.click("nav.steps button:nth-child(4)"); pg.click("#add")
    c = pg.locator(".student").first; c.locator(".name").fill("Test Student"); c.locator(".work").fill("My HMW questions...")
    pg.evaluate("document.querySelector('.student').dataset.rid = 'CH-1'")
    pg.click("#go"); pg.wait_for_function("document.querySelectorAll('.student .out:not(.err)').length === 1", timeout=30000); time.sleep(1.2)
    c.locator(".level").select_option("Proficient"); time.sleep(1.1); c.locator(".review-controls button").click(); time.sleep(1.1)
    check("8 reviewed before change", "Reviewed" in c.locator(".review-state").text_content())
    pg.click("nav.steps button:nth-child(2)")
    pg.fill("#rubric", ins + "\nInclude a sketch."); time.sleep(1.2)
    pg.click("nav.steps button:nth-child(4)"); time.sleep(1.1)
    check("  draft flagged possibly outdated", c.locator(".draft-note").count() == 1)
    check("  review mark voided", "review again" in c.locator(".review-state").text_content(), c.locator(".review-state").text_content())
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    rec = read_rec(aid)
    check("9 instruction change recorded as 'content'", rec["version"] == 3 and rec["history"][-1]["kind"] == "content", rec["history"][-1])
    check("  note explains drafts", "possibly outdated" in note(), note())

    # --- reopen after reload: same instructions, course, grade, standards
    pg.click("nav.steps button:nth-child(2)")
    pg.locator(".std").first.check(); time.sleep(0.3); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    rec = read_rec(aid)
    check("10 standard tick saved (content)", rec["standards"] == ["ADST 9 - Learning Standard 1: Defining"] and rec["history"][-1]["kind"] == "content")
    pg.evaluate("localStorage.setItem('rubric','something else'); localStorage.setItem('grade','Grade 12'); localStorage.setItem('course','Senior Band')")
    pg.reload(); time.sleep(2.5)
    check("11 reopened last assignment", pg.input_value("#atitle") == "Task 2: Define and Ideate" and pg.input_value("#rubric") == ins + "\nInclude a sketch.", pg.input_value("#atitle"))
    check("  course/grade/term restored", pg.eval_on_selector("#course", "s => s.selectedOptions[0].textContent").startswith("ICT 9 (Q1)") and pg.input_value("#grade") == "Grade 9" and pg.input_value("#quarter") == "Q1")
    check("  standards restored", pg.eval_on_selector_all(".std:checked", "bs => bs.map(b => b.closest('label').textContent.trim())") == ["ADST 9 - Learning Standard 1: Defining"])
    check("  not dirty after reopen", "Saved · version 4" in bar(), bar())
    srcs = pg.eval_on_selector_all(".field-source", "es => es.map(e => e.textContent)")
    check("  sources restored", srcs[0].startswith("Source: Edited here") and "match you confirmed" in srcs[3], srcs)

    # --- new / switch back
    pg.select_option(".asg-pick", ""); time.sleep(0.5)
    check("12 new assignment clears name and instructions", pg.input_value("#atitle") == "" and pg.input_value("#rubric") == "" and "New assignment" in bar())
    pg.select_option(".asg-pick", aid); time.sleep(1)
    check("  switching back restores it", pg.input_value("#atitle") == "Task 2: Define and Ideate" and "Saved · version 4" in bar(), bar())

    # --- saved match is offered next time
    pg.click("text=Match Teams class"); time.sleep(0.3)
    r = rows()
    check("13 saved match offered", any("your saved match" in x for x in r), [x for x in r if x.startswith("Course")])
    pg.click(".teams-close")

    # --- multi-grade course: never guessed
    pg.select_option("#course", label="Senior Band"); time.sleep(0.4)
    pg.click("text=Use course grades"); time.sleep(0.2)
    check("14 mixed-grade course asks", pg.eval_on_selector_all(".grade-choice button", "bs => bs.map(b => b.textContent)") == ["Grade 10", "Grade 11", "Grade 12"])
    pg.click(".grade-choice >> text=Grade 11"); time.sleep(0.2)
    check("  chosen grade + source", pg.input_value("#grade") == "Grade 11" and "you chose" in pg.eval_on_selector_all(".field-source", "es => es[2].textContent"))
    pg.select_option("#course", label="ICT 9 (Q1)"); time.sleep(0.4)
    # a fresh draft (the reload cleared the earlier one), to see it flagged when the design replaces the instructions
    pg.click("nav.steps button:nth-child(4)"); pg.click("#add")
    c = pg.locator(".student").first; c.locator(".name").fill("Test Student"); c.locator(".work").fill("My HMW questions...")
    pg.click("#go"); pg.wait_for_function("document.querySelectorAll('.student .out:not(.err)').length === 1", timeout=30000); time.sleep(1.2)
    check("  fresh draft not flagged", pg.locator(".student .draft-note").count() == 0)

    # --- design tab
    pg.click("nav.steps button:nth-child(1)"); time.sleep(0.4)
    d = lambda lab: pg.locator(".design .d-field", has=pg.locator("label", has_text=lab)).locator("input, textarea, select").first
    check("  intended Teams class fills from the confirmed course match", pg.input_value("#design-teams-class") == "RCS - H - Q1 ICT 9 [2026-27]")
    d("Course (Course Hub)").select_option(label="Senior Band"); time.sleep(0.3)
    check("  another course does not retain the previous Teams class", pg.input_value("#design-teams-class") == "" and "No confirmed Teams class" in pg.locator("#design-teams-class").inner_text())
    check("  a class lookup is available when no mapping exists", pg.get_by_role("button", name="Choose class from Teams…", exact=True).is_visible())
    d("Course (Course Hub)").select_option(label="ICT 9 (Q1)"); time.sleep(0.3)
    check("  returning to the course restores its confirmed Teams class", pg.input_value("#design-teams-class") == "RCS - H - Q1 ICT 9 [2026-27]")
    d("Purpose").fill("Find out what your client really needs.")
    d("Directions").fill("Write five How might we questions. Explain how each idea helps your client.")
    d("Required evidence").fill("Five HMW questions\nOne sketch")
    pg.click("text=+ Add criterion"); pg.click("text=+ Add criterion")
    crit = pg.locator(".d-crit")
    crit.nth(0).locator("input").nth(0).fill("Five or more HMW questions"); crit.nth(0).locator("input").nth(1).fill("Numbered list on the page")
    crit.nth(0).locator("select").select_option(label="ADST 9 - Learning Standard 1: Defining")
    crit.nth(1).locator("input").nth(0).fill("Each idea explains how it helps the client in a really detailed way")
    d("Feedback must address").fill("Names a specific client need")
    d("Notes for marking").fill("SECRET-NOTE: watch for copied HMW examples")
    d("MySchool comment guidance").fill("Name the level and one next step")
    time.sleep(0.4)
    warns = pg.eval_on_selector_all(".d-crit-warn", "ws => ws.map(w => w.textContent)")
    check("15 criterion warnings", "Over 8 words" in warns[1] and "Link a standard" in warns[1] and warns[0] == "", warns)
    check("  command terms noted", "explain" in pg.text_content(".design .status"), pg.text_content(".design .status"))
    preview = pg.text_content(".d-prev-ins"); brief = pg.text_content(".d-brief")
    check("  student preview has criteria and submission", "Success criteria:\n- Five or more HMW questions" in preview and 'Class Notebook → Homework → "Task 2: Define and Ideate"' in preview, preview[:400])
    check("  teacher text kept out of the student preview", "SECRET" not in preview and "Names a specific client need" not in preview and "MySchool" not in preview.replace("recorded in MySchool", ""))
    check("  brief holds teacher-only notes", "SECRET-NOTE" in brief and "Names a specific client need" in brief and "Name the level" in brief)
    # Microsoft Forms quiz as the submission type (saves the setup only; importing responses isn't built)
    vis = lambda lab: pg.locator(".design .d-field", has=pg.locator("label", has_text=lab)).first.is_visible()
    d("Students submit").select_option("forms"); time.sleep(0.4)
    fprev = pg.text_content(".d-prev-ins")
    check("  Forms: notebook and file fields are hidden, the Forms note is shown", not vis("Notebook section") and not vis("Notebook page title") and not vis("Required files") and "Forms response import is not built" in pg.locator(".design").inner_text())
    check("  Forms: the student preview points to the quiz and has no notebook or file instructions", "Microsoft Forms quiz" in fprev and "Class Notebook" not in fprev and "attach your work" not in fprev, fprev[-300:])
    check("  Forms: the completion wording changes to the Forms default", "click Submit in Microsoft Forms" in d("How students show they").input_value(), d("How students show they").input_value())
    d("Students submit").select_option("both"); time.sleep(0.3)
    check("  Both: notebook and file fields show again, no Forms note", vis("Notebook section") and vis("Required files") and "Forms response import is not built" not in pg.locator(".design").inner_text())
    d("Students submit").select_option("notebook"); time.sleep(0.4)
    check("  back to Notebook: the completion wording returns and the notebook preview is restored", "click Turn in in Teams" in d("How students show they").input_value() and 'Class Notebook → Homework' in pg.text_content(".d-prev-ins") and not vis("Required files"))
    check("  out-of-sync warning", "different from this design" in pg.text_content(".d-sync"), pg.text_content(".d-sync"))
    pg.click("text=Copy instructions"); time.sleep(0.3)
    clipb = pg.evaluate("navigator.clipboard.readText()")
    check("16 copied instructions are student-facing only", clipb == preview and "SECRET" not in clipb and "Teacher" not in clipb)
    pg.screenshot(path=SHOTS + "/design.png", full_page=True)
    pg.click("button:has-text('Use this design in Setup')"); time.sleep(0.5)
    rub = pg.input_value("#rubric")
    check("17 Setup uses the design + focus, no notes", rub.startswith("Find out what your client really needs.") and "Teacher's feedback focus (not shown to students):\nMust include:\n- Names a specific client need" in rub and "SECRET" not in rub)
    check("  linked standard ticked", pg.eval_on_selector_all(".std:checked", "bs => bs.map(b => b.closest('label').textContent.trim())") == ["ADST 9 - Learning Standard 1: Defining"])
    check("  in sync now", pg.text_content(".d-sync") == "Setup uses this design.", pg.text_content(".d-sync"))
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    rec = read_rec(aid)
    check("18 design saved as content change", rec["history"][-1]["kind"] == "content" and rec["focus"] == ["Names a specific client need"]
          and rec["design"]["teacherNotes"].startswith("SECRET") and "SECRET" not in rec["instructions"], rec["history"][-1])
    pg.click("nav.steps button:nth-child(4)"); time.sleep(0.3)
    check("19 brief in Draft & review", pg.is_visible(".brief-card") and "SECRET-NOTE" in pg.text_content(".brief-card pre"))
    check("  existing draft flagged after design change", pg.locator(".student .draft-note").count() == 1)

    # --- two tabs: no silent overwrite
    pg.click("nav.steps button:nth-child(2)")
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errs.append("tab2: " + str(e))); pg2.on("dialog", lambda d: d.accept())
    pg2.goto("http://127.0.0.1:8765/"); time.sleep(2.5)
    v = read_rec(aid)["version"]
    check("21 second tab opened the same version", ("Saved · version %d" % v) in pg2.text_content(".asg-status"), pg2.text_content(".asg-status"))
    pg2.fill("#atitle", "Task 2 (tab two)"); pg2.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    check("  tab two saved", read_rec(aid)["version"] == v + 1)
    pg.fill("#atitle", "Task 2 (tab one)"); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    check("  tab one refused, nothing written", read_rec(aid)["version"] == v + 1 and read_rec(aid)["title"] == "Task 2 (tab two)"
          and "saved somewhere else" in note(), note())
    pg.click("button:has-text('Save mine as version')"); time.sleep(0.6)
    rec = read_rec(aid)
    check("  'save mine' writes the next version", rec["version"] == v + 2 and rec["title"] == "Task 2 (tab one)" and rec["history"][-1]["kind"] == "title", rec["history"][-1])
    pg2.fill("#atitle", "Task 2 (tab two again)"); pg2.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    pg2.click("button:has-text('Load version')"); time.sleep(1)
    check("  'load version' shows the newer save", pg2.input_value("#atitle") == "Task 2 (tab one)" and ("Saved · version %d" % (v + 2)) in pg2.text_content(".asg-status")
          and read_rec(aid)["version"] == v + 2, pg2.text_content(".asg-status"))
    pg2.close()

    # --- two tabs: the second save must not silently overwrite the first
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errs.append("tab2: " + str(e))); pg2.on("dialog", lambda dd: dd.accept())
    pg2.goto("http://127.0.0.1:8765/"); time.sleep(2.5)
    v_before = read_rec(aid)["version"]
    pg2.fill("#atitle", "Task 2 (edited in tab 2)"); pg2.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    check("21 tab 2 saved", read_rec(aid)["version"] == v_before + 1 and read_rec(aid)["title"] == "Task 2 (edited in tab 2)")
    pg.click("nav.steps button:nth-child(2)"); pg.fill("#atitle", "Task 2 (edited in tab 1)"); pg.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    r1 = read_rec(aid)
    check("  tab 1's save refused, nothing overwritten", r1["version"] == v_before + 1 and r1["title"] == "Task 2 (edited in tab 2)", note())
    check("  tab 1 keeps its edit and offers both choices", pg.input_value("#atitle") == "Task 2 (edited in tab 1)" and
          pg.locator(".asg-note button").count() == 2, pg.eval_on_selector_all(".asg-note button", "bs => bs.map(b => b.textContent)"))
    pg.click(".asg-note >> text=Save mine"); time.sleep(0.6)
    r1 = read_rec(aid)
    check("  'Save mine' saves on top, recorded as a title change", r1["version"] == v_before + 2 and r1["title"] == "Task 2 (edited in tab 1)"
          and r1["history"][-1]["kind"] == "title", r1["history"][-1])
    pg2.fill("#atitle", "Stale tab 2 edit"); pg2.click(".assignment-bar >> text=Save assignment"); time.sleep(0.6)
    pg2.click(".asg-note >> text=Load version"); time.sleep(1)
    check("  'Load version' brings the newer record into tab 2", pg2.input_value("#atitle") == "Task 2 (edited in tab 1)" and "Saved · version " + str(v_before + 2) in pg2.text_content(".asg-status"),
          pg2.text_content(".asg-status"))
    pg2.close()

    # --- server guards
    def post(path, body, headers):
        req = urllib.request.Request("http://127.0.0.1:8765" + path, data=json.dumps(body).encode(), headers=headers, method="POST")
        try: return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e: return e.code
    check("20 other origin refused", post("/api/assignments", {"assignment": {"title": "x"}}, {"Content-Type": "application/json", "Origin": "https://evil.example"}) == 403)
    check("  form post refused", post("/api/class-map", {}, {"Content-Type": "text/plain"}) == 403)
    with urllib.request.urlopen("http://127.0.0.1:8765/api/assignments/..%2F..%2Fetc") as r: bad = json.load(r)
    check("  bad id refused", bad.get("error") == "Assignment not found.")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.click("nav.steps button:nth-child(1)"); time.sleep(0.3)
    pg.screenshot(path=SHOTS + "/design-phone.png", full_page=True)
    check("  no horizontal scroll at phone width", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("document.documentElement.scrollWidth"))
    print("JS errors:", errs or "none")
    print("ALL PASS" if all(ok_all) and not errs else f"{ok_all.count(False)} FAILED")
    b.close()
