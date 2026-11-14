"""The class patterns routes' functions in app.py: the per-student criteria check and the counting. A stand-in replaces the
model, so no model, browser, Teams or MySchool is involved. Everything runs in a temporary HOME with invented data."""
import json, os, sys, tempfile
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

RUBRIC = "Assignment: one persuasive paragraph.\nLooking for: clear claim, at least two supporting reasons, evidence, concluding sentence."
seen = []
def fake_chat(model, messages, temperature):
    """Say 'done' for the claim only when the work contains the invented word CLAIMHERE, quoting it exactly."""
    prompt = messages[0]["content"]; seen.append(prompt)
    work = prompt.split('"""')[1].strip()
    rows = [{"criterion": c, "done": "CLAIMHERE" in work and c == "clear claim", "quote": "CLAIMHERE" if "CLAIMHERE" in work and c == "clear claim" else ""}
            for c in ["clear claim", "at least two supporting reasons", "evidence", "concluding sentence"]]
    return json.dumps(rows)
app.fb.chat = fake_chat

a = app.criteria_check_for({"model": "x", "rubric": RUBRIC, "work": "I think CLAIMHERE is true."})
check("1 a met criterion comes back done, the rest missing", a["done"] == ["clear claim"] and len(a["missing"]) == 3 and a["checked"], a)
check("2 the criteria are the teacher's, in order", a["criteria"] == ["clear claim", "at least two supporting reasons", "evidence", "concluding sentence"])
check("3 the reply holds no work text", "CLAIMHERE" not in json.dumps(a))
b = app.criteria_check_for({"model": "x", "rubric": RUBRIC, "work": "Nothing useful here."})
check("4 work with no claim has everything missing", b["done"] == [] and len(b["missing"]) == 4 and b["checked"])

def refused(p):
    try: app.criteria_check_for(p); return None
    except ValueError as e: return str(e)
check("5 no 'Looking for' criteria is refused with a plain message", "Looking for" in (refused({"model": "x", "rubric": "Just a description.", "work": "w"}) or ""))
check("6 empty work is refused", "no work" in (refused({"model": "x", "rubric": RUBRIC, "work": "  "}) or ""))

# A model that fails gives "not checked", never a made-up result.
def broken(*a, **k): raise ConnectionError("down")
app.fb.chat = broken
c = app.criteria_check_for({"model": "x", "rubric": RUBRIC, "work": "w"})
check("7 an unreachable model returns not-checked", c["checked"] is False and c["done"] == [] and c["missing"] == [], c)

# Counting: ten invented students, 8 lack evidence.
crit = a["criteria"]
rows = [{"done": ["clear claim"], "missing": ["evidence"]} for _ in range(8)] + [{"done": ["clear claim", "evidence"], "missing": []} for _ in range(2)]
out = app.class_patterns_for({"criteria": crit, "rows": rows, "title": "Invented task"})
ev = next(x for x in out["summary"]["criteria"] if x["criterion"] == "evidence")
check("8 the counts come back", ev["met"] == 2 and ev["not_met"] == 8 and ev["percent_not_met"] == 80, ev)
check("9 the markdown carries the title and the review note", "Invented task" in out["markdown"] and "Review it before using or sharing it" in out["markdown"])
small = app.class_patterns_for({"criteria": crit, "rows": rows[:3]})
check("10 three students: counts are hidden", small["summary"]["suppressed"] and "| evidence |" not in small["markdown"])
extra = app.class_patterns_for({"criteria": crit, "rows": [dict(r, name="Invented Name", work="invented work") for r in rows]})
check("11 extra fields such as names are ignored", "Invented Name" not in json.dumps(extra) and "invented work" not in json.dumps(extra))
check("12 junk rows are skipped without an error", app.class_patterns_for({"criteria": crit, "rows": rows + ["junk", 5, None]})["summary"]["students"] == 10)

# The page file is served and registered.
page = app.PAGE if isinstance(app.PAGE, str) else app.PAGE.decode()
check("13 the page loads patterns.js", '<script src="/ui/patterns.js"></script>' in page and os.path.exists(os.path.join(APPDIR, "ui", "patterns.js")))
check("14 patterns.js never sends a name", "'.name'" not in open(os.path.join(APPDIR, "ui", "patterns.js")).read())

print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
