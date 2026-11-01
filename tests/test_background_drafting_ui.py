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
        self.rfile.read(int(self.headers.get("Content-Length", 0))); time.sleep(1.5)
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
app.start_worker()
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler).serve_forever, daemon=True).start()


ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:200]) if extra != "" else ""))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://127.0.0.1:8765")
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    pg.fill("#atitle", "Task 2"); pg.fill("#rubric", "Explain how each idea helps your client.")
    pg.select_option("#course", label="ICT 9 (Q1)"); time.sleep(0.5)
    pg.click("nav.steps button:nth-child(4)")
    for _ in range(4): pg.click("#add")
    cards = pg.locator(".student")
    for i, (nm, wk) in enumerate([("Bea Zed", "Bea's ideas."), ("Al Adams", "Al's ideas."), ("Cy Cole", "Cy's ideas."), ("Di Dunn", "")]):
        cards.nth(i).locator(".name").fill(nm); cards.nth(i).locator(".work").fill(wk)
    check("1 button is in the review toolbar", pg.locator("button:has-text('Draft in the background')").count() == 1)
    pg.click("button:has-text('Draft in the background')"); time.sleep(0.5)
    check("2 unsaved assignment: asked to save first", "Save the assignment first" in pg.text_content(".bg-note"), pg.text_content(".bg-note"))
    pg.click(".assignment-bar >> text=Save assignment"); time.sleep(1)
    pg.click("button:has-text('Draft in the background')"); time.sleep(0.8)
    check("3 queued 3 (student with no work left out)", "Queued 3 drafts" in pg.text_content(".bg-note"), pg.text_content(".bg-note"))
    pg.wait_for_selector(".jobs-panel:not([hidden])", timeout=8000)
    check("  panel shows progress and Cancel", pg.locator(".jobs-panel progress").count() == 1 and pg.locator(".jobs-panel button:has-text('Cancel')").count() == 1)
    # Cy's work is edited after queueing: that draft must not be applied
    time.sleep(1); cards.nth(2).locator(".work").fill("Cy changed everything.")
    pg.wait_for_function("document.querySelectorAll('.student .out:not(.err)').length >= 2", timeout=30000)
    pg.wait_for_function("!document.querySelector('.jobs-panel') || document.querySelector('.jobs-panel').hidden || /Finished/.test(document.querySelector('.jobs-panel').textContent) || !document.querySelector('.jobs-panel progress')", timeout=30000); time.sleep(8)
    got = pg.evaluate("[...document.querySelectorAll('.student')].map(c => !!c.querySelector('.out:not(.err)'))")
    check("4 drafts appear in the cards; the one whose work changed is left alone", got[:4] == [True, True, False, False], got)
    check("  note says one wasn't added", "work changed" in pg.text_content(".bg-note"), pg.text_content(".bg-note"))
    check("  drafted text is plain, editable, with Copy", pg.evaluate("(()=>{const o=document.querySelector('.student .out');return o.contentEditable==='true' && !o.innerText.includes('**') && !!o.parentElement.querySelector('button')})()"))
    check("  draft carries a basis so later instruction edits flag it", pg.evaluate("(()=>{const w=window.feedbackWorkspace;const o=document.querySelector('.student .out');return w.draftBasis.get(o)===w.basisNow()})()"))
    # close the page mid-job, reopen, collect
    cards.nth(2).locator(".work").fill("Cy's ideas.")
    time.sleep(2.5)
    pg.click("button:has-text('Draft in the background')"); time.sleep(0.8)
    check("5 second job queues only students still lacking feedback", "Queued 1 draft" in pg.text_content(".bg-note"), pg.text_content(".bg-note"))
    pg.close(); time.sleep(5)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/"); time.sleep(4)
    pg.click("nav.steps button:nth-child(4)"); time.sleep(3.5)
    got = pg.evaluate("[...document.querySelectorAll('.student')].map(c => !!c.querySelector('.out:not(.err)'))")
    n_asg = pg.evaluate("document.querySelector('#asg-pick').value")
    check("6 reopened page collects the draft written while it was closed", sum(got) >= 3, (got, n_asg))
    check("  jobs panel gone when nothing is pending", pg.evaluate("document.querySelector('.jobs-panel').hidden"))
    check("7 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} passed"); sys.exit(0 if all(ok_all) else 1)
