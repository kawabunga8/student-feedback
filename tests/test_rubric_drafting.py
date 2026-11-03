"""Teams rubric -> drafting: the rubric goes to the model as its own 'Assessment criteria' block, feedback must name each
criterion without copying descriptors or naming a level, and the rubric comes from the SAVED record. The model is a
scripted stand-in; nothing contacts Teams or a real model. All wording is invented."""
import json, os, re, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, feedback as fb, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))

LV = ("Extending", "Proficient", "Developing", "Emerging")
D = {"Planning": {"Extending": "Plans ahead in detail and adapts the plan with clear reasons for every change.",
                  "Proficient": "Makes a clear plan and follows it through most of the project steps.",
                  "Developing": "Makes a plan with some gaps and follows part of it.",
                  "Emerging": "Needs help to make a plan and follows it with support."},
     "Building": {"Extending": "Builds an excellent sample and improves it using careful testing at each stage.",
                  "Proficient": "Builds a working sample that does most of what was asked.",
                  "Developing": "Builds part of the sample and tests it sometimes.",
                  "Emerging": "Builds with support and tests when reminded."}}
RUB, why = T.validate_rubric({"title": "Sample Design Rubric (Test)", "criteria": [
    {"name": n, "heading": n, "levels": [{"level": l, "descriptor": D[n][l]} for l in LV]} for n in D]})
assert RUB, why

# ---- prompt pieces (pure)
blk = fb.assessment_block(RUB)
check("1 the block carries every criterion with all four descriptors in full", all(d in blk for n in D for d in D[n].values()) and "Criterion: Planning" in blk and "Criterion: Building" in blk)
check("  and says it is reference only: no copying, no levels", "Reference for you only" in blk and "never name or imply a level" in blk)
check("  no rubric -> no block", fb.assessment_block(None) == "")
check("rubric paragraph has one sentence per criterion without a competing generic sentence target", "ONE paragraph of 2 sentences" in fb.system_prompt('paragraph', 'Grade 9', RUB) and '3 to 5 sentences' not in fb.system_prompt('paragraph', 'Grade 9', RUB))
check("ordinary paragraphs keep their existing format", '3 to 5 sentences' in fb.system_prompt('paragraph', 'Grade 9'))
check("writing plan includes every exact name and evidence/next action, but no descriptors", all('For '+n+',' in fb.criterion_plan(RUB) for n in D) and 'one specific next action' in fb.criterion_plan(RUB) and not any(d in fb.criterion_plan(RUB) for n in D for d in D[n].values()) and fb.criterion_plan(None)=='')
check("2 the system rules tell the model to name, give evidence, give a next step, and never copy or imply a level", "name the criterion, describe the evidence" in fb.system_prompt("paragraph", "Grade 9") and "Only the teacher chooses levels" in fb.system_prompt("paragraph", "Grade 9"))
cp = fb.descriptor_copies("You make a clear plan and follows it through most of the project steps, which helps.", RUB)
check("3 copying 7+ consecutive descriptor words is detected; plain paraphrase is not", cp and not fb.descriptor_copies("Your plan was clear and you kept to it for nearly all of the steps in the project.", RUB), cp)

# Directional scale wording, including the noun used in the real-model failure.
for phrase in ["move toward proficiency", "moving towards proficiency", "approaching proficiency", "reach proficiency",
               "achieve proficiency", "attain the Proficient level", "aim for higher proficiency", "become proficient",
               "progress toward proficiency", "toward developing level", "reach Extending+", "towards emerging standard"]:
    check("directional level wording caught: " + phrase, bool(fb.directional_level_words("You can " + phrase + " in this criterion.")))
for phrase in ["Developing your ideas will help your client.", "Keep working toward developing a steadier pulse.",
               "Try extending the melody by two bars.", "Your emerging ideas need an example.",
               'You wrote "move toward proficiency" in your reflection.', "Aim for a steady pulse at 80 BPM."]:
    check("ordinary wording or quoted evidence preserved: " + phrase, not fb.directional_level_words(phrase))

# ---- generate() with a scripted model
seen = []
script = []
def fake_chat(model, messages, temperature):
    seen.append(messages); return script.pop(0) if script else "You explained your plan for the sample. Next, test the sample at more stages."
fb.chat = fake_chat
WORK = "I made a sample app and wrote down my steps."
def gen(**kw): return fb.generate("m", "Build a small sample app.", "Grade 9", "Student 1", WORK, length=kw.pop("length", "paragraph"), **kw)

seen.clear(); script[:] = ["Your planning notes list each step you took, and next you could say why you changed the order. For building, your sample runs, and next you could test it at more stages."]
out = gen(assessment=RUB)
user = seen[0][1]["content"]
check("4 the model is sent the Assessment criteria block, separate from the assignment text", "Assessment criteria (from the teacher's rubric" in user and user.index("Rubric / what the teacher is looking for") < user.index("Assessment criteria") and D["Planning"]["Proficient"] in user)
check("  the first acceptable draft is returned as is", len(seen) == 1 and "planning" in out.lower() and "building" in out.lower(), out)
seen.clear(); script[:] = ["You make a clear plan and follows it through most of the project steps. Planning and building both show effort. Next, test more.",
                           "Your planning notes list each step, and next say why you changed the order. Your building shows a sample that runs, and next test it more often."]
out = gen(assessment=RUB)
check("5 a draft that copies descriptor wording is sent back with that reason, and the retry is used", len(seen) == 2 and "copies rubric descriptor wording" in seen[1][1]["content"] and "most of the project steps" not in out, out)
seen.clear(); script[:] = ["Your sample runs well and your notes are tidy. Next, test it at more stages."]*3
try: fb.generate("m", "Build a small sample app.", "Grade 9", "Student 1", WORK, length="paragraph", assessment=RUB); rejected = ""
except fb.DraftRejected as e: rejected = str(e)
check("6 a draft that never names a criterion, after the retries, is REJECTED (not returned as 'best')", len(seen) == 3 and "never names these rubric criteria" in rejected and "Planning" in rejected, rejected)
check("  the retries asked for it", "rubric criteria by name" in seen[1][1]["content"])
seen.clear(); script[:] = ["Your planning is at the Proficient level. Building: next, test more.", "Your planning notes list each step; next explain order changes. Your building runs; next test more often."]
out = gen(assessment=RUB)
check("7 naming a level is retried by the existing level check, and the clean retry is what is returned", len(seen) == 2 and "Proficient" not in out, out)
for label, kw in (("with the rubric", {"assessment": RUB}), ("without any rubric", {})):
    seen.clear(); script[:] = ["Your planning is at the Proficient level and your building is Developing. Next, test more."] * 3
    try: gen(**kw); r_ = ""
    except fb.DraftRejected as e: r_ = str(e)
    check(f"7b a draft that keeps naming a level is rejected after the retries, {label}", len(seen) == 3 and "names a level" in r_, r_)
seen.clear(); script[:] = ["You make a clear plan and follows it through most of the project steps. Your building runs; next test more. Next, plan more."] * 3
try: gen(assessment=RUB); r_ = ""
except fb.DraftRejected as e: r_ = str(e)
check("7c a draft that keeps copying descriptor wording is rejected", "copies rubric descriptor wording" in r_, r_)
seen.clear(); script[:] = ["Your planning notes list each step; next explain the order changes. Your sample runs.",
                           "Your planning notes list each step; next explain the order changes. Your building runs; next test it more often."]
out = gen(assessment=RUB)
check("7d a retry that names every criterion is returned, and no further retry is made", len(seen) == 2 and "building" in out.lower(), out)
seen.clear(); script[:] = ["Your planning is Proficient. Next, test more.", "Your planning notes list each step; next explain order changes. Your sample runs.", "Your planning is Developing. Next, test more."]
try: gen(assessment=RUB); r_ = ""
except fb.DraftRejected as e: r_ = str(e)
check("7e when every attempt fails, the reason reported is the attempt with the fewest rule problems (not the last)", "never names these rubric criteria" in r_ and "names a level" not in r_, r_)

for use in (None, RUB):
    seen.clear(); script[:] = ['Your planning and building show effort; move toward proficiency in the "Planning" criterion.'] * 3
    try: gen(assessment=use); rejected = False
    except fb.DraftRejected as e: rejected = "move toward proficiency" in str(e)
    check("live-trial phrase rejected after retries " + ("with rubric" if use else "without rubric"), rejected and len(seen) == 3)
seen.clear(); script[:] = ['Your planning and building can move toward proficiency.', 'Your planning notes list each step; next explain order changes. Your building runs; next test it more often.']
out = gen(assessment=RUB)
check("directional wording triggers a retry and a clean draft is accepted", len(seen) == 2 and "proficiency" not in out and "move toward proficiency" in seen[1][1]["content"])

# ---- the saved record is the source (server side)
srv = ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
def call(method, path, body=None):
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"} if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
app.start_worker()
mk = lambda t: call("POST", "/api/assignments", {"assignment": {"title": t, "course": {"name": "ICT 9", "label": "ICT 9 (Q1)", "sectionIds": [], "schoolYear": "2026-27"}, "grade": "Grade 9", "term": "Q1", "instructions": "x"}})[1]["assignment"]["id"]
ADIR = os.path.join(HOME, "Library/Application Support/student-feedback/assignments")
def set_teams(aid, teams):
    p = os.path.join(ADIR, aid + ".json"); r = json.load(open(p)); r["teams"] = teams; json.dump(r, open(p, "w"))
with_r, without_r, unread = mk("With rubric"), mk("No rubric"), mk("Unread rubric")
set_teams(with_r, {"rubricState": "read", "rubric": RUB}); set_teams(unread, {"rubricState": "present_unread"})
P = lambda aid, **kw: {"model": "m", "rubric": "Build a small sample app.", "grade": "Grade 9", "label": "Student 1", "work": WORK, "length": "paragraph", "assignment": aid, **kw}
seen.clear(); script[:] = ["Your planning notes list each step; next explain order changes. Your building runs; next test more often."]
app.draft_for(P(with_r, use_rubric=True))
check("10 draft_for with use_rubric takes the rubric from the saved record", "Criterion: Building" in seen[0][1]["content"] and D["Building"]["Emerging"] in seen[0][1]["content"])
seen.clear(); app.draft_for(P(with_r, use_rubric=False))
check("  not asked for -> not used, even though the record has one", "Assessment criteria" not in seen[0][1]["content"])
for label, aid in (("an assignment with no rubric", without_r), ("a rubric that is present but unread", unread)):
    try: app.draft_for(P(aid, use_rubric=True)); msg = ""
    except ValueError as e: msg = str(e)
    check(f"11 use_rubric on {label} is refused clearly, not drafted without it", "no saved Teams rubric" in msg, msg)
try: app.draft_for(P(with_r, use_rubric=True, rubric_sha="0000")); msg = ""
except ValueError as e: msg = str(e)
check("12 a job whose rubric changed since it was queued refuses", "changed after this job was queued" in msg, msg)
bad = json.load(open(os.path.join(ADIR, with_r + ".json"))); bad["teams"]["rubric"]["criteria"][0]["levels"].pop()
json.dump(bad, open(os.path.join(ADIR, with_r + ".json"), "w"))
check("13 a saved rubric that no longer validates is not used", app.saved_rubric(with_r) is None)
set_teams(with_r, {"rubricState": "read", "rubric": RUB})

# ---- background job path
IT = [{"key": "k1", "work": WORK, "notes": "", "level": "", "grade": "Grade 9", "label": "Student 1"}]
st, r = call("POST", "/api/jobs", {"assignment": without_r, "settings": {"model": "m", "rubric": "x", "use_rubric": True, "length": "paragraph"}, "items": IT})
check("14 queueing with the rubric on an assignment that has none is refused up front", "no saved Teams rubric" in r.get("error", ""), r)
seen.clear(); script[:] = ["Your planning notes list each step; next explain order changes. Your building runs; next test more often."]
st, r = call("POST", "/api/jobs", {"assignment": with_r, "settings": {"model": "m", "rubric": "Build a small sample app.", "use_rubric": True, "length": "paragraph", "grade": "Grade 9"}, "items": IT})
jid = r["job"]["id"]; end = time.time() + 20
while time.time() < end and call("GET", "/api/jobs/" + jid)[1]["job"]["state"] not in ("completed", "failed"): time.sleep(0.3)
j = call("GET", "/api/jobs/" + jid)[1]["job"]
check("15 the background job drafts with the saved rubric and finishes", j["state"] == "completed" and seen and "Criterion: Planning" in seen[0][1]["content"], (j["state"], j.get("error")))
db = open(os.path.join(HOME, "Library/Application Support/student-feedback/jobs.sqlite"), "rb").read()
check("  the journal holds no rubric wording or student work", D["Planning"]["Extending"].encode() not in db and WORK.encode() not in db)

# ---- approvals are bound to the rubric setting and the rubric itself (server side)
rec_on = json.load(open(os.path.join(ADIR, with_r + ".json"))); rec_on["teams"]["useRubric"] = True
rec_off = json.loads(json.dumps(rec_on)); rec_off["teams"]["useRubric"] = False
def bound_for(rec, **over):
    course = rec.get("course") or {}
    b = {"student_id": "S1", "name": "Student 1", "work": WORK, "notes": "", "level": "Proficient", "feedback": "x", "myschool_comment": "",
         "grade": rec.get("grade", ""), "assignment": rec.get("title", ""), "course": course.get("label", ""), "school_year": course.get("schoolYear", ""),
         "quarter": rec.get("term", ""), "instructions": app.compose_rubric(rec.get("instructions"), rec.get("focus")), "standards": []}
    b.update(over); return json.dumps(b)
stu = {"student_id": "S1", "name": "Student 1", "work": WORK, "notes": "", "level": "Proficient", "feedback": "x", "myschool_comment": "", "grade": ""}
stamp = {"assignment_version": 99}
rb_on = {"use": True, "canon": app.rubric_canon(RUB)}
check("16 an approval made with the rubric ON is current while the saved setting and rubric are unchanged", app.check_reviewed(bound_for(rec_on, rubric=rb_on), stu, rec_on, stamp)["current"], app.check_reviewed(bound_for(rec_on, rubric=rb_on), stu, rec_on, stamp))
r16 = app.check_reviewed(bound_for(rec_on, rubric=rb_on), stu, rec_off, stamp)
check("17 switching the rubric OFF afterwards voids it", not r16["current"] and "Teams rubric setting" in r16["reasons"], r16)
r17 = app.check_reviewed(bound_for(rec_off, rubric={"use": False, "canon": ""}), stu, rec_on, stamp)
check("  switching it ON after an approval made without it voids it too", not r17["current"] and "Teams rubric setting" in r17["reasons"], r17)
rec_chg = json.loads(json.dumps(rec_on)); rec_chg["teams"]["rubric"]["criteria"][0]["levels"][0]["descriptor"] = "Changed wording that still validates fine."
r18 = app.check_reviewed(bound_for(rec_on, rubric=rb_on), stu, rec_chg, stamp)
check("18 changing the rubric's wording after an approval voids it", not r18["current"] and "Teams rubric" in r18["reasons"], r18)
check("19 approvals saved before this existed (no rubric key) stay valid when no rubric is in use", app.check_reviewed(bound_for(rec_off), stu, rec_off, stamp)["current"])
check("  and the page and server agree on the rubric's canonical text", app.rubric_canon(RUB).splitlines()[0] == RUB["title"] and app.rubric_canon(RUB).splitlines()[1] == "Planning|Extending|" + D["Planning"]["Extending"])
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
