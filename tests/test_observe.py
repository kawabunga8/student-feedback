"""Observation model for performance evidence: validation, notes for the drafting model, claim check, counts-only
summary, versioned sidecar. Pure Python with invented data; no app, browser, model or media is touched."""
import os, sys, tempfile
from _common import APPDIR
sys.path.insert(0, APPDIR)
import observe as O
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

# classification by extension only
check("1 video/audio/document/other by extension", [O.classify(n) for n in ("a.MOV", "b.mp4", "c.webm", "d.mp3", "e.docx", "f.whiteboard", "g")] == ["video", "video", "video", "audio", "document", "other", "other"])

# levels are never defaulted
check("2 an empty or invalid level stays empty", [O.clean_level(v) for v in ("", None, "great", "Proficiency", "Prof")] == ["", "", "", "", ""])
check("3 valid levels normalise, + allowed except above Extending", [O.clean_level(v) for v in ("proficient", "DEVELOPING+", "extending+", " Emerging ")] == ["Proficient", "Developing+", "Extending", "Emerging"])
o = O.normalize_observation({"criteria": [{"id": "c1", "note": "steady tempo"}]})
check("4 a note without a level keeps level empty (nothing pre-filled)", o["criteria"][0]["level"] == "" and o["status"] == "unobserved")

# validation and bounds
o = O.normalize_observation({"status": "weird", "criteria": [{"id": "c1", "level": "Proficient", "note": "x" * 5000, "ts": "1:24"}, {"id": "c1", "note": "dup"}, {"note": "no id"}, "junk", None], "strengths": "s" * 9000})
check("5 bad status -> unobserved; duplicate/blank-id criteria dropped; text capped", o["status"] == "unobserved" and len(o["criteria"]) == 1 and len(o["criteria"][0]["note"]) == O.MAX_NOTE and len(o["strengths"]) == O.MAX_TEXT, o["status"])
check("6 non-dict input is safe", O.normalize_observation(None) == {"status": "unobserved", "criteria": [], "strengths": "", "next_step": ""} and O.normalize_store("x") == {} and O.normalize_store(None) == {})
big = {str(i): {"status": "observed"} for i in range(O.MAX_STUDENTS + 50)}
check("7 the store is capped at MAX_STUDENTS", len(O.normalize_store(big)) == O.MAX_STUDENTS)
check("8 a review flag in the input is ignored (editing never arrives pre-reviewed)", "reviewed" not in O.normalize_observation({"reviewed": True, "status": "observed"}))

# notes for the drafting model: no levels, names stay as typed by the teacher, timestamps kept
obs = {"status": "observed", "criteria": [{"id": "0", "level": "Extending", "note": "steady tempo throughout", "ts": "1:24"}, {"id": "1", "level": "Emerging", "note": ""}], "strengths": "confident tone", "next_step": "watch the last four bars"}
t = O.to_notes(obs, ["Rhythm and tempo", "Intonation"])
check("9 notes include criterion label, note, timestamp, strengths and next step", "- Rhythm and tempo: steady tempo throughout (at 1:24)" in t and "Strengths: confident tone" in t and "Next step: watch the last four bars" in t and t.startswith(O.HEAD), t)
check("10 notes never name a level", not any(l in t for l in O.LEVELS), t)
check("11 a criterion with a level but no note adds nothing", "Intonation" not in t)
check("12 no notes -> empty string", O.to_notes({"criteria": [{"id": "0", "level": "Proficient"}]}) == "" and O.to_notes(None) == "")

# claim check flags unsupported content, not greetings
draft = "Thank you for sharing your performance. You kept a steady tempo throughout the piece. Your vibrato was beautiful and your breath control was outstanding. Keep going!"
fl = O.claim_check(draft, obs)
check("13 an invented claim is flagged", any("vibrato" in s for s in fl), fl)
check("14 a supported sentence is not flagged", not any("steady tempo" in s for s in fl), fl)
check("15 greetings and closers are not flagged", not any(s.startswith("Keep going") or s.startswith("Thank you") for s in fl), fl)
check("16 no notes -> every substantive sentence is flagged", len(O.claim_check(draft, {})) >= 2)

# counts-only summary hides small groups
store = {f"s{i}": {"status": "observed", "criteria": [{"id": "c1", "level": "Proficient" if i % 2 else "Developing"}]} for i in range(6)}
store["s6"] = {"status": "revisit"}
sm = O.summary(store, ["c1", "c2"], [f"s{i}" for i in range(8)])
check("17 summary counts statuses incl. students with no record", sm["status"] == {"unobserved": 1, "observed": 6, "revisit": 1} and sm["students"] == 8, sm["status"])
check("18 levels shown when >=5 chose one, hidden (None) below", sm["levels"]["c1"] == {"Emerging": 0, "Developing": 3, "Proficient": 3, "Extending": 0} and sm["levels"]["c2"] is None, sm["levels"])
check("19 summary contains no notes or names", "note" not in str(sm) and "s1" not in str(sm["levels"]))

# sidecar store: atomic, versioned, conflict-safe
d = tempfile.mkdtemp()
s0 = O.load_store(d)
check("20 an empty folder loads version 0 and no students", s0 == {"version": 0, "students": {}})
s1 = O.save_store(d, {"a": {"status": "observed", "criteria": [{"id": "c1", "level": "Proficient", "note": "n"}]}}, 0)
check("21 first save is version 1 and persists", s1["version"] == 1 and O.load_store(d)["students"]["a"]["criteria"][0]["note"] == "n")
try: O.save_store(d, {"a": {}}, 0); stale = False
except O.ObservationConflict as c: stale = c.current["version"] == 1
check("22 saving from a stale version is refused with the current copy", stale and O.load_store(d)["students"]["a"]["status"] == "observed")
s2 = O.save_store(d, {"a": {"status": "revisit"}}, 1)
check("23 saving from the current version succeeds", s2["version"] == 2 and O.load_store(d)["students"]["a"]["status"] == "revisit")
open(os.path.join(d, O.STORE_NAME), "w").write("{not json")
check("24 a corrupt file loads as empty instead of crashing", O.load_store(d) == {"version": 0, "students": {}})
check("25 no temp file is left behind", not [f for f in os.listdir(d) if f.endswith(".tmp")], os.listdir(d))

sys.exit(0 if all(ok) else 1)
