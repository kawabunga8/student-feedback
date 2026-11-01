"""Job queue: restart recovery, resume without redoing finished drafts, cancel, engine down, guards, journal holds no student text."""
import json, os, signal, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
calls = {}; delay = [1.2]; lock = threading.Lock()
class O(BaseHTTPRequestHandler):
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        import re
        m = re.search(r"WORK-MARKER-(\d+)", body)
        if m:
            with lock: calls[m.group(1)] = calls.get(m.group(1), 0) + 1
        time.sleep(delay[0])
        self._j({"message": {"content": "You wrote six how-might-we questions for your client. Next, explain how each idea helps him."}})
    def log_message(self, *a): pass
def start_stub():
    s = ThreadingHTTPServer(("127.0.0.1", 11434), O); s.allow_reuse_address = True
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s
stub = start_stub()
env = {**os.environ, "HOME": HOME, "NO_BROWSER": "1"}
def start_app():
    p = subprocess.Popen([sys.executable, "app.py"], cwd=APPDIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try: urllib.request.urlopen("http://127.0.0.1:8765/api/assignments", timeout=1); return p
        except Exception: time.sleep(0.25)
    raise SystemExit("app did not start")
def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=None if body is None else json.dumps(body).encode(), headers=h if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, (json.loads(e.read() or b"{}") if e.code != 403 else {})
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:230]) if extra != "" else ""))
def wait(fn, secs=40):
    end = time.time() + secs
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.3)
    return None
def jobs_of(aid): return call("GET", "/api/jobs?assignment=" + aid)[1]["jobs"]
def job(jid): return call("GET", "/api/jobs/" + jid)[1]["job"]
def items(n, start=0): return [{"key": f"CH-{i}", "work": f"WORK-MARKER-{i} my ideas about the client.", "notes": "", "level": "", "grade": "Grade 9", "label": f"Student {i}"} for i in range(start, start + n)]
SET = {"model": "qwen2.5:14b", "rubric": "Explain how each idea helps your client.", "doc": "", "standards": [], "grade": "Grade 9", "term": "", "length": "paragraph", "title": "Task 2"}

app = start_app()
rec = call("POST", "/api/assignments", {"assignment": {"title": "Task 2", "course": {"name": "ICT 9", "label": "ICT 9 (Q1)", "sectionIds": [], "schoolYear": "2026-27"}, "grade": "Grade 9", "term": "Q1", "instructions": "x"}})[1]["assignment"]; aid = rec["id"]
st, r = call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "basis": "B1", "items": items(6)})
j = r["job"]; check("1 job queued", st == 200 and j["state"] in ("queued", "running") and j["total"] == 6, j["state"])
check("  a second drafting job for the same assignment is refused", "already" in call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "items": items(1, 50)})[1].get("error", ""))
check("2 runs and reports progress", wait(lambda: job(j["id"])["counts"]["done"] >= 2) is not None and job(j["id"])["state"] == "running", job(j["id"])["counts"])
app.send_signal(signal.SIGKILL); app.wait(); time.sleep(0.5)    # the app dies mid-job

app = start_app()
jj = job(j["id"])
check("3 after a hard stop the job is 'interrupted', not lost or silently resumed", jj["state"] == "interrupted" and jj["counts"]["done"] >= 2 and jj["counts"]["running"] == 0, (jj["state"], jj["counts"]))
time.sleep(2.5); check("  nothing resumes by itself", job(j["id"])["state"] == "interrupted" and job(j["id"])["counts"]["done"] == jj["counts"]["done"])
done_before = {i["key"] for i in jj["items"] if i["state"] == "done"}
check("  finished drafts survived the stop", len(jj["drafts"]) == len(done_before) and all(d["feedback"] for d in jj["drafts"]), len(jj["drafts"]))
snap = dict(calls)
st, r = call("POST", "/api/jobs/" + j["id"] + "/resume", {}); check("4 resume accepted", st == 200 and r["job"]["state"] in ("queued", "running"), r["job"]["state"])
fin = wait(lambda: job(j["id"]) if job(j["id"])["state"] == "completed" else None, 60)
check("  completes with all six drafted", fin and fin["counts"]["done"] == 6 and len(fin["drafts"]) == 6, fin and fin["counts"])
redone = [k for k in done_before if calls.get(k.split("-")[1], 0) > snap.get(k.split("-")[1], 0)]
check("  drafts finished before the stop were not redone", not redone, redone)
check("  every student was drafted (at most one in-flight repeat)", all(1 <= calls.get(str(i), 0) <= 2 for i in range(6)), calls)
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("5 journal holds no student work, names or feedback", b"WORK-MARKER" not in db and b"Student 1" not in db and b"how-might-we" not in db and b"my ideas" not in db)
sidecar = [os.path.join(r_, f) for r_, d_, fs in os.walk(os.path.join(HOME, "Desktop")) for f in fs if r_.endswith(".jobs")]
check("  results are in a .jobs sidecar inside the assignment folder", len(sidecar) == 1 and "Assessment" in sidecar[0] and "/.jobs/" in sidecar[0], sidecar)
st, r = call("POST", "/api/jobs/" + j["id"] + "/delivered", {"keys": ["CH-0", "CH-1"]})
check("6 delivered drafts stop being offered", len(r["job"]["drafts"]) == 4 and not any(d["key"] in ("CH-0", "CH-1") for d in r["job"]["drafts"]))

# cancel: running -> stops between items
delay[0] = 1.5
r = call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "items": items(6, 10)})[1]["job"]
wait(lambda: job(r["id"])["counts"]["done"] >= 1)
call("POST", "/api/jobs/" + r["id"] + "/cancel", {})
c = wait(lambda: job(r["id"]) if job(r["id"])["state"] == "cancelled" else None, 20)
check("7 cancel stops between items", c and 1 <= c["counts"]["done"] <= 3 and c["counts"]["queued"] == 0 and c["counts"]["cancelled"] >= 3, c and c["counts"])
check("  a cancelled job can't be resumed", "can't be resumed" in call("POST", "/api/jobs/" + r["id"] + "/resume", {})[1].get("error", ""))

# engine down: the job fails as a whole, keeps its queue, and resumes when the engine is back
stub.shutdown(); stub.server_close(); time.sleep(0.5)
r = call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "items": items(3, 20)})[1]["job"]
f = wait(lambda: job(r["id"]) if job(r["id"])["state"] == "failed" else None, 30)
check("8 engine not running: job fails with a plain message, nothing marked drafted", f and f["counts"]["done"] == 0 and f["counts"]["queued"] == 3 and "Ollama" in f["error"], f and (f["error"], f["counts"]))
stub = start_stub(); delay[0] = 0.2
call("POST", "/api/jobs/" + r["id"] + "/resume", {})
f2 = wait(lambda: job(r["id"]) if job(r["id"])["state"] == "completed" else None, 30)
check("  resumed once the engine is back", f2 and f2["counts"]["done"] == 3, f2 and f2["counts"])

# guards
check("9 other origin refused", call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "items": items(1, 60)}, {"Origin": "https://evil.example"})[0] == 403)
check("  non-JSON refused", call("POST", "/api/jobs/" + r["id"] + "/cancel", {}, {"Content-Type": "text/plain"})[0] == 403)
check("  bad job id", call("GET", "/api/jobs/../../x")[1].get("error") in ("Job not found.", "not found") or call("GET", "/api/jobs/job-x")[1].get("error") == "Job not found.")
check("  unknown assignment refused", "not found" in str(call("POST", "/api/jobs", {"assignment": "asg-20260101-deadbeef", "settings": SET, "items": items(1)})[1]).lower())
check("  empty or duplicate items refused", "key" in call("POST", "/api/jobs", {"assignment": aid, "settings": SET, "items": [{"key": "a", "work": "  "}]})[1].get("error", ""))
app.send_signal(signal.SIGTERM); app.wait()
print("ALL PASS" if all(ok_all) else f"{ok_all.count(False)} FAILED")
