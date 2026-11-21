"""Start a review log: two rows per case (one for the AI draft, one for the rules), with the repeated columns filled in.

    python3 earmaster_review_log.py earmaster_cases/                       (writes earmaster_review_log.csv here)
    python3 earmaster_review_log.py /Volumes/StudentVault/cases --out /Volumes/StudentVault/review_log.csv   (real cases: keep it in the vault)

Fills case_id, method and, if the case has the coded fields prompts_answered and prompts_on_page, "prompts answered" (e.g. 5/7).
You fill in the rest by hand. Columns follow earmaster_review_log_template.csv. Will not overwrite an existing file.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "earmaster_review_log_template.csv"
METHODS = ["AI", "rules"]


def prompts_text(case):
    a, n = case.get("prompts_answered"), case.get("prompts_on_page")
    return f"{a}/{n}" if isinstance(a, int) and isinstance(n, int) and not isinstance(a, bool) and not isinstance(n, bool) else ""


def rows_for(cases, header):
    out = []
    for case in cases:
        for m in METHODS:
            row = dict.fromkeys(header, "")
            row[header[0]], row[header[1]], row[header[2]] = case["case_id"], m, prompts_text(case)
            out.append([row[h] for h in header])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", type=Path, help="folder of case .json files")
    ap.add_argument("--out", type=Path, default=HERE / "earmaster_review_log.csv")
    a = ap.parse_args(argv)
    paths = sorted(a.cases.glob("*.json"))
    if not paths:
        sys.exit(f"No .json cases in {a.cases}")
    if a.out.exists():
        sys.exit(f"{a.out} already exists; not overwriting it. Pass --out with another name.")
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    header = next(csv.reader(open(TEMPLATE, newline="", encoding="utf-8")))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows_for(cases, header))
    print(f"Wrote {a.out} with {2 * len(cases)} rows ({len(cases)} cases x AI and rules).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
