"""A saved folder that no longer matches the assignment's year/term/course is reported and can be moved.
Everything runs in a temporary HOME with invented data; nothing contacts Course Hub, Teams or a browser."""
import os, sys, tempfile
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, jobs, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

app.APP_DATA.mkdir(parents=True, exist_ok=True); app.ASSIGNMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.QUEUE = jobs.JobQueue(app.APP_DATA / "jobs.sqlite", {"onenote_read": lambda q, j: None}, lambda r: app.session_folder_for(r)[1], app._atomic_write_json, app._read_json)
rec = app.save_assignment_record({"title": "Stage 1", "term": "Q1", "course": {"name": "ICT 9 (Q1)", "label": "ICT 9 (Q1)", "schoolYear": "2026-27"}})
aid = rec["id"]
app.save_session(aid, [{"student_id": "s1", "name": "Ada Test", "work": "w"}], None)
s = app.load_session(aid)
check("1 a folder that matches its record is not flagged", s["folderCheck"] is None, s["path"])
old_rel = s["path"]

rec = app.save_assignment_record({**app.load_assignment_record(aid), "course": {"name": "CS10 (Q1/Q2)", "label": "CS10 (Q1/Q2)", "schoolYear": "2026-27"}}, rec["version"])
s = app.load_session(aid)
check("2 after the course changes, the old folder is flagged with have and want", s["folderCheck"] == {"have": "2026-27/Q1/ICT 9 (Q1)", "want": "2026-27/Q1/CS10 (Q1 Q2)"}, s["folderCheck"])

# a job sidecar must move with the folder
j = app.QUEUE.enqueue("onenote_read", aid, old_rel, {"url": "x"}, [{"key": "collect", "work_sha": ""}])
try: app.move_session(aid); blocked = False
except ValueError: blocked = True
check("3a a move is refused while a job for the assignment is active", blocked and (app.ASSESSMENT / old_rel).exists())
with app.QUEUE._db() as c: c.execute("UPDATE jobs SET state='completed'")
out = app.move_session(aid)
check("3 the move reports the new path and the old folder is gone", out["moved"] and out["path"] == "2026-27/Q1/CS10 (Q1 Q2)/" + old_rel.split("/")[-1] and not (app.ASSESSMENT / old_rel).exists(), out)
s = app.load_session(aid)
check("4 the students come back from the new folder and nothing is flagged", s["folderCheck"] is None and [x["name"] for x in s["session"]["students"]] == ["Ada Test"])
check("5 the job record follows (journal and sidecar)", app.QUEUE.get(j["id"])["folder"] == out["path"] and (app.ASSESSMENT / out["path"] / ".jobs" / (j["id"] + ".json")).exists())
check("6 moving again does nothing", app.move_session(aid)["moved"] is False)

# a busy job and an existing target are refused
rec2 = app.save_assignment_record({"title": "Other", "term": "Q1", "course": {"name": "ICT 9 (Q1)", "label": "ICT 9 (Q1)", "schoolYear": "2026-27"}})
app.save_session(rec2["id"], [{"student_id": "s2", "name": "Bo Test", "work": "w"}], None)
r2 = app.save_assignment_record({**app.load_assignment_record(rec2["id"]), "course": {"name": "CS10 (Q1/Q2)", "label": "CS10 (Q1/Q2)", "schoolYear": "2026-27"}}, rec2["version"])
rel2 = app.load_session(rec2["id"])["path"]
(app.ASSESSMENT / "2026-27/Q1/CS10 (Q1 Q2)" / rel2.split("/")[-1]).mkdir(parents=True)
try: app.move_session(rec2["id"]); refused = False
except ValueError as e: refused = "already exists" in str(e)
check("7 an existing target folder is refused and nothing moves", refused and (app.ASSESSMENT / rel2).exists())
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
