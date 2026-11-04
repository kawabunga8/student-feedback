"""The Teams and MySchool batch job handlers with stand-in engines (no browser, no network): what each student is recorded as when a
run goes well, stops part-way, is cancelled, loses its approval, or ends with an uncertain outcome."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, teams_post

ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:230]) if extra != "" else ""))

APPROVED = {"x": 1}
app.teams_approved = lambda aid, sid: APPROVED
app.teams_destination = lambda rec: DEST
app.load_assignment_record = lambda aid: {}
app.approved_for_posting = lambda aid, destination=None: [{"student_id": s, "k": 1} for s in ("s1", "s2", "s3")]
app._bd = lambda st: "sha-ok"
DEST = {"class": "C", "title": "T", "source": {}}
SHA = teams_post.digest(APPROVED)

class Q:
    def __init__(self, cancel=False): self.items, self.results, self.cancel = {}, {}, cancel
    def request_of(self, job): return {"request": job["req"]}
    def cancel_requested(self, jid): return self.cancel
    def item_finished(self, job, idx, key, state, error="", result=None): self.items[key] = (state, error); self.results[key] = result
def teams_job():
    req = {"mode": "save", "class": "C", "title": "T", "source": {}, "destination": DEST,
           "students": [{"student_id": s, "target_name": s.upper(), "feedback": "fb " + s, "approval_sha": SHA, "preview_existing": ""} for s in ("s1", "s2", "s3")]}
    return {"id": "j", "assignment": "a", "req": req, "items": [{"idx": i, "key": s} for i, s in enumerate(("s1", "s2", "s3"))]}
def run_teams(runner, cancel=False):
    q = Q(cancel); app.TEAMS_BATCH_RUNNER = runner; app._run_teams_batch_job(q, teams_job()); return q

# ---- Teams
q = run_teams(lambda req, current, item, jid, queue: (current("s1"), item({"student_id": "s1", "verified": True}), current("s2"), item({"student_id": "s2", "verified": True}),
                                                      current("s3"), item({"student_id": "s3", "verified": True}), "")[-1])
check("A1 a clean run: every student done, with the approval and text they were posted with", all(q.items[s][0] == "done" for s in ("s1", "s2", "s3")) and
      q.results["s1"]["teams_batch"]["approval_sha"] == SHA and q.results["s1"]["teams_batch"]["feedback"] == "fb s1", q.items)
def partial(req, current, item, jid, queue):
    item({"student_id": "s1", "verified": True})
    item({"student_id": "s2", "error": "Return may have run, but the roster does not list this student under Returned. Check Teams before trying again."})
    return "Return may have run, but the roster does not list this student under Returned. Check Teams before trying again."
q = run_teams(partial)
check("A2 partial success: the first is done, the uncertain one is failed with its warning", q.items["s1"][0] == "done" and q.items["s2"][0] == "failed" and "may have run" in q.items["s2"][1], q.items)
check("  the student after it is NOT told a post 'may have run'; they are told nothing was done", q.items["s3"][0] == "failed" and "may have run" not in q.items["s3"][1] and "Nothing was done" in q.items["s3"][1], q.items["s3"])
q = run_teams(lambda *a: "Sign in to Microsoft in the Chrome window.")
check("A3 a run that fails before any student keeps its reason for everyone", all(q.items[s][0] == "failed" and "Sign in" in q.items[s][1] for s in ("s1", "s2", "s3")), q.items)
def cancelled(req, current, item, jid, queue):
    try: current("s1")
    except teams_post.PilotError as e: item({"student_id": "s1", "error": str(e)})
    return str("cancelled")
q = run_teams(cancelled, cancel=True)
check("A4 cancelled before writing: authorization is refused and nothing is marked done", all(q.items[s][0] == "failed" for s in q.items) and "cancelled" in q.items["s1"][1], q.items)
APPROVED = {"x": 2}
def changed(req, current, item, jid, queue):
    try: current("s1"); item({"student_id": "s1", "verified": True})
    except teams_post.PilotError as e: item({"student_id": "s1", "error": str(e)})
    return ""
q = run_teams(changed)
check("A5 an approval edited after the preview is refused at the moment of writing", q.items["s1"][0] == "failed" and "approval" in q.items["s1"][1], q.items["s1"])
APPROVED = {"x": 1}
q = run_teams(lambda req, current, item, jid, queue: (item({"student_id": "s1", "verified": True}), item({"student_id": "s1", "error": "late"}), item({"student_id": "zz", "verified": True}), "")[-1])
check("A6 a student is recorded once; an unknown student is ignored", q.items["s1"][0] == "done" and "zz" not in q.items, q.items)

# ---- MySchool
def ms_job():
    req = {"mode": "save", "url": "u", "mark_graded": False, "students": [{"student_id": s, "approval_sha": "sha-ok", "comment": "c"} for s in ("s1", "s2", "s3")]}
    return {"id": "j", "assignment": "a", "req": req, "items": [{"idx": i, "key": s} for i, s in enumerate(("s1", "s2", "s3"))]}
def run_ms(runner, cancel=False):
    q = Q(cancel); app.MYSCHOOL_BATCH_RUNNER = runner; app._run_myschool_batch_job(q, ms_job()); return q
def ms_partial(req, current, item, jid, queue, header):
    current("s1"); item({"student_id": "s1", "verified": True})
    item({"student_id": "s2", "error": "Save may have run, but MySchool could not be read back to confirm it. Check MySchool before trying again."})
    return "Save may have run, but MySchool could not be read back to confirm it. Check MySchool before trying again."
q = run_ms(ms_partial)
check("B1 MySchool partial: verified student done, uncertain one failed with its warning, the rest told nothing was done",
      q.items["s1"][0] == "done" and "may have run" in q.items["s2"][1] and "may have run" not in q.items["s3"][1] and "Nothing was done" in q.items["s3"][1], q.items)
check("  the done record carries the approval it was saved with", q.results["s1"]["myschool_batch"]["approval_sha"] == "sha-ok")
app._bd = lambda st: "sha-changed"
def ms_changed(req, current, item, jid, queue, header):
    try: current("s1")
    except Exception as e: item({"student_id": "s1", "error": str(e)})
    return ""
q = run_ms(ms_changed)
check("B2 MySchool approval changed since the preview: refused", q.items["s1"][0] == "failed" and "approval changed" in q.items["s1"][1], q.items["s1"])

print(f"\n{sum(ok_all)}/{len(ok_all)} passed")
sys.exit(0 if all(ok_all) else 1)
