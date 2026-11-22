"""team_draft: the transcript is reduced to spoken words, the team rules ride with the request, and no level or student name
goes to the drafter. Pure functions, synthetic text only."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import team_draft as T
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:200]) if extra != "" else ""))

raw = "duration_s=101.2\n[   0.6-   5.8] Hello there\n\n[  10.0-  12.5]   second line  \nplain line"
check("T1 timestamps and the duration line are removed, spoken words kept in order", T.clean_transcript(raw) == "Hello there\nsecond line\nplain line", T.clean_transcript(raw))
check("T2 empty or non-text input gives an empty transcript", T.clean_transcript("") == "" and T.clean_transcript(None) == "")
try: T.team_work("duration_s=5\n"); no_words = False
except ValueError: no_words = True
check("T3 a transcript with no words is refused, so nothing is drafted from nothing", no_words)
w = T.team_work("[0.0-1.0] " + "x" * 20000)
check("T4 a very long transcript is cut, and labelled as speech recognition without picture or sound", len(w) < T.MAX_CHARS + 400 and "speech recognition" in w and "no picture or sound" in w, len(w))
q = T.team_request({"transcript": "[0.0-1.0] hi", "notes": "private", "level": "Proficient", "label": "Pat Example", "rubric": "r"})
check("T5 the request is a team's: the level and any name are dropped, and the rules lead the notes", q["level"] == "" and q["label"] == "student" and q["notes"].startswith(T.TEAM_NOTE) and q["notes"].endswith("private") and "Pat" not in str(q))
orig = {"transcript": "[0.0-1.0] hi", "notes": "private", "level": "Proficient", "label": "Pat Example"}
T.team_request(orig)
check("T6 the original request is not changed", orig == {"transcript": "[0.0-1.0] hi", "notes": "private", "level": "Proficient", "label": "Pat Example"})
check("T7 a stray 'the student' becomes 'your team', capital kept at a sentence start", T.tidy("The student did well. Say the student again.") == "Your team did well. Say your team again.", T.tidy("The student did well. Say the student again."))
import tempfile, pathlib
with tempfile.TemporaryDirectory() as d:
    r = pathlib.Path(d)
    for rel in ("Skit-videos/Pat Example/a.mov", "Skit-videos/Pat Example/notes.txt", "Skit-videos/Sam Sample/b.MP4", "Other/Zed/c.mov", "Skit-videos-C/Kim Tester/.hid.mov"):
        (r / rel).parent.mkdir(parents=True, exist_ok=True); (r / rel).write_bytes(b"x")
    v = T.video_files(r)
    check("T8 downloaded videos are listed from the *-videos* folders only, videos only, no hidden files", [(x["folder"], x["student"], x["file"]) for x in v] == [("Skit-videos", "Pat Example", "a.mov"), ("Skit-videos", "Sam Sample", "b.MP4")], v)
check("T9 a missing folder gives an empty list", T.video_files("/nonexistent-folder-xyz") == [])
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed"); sys.exit(0 if all(ok_all) else 1)
