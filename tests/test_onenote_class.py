"""Whole-class OneNote collection (title guessing). No network, no browser, no real notebook:
  A. candidate titles, notebook address, title comparison;
  B. the job handler with a stand-in reader: found students are saved as done, others fail with how many titles were tried,
     a sign-in request leaves the job waiting, and nothing is invented for students the reader did not report."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, jobs, teams_read as T, onenote_class as C

ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))

BASE = "https://rcs.sharepoint.com/sites/cn/_layouts/15/Doc.aspx?sourcedoc=%7Babc-123%7D&action=edit&wd=target(x)"

# ---- A
t = C.candidate_titles("Task 3: Prototype & Test")
check("A1 the assignment title comes first, then the short forms students usually write (Task 3, Task three)", t[0] == "Task 3: Prototype & Test" and t[1:3] == ["Task 3", "Stage 3"] and "Task three" in t[:8], t[:8])
check("  every one of those is within the per-student try limit", all(x in t[:C.MAX_TRIES] for x in ("Task 3", "Task three", "Stage 3", "Prototype & Test")), t[:C.MAX_TRIES])
check("  'and' and '&' spellings are both offered", "Prototype and Test" in t and "Stage 3 - Prototype & Test" in t)
check("  the bare number is still offered", "3" in t and "three" in t)
check("  no duplicates, ignoring case", len({x.lower() for x in t}) == len(t))
check("A2 a title with no 'Task N' prefix is tried as given", C.candidate_titles("Poster design") == ["Poster design"])
u = C.page_url(BASE, "Rihanna Lan", "Homework", "Define and ideate")
check("A3 address: view mode, notebook id kept, student/section/page in wd=target(...)",
      "action=view" in u and "action=edit" not in u and "sourcedoc=%7Babc-123%7D" in u.replace("{", "%7B").replace("}", "%7D") and
      u.endswith("wd=target(Rihanna%20Lan/Homework.one|/Define%20and%20ideate|/)"), u)
try: C.page_url("https://rcs.sharepoint.com/sites/cn/_layouts/15/Doc.aspx?action=view", "A B", "Homework", "T"); got = "accepted"
except T.ReadError as e: got = e.kind
check("A4 an address without a notebook id is refused", got == "differs", got)
check("A5 'Define & Ideate' counts as the title 'define and ideate'", C.norm_tokens("Define & Ideate") == C.norm_tokens("define and ideate"))
check("  a different page does not", C.norm_tokens("canva") != C.norm_tokens("Define and ideate"))

# ---- A6: whose page really opened (the address OneNote rewrites to once it has opened a page)
RES = "https://rcs.sharepoint.com/sites/cn/_layouts/15/Doc.aspx?sourcedoc=%7Babc-123%7D&wd=target%28{}%29"
def resolved(student, page="Task%203"): return RES.format(student + "%2FHomework.one%7Cs1%2F" + page + "%7Cp1%2F")
check("A6 an opened page reports its student, section and page", C.resolved_identity(resolved("Alex%20Example")) == {"student": "Alex Example", "section": "Homework", "page": "Task 3"})
check("  the address as asked for (no ids yet) proves nothing", C.resolved_identity(C.page_url(BASE, "Alex Example", "Homework", "Task 3")) is None)
check("  a notebook-level fallback page (Welcome) has no student", C.resolved_identity(RES.format("Welcome.one%7Cw1%2FWelcome%7Cw2%2F")) is None)

class FakePage:
    """OneNote as the automated browser sees it. A student with no section silently gets the previous student's page."""
    def __init__(self, sections, fallback_last=True): self.url = "https://rcs.sharepoint.com/"; self.sections = sections; self.last = None; self.fallback_last = fallback_last
    def goto(self, url, wait_until=None):
        who = urllib.parse.unquote(url.split("wd=target(")[1].split("/")[0])
        self.last = who if who in self.sections else (self.last if self.fallback_last else None)
        self.url = resolved(urllib.parse.quote(self.last, safe="")) if self.last else RES.format("Welcome.one%7Cw1%2FWelcome%7Cw2%2F")
    def wait_for_timeout(self, ms): pass
class FakeCtx:
    def __init__(self, page): self.pages = [page]
    def close(self): pass
class FakeLock:
    def __enter__(self): return self
    def __exit__(self, *a): return False
import types, urllib.parse
def run_fake(page, students):
    fake_api = types.ModuleType("playwright.sync_api")
    class _P:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    fake_api.sync_playwright = lambda: _P()
    saved = (sys.modules.get("playwright"), sys.modules.get("playwright.sync_api"), T.BrowserLock, T._launch, C.O.read_loaded)
    sys.modules["playwright"] = types.ModuleType("playwright"); sys.modules["playwright.sync_api"] = fake_api
    T.BrowserLock = FakeLock; T._launch = lambda p: FakeCtx(page)
    C.O.read_loaded = lambda pg, url, who, note, wait=60: {"page": {"text": "Task 3\nwork of " + str(pg.last), "chars": 20}, "source": {"student_hint": who["student_hint"]}}
    got = {}
    try:
        C.run_class({"base": BASE, "titles": ["Task 3"], "sections": ["Homework"], "students": students}, lambda m: got.__setitem__(m["item"]["key"], m["item"]))
    finally:
        T.BrowserLock, T._launch, C.O.read_loaded = saved[2:]
        for k, v in (("playwright", saved[0]), ("playwright.sync_api", saved[1])):
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
    return got
two = [{"key": "a", "name": "Alex Example"}, {"key": "b", "name": "Blair Example"}]
got = run_fake(FakePage({"Alex Example"}), two)
check("A7 a student with no section is NOT given the previous student's page (title matches, student doesn't)", got["a"]["found"] and not got["b"]["found"], got)
check("  and the wrong page is not tried again for every title", got["b"]["tried"] == 1, got["b"])
check("  the found page names the student it really came from", got["a"]["page"]["source"]["student_hint"] == "Alex Example", got["a"])
got = run_fake(FakePage({"Alex Example", "Blair Example"}), two)
check("A8 two students who both have the page are both found", got["a"]["found"] and got["b"]["found"], got)

# ---- A9: choosing among a student's real pages
# A9
T2 = ["Task 2: Define & Ideate", "Task 2", "Stage 2"]
check("  exact title wins", C.pick_page(["canva", "Task 2: Define and Ideate", "Stage 2"], T2) == ("Task 2: Define and Ideate", ""))
check("  'Stage 2- Ideate', '2.Brainstorm', 'ICT Part 2- Define' are found when only one fits", all(C.pick_page(["x", w], T2)[0] == w for w in ("Stage 2- Ideate", "2.Brainstorm", "ICT Part 2- Define", "Task two notes")))
check("  two possible pages are never guessed between", C.pick_page(["Stage 2 a", "2. b"], T2)[0] is None)
check("  a student with nothing for it gets no page", C.pick_page(["Michaela's app", "Untitled Page", "Task three"], T2)[0] is None)
check("  Task 3 is not mistaken for Task 2 or 30", C.pick_page(["Task 30", "Stage 3"], T2)[0] is None)

# ---- B
class Q:
    def __init__(self): self.items = {}; self.results = {}; self.queue = ["s1", "s2", "s3"]; self.cancel = False
    def request_of(self, job): return {"request": {"base": BASE, "titles": ["Task 3"], "sections": ["Homework"],
                                                   "students": [{"key": "s1", "name": "Ada Example"}, {"key": "s2", "name": "Ben Test"}, {"key": "s3", "name": "Cy Nobody"}]}}
    def cancel_requested(self, jid): return self.cancel
    def next_item(self, jid): return {"idx": int(self.queue[0][1:]), "key": self.queue.pop(0)} if self.queue else None
    def item_finished(self, job, idx, key, state, error="", result=None): self.items[key] = (state, error); self.results[key] = result
job = {"id": "j1"}
seen = []
def fake(req, item):
    seen.append(req)
    item({"key": "s1", "found": True, "section": "Homework", "title": "Task 3", "tried": 1, "page": {"op": "collect", "page": {"text": "work", "chars": 4}}})
    item({"key": "s2", "found": False, "tried": 20})
    item({"key": "zz", "found": True, "title": "x", "tried": 1, "page": {}})          # not a student of this job: ignored
    return {}
app.ONENOTE_CLASS_RUNNER = fake
q = Q(); app._run_onenote_class_job(q, job)
check("B1 one reader run gets all three students", len(seen) == 1 and [s["name"] for s in seen[0]["students"]] == ["Ada Example", "Ben Test", "Cy Nobody"])
check("B2 a found student is done with the page in the result", q.items["s1"][0] == "done" and q.results["s1"]["collect"]["page"]["text"] == "work" and q.results["s1"]["collect"]["title"] == "Task 3")
check("B3 a student not found fails and says who and how many titles were tried", q.items["s2"][0] == "failed" and "Ben Test" in q.items["s2"][1] and "20" in q.items["s2"][1], q.items["s2"])
check("B4 a student the reader never reported is not marked finished, and an unknown key is ignored", "s3" not in q.items and "zz" not in q.items, list(q.items))
app.ONENOTE_CLASS_RUNNER = lambda req, item: {"kind": "sign_in", "error": "Sign in."}
try: app._run_onenote_class_job(Q(), job); got = "returned"
except jobs.NeedsSignIn: got = "sign_in"
check("B5 a sign-in request leaves the job waiting for the teacher", got == "sign_in", got)
app.ONENOTE_CLASS_RUNNER = lambda req, item: {"kind": "error", "error": "boom"}
try: app._run_onenote_class_job(Q(), job); got = "returned"
except jobs.JobFailed: got = "failed"
check("B6 any other reader failure fails the job (unfinished students stay queued)", got == "failed", got)
os.environ["SF_FORBID_BROWSER"] = "1"
check("B7 the real runner refuses to open a browser when tests forbid it", app.onenote_class_runner({}, lambda m: None).get("kind") == "setup")

print(f"\n{sum(ok_all)}/{len(ok_all)} passed")
sys.exit(0 if all(ok_all) else 1)
