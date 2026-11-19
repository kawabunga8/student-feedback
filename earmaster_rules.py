"""Apply Shingo's if/then rules (earmaster_rules.csv) to the made-up cases, beside the newest AI draft. No model, no network.

    python3 earmaster_rules.py earmaster_cases/ [--rules earmaster_rules.csv]
"""
import argparse
import csv
import operator
import re
import sys
from datetime import datetime
from pathlib import Path

from earmaster_cases import load_folder

HERE = Path(__file__).parent
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne}


def fields(case):
    f = dict(case)
    f["accuracy_change"] = case["accuracy_latest_pct"] - case["accuracy_first_pct"]
    f["lessons_completed_count"] = len(case["lessons_completed"])
    f["self_chosen_count"] = len(case["self_chosen_exercises"])
    f.setdefault("first_mate_note", "")
    return f


def holds(f, field, op, value):
    if not field:
        return True  # an empty condition never blocks the rule
    if field not in f:
        raise ValueError(f"unknown field '{field}'")
    have = f[field]
    if op == "contains":
        return value.strip().lower() in str(have).lower()
    if op not in OPS:
        raise ValueError(f"unknown operator '{op}'")
    return OPS[op](have, type(have)(value)) if isinstance(have, (int, float)) else OPS[op](str(have), value)


def load_rules(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8", newline="")))
    return [r for r in rows if not r["status"].strip().upper().startswith(("EXAMPLE", "OFF"))]


def apply(rules, case):
    f, out = fields(case), []
    for r in rules:
        try:
            if all(holds(f, r[f"condition_{n}_field"].strip(), r[f"condition_{n}_operator"].strip(), r[f"condition_{n}_value"]) for n in (1, 2)):
                out.append((r["rule_id"], r["message_to_student"].format_map(f)))
        except (ValueError, KeyError) as e:
            out.append((r["rule_id"], f"[RULE ERROR: {e}]"))
    return out


def newest_ai(out_dir, case_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)
    files = sorted(out_dir.glob(f"{safe}__*.md"))
    return files[-1].read_text(encoding="utf-8").split("---\n", 2)[-1].strip() if files else "(no AI draft yet: run earmaster_feedback.py first)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", type=Path)
    ap.add_argument("--rules", type=Path, default=HERE / "earmaster_rules.csv")
    ap.add_argument("--out", type=Path, default=HERE / "earmaster_outputs")
    a = ap.parse_args()
    if not a.rules.exists():
        sys.exit(f"No {a.rules.name} yet. Copy earmaster_rules_template.csv to {a.rules.name} and write your rules.")
    rules = load_rules(a.rules)
    if not rules:
        sys.exit("No live rules found (example rows are skipped). Add your rules first.")
    parts = [f"# Rule-based vs AI comparison ({datetime.now().astimezone().isoformat(timespec='seconds')}, {len(rules)} rules)\n"]
    for case in load_folder(a.cases):
        fired = apply(rules, case)
        parts.append(f"## {case['case_id']}\n\n**Rule-based** (" + (", ".join(i for i, _ in fired) or "no rule fired") + ")\n\n"
                     + ("\n".join(f"- {m}" for _, m in fired) or "_nothing sent_") + f"\n\n**AI draft (newest)**\n\n{newest_ai(a.out, case['case_id'])}\n")
    a.out.mkdir(exist_ok=True)
    dest = a.out / f"comparison_{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    dest.write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts)); print(f"Saved {dest}")


if __name__ == "__main__":
    main()
