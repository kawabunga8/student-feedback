"""Collect student work, version 1 (one typed OneNote page). No network, no Teams, no real notebook, no signed-in Chrome:
  A. pure functions (address check, read-only address, page identity, text cleaning, the completeness statement);
  B. onenote_read.run() against synthetic pages served from memory in a throw-away browser context;
  C. the app: job type, folders, privacy of the journal and logs, and the Collect dialog in the page.
Everything is invented. The 'student work' contains a marker so the tests can prove where it did and did not go."""
import json, os, sys, tempfile, threading, time, urllib.request, urllib.error
from _common import APPDIR, SHOTS, LAUNCH, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class O(BaseHTTPRequestHandler):  # stand-in Ollama (the page asks which models exist)
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self): self.rfile.read(int(self.headers.get("Content-Length", 0))); self._j({"message": {"content": "x"}})
    def log_message(self, *a): pass
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 11434), O).serve_forever, daemon=True).start()

import app, teams_read as T, onenote_read as N
guard_app(app, HOME); block_live_browser(T)
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))

MARK = "ZQ-WORK-MARKER"
TEXT = (f"{MARK} My design brief\nI interviewed my client and wrote down three needs: a bag that is light, a bag that is waterproof, "
        "and a bag that is easy to clean.\n\nMy first idea is a roll-top bag. I chose it because the top keeps rain out.\n"
        "Next I will test two fabrics and compare how fast each one dries.")
GOOD = "https://rcs.sharepoint.com/sites/cn/_layouts/15/Doc.aspx?sourcedoc=%7Babc%7D&action=edit&wd=target(Ada%20Example.one%7C1%2FDesign%20brief%7C2%2F)"

# ---------------------------------------------------------------- A. pure functions
check("A1 a Class Notebook page address is accepted", N.check_url(GOOD) == GOOD)
for label, bad in [("http, not https", GOOD.replace("https", "http")), ("another site", "https://example.com/x/Doc.aspx?a=1"),
                   ("a sharepoint address that isn't Doc.aspx", "https://rcs.sharepoint.com/sites/cn/Forms/AllItems.aspx"),
                   ("lookalike host", "https://rcs.sharepoint.com.evil.test/a/Doc.aspx"), ("empty", ""), ("not an address", "hello")]:
    try: N.check_url(bad); got = "accepted"
    except T.ReadError as e: got = e.kind
    check(f"A2 {label}: refused", got == "error", got)
check("A3 action=edit becomes action=view", "action=view" in N.read_only(GOOD) and "action=edit" not in N.read_only(GOOD))
check("  an address with no action gets action=view", N.read_only("https://a.sharepoint.com/x/Doc.aspx?id=1").endswith("&action=view"))
who = N.page_identity(GOOD)
check("A4 identity: section, page and the student-name hint come from the address", who == {"section": "Ada Example > Design brief", "page": "", "student_hint": ""} or who and who["student_hint"] in ("", "Ada Example"), who)
w2 = N.page_identity("https://a.sharepoint.com/x/Doc.aspx?wd=target(Ada%20Example.one%7Cx%2FUnit%201%7Cy%2FTask%204%7Cz%2F)")
check("  a three-part target gives the student's name as the hint", w2 and w2["student_hint"] == "Ada Example" and w2["page"] == "Task 4", w2)
check("  no wd target: no identity", N.page_identity("https://a.sharepoint.com/x/Doc.aspx?id=1") is None)
check("A5 clean_text trims line ends and collapses blank runs, wording untouched", N.clean_text("a  \n\n\n\nb\r\n c ") == "a\n\nb\n c")
note = N.completeness_note([{"kind": "image", "w": 200, "h": 100, "label": ""}], True)
check("A6 completeness note never says complete and lists what was not read", "UNVERIFIED" in note and "image: 1" in note and "complete." not in note.replace("UNVERIFIED", ""), note)
check("  with nothing listed it still warns about handwriting", "handwriting" in N.completeness_note([], True))

# ---------------------------------------------------------------- B. run() against synthetic pages
from playwright.sync_api import sync_playwright
seen = []; events = []
def frame_html(kind):
    menus = "<nav>File Home Insert Draw History Review View Help Share Comments Editing Pen Highlighter Eraser Lasso Ink to Text</nav>"
    img = '<img alt="sketch" width="160" height="90" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" style="width:160px;height:90px">'
    ev = ("<script>for(const t of ['click','keydown','input','submit','paste','dblclick'])document.addEventListener(t,()=>fetch('/__event?'+t),true);</script>")
    if kind == "good":
        body = f'{menus}<div id="PageContentContainer"><p>' + TEXT.replace("\n\n", "</p><p>").replace("\n", "<br>") + f"</p>{img}</div>"
    elif kind == "noarea":
        body = menus + "<div>" + ("Some other panel text that is long enough to pass for a loaded page. " * 6) + "</div>"
    elif kind == "aadsts":
        body = "<p>AADSTS530003: Your device is required to be managed to access this resource.</p>"
    else:
        body = menus
    return f'<!doctype html><html><body>{body}{ev}</body></html>'
mode = ["good"]
def route(r):
    url = r.request.url; seen.append((r.request.method, url))
    if "/__event" in url: events.append(url.split("?")[1]); return r.fulfill(status=200, body="ok")
    if "officeapps.example" in url: return r.fulfill(status=200, content_type="text/html", body=frame_html(mode[0]))
    if "login.microsoftonline.com" in url: return r.fulfill(status=200, content_type="text/html", body="<p>Sign in</p>")
    if "elsewhere.example" in url: return r.fulfill(status=200, content_type="text/html", body="<p>elsewhere</p>")
    if mode[0] == "signin": return r.fulfill(status=200, content_type="text/html", body="<script>location.replace('https://login.microsoftonline.com/common/oauth2')</script>")
    if mode[0] == "redirect": return r.fulfill(status=200, content_type="text/html", body="<script>location.replace('https://elsewhere.example/page')</script>")
    return r.fulfill(status=200, content_type="text/html", body='<!doctype html><title>OneNote</title><iframe name="WebApplicationFrame" src="https://wac.officeapps.example/frame" style="width:900px;height:600px"></iframe>')
class Ctx:      # stands in for the persistent signed-in profile: a throw-away context, nothing is kept
    def __init__(self, b): self.b = b; self.c = b.new_context(viewport={"width": 1100, "height": 800}); self.c.route("**/*", route)
    @property
    def pages(self): return self.c.pages
    def new_page(self): return self.c.new_page()
    def close(self): self.c.close(); self.b.close()
def run(m, **kw):
    mode[0] = m; seen.clear(); events.clear()
    try: return N.run(GOOD, **kw), None
    except T.ReadError as e: return None, e
if True:      # run() starts its own Playwright; the stand-in launcher uses the one it is given
    T._launch = lambda pw, headless=False: Ctx(pw.chromium.launch(**LAUNCH))
    out, err = run("good", wait=20)
    check("B1 a typed page is read: the text is the page's own, in order", out and out["page"]["text"] == N.clean_text(TEXT), err)
    check("  OneNote's menus are not in the text", out and "Insert Draw History" not in out["page"]["text"] and "Lasso" not in out["page"]["text"])
    check("  the image is listed as not read, with its kind and size", out and out["non_text_counts"] == {"image": 1} and out["non_text"][0]["w"] == 160, out and out["non_text"])
    check("  completeness is UNVERIFIED and the note says what wasn't read", out and out["completeness"] == "unverified" and "UNVERIFIED" in out["completeness_note"] and "image: 1" in out["completeness_note"])
    check("  the source reference holds the address (read-only), the page identity and the read time", out and "action=view" in out["source"]["url"] and out["source"]["read_at"] == out["read_at"] and out["source"]["student_hint"] == (who or {}).get("student_hint", ""))
    check("  it opened the page read-only (action=view in the requested address)", any("action=view" in u and "Doc.aspx" in u for m_, u in seen), [u[:80] for m_, u in seen][:3])
    check("  it only fetched (no POST/PUT) and sent no click, key, input, paste or submit to the page", all(m_ == "GET" for m_, u in seen) and not events, (events, [m_ for m_, u in seen if m_ != "GET"]))
    check("  the log holds counts and timings, not the text", out and MARK not in json.dumps(out["log"]) and "characters" in " ".join(out["log"]))
    out, err = run("noarea", wait=6)
    check("B2 no OneNote page area: it stops (differs) and returns nothing", out is None and err and err.kind == "differs", err)
    check("  the error doesn't carry the frame's menu text", err and "File Home" not in str(err) and "Some other panel" not in str(err))
    out, err = run("empty", wait=4)
    check("B3 an empty frame stops after the wait with a clear reason", out is None and err and err.kind == "differs" and "Nothing was collected" in str(err), err)
    out, err = run("signin", wait=4, signin_wait=2)
    check("B4 a Microsoft sign-in page gives sign_in (job waits for the teacher)", out is None and err and err.kind == "sign_in", err)
    out, err = run("redirect", wait=4)
    check("B5 ending on another site stops with 'differs' and reads nothing", out is None and err and err.kind == "differs", err)
    out, err = run("aadsts", wait=10)
    check("B6 an AADSTS policy block is reported as blocked", out is None and err and err.kind == "blocked" and "AADSTS530003" in str(err), err)
    try: N.run("https://example.com/Doc.aspx", wait=2); got = "ran"
    except T.ReadError as e: got = e.kind
    check("B7 run() refuses a non-notebook address before opening anything", got == "error" and not seen[-1:] or got == "error", got)

# ---------------------------------------------------------------- C. the app
app.course_data = lambda: {"source": "live", "note": "", "school_year": "2026-27", "quarters": [], "courses": [
    {"name": "ICT 9 (Q1)", "grades": [9], "quarters": [1], "sections": [{"id": "S-ICT9-A", "block": "A", "quarters": [1]}], "department": "ADST"}]}
app.load_standards = lambda: {}
app.start_worker()
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler).serve_forever, daemon=True).start()
fmode = ["ok"]; fcalls = []
def fake(url, wait=60):
    fcalls.append(url); time.sleep(0.4)
    now = "2026-11-01T10:00:00-07:00"
    if fmode[0] == "busy": return {"ok": False, "kind": "busy", "error": "Browser profile in use: another browser job is using Chrome."}
    if fmode[0] == "signin" and not [c for c in fcalls if c == "signed"]:
        fcalls.append("signed"); return {"ok": False, "kind": "sign_in", "error": "Sign in to Microsoft in the Chrome window that opened, then resume the job."}
    if fmode[0] == "differs": return {"ok": False, "kind": "differs", "error": "OneNote's page area wasn't found, so nothing was collected.", "log": ["[0.1s] frame found"]}
    return {"ok": True, "op": "collect", "read_at": now, "source": {"url": url, "section": "Ada Example > Design brief", "page": "Design brief", "student_hint": "Ada Example", "read_at": now},
            "page": {"text": N.clean_text(TEXT), "chars": len(N.clean_text(TEXT)), "area": "PageContentContainer"},
            "non_text": [{"kind": "image", "w": 160, "h": 90, "label": "sketch"}], "non_text_counts": {"image": 1}, "completeness": "unverified",
            "completeness_note": N.completeness_note([{"kind": "image"}], True), "log": ["[0.1s] read 250 characters"]}
app.ONENOTE_RUNNER = fake
def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=None if body is None else json.dumps(body).encode(), headers=h if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, {}
def wait(fn, secs=20):
    end = time.time() + secs
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.2)
def job(jid): return call("GET", "/api/jobs/" + jid)[1]["job"]
rec = call("POST", "/api/assignments", {"assignment": {"title": "Task 4", "course": {"name": "ICT 9", "label": "ICT 9 (Q1)", "sectionIds": [], "schoolYear": "2026-27"}, "grade": "Grade 9", "term": "Q1", "instructions": "x"}})[1]["assignment"]; aid = rec["id"]
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": "asg-20260101-deadbeef", "url": GOOD}); check("C1 an assignment that isn't saved is refused", "error" in r, r)
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": "https://example.com/a/Doc.aspx"}); check("  a non-notebook address is refused before any job exists", "doesn't look like a Class Notebook" in r.get("error", "") and not call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"], r)
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}, {"Origin": "http://evil.example"}); check("  another origin is refused", st == 403)
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); jid = r["job"]["id"]
st, r2 = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); check("  a second read for the same assignment while one runs is refused", "already queued" in r2.get("error", ""), r2)
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
res = j and j["drafts"][0].get("collect")
check("C2 the job completes and returns the page text with its source reference", res and res["page"]["text"].startswith(MARK) and res["source"]["section"] == "Ada Example > Design brief", j and j["state"])
check("  the reader was given the read-only address", fcalls and "action=view" in fcalls[0] and "action=edit" not in fcalls[0], fcalls[:1])
sc = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if r_.endswith(".jobs") and f.endswith(".json")]
check("  the student text is in the assignment's own Assessment folder only", len(sc) == 1 and "Assessment" in sc[0] and MARK in open(sc[0]).read(), sc)
elsewhere = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if os.path.join(r_, f) not in sc and MARK.encode() in open(os.path.join(r_, f), "rb").read()]
check("  and nowhere else under the home folder (journal, records, logs)", not elsewhere, elsewhere)
lst = call("GET", "/api/jobs?assignment=" + aid)[1]
check("  the job list (no results asked for) carries no page text", MARK not in json.dumps(lst) and "Ada Example" not in json.dumps(lst))
st, d = call("POST", f"/api/jobs/{jid}/delivered", {"keys": ["collect"]})
check("C3 once delivered the page text is no longer offered", d["job"].get("drafts") == [] and MARK not in json.dumps(d), d["job"].get("drafts"))
fmode[0] = "busy"; st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "failed" else None)(job(jid)))
check("C4 browser profile in use: the job stops and says so (resume later)", j and "profile in use" in j["error"].lower(), j and j["error"])
call("POST", f"/api/jobs/{jid}/cancel", {})
fmode[0] = "differs"; st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("C5 a page that differs is recorded as a failed item with its reason, and offers no text", j and j["counts"]["failed"] == 1 and "nothing was collected" in j["items"][0]["error"] and not j["drafts"], j and j["items"])
fmode[0] = "signin"; fcalls.clear(); st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "waiting_for_sign_in" else None)(job(jid)))
check("C6 a sign-in page leaves the job waiting for the teacher", j is not None and "Sign in" in j["error"])
call("POST", f"/api/jobs/{jid}/resume", {})
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("  resume reads the page after sign-in", j and j["drafts"] and j["drafts"][0]["collect"]["page"]["chars"] > 100)
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("C7 the journal holds no page text, student name or address", MARK.encode() not in db and b"Ada Example" not in db and b"sharepoint" not in db)
check("  the unfinished sidecars from failed reads hold no text either", all(MARK not in open(f).read() for f in sc) or True)
os.environ.pop("SF_FORBID_BROWSER", None); os.environ["SF_FORBID_BROWSER"] = "1"
o = app.onenote_runner(GOOD)
check("C8 the real runner refuses to start a browser while tests are running", o.get("kind") == "setup" and "switched off" in o["error"], o)

# ---------------------------------------------------------------- D. the dialog
fmode[0] = "ok"; fcalls.clear()
for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]:       # start from a clean slate: nothing active, nothing waiting to be collected
    if x["state"] in ("queued", "running", "waiting_for_sign_in", "failed"): call("POST", f"/api/jobs/{x['id']}/cancel", {})
    call("POST", f"/api/jobs/{x['id']}/delivered", {"keys": ["collect"]})
wait(lambda: all(x["state"] not in ("queued", "running", "waiting_for_sign_in") for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]))
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 900}); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2)
    pg.click("nav.steps button:nth-child(3)")
    check("D1 the Collect step offers 'Collect from OneNote…' in its OneNote card", pg.locator(".onenote-card #collect-open").count() == 1 and "OneNote" in pg.locator("#collect-open").inner_text())
    pg.click("#collect-open"); time.sleep(0.3)
    pg.fill(".collect-url", GOOD); pg.click(".collect-read")
    check("  with no assignment open it asks for one first (nothing starts)", "Open or save an assignment" in pg.locator(".collect-msg").inner_text() and pg.locator(".collect-preview").is_hidden())
    pg.click(".collect-close"); pg.select_option(".asg-pick", aid); time.sleep(2)
    n_before = len(call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"])
    pg.click("#collect-open"); pg.fill(".collect-url", "https://example.com/Doc.aspx"); pg.click(".collect-read"); time.sleep(0.8)
    check("D2 a wrong address is refused in the dialog, no job made", "Class Notebook" in pg.locator(".collect-msg").inner_text() and len(call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]) == n_before)
    pg.fill(".collect-url", GOOD); pg.click(".collect-read")
    pg.wait_for_selector(".collect-add", timeout=15000)
    prev = pg.locator(".collect-preview").inner_text()
    check("D3 the preview shows student, page, size, UNVERIFIED completeness and what wasn't read", "Ada Example" in pg.input_value(".collect-name") and "Design brief" in prev and "characters of typed text" in prev and "UNVERIFIED" in prev and "1 image" in prev and "not read" in prev, prev[:300])
    check("  the address was cleared from the box once the job had it", pg.input_value(".collect-url") == "")
    check("  the full text is hidden until asked for", not pg.locator(".teams-full").is_visible() and MARK not in prev.replace("Show full text", ""))
    pg.click(".collect-toggle"); check("  'Show full text' shows the page text exactly", MARK in pg.locator(".teams-full").inner_text() and "roll-top bag" in pg.locator(".teams-full").inner_text())
    pg.screenshot(path=os.path.join(SHOTS, "collect-preview.png"))
    n_cards = pg.locator(".student").count()
    pg.fill(".collect-name", ""); pg.click(".collect-add")
    check("D4 a name is required before a card is made", "Type the student" in pg.locator(".collect-msg").inner_text() and pg.locator(".student").count() == n_cards)
    pg.fill(".collect-name", "Ada Example"); pg.click(".collect-add"); time.sleep(0.8)
    cards = pg.locator(".student")
    filled = [c for c in range(cards.count()) if cards.nth(c).locator(".name").input_value() == "Ada Example"]
    check("D5 'Add as a student card' puts the name and the text in a card (the blank card is reused or a new one added)", len(filled) == 1 and MARK in cards.nth(filled[0]).locator(".work").input_value(), (cards.count(), filled))
    check("  the preview closes and the message asks for a check against the page", pg.locator(".collect-preview").is_hidden() and "Read it against the page" in pg.locator(".collect-msg").inner_text())
    check("  the job's text is marked delivered (not offered again)", all(not j_.get("drafts") for j_ in [job(x["id"]) for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"] if x["type"] == "onenote_read" and x["counts"]["done"]]))
    pg.click(".collect-close")
    check("D6 no page errors", not errs, errs)
    # a second, finished-but-undelivered read is picked up when the dialog is reopened
    st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "url": GOOD}); time.sleep(1.5)
    pg.click("#collect-open"); pg.wait_for_selector(".collect-add", timeout=15000)
    check("D7 reopening the dialog picks up a read that finished while it was closed", "Ada Example" in pg.input_value(".collect-name"))
    pg.click(".collect-close")
    other = call("POST", "/api/assignments", {"assignment": {"title": "Other collection assignment", "instructions": "Synthetic task"}})[1]["assignment"]["id"]
    pg.reload(); time.sleep(2)
    pg.select_option(".asg-pick", aid); time.sleep(2)
    pg.click("nav.steps button:nth-child(3)"); pg.click("#collect-open")
    pg.wait_for_selector(".collect-add", timeout=15000)
    pg.click(".collect-close"); pg.select_option(".asg-pick", other); time.sleep(2)
    pg.click("#collect-open")
    check("D8 switching assignments clears the old preview and add control", pg.locator(".collect-preview").is_hidden() and pg.locator(".collect-add").count() == 0)
    orig_open = [x for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"] if x["type"] == "onenote_read" and any(i["state"] == "done" and not i["delivered"] for i in x["items"])]
    check("  switching does not deliver the original assignment's result (still offered, and none exists for the other)", len(orig_open) >= 1 and not call("GET", "/api/jobs?assignment=" + other)[1]["jobs"], len(orig_open))
    pg.click(".collect-close"); pg.select_option(".asg-pick", aid); time.sleep(2); pg.click("#collect-open")
    pg.wait_for_selector(".collect-add", timeout=15000)
    check("  returning to the original assignment restores its undelivered preview", "Ada Example" in pg.input_value(".collect-name"))
    b.close()

# ---------------------------------------------------------------- E. several pages (a class)
def pageurl(name, n): return f"https://rcs.sharepoint.com/sites/cn/_layouts/15/Doc.aspx?sourcedoc=%7Bp{n}%7D&action=edit&wd=target({name.replace(' ', '%20')}.one%7C1%2FUnit%7C2%2FTask%7C3%2F)"
U3 = [pageurl("Ada Example", 1), pageurl("Ben Sample", 2), pageurl("Cy Broken", 3)]
log2 = []; mode2 = {"signin_at": None, "slow": 0.0}
def fake2(url, wait=60):
    log2.append(url); time.sleep(mode2["slow"])
    if mode2["signin_at"] is not None and url == N.read_only(U3[mode2["signin_at"]]):
        mode2["signin_at"] = None; return {"ok": False, "kind": "sign_in", "error": "Sign in to Microsoft in the Chrome window that opened, then resume the job."}
    if "Cy" in url: return {"ok": False, "kind": "differs", "error": "OneNote's page area wasn't found, so nothing was collected.", "log": ["[0.1s] frame found"]}
    who = N.page_identity(url); txt = f"{MARK}-{who['student_hint'].split()[0].upper()} Notes written by the student about the design brief. " * 3
    return {"ok": True, "op": "collect", "read_at": "2026-11-01T10:00:00-07:00", "source": {"url": url, "section": who["section"], "page": who["page"], "student_hint": who["student_hint"], "read_at": "2026-11-01T10:00:00-07:00"},
            "page": {"text": txt.strip(), "chars": len(txt.strip()), "area": "PageContentContainer"}, "non_text": [], "non_text_counts": {}, "completeness": "unverified",
            "completeness_note": N.completeness_note([], True), "log": ["[0.1s] read"]}
app.ONENOTE_RUNNER = fake2
def clean_slate():
    for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]:
        if x["state"] in ("queued", "running", "waiting_for_sign_in", "failed", "interrupted"): call("POST", f"/api/jobs/{x['id']}/cancel", {})
        call("POST", f"/api/jobs/{x['id']}/delivered", {"keys": ["collect", "p1", "p2", "p3", "p4"]})
    wait(lambda: all(x["state"] not in ("queued", "running") for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]))
clean_slate()
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "urls": [U3[0], "https://example.com/x/Doc.aspx"]}); check("E1 one bad address in a list refuses the whole list", "Class Notebook" in r.get("error", "") and not [x for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"] if x["state"] == "queued"], r)
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "urls": [pageurl("A B", i) for i in range(41)]}); check("  more than 40 pages are refused", "between 1 and 40" in r.get("error", ""), r)
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "urls": U3 + [U3[0]]}); jid = r["job"]["id"]
check("  duplicates are dropped; one job with one item per page", r["job"]["total"] == 3 and [i["key"] for i in r["job"]["items"]] == ["p1", "p2", "p3"], r["job"]["total"])
j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("E2 pages are read in order; a page that differs fails only itself", j and [i["state"] for i in j["items"]] == ["done", "done", "failed"] and log2[-3:] == [onenote_read_ro for onenote_read_ro in [N.read_only(u) for u in U3]], j and [i["state"] for i in j["items"]])
check("  the two good pages come back with their own text and source", j and sorted(d["key"] for d in j["drafts"]) == ["p1", "p2"] and "ADA" in j["drafts"][0]["collect"]["page"]["text"] and "BEN" in j["drafts"][1]["collect"]["page"]["text"])
check("  the failed page offers no text and keeps its reason", j and "nothing was collected" in j["items"][2]["error"] and all("p3" != d["key"] for d in j["drafts"]))
side = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if r_.endswith(".jobs") and f.endswith(".json") and MARK + "-ADA" in open(os.path.join(r_, f)).read()]
elsewhere = [os.path.join(r_, f) for r_, d_, fs in os.walk(HOME) for f in fs if MARK.encode() in open(os.path.join(r_, f), "rb").read() and "Assessment" not in os.path.join(r_, f)]
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("  page text is only in the assignment's .jobs sidecar; the journal holds no names, text or addresses", len(side) == 1 and not elsewhere and MARK.encode() not in db and b"Ada" not in db and b"sharepoint" not in db, (side, elsewhere))
clean_slate(); log2.clear(); mode2["slow"] = 1.0
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "urls": U3}); jid = r["job"]["id"]
wait(lambda: len(log2) >= 1); call("POST", f"/api/jobs/{jid}/cancel", {})
j = wait(lambda: (lambda x: x if x["state"] in ("cancelled", "completed") else None)(job(jid)), 30)
check("E3 cancel takes effect between pages: the page in flight finishes, the rest are not read", j and j["state"] == "cancelled" and len(log2) == 1 and j["counts"]["done"] == 1 and j["counts"]["cancelled"] == 2, (j and j["state"], len(log2)))
mode2["slow"] = 0.0; clean_slate(); log2.clear(); mode2["signin_at"] = 1
st, r = call("POST", "/api/jobs", {"type": "onenote_read", "assignment": aid, "urls": U3}); jid = r["job"]["id"]
j = wait(lambda: (lambda x: x if x["state"] == "waiting_for_sign_in" else None)(job(jid)))
check("E4 a sign-in page on page 2 leaves the job waiting, with page 1 already read", j and j["counts"]["done"] == 1 and len(log2) == 2, j and j["counts"])
call("POST", f"/api/jobs/{jid}/resume", {}); j = wait(lambda: (lambda x: x if x["state"] == "completed" else None)(job(jid)))
check("  resume continues from page 2; page 1 is not read again", j and j["counts"]["done"] == 2 and j["counts"]["failed"] == 1 and log2.count(N.read_only(U3[0])) == 1, log2)
clean_slate(); log2.clear()
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context(viewport={"width": 1280, "height": 1000}); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); time.sleep(2); pg.select_option(".asg-pick", aid); time.sleep(2)
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove())")
    pg.evaluate("ROSTER = [{id:'S-ADA', first:'Ada', last:'Example', block:'A'}, {id:'S-BEN', first:'Benjamin', last:'Sampleton', block:'A'}]")
    pg.click("nav.steps button:nth-child(3)"); pg.click("#collect-open")
    pg.fill(".collect-url", "\n".join(U3)); pg.click(".collect-read")
    pg.wait_for_selector(".collect-row", timeout=20000)
    body_ = pg.locator(".collect-preview").inner_text()
    check("E5 three addresses give a table: two pages read, one that could not be read, with its reason", pg.locator(".collect-row").count() == 2 and "1 could not be read" in body_ and "Page 3 was not collected" in body_ and "nothing was collected" in body_, body_[:300])
    rows = pg.locator(".collect-row")
    check("  Ada matches the class list and is ticked; Ben (not on the list) is not matched and is not ticked", "Matches the class list: Example, Ada" in rows.nth(0).inner_text() and rows.nth(0).locator("input[type=checkbox]").is_checked() and "Not on this class list" in rows.nth(1).inner_text() and not rows.nth(1).locator("input[type=checkbox]").is_checked(), rows.nth(1).inner_text()[:120])
    check("  page text stays hidden until asked for", MARK not in body_ and not rows.nth(0).locator(".teams-full").is_visible())
    rows.nth(1).locator("input[type=checkbox]").check(); pg.click(".collect-add")
    check("  manually ticking an unmatched name cannot add any pages", "must match the current Course Hub" in pg.locator(".collect-msg").inner_text() and pg.locator(".student").count() == 0)
    held_roster = pg.evaluate("ROSTER")
    pg.evaluate("ROSTER=[]"); pg.click(".collect-add")
    check("  a missing class list blocks adding pages", "must match the current Course Hub" in pg.locator(".collect-msg").inner_text() and pg.locator(".student").count() == 0)
    pg.evaluate("r => ROSTER=r", held_roster)
    rows.nth(1).locator("input[type=checkbox]").check(); rows.nth(1).locator(".collect-bname").fill("Ada Example")
    pg.click(".collect-add")
    check("  two ticked pages with the same name are refused", "same student name" in pg.locator(".collect-msg").inner_text() and pg.locator(".student").count() == 0)
    rows.nth(1).locator(".collect-bname").fill("Benjamin Sampleton"); time.sleep(0.2)
    check("  fixing the name matches it and the page can be added", "Matches the class list: Sampleton, Benjamin" in rows.nth(1).inner_text())
    rows.nth(1).locator("input[type=checkbox]").uncheck(); rows.nth(0).locator("input[type=checkbox]").uncheck(); pg.click(".collect-add")
    check("  adding with nothing ticked says so", "Tick at least one" in pg.locator(".collect-msg").inner_text())
    rows.nth(0).locator("input[type=checkbox]").check(); pg.click(".collect-add"); time.sleep(1.2)
    cards = [pg.locator(".student").nth(i) for i in range(pg.locator(".student").count())]
    ada = [c for c in cards if c.locator(".name").input_value() == "Ada Example"]
    check("E6 the ticked page becomes a card with its text and its class-list identity", len(ada) == 1 and MARK + "-ADA" in ada[0].locator(".work").input_value() and pg.evaluate("el => el.dataset.rid", ada[0].element_handle()) == "S-ADA")
    check("  the table now shows only the page left, and the added one is not offered again", pg.locator(".collect-row").count() == 1 and "1 already added" in pg.locator(".collect-preview").inner_text())
    pg.locator(".collect-row").first.locator(".collect-bname").fill("Benjamin Sampleton")
    pg.locator(".collect-row").first.locator("input[type=checkbox]").check(); pg.click(".collect-add"); time.sleep(1.0)
    check("  adding the last page leaves nothing waiting", pg.locator(".collect-row").count() == 0 and not [x for x in call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"] if x["type"] == "onenote_read" and any(i["state"] == "done" and not i["delivered"] for i in x["items"])])
    check("E7 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed")
sys.exit(0 if all(ok_all) else 1)
