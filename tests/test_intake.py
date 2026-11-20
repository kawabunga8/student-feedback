"""Private intake and de-identification (earmaster_intake.py), end to end on INVENTED students in a temporary folder.
Covers: vault location guard, random codes, consent first, name-format mismatch, nicknames, ambiguous and missing matches
(never guessed), counts-only cases, scrubbing of a classmate / First Mate / staff, flags, publish gate, delete, output folder.
No real data, no model, no network."""
import csv, io, json, os, re, sys, tempfile
from pathlib import Path
from contextlib import redirect_stdout
from _common import APPDIR
sys.path.insert(0, APPDIR)
import earmaster_intake as I
from earmaster_cases import validate
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))

tmp = Path(tempfile.mkdtemp(prefix="sf-intake-")).resolve()
vault = tmp / "StudentVault"; vault.mkdir(); (vault / "reflections").mkdir()
I.DATA = tmp / "data"
COLS = tmp / "cols.json"; COLS.write_text(json.dumps(json.loads(I.COLUMNS_FILE.read_text())))

# ---- vault location guard (fake home and fake repo) ----
home = tmp / "home"; (home / "Desktop").mkdir(parents=True); (home / "Documents").mkdir(); (home / "OneDrive - School" / "x").mkdir(parents=True)
repo = tmp / "repo"; (repo / "sub").mkdir(parents=True)
check("1 a vault inside the repo is refused", I.vault_problem(repo / "sub", repo, home))
check("2 a vault holding the repo is refused", I.vault_problem(tmp, repo, home))
check("3 a vault in OneDrive is refused", I.vault_problem(home / "OneDrive - School" / "x", repo, home))
check("4 Desktop is fine when iCloud is not syncing it", I.vault_problem(home / "Desktop" / "V", repo, home) is None)
(home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Desktop").mkdir(parents=True)
check("5 Desktop is refused when iCloud syncs it", I.vault_problem(home / "Desktop" / "V", repo, home))
check("6 Documents is fine when only Desktop is synced", I.vault_problem(home / "Documents" / "V", repo, home) is None)
check("7 iCloud Drive itself is refused", I.vault_problem(home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "V", repo, home))
check("8 the real repo is refused as a vault", I.vault_problem(I.REPO / "data", I.REPO, home))
try: I.main(["intake", str(I.REPO / "tests")]); refused = False
except SystemExit as e: refused = "Refusing" in str(e)
check("9 the commands themselves stop on a bad vault", refused)

# ---- make-key ----
names = tmp / "names.txt"; names.write_text("Jordan Lee\nAlex Rivera\n")
with redirect_stdout(io.StringIO()): I.main(["make-key", str(vault), "--names", str(names)])
rows = list(csv.DictReader(open(vault / "key.csv")))
codes = [r["code"] for r in rows]
check("10 make-key gives each student a unique code of the form S07", len(set(codes)) == 2 and all(re.fullmatch(r"S\d\d", c) for c in codes), codes)
check("11 codes do not contain letters or digits taken from the name", all("Jordan" not in c and "Alex" not in c for c in codes))
try: I.main(["make-key", str(vault), "--names", str(names)]); kept = False
except SystemExit: kept = True
check("12 make-key will not overwrite an existing key", kept)

# ---- invented roster, EarMaster export and reflections ----
KEY = [dict(name="Jordan Lee", earmaster_name="Lee, Jordan", onenote_name="Jordan Lee", nicknames="JJ", grade="10", consent="yes", code="S07"),
       dict(name="Alex Rivera", earmaster_name="Alex Rivera", onenote_name="Alex Rivera", nicknames="", grade="11", consent="yes", code="S12"),
       dict(name="Sam Okafor", earmaster_name="Sam Okafor", onenote_name="Sam Okafor", nicknames="Sammy", grade="10", consent="no", code="S03"),
       dict(name="Pat Nguyen", earmaster_name="Pat Nguyen", onenote_name="Pat N 1", nicknames="", grade="9", consent="yes", code="S21"),
       dict(name="Pat Nguyen", earmaster_name="Pat Nguyen", onenote_name="Pat N 2", nicknames="", grade="12", consent="yes", code="S22"),
       dict(name="Casey Moon", earmaster_name="Casey Moon", onenote_name="Casey Moon", nicknames="", grade="9", consent="yes", code="S30")]
with open(vault / "key.csv", "w", newline="") as f:
    w = csv.DictWriter(f, I.KEY_COLS); w.writeheader(); w.writerows(KEY)
(vault / "others.csv").write_text("name,role\nMs Tanaka,teacher\nRiley Chen,firstmate\n")
em = [("Lee, Jordan", "2026-11-03 15:10:00", "Intervals 1", "Lesson", "52", "no"), ("Lee, Jordan", "2026-11-05 15:10:00", "Intervals 1", "Lesson", "80%", "yes"),
      ("Lee, Jordan", "2026-11-05 15:30:00", "Intervals 1", "Lesson", "85", "yes"), ("Lee, Jordan", "2026-11-10 12:00:00", "Rhythm Dictation", "Self", "70", "no"),
      ("Alex Rivera", "2026-11-04 08:00:00", "Chords 2", "Lesson", "60", "no"), ("Alex Rivera", "2026-11-11 08:00:00", "Chords 2", "Lesson", "90", "yes"),
      ("Sam Okafor", "2026-11-04 08:00:00", "Chords 2", "Lesson", "99", "yes"),
      ("Pat Nguyen", "2026-11-04 08:00:00", "Chords 2", "Lesson", "50", "no"),
      ("Casey Moon", "2026-11-04 08:00:00", "Chords 2", "Lesson", "50", "no"),
      ("Zed Unlisted", "2026-11-04 08:00:00", "Chords 2", "Lesson", "50", "no")]
with open(vault / "earmaster.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Student", "Date", "Exercise", "Type", "Score", "Passed"]); w.writerows(em)
(vault / "reflections" / "Jordan Lee.txt").write_text(
    "Where am I going?\nI want better rhythm for the winter concert.\nHow am I going?\nJJ here. I practised on Nov 12 with my flute. Sam Okafor and Sammy helped me, "
    "Riley Chen was my First Mate, and Ms Tanaka said try Vancouver Hall. Lee Jordan also called Lee, Jordan.\nWhere to next?\nRhythm Dictation again.\n")
(vault / "reflections" / "Alex Rivera.txt").write_text("Where am I going?\nChords.\nHow am I going?\nSlowly getting better.\n")
(vault / "reflections" / "Pat N 1.txt").write_text("Pat's reflection one\n")
(vault / "reflections" / "Pat N 2.txt").write_text("Pat's reflection two\n")

out = io.StringIO()
with redirect_stdout(out): I.main(["intake", str(vault), "--columns", str(COLS)])
said = out.getvalue()
cases = {p.stem: json.loads(p.read_text()) for p in (vault / "cases").glob("*.json")}
check("13 only the two clean consenting students became cases", sorted(cases) == ["S07", "S12"], sorted(cases))
check("14 every case passes the existing validator", all(not validate(c) for c in cases.values()), [validate(c) for c in cases.values()])
j = cases["S07"]
check("15 'Lee, Jordan' in EarMaster matched 'Jordan Lee' in OneNote", j["journal_entry"].startswith("Where am I going?") and j["attempts_30d"] == 4)
check("16 the case holds counts only", (j["lessons_completed"], j["self_chosen_exercises"], j["active_days_30d"], j["attempts_after_pass"], j["accuracy_first_pct"], j["accuracy_latest_pct"]) == (["Intervals 1"], ["Rhythm Dictation"], 3, 1, 52.0, 70.0), j)
check("17 no timestamps or durations anywhere in the case", "2026-" not in json.dumps({k: v for k, v in j.items() if k != "journal_entry"}) and not any("minute" in k or "duration" in k or "time" in k for k in j))
check("18 the question labels stay above the answers", "How am I going?\nJJ here" in j["journal_entry"])
check_text = (vault / "check-these.txt").read_text()
check("19 the non-consenting student's rows were not summarised or listed", "Sam Okafor" not in check_text and "S03" not in check_text and "S03" not in said)
check("20 a shared name is flagged, not guessed", "S21" in check_text and "S22" in check_text and "more than one student" in check_text, check_text)
check("21 a consenting student with no reflection or rows is flagged", "S30" in check_text and "no reflection" in check_text, check_text)
check("22 an EarMaster name nobody owns is flagged", "zed unlisted" in check_text)
check("23 the terminal output prints no student names", not re.search(r"Jordan|Alex|Sam|Pat|Casey|Zed|Lee", said), said)

# ---- scrub ----
with redirect_stdout(io.StringIO()): pass
(vault / "outputs").mkdir()
(vault / "outputs" / "S07__20261120-100000.md").write_text("---\ncase_id: S07\n---\n\n**Where am I going?** Jordan, you want steadier rhythm.\n**How am I going?** Sam Okafor's tip about Intervals 1 helped.\n")
with open(vault / "review_log_filled.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["case_id", "what_shingo_changed"]); w.writerow(["S07", "Removed Jordan Lee"]); w.writerow(["S12", "Alex Rivera to Sam"])
out = io.StringIO()
with redirect_stdout(out): I.main(["scrub", str(vault)])
sc = {p.stem: json.loads(p.read_text()) for p in (vault / "scrubbed" / "cases").glob("*.json")}
t = sc["S07"]["journal_entry"]
check("24 the student's own name, nickname and name formats become their code", "S07" in t and "JJ" not in t and "Lee, Jordan" not in t and "Lee Jordan" not in t, t)
check("25 a classmate (and her nickname) becomes [student], consenting or not", "Sam" not in t and "Sammy" not in t and t.count("[student]") >= 3, t)
check("26 the First Mate becomes [student] and staff become [teacher]", "Riley" not in t and "Tanaka" not in t and "[teacher]" in t, t)
fl = json.loads((vault / "scrubbed" / "flags.json").read_text())
check("27 dates, instruments and unknown capitalised places are flagged, not removed", "Nov 12" in t and "flute" in t and any("date" in f for f in fl["S07"]) and any("instrument" in f for f in fl["S07"]) and any("Vancouver" in f for f in fl["S07"]), fl)
check("28 a case without such details has no flags", "S12" not in fl, fl)
check("29 lesson names are not flagged as names", not any("Intervals" in f or "Rhythm" in f for f in fl.get("S07", [])), fl)
d = (vault / "scrubbed" / "outputs" / "S07__20261120-100000.md").read_text()
check("30 drafts are scrubbed too", "Jordan" not in d and "Okafor" not in d and "S07" in d and "[student]" in d, d)
r = list(csv.reader(open(vault / "scrubbed" / "review_log_filled.csv")))
check("31 the review log is scrubbed row by row", "Jordan" not in r[1][1] and "S07" in r[1][1] and "[student]" in r[2][1] and "Sam" not in r[2][1] and "Alex" not in r[2][1], r)
html_page = (vault / "review-sidebyside.html").read_text()
check("32 a side-by-side page shows original and scrubbed with highlights", "Jordan Lee" in html_page and "<mark>" in html_page and 'class="flag"' in html_page)

# ---- publish ----
try: I.main(["publish", str(vault), "--approve", "S07"]); gated = False
except SystemExit as e: gated = "flags" in str(e)
check("33 a case with flags cannot be published by plain --approve", gated and not (I.DATA / "cases" / "S07.json").exists())
with redirect_stdout(io.StringIO()): I.main(["publish", str(vault), "--approve", "S12", "--approve-flagged", "S07"])
files = [p for p in I.DATA.rglob("*") if p.is_file()]
blob = "\n".join(p.read_text() for p in files)
check("34 approved copies reach data/", {p.name for p in files} >= {"S07.json", "S12.json", "S07__20261120-100000.md", "review_log_filled.csv"}, [p.name for p in files])
check("35 nothing in data/ contains a roster name", not re.search(r"Jordan|Alex|Rivera|Okafor|Sam\b|Sammy|Riley|Tanaka|Lee\b|\bJJ\b", blob), re.findall(r"Jordan|Alex|Rivera|Okafor|Sammy|Riley|Tanaka|Lee\b|\bJJ\b", blob))
check("36 an unapproved case is not published", "S99" not in blob)

# ---- the feedback run keeps drafts in the vault ----
import subprocess
calls = []
real_run = subprocess.run
subprocess.run = lambda argv, **k: (calls.append(argv), type("R", (), {"returncode": 0})())[1]
try:
    I.main(["run", str(vault)])
finally:
    subprocess.run = real_run
check("37 run sends outputs to a folder inside the vault", calls and "--out" in calls[0] and calls[0][calls[0].index("--out") + 1] == str(vault / "outputs") and calls[0][2] == str(vault / "cases"), calls)

# ---- delete: key first, then everything ----
unlinked = []
orig_unlink = Path.unlink
Path.unlink = lambda self, *a, **k: (unlinked.append(self.name), orig_unlink(self, *a, **k))[1]
import builtins; builtin_input = builtins.input; builtins.input = lambda prompt="": "wrong name"
with redirect_stdout(io.StringIO()): rc = I.main(["delete", "--vault", str(vault)])
check("38 a wrong confirmation leaves the vault alone, but data/ is cleared", rc == 1 and (vault / "key.csv").exists() and not I.DATA.exists())
builtins.input = lambda prompt="": "StudentVault"
with redirect_stdout(io.StringIO()): rc = I.main(["delete", "--vault", str(vault)])
Path.unlink = orig_unlink; builtins.input = builtin_input
check("39 confirming empties the vault, deleting the key first", rc == 0 and unlinked and unlinked[0] == "key.csv" and not list(vault.iterdir()), (unlinked[:3], list(vault.iterdir())))
check("40 the repo's real data/ folder was never touched or created", not (I.REPO / "data").exists())
print(f"{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
