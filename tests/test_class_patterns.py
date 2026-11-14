"""Checks for class_patterns.py on invented rows. No model, no files, no student data.   python3 tests/test_class_patterns.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import class_patterns as cp

CRIT = ["clear claim", "at least two supporting reasons", "evidence", "concluding sentence"]
failed = 0
n = 0


def check(name, ok, detail=""):
    global failed, n
    n += 1
    failed += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + f"{n} {name}" + (f"  | {detail}" if detail else ""))


# Ten invented students: everyone has a claim, 8 of 10 lack evidence, 3 of 10 lack a conclusion.
rows = []
for i in range(10):
    done = ["clear claim", "at least two supporting reasons"]
    missing = []
    (missing if i < 8 else done).append("evidence")
    (missing if i < 3 else done).append("concluding sentence")
    rows.append({"done": done, "missing": missing})
s = cp.summarize(rows, CRIT)
by = {c["criterion"]: c for c in s["criteria"]}
check("counts met and not met", by["evidence"]["met"] == 2 and by["evidence"]["not_met"] == 8, by["evidence"])
check("percent not met", by["evidence"]["percent_not_met"] == 80 and by["concluding sentence"]["percent_not_met"] == 30)
check("a criterion everyone met is 0% not met", by["clear claim"]["not_met"] == 0 and by["clear claim"]["percent_not_met"] == 0)
check("teacher's order is kept in the summary", [c["criterion"] for c in s["criteria"]] == CRIT)
check("not suppressed with ten students", s["suppressed"] is False and s["students"] == 10)

md = cp.render_markdown(s, title="Task 2")
check("report lists most-often-unmet first", md.index("| evidence |") < md.index("| concluding sentence |") < md.index("| clear claim |"))
check("report says it needs teacher review and sets no levels", "Review it before using or sharing it" in md and "does not set levels" in md)

# Small class: nothing is reported.
small = cp.summarize(rows[:4], CRIT)
check("fewer than five students: all counts hidden", small["suppressed"] and all(c["met"] is None for c in small["criteria"]))
check("small-class report has no table", "| Criterion |" not in cp.render_markdown(small) and "Too few students" in cp.render_markdown(small))

# Mixed: one criterion only checked for 3 students is hidden, the rest still show.
mixed = [dict(r) for r in rows]
for r in mixed[3:]:
    r["done"] = [c for c in r["done"] if c != "concluding sentence"]
    r["missing"] = [c for c in r["missing"] if c != "concluding sentence"]
m = cp.summarize(mixed, CRIT)
mb = {c["criterion"]: c for c in m["criteria"]}
check("a criterion with too few checked students is hidden on its own",
      mb["concluding sentence"]["met"] is None and mb["concluding sentence"]["checked"] == 3 and mb["evidence"]["met"] == 2)
check("mixed report names the hidden criterion", "Hidden because fewer than 5" in cp.render_markdown(m) and "concluding sentence" in cp.render_markdown(m))

# Students with no checklist are not counted, and a self-contradicting record is ignored.
odd = rows + [{"done": [], "missing": []}, {}, {"done": ["evidence"], "missing": ["evidence"]}]
o = cp.summarize(odd, CRIT)
ob = {c["criterion"]: c for c in o["criteria"]}
check("unchecked and contradictory rows leave counts unchanged", ob["evidence"]["checked"] == 10 and o["students"] == 13)

# Wording differences in case and punctuation still match.
loose = cp.summarize([{"done": ["Clear Claim."], "missing": []}] * 5, ["clear claim"])
check("matching ignores case and punctuation", loose["criteria"][0]["met"] == 5)

# The result carries criteria and numbers only, nothing else from the rows.
extra = [dict(r, name="Invented Student", work="invented work text") for r in rows]
blob = repr(cp.summarize(extra, CRIT)) + cp.render_markdown(cp.summarize(extra, CRIT))
check("names and work text never reach the output", "Invented Student" not in blob and "invented work" not in blob)

print(f"\n{n - failed}/{n} passed")
sys.exit(1 if failed else 0)
