"""earmaster_review_log.py: two rows per case, repeated columns filled, no overwrite. Invented cases only."""
import csv, json, sys, tempfile
from pathlib import Path
from _common import APPDIR
sys.path.insert(0, APPDIR)
import earmaster_review_log as R
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))
tmp = Path(tempfile.mkdtemp(prefix="sf-rlog-"))
(tmp / "S01.json").write_text(json.dumps({"case_id": "S01", "prompts_answered": 5, "prompts_on_page": 7}))
(tmp / "S02.json").write_text(json.dumps({"case_id": "S02"}))
out = tmp / "log.csv"
R.main([str(tmp), "--out", str(out)])
rows = list(csv.reader(open(out)))
h = rows[0]
check("1 header has the proposal's checklist columns", [c.split(" ")[0] for c in h] == ["case_id", "method", "prompts_answered", "accurate_to_data", "factual_errors", "linked_to_student_goal", "one_concrete_next_practice_step", "levels_targeted", "person_level_praise_present", "data_named", "what_shingo_changed", "review_minutes", "coding_minutes", "verdict"], h)
check("2 two rows per case, AI then rules", [(r[0], r[1]) for r in rows[1:]] == [("S01", "AI"), ("S01", "rules"), ("S02", "AI"), ("S02", "rules")], rows[1:])
check("3 prompts answered is filled from the coded fields", rows[1][2] == rows[2][2] == "5/7")
check("4 a case without coded fields is left blank, not guessed", rows[3][2] == "" and rows[4][2] == "")
check("5 every other column starts empty", all(c == "" for r in rows[1:] for c in r[3:]))
try: R.main([str(tmp), "--out", str(out)]); kept = False
except SystemExit: kept = True
check("6 an existing log is never overwritten", kept)
print(f"{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
