"""Evidence listing: metadata only, conservative matching, counts-only summary. Invented students and files in a
temporary folder; nothing contacts SharePoint, Teams, a model or a browser, and no file is ever opened."""
import os, sys, tempfile, builtins
from _common import APPDIR
sys.path.insert(0, APPDIR)
import evidence_collect as E
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

R = [{"id": "1", "first": "Ada", "last": "Test", "grade": "10", "block": "D"}, {"id": "2", "first": "Bo", "last": "Sample", "grade": "11", "block": "D"},
     {"id": "3", "first": "Cy", "last": "Demo", "grade": "12", "block": "D"}, {"id": "4", "first": "Di", "last": "Mock", "grade": "10", "block": "D"}]
def ent(p, b=10): return {"path": p, "bytes": b, "modified": "1", "url": "https://example.invalid/" + p.replace(" ", "%20")}
entries = [ent("Ada Test/Scales 1/take1.mov", 500), ent("Ada Test/Scales 1/Retake/take2.MP4", 700), ent("Ada Test/Rhythm Check/a.mp4"),
           ent("Bo Sample/Scales 1/s.webm"), ent("Bo Sample/Scales 1/notes.docx"),
           ent("Cy Demo/Rhythm Check/x.mp4"),
           ent("Zed Unknown/Scales 1/z.mov"),
           ent("Di Mock/loose.mov")]
r = E.build(entries, R, "Scales 1")
check("1 matches students to the roster and picks only the assignment's folder", set(r["students"]) == {"1", "2"} and r["students"]["1"]["name"] == "Ada Test", set(r["students"]))
check("2 files below an extra subfolder are included", [i["name"] for i in r["students"]["1"]["items"]] == ["take1.mov", "take2.MP4"])
check("3 kinds come from the extension", [i["kind"] for i in r["students"]["2"]["items"]] == ["document", "video"] or sorted(i["kind"] for i in r["students"]["2"]["items"]) == ["document", "video"])
check("4 size and link are carried through, nothing else", r["students"]["1"]["items"][0]["bytes"] == 500 and r["students"]["1"]["items"][0]["url"].startswith("https://example.invalid/"))
check("5 an unknown student folder is flagged, not guessed", any(f["folder"] == "Zed Unknown" for f in r["flagged"]))
check("6 files directly in a student folder are flagged", any(f["folder"] == "Di Mock" and "directly" in f["reason"] for f in r["flagged"]), r["flagged"])
check("7 roster students with nothing for this assignment are listed", set(r["no_evidence"]) == {"3", "4"}, r["no_evidence"])
check("8 files under a different assignment are counted, not included", r["other_assignment_files"] == 2, r["other_assignment_files"])

# assignment title matching
check("9 exact match after normalising", E.assignment_folder(["Scales 1", "Rhythm Check"], "scales  1") == "Scales 1")
check("10 one unique containment match is accepted", E.assignment_folder(["Scales 1 (Grades 10-12)", "Rhythm Check"], "Scales 1") == "Scales 1 (Grades 10-12)")
check("11 two containment matches are refused", E.assignment_folder(["Scales 1 A", "Scales 1 B"], "Scales 1") is None)
check("12 duplicate exact matches are refused", E.assignment_folder(["Scales 1", "scales 1"], "Scales 1") is None)
check("13 an empty title matches nothing", E.assignment_folder(["Scales 1"], "") is None)
amb = E.build([ent("Ada Test/Scales 1 A/a.mov"), ent("Ada Test/Scales 1 B/b.mov")], R, "Scales 1")
check("14 an ambiguous assignment folder is flagged for that student", amb["students"] == {} and any("more than one" in f["reason"] for f in amb["flagged"]), amb["flagged"])

# duplicate roster names are not guessed
dup = E.build([ent("Ada Test/Scales 1/a.mov")], R + [{"id": "9", "first": "Ada", "last": "Test", "grade": "10", "block": "D"}], "Scales 1")
check("15 a duplicate roster name is flagged", dup["students"] == {} and dup["flagged"] and "more than one" in dup["flagged"][0]["reason"], dup["flagged"])

# counts only
c = E.counts(r)
check("16 counts contain no names or file names", c == {"students_with_evidence": 2, "flagged": 2, "no_evidence": 2, "files_by_kind": {"video": 3, "document": 1}, "cloud_only_files": 0, "files_under_other_assignments": 2}, c)
check("17 counts text has no student names", not any(n in str(c) for n in ("Ada", "Bo", "Zed", "take1")))

# local folder scan: metadata only, no opens, no symlink following, bounded
root = tempfile.mkdtemp(); outside = tempfile.mkdtemp()
os.makedirs(os.path.join(root, "Ada Test", "Scales 1")); open(os.path.join(root, "Ada Test", "Scales 1", "a.mov"), "wb").write(b"x" * 123)
open(os.path.join(outside, "secret.txt"), "w").write("s")
os.symlink(outside, os.path.join(root, "Ada Test", "linked")); os.symlink(os.path.join(outside, "secret.txt"), os.path.join(root, "Ada Test", "Scales 1", "l.txt"))
open(os.path.join(root, "Ada Test", ".DS_Store"), "w").write("x")
real_open, opened = builtins.open, []
builtins.open = lambda *a, **k: (opened.append(a[0]), real_open(*a, **k))[1]
try: got = E.entries_from_folder(root)
finally: builtins.open = real_open
check("18 the scan lists the real file with its size", [(g["path"], g["bytes"]) for g in got] == [("Ada Test/Scales 1/a.mov", 123)], got)
check("19 symlinks and hidden files are skipped", len(got) == 1)
check("20 the scan never opens a file", opened == [], opened)
deep = tempfile.mkdtemp(); p = deep
for i in range(10): p = os.path.join(p, f"d{i}")
os.makedirs(p); real_open(os.path.join(p, "f.mov"), "w").write("x"); real_open(os.path.join(deep, "d0", "top.mov"), "w").write("x")
names = [g["path"] for g in E.entries_from_folder(deep)]
check("21 the scan stops at the depth limit", names == ["d0/top.mov"], names)

# CLI: dry run writes nothing; --commit writes metadata only, into an existing session folder; roster is stubbed
import json, io, contextlib, stage_submissions as S
S.fetch_roster = lambda course, quarter: R
src = tempfile.mkdtemp(); ses = tempfile.mkdtemp()
os.makedirs(os.path.join(src, "Ada Test", "Scales 1")); real_open(os.path.join(src, "Ada Test", "Scales 1", "a.mov"), "wb").write(b"x" * 2048)
def run_cli(*args):
    old = sys.argv; sys.argv = ["evidence_collect.py", *args]; buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            try: E.main(); code = 0
            except SystemExit as e: code = e.code or 0
    finally: sys.argv = old
    return code, buf.getvalue()
code, out = run_cli("--root", src, "--course", "Band 10", "--quarter", "1", "--title", "Scales 1", "--out", ses)
check("22 a dry run prints counts, writes nothing and prints no names", code == 0 and not os.path.exists(os.path.join(ses, "evidence.json")) and "Ada" not in out and '"students_with_evidence": 1' in out, out[-160:])
code, out = run_cli("--root", src, "--course", "Band 10", "--quarter", "1", "--title", "Scales 1", "--out", ses, "--commit")
saved = json.load(real_open(os.path.join(ses, "evidence.json")))
check("23 --commit writes evidence.json with metadata only", code == 0 and list(saved["students"]["1"]["items"][0]) == ["name", "kind", "bytes", "modified", "url", "cloud_only"] and saved["students"]["1"]["items"][0]["bytes"] == 2048, saved)
code, out = run_cli("--root", src, "--course", "Band 10", "--quarter", "1", "--title", "Scales 1", "--out", os.path.join(ses, "missing"), "--commit")
check("24 --commit refuses when the session folder does not exist", code != 0 and "session" in str(code).lower() + out.lower(), (code, out))
code, out = run_cli("--course", "Band 10", "--quarter", "1", "--title", "Scales 1")
check("25 giving neither --root nor --entries is refused", code != 0)

sys.exit(0 if all(ok) else 1)
