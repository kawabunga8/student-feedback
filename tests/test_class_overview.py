"""The class overview (Draft & review): one read-only row per student card with the next thing to do. Synthetic cards only.
It must classify each stage correctly, filter, jump to a card, and never copy student work or feedback into the table."""
import json, os, sys, tempfile, threading, time
from _common import APPDIR, LAUNCH, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class O(BaseHTTPRequestHandler):
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self): self.rfile.read(int(self.headers.get("Content-Length", 0))); self._j({"message": {"content": "x"}})
    def log_message(self, *a): pass
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 11434), O).serve_forever, daemon=True).start()
import app, teams_read as T
guard_app(app, HOME); block_live_browser(T)
srv = app.ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler); threading.Thread(target=srv.serve_forever, daemon=True).start(); time.sleep(0.5)
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))
from playwright.sync_api import sync_playwright
MARK = "ZQ-OVERVIEW-WORK"; FB = "ZQ-OVERVIEW-FEEDBACK"
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); pg = b.new_page(viewport={"width": 1280, "height": 1000}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); time.sleep(1.5)
    pg.click("nav.steps button:nth-child(4)")
    cl = lambda **k: pg.evaluate("i => window.feedbackOverview.classify(i)", {"hasWork": True, "matched": True, **k})
    check("A1 the first missing thing decides the stage", cl(hasWork=False) == "work" and cl(matched=False) == "match" and cl(duplicate=True) == "duplicate" and cl(draftError=True) == "failed" and cl() == "draft" and cl(hasDraft=True, outdated=True) == "regen" and cl(hasDraft=True) == "level", None)
    check("  review, changed-after-review, ready and done", cl(hasDraft=True, level="Developing") == "review" and cl(hasDraft=True, level="Developing", changed=True) == "rereview" and cl(hasDraft=True, level="Developing", reviewed=True) == "post" and cl(hasDraft=True, level="Developing", reviewed=True, postedTeams=True, postedMyschool=True) == "done")
    check("  an earlier problem hides a later one (no work beats everything)", cl(hasWork=False, matched=False, draftError=True, duplicate=True) == "work")
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())")
    pg.evaluate(f"""() => {{
      const a = addStudent('Alpha Test', '{MARK} a'); const b = addStudent('Bravo Test', '{MARK} b'); const c = addStudent('Charlie Test', ''); const d = addStudent('Delta Test', '{MARK} d');
      a.dataset.rid = 'S1'; b.dataset.rid = 'S2'; d.dataset.rid = 'S4';
      a.querySelector('.result').innerHTML = '<div class="out">{FB} text</div>'; a.querySelector('.level').value = 'Developing';
      d.querySelector('.result').innerHTML = '<div class="out err">failed</div>'; d.dataset.tstatus = 'Returned';
    }}""")
    time.sleep(1.5)
    rows = pg.locator(".overview-table tbody tr")
    got = {rows.nth(i).locator("td").first.inner_text(): rows.nth(i).locator("td").last.inner_text() for i in range(rows.count())}
    check("B1 each card gets a row with its own next step", got == {"Alpha Test": "Read it and mark reviewed", "Bravo Test": "Draft the feedback", "Charlie Test": "Add the student’s work", "Delta Test": "Draft failed: try again or write it yourself"}, got)
    check("  the Teams status shows, and the counts add up", "Returned" in pg.locator(".overview-table").inner_text() and "2 need attention" in pg.locator(".overview-counts").inner_text() and "2 still to do" in pg.locator(".overview-counts").inner_text(), pg.locator(".overview-counts").inner_text())
    check("B2 no student work or feedback text is copied into the overview", MARK not in pg.locator(".overview").inner_text() and FB not in pg.locator(".overview").inner_text())
    # mark Alpha reviewed through the real button
    pg.locator(".student").first.locator(".review-controls button").click(); time.sleep(1.4)
    check("B3 marking a student reviewed moves them to ready to post", "Reviewed: ready to post" in pg.locator(".overview-table").inner_text() and "1 ready to post" in pg.locator(".overview-counts").inner_text(), pg.locator(".overview-counts").inner_text())
    pg.locator(".student").first.locator(".work").fill(MARK + " edited"); time.sleep(1.4)
    check("B4 editing after review shows 'review again'", "Changed since review: review again" in pg.locator(".overview-table").inner_text())
    pg.select_option(".overview select", "attention"); time.sleep(0.5)
    check("C1 the filter shows only the chosen group", {pg.locator(".overview-table tbody tr").nth(i).locator("td").first.inner_text() for i in range(pg.locator(".overview-table tbody tr").count())} == {"Charlie Test", "Delta Test"})
    pg.select_option(".overview select", "all"); time.sleep(0.5)
    pg.locator(".overview-table button", has_text="Delta Test").click(); time.sleep(0.3)
    check("C2 clicking a name goes to that student's card", pg.evaluate("document.activeElement && document.activeElement.value") == "Delta Test")
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())"); time.sleep(1.4)
    check("D1 with no students it says so", "No students yet" in pg.locator(".overview-counts").inner_text())
    check("D2 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed"); sys.exit(0 if all(ok_all) else 1)
