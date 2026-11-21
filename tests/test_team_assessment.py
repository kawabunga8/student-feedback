"""Team assessment dialog (Draft & review): one level and comment for the members of a group project. Synthetic cards only.
Each member keeps their own card and approval; the dialog never overwrites work or feedback, never picks a level, and never
posts."""
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
model = ThreadingHTTPServer(("127.0.0.1", 0), O)
os.environ['OLLAMA_URL'] = os.environ['LMSTUDIO_URL'] = f'http://127.0.0.1:{model.server_port}'
threading.Thread(target=model.serve_forever, daemon=True).start()
import app, teams_read as T
guard_app(app, HOME); block_live_browser(T)
srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
app.PORT = srv.server_port
app.ALLOWED_HOSTS = {f"127.0.0.1:{app.PORT}", f"localhost:{app.PORT}"}
threading.Thread(target=srv.serve_forever, daemon=True).start(); time.sleep(0.5)
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:260]) if extra != "" else ""))
from playwright.sync_api import sync_playwright
COMMENT = "ZQ-TEAM-COMMENT shared comment"
EVID = "group video, Demo.mp4, watched 2026-11-21"
def card(pg, rid):
    return pg.evaluate("""rid => { const c = [...document.querySelectorAll('.student')].find(c => c.dataset.rid === rid);
      if(!c) return null; const o = c.querySelector('.out:not(.err)');
      return {work: c.querySelector('.work').value, level: c.querySelector('.level').value, feedback: o ? o.innerText : '',
              ms: c.querySelector('.myschool-comment')?.value || '', review: c.querySelector('.review-state')?.textContent || '',
              nosub: c.querySelector('.nosub')?.value || ''}; }""", rid)
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); pg = b.new_page(viewport={"width": 1280, "height": 1000}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv.server_port}/"); time.sleep(1.5)
    pg.click("nav.steps button:nth-child(4)")
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())")
    pg.evaluate("""() => {
      const mk = (n, w, rid) => { const c = addStudent(n, w); if(rid) c.dataset.rid = rid; return c; };
      mk('Alpha Team', '', 'S1'); mk('Bravo Team', '', 'S2'); mk('Charlie Team', '', 'S3');
      mk('Delta Own Work', 'ZQ-OWN-WORK delta wrote this', 'S4'); mk('Echo Unmatched', '', '');
      const f = mk('Foxtrot Drafted', '', 'S6'); window.insertDraft(f, 'ZQ-EXISTING-FEEDBACK', null);
    }""")
    time.sleep(1.2)
    pg.get_by_role('button', name='Team assessment…', exact=True).click()
    dlg = pg.locator('.team-dialog')
    check('A1 the dialog opens without errors and starts with nothing ticked, no level and an empty comment',
          dlg.locator('input[type=checkbox]:checked').count() == 0 and dlg.locator('select').input_value() == '' and dlg.locator('textarea').input_value() == '', errs)
    text = dlg.inner_text()
    check('A2 students with work, feedback or no match are listed greyed with the reason',
          'Delta Own Work (already has work)' in text and 'Foxtrot Drafted (already has feedback)' in text and 'Echo Unmatched (not matched to Course Hub)' in text, text)
    check('A3 those students cannot be ticked and the eligible ones can',
          dlg.get_by_label('Delta Own Work (already has work)', exact=True).is_disabled() and dlg.get_by_label('Echo Unmatched (not matched to Course Hub)', exact=True).is_disabled()
          and dlg.get_by_label('Alpha Team', exact=True).is_enabled())
    apply = dlg.get_by_role('button', name='Apply and mark reviewed')
    apply.click(); check('B1 nothing ticked has visible guidance', 'Select at least one student' in dlg.inner_text())
    dlg.get_by_label('Alpha Team', exact=True).check(); dlg.get_by_label('Bravo Team', exact=True).check()
    apply.click(); check('B2 a team name is required', 'Enter the team name' in dlg.inner_text())
    dlg.get_by_label('Team name', exact=True).fill('3')
    apply.click(); check('B3 the evidence is required', 'Enter what you assessed' in dlg.inner_text())
    dlg.get_by_label('What was assessed', exact=True).fill(EVID)
    apply.click(); check('B4 the comment is required: nothing is written for you', 'Enter the comment' in dlg.inner_text())
    check('B5 nothing was changed by the refused attempts', card(pg, 'S1')['work'] == '' and card(pg, 'S1')['feedback'] == '' and card(pg, 'S1')['level'] == '' and 'Reviewed' not in card(pg, 'S1')['review'], card(pg, 'S1'))
    dlg.get_by_label('Comment (Teams and MySchool)', exact=True).fill(COMMENT)
    dlg.locator('select').select_option(label='Developing')
    apply.click(); time.sleep(1.4)
    a, bq, c, d, f = card(pg, 'S1'), card(pg, 'S2'), card(pg, 'S3'), card(pg, 'S4'), card(pg, 'S6')
    want_work = 'Team 3: ' + EVID
    check('C1 both members got the same evidence, level and comment in Teams and MySchool fields',
          all(x['work'] == want_work and x['level'] == 'Developing' and x['feedback'] == COMMENT and x['ms'] == COMMENT for x in (a, bq)), (a, bq))
    check('C2 both members are marked reviewed, each on their own card', all('Reviewed' in x['review'] for x in (a, bq)), (a['review'], bq['review']))
    check('C3 no "no submission" note is written for a team that submitted', a['nosub'] == '' and bq['nosub'] == '', a['nosub'])
    check('C4 the unticked eligible student is untouched', c['work'] == '' and c['feedback'] == '' and c['level'] == '', c)
    check('C5 existing work and existing feedback are never overwritten',
          d['work'] == 'ZQ-OWN-WORK delta wrote this' and d['feedback'] == '' and f['feedback'] == 'ZQ-EXISTING-FEEDBACK' and f['work'] == '', (d, f))
    check('C6 the dialog closed and the page had no errors', pg.locator('.team-dialog').count() == 0 and not errs, errs)
    # an individual adjustment voids only that member's review
    pg.evaluate("[...document.querySelectorAll('.student')].find(c => c.dataset.rid === 'S2').querySelector('.level').value = 'Proficient'; [...document.querySelectorAll('.student')].find(c => c.dataset.rid === 'S2').querySelector('.level').dispatchEvent(new Event('change', {bubbles: true}))")
    time.sleep(1.4)
    a, bq = card(pg, 'S1'), card(pg, 'S2')
    check('D1 changing one member voids only that member\'s review', 'Reviewed' in a['review'] and 'Changed' in bq['review'] and bq['level'] == 'Proficient' and a['level'] == 'Developing', (a['review'], bq['review']))
    # members now count as ready work: overview and posting table list them, with the evidence kept out of the overview
    pg.evaluate('feedbackOverview.render()')
    ov = pg.locator('.overview').inner_text()
    check('D2 the overview lists the members and does not copy the evidence or comment into itself', 'Alpha Team' in ov and EVID not in ov and COMMENT not in ov, ov[:200])
    check('D3 the posting table lists the reviewed member', 'Alpha Team' in pg.locator('.posting-table').inner_text())
    # the level can stay unset
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove()); const x = addStudent('Golf Team',''); x.dataset.rid='S7';"); time.sleep(0.8)
    pg.get_by_role('button', name='Team assessment…', exact=True).click(); dlg = pg.locator('.team-dialog')
    dlg.get_by_label('Golf Team', exact=True).check(); dlg.get_by_label('Team name', exact=True).fill('Blue'); dlg.get_by_label('What was assessed', exact=True).fill(EVID)
    dlg.get_by_label('Comment (Teams and MySchool)', exact=True).fill(COMMENT); dlg.get_by_role('button', name='Apply and mark reviewed').click(); time.sleep(1.2)
    g = card(pg, 'S7')
    check('E1 with no level chosen the member is reviewed with no level (feedback only)', g['level'] == '' and 'Reviewed' in g['review'] and g['work'] == 'Team Blue: ' + EVID, g)
    # nothing eligible
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())"); time.sleep(0.6)
    pg.get_by_role('button', name='Team assessment…', exact=True).click(); dlg = pg.locator('.team-dialog')
    check('F1 with no students it says so and Apply is disabled', 'No students are loaded' in dlg.inner_text() and dlg.get_by_role('button', name='Apply and mark reviewed').is_disabled())
    check('F2 no page errors', not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed"); sys.exit(0 if all(ok_all) else 1)
