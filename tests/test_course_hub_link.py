"""The Course Hub link: school-year rollover, refusal messages, finding a course by plain name, and course folder names.
A stand-in Course Hub on a random local port with invented courses and students; never contacts the real one."""
import json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, stage_submissions as S, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

QUARTERS = [{"id": 101, "label": "Q1", "start_date": "2026-09-08", "end_date": "2026-11-13", "school_year": "2026-27"},
            {"id": 102, "label": "Q2", "start_date": "2026-11-16", "end_date": "2027-01-28", "school_year": "2026-27"}]
COURSES = [{"id": "c-ict-q1", "name": "ICT 9", "block": "A", "grade_years": [9], "school_year": "2026-27", "type": "academic", "quarters": ["Q1"]},
           {"id": "c-ict-q2", "name": "ICT 9", "block": "B", "grade_years": [9], "school_year": "2026-27", "type": "academic", "quarters": ["Q2"]},
           {"id": "c-band", "name": "Band 10", "block": "C", "grade_years": [10], "school_year": "2026-27", "type": "academic", "quarters": []}]
ROSTERS = {"c-ict-q1": [{"id": "s1", "first_name": "Ada", "last_name": "Testwell", "email": "x@example.invalid", "gender": "F", "grade_year": 9}],
           "c-ict-q2": [{"id": "s2", "first_name": "Bo", "last_name": "Samplely", "email": "y@example.invalid", "gender": "M", "grade_year": 9}],
           "c-band": [{"id": "s3", "first_name": "Cy", "last_name": "Mockford", "email": None, "gender": None, "grade_year": 10}]}
hub = {"quarters": QUARTERS, "courses": COURSES, "fail": None, "retry": None}

class Hub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if hub["fail"]:
            self.send_response(hub["fail"])
            if hub["retry"]: self.send_header("Retry-After", hub["retry"])
            self.end_headers(); return
        p = self.path.split("?")[0]
        body = hub["quarters"] if p == "/api/quarters" else hub["courses"] if p == "/api/courses" else ROSTERS.get(p.split("/")[3], [])
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

srv = ThreadingHTTPServer(("127.0.0.1", 0), Hub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["COURSE_HUB_URL"] = f"http://127.0.0.1:{srv.server_port}"     # env wins over student-feedback's .env.local
os.environ["COURSE_HUB_API_KEY"] = "test-key-not-real"
app.CACHE = Path(HOME) / "courses.cache.json"                          # never the repo's real cache

def fresh():
    app._mem.update(at=0, data=None)
    return app.course_data()

# 3: school year and the new-year rollover
d = fresh()
check("1 a normal fetch is live, with the school year from the quarters", d["source"] == "live" and d["school_year"] == "2026-27" and len(d["courses"]) == 3, (d["source"], d.get("school_year")))
good_cache = app.CACHE.read_text()
hub["quarters"] = []
d = fresh()
check("2 quarters not entered yet: the school year comes from the courses (no 'not connected' state)", d["source"] == "live" and d["school_year"] == "2026-27", d.get("school_year"))
app.CACHE.write_text(good_cache)
hub.update(quarters=[{**QUARTERS[0], "school_year": "2027-28", "start_date": "2027-09-07", "end_date": "2027-11-12"}], courses=[])
d = fresh()
check("3 a new year with no courses yet keeps the last good copy and says why", d["source"] == "cache" and len(d["courses"]) == 3
      and "no courses for 2027-28 yet" in d["note"], d.get("note"))
check("4 the good cache file is not overwritten by the empty year", app.CACHE.read_text() == good_cache)
app.CACHE.unlink()
d = fresh()
check("5 with no cache either, the built-in list is used and the note explains", d["source"] == "file" and "no courses" in d["note"], d.get("note"))
hub.update(quarters=QUARTERS, courses=COURSES)

# 4: refusal messages
def note_for(code, retry=None):
    hub.update(fail=code, retry=retry); app.CACHE.unlink(missing_ok=True)
    n = fresh()["note"]; hub.update(fail=None, retry=None); return n
check("6 401 says the API key wasn't accepted and where it's set", "didn't accept" in note_for(401) and "COURSE_HUB_API_KEY" in note_for(401))
check("7 403 says the key isn't allowed to read that endpoint", "isn't allowed to read the quarters" in note_for(403))
n = note_for(429, "42")
check("8 429 explains the pause, that another app may cause it, and when to retry", "pausing" in n and "another app" in n and "42 seconds" in n, n)
check("9 500 says Course Hub had an internal error", "internal error" in note_for(500))
d = fresh()

# 4 and 5: finding a course for a class list
names = [c["name"] for c in d["courses"]]
check("10 same-named courses in different quarters are labelled apart on the page", "ICT 9 (Q1)" in names and "ICT 9 (Q2)" in names, names)
check("11 the class list is found by the page's label", [s["id"] for s in app.roster_for("ICT 9 (Q1)", "1")] == ["s1"])
check("12 ...and by the plain name, using the quarter to choose", [s["id"] for s in app.roster_for("ICT 9", "2")] == ["s2"])
check("13 the class list never carries email or gender", all(set(s) == {"id", "first", "last", "grade", "grade_year_reference", "block"} for s in app.roster_for("ICT 9", "2")))
def err(*a):
    try: app.roster_for(*a); return ""
    except RuntimeError as e: return str(e)
check("14 the plain name without a quarter asks which course", "could be ICT 9 (Q1) or ICT 9 (Q2)" in err("ICT 9", ""), err("ICT 9", ""))
check("15 an unknown course says it isn't in the list for that year (not 'needs live data')", err("Chemistry 11", "1") == "“Chemistry 11” isn't in Course Hub's course list for 2026-27", err("Chemistry 11", "1"))
check("16 a full-year course is found by name in any quarter", [s["id"] for s in app.roster_for("Band 10", "2")] == ["s3"])

# 5: folder names
check("17 staged folders drop the quarter suffix", S.staged_path("2026-27", "1", "ICT 9 (Q1)", "Task 2").parts[-4:] == ("2026-27", "Q1", "ICT 9", "Task 2"))
check("18 ...including two-quarter and full-year suffixes", S.base_course_name("CS10 (Q1/Q2)") == "CS10" and S.base_course_name("Band 10 (full year)") == "Band 10"
      and S.base_course_name("Media Arts (Year 2)") == "Media Arts (Year 2)")
app.APP_DATA.mkdir(parents=True, exist_ok=True); app.ASSIGNMENTS_DIR.mkdir(parents=True, exist_ok=True)
rec = app.save_assignment_record({"title": "Task 2", "term": "Q1", "course": {"name": "ICT 9 (Q1)", "label": "ICT 9 (Q1)", "schoolYear": "2026-27"}})
rel, _ = app.session_folder(rec["id"], rec)
check("19 a new assignment's folder uses the plain course name", rel == "2026-27/Q1/ICT 9/Task 2", rel)
check("20 a folder named the old way ('ICT 9 (Q1)') still counts as in place", app.folder_check(rec, "2026-27/Q1/ICT 9 (Q1)/Task 2") is None)
check("21 a folder under a different course is still flagged", app.folder_check(rec, "2026-27/Q1/Band 10/Task 2") == {"have": "2026-27/Q1/Band 10", "want": "2026-27/Q1/ICT 9"})

srv.shutdown()
print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
