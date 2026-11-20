"""Test-case format for the EarMaster reflection feedback mode.

A case is one JSON file in a folder (default: earmaster_cases/). Cases are MADE-UP composites only:
never put a real student's name, journal text or records here.

Fields
  case_id                   short label, e.g. "sample-01" (no real names)
  grade                     9-12
  lessons_completed         list of assigned lesson names the student has passed
  self_chosen_exercises     list of exercises the student picked themselves
  attempts_30d              number of attempts in the last 30 days
  active_days_30d           number of days with any practice in the last 30 days
  attempts_after_pass       attempts made after a lesson was already passed
  accuracy_first_pct        accuracy % on the first attempt
  accuracy_latest_pct       accuracy % on the latest attempt
  journal_entry             the student's reflection text (made up)
  first_mate_note           optional check note (may be "")

There is deliberately NO practice-duration field: EarMaster's time logs are unreliable.
"""
import json
import sys
from pathlib import Path

REQUIRED = {
    "case_id": str, "grade": int, "lessons_completed": list, "self_chosen_exercises": list,
    "attempts_30d": int, "active_days_30d": int, "attempts_after_pass": int,
    "accuracy_first_pct": (int, float), "accuracy_latest_pct": (int, float), "journal_entry": str,
}
OPTIONAL = {"first_mate_note": str, "probe": str, "must_not_say": list}  # probe = a note to yourself on what this case tests (not sent to the model); must_not_say = words the draft must never contain (checked by code)
FORBIDDEN_HINTS = ("duration", "minutes", "time_spent", "practice_time")


def validate(case):
    """Return a list of problems (empty list = fine)."""
    problems = []
    for key, typ in REQUIRED.items():
        if key not in case:
            problems.append(f"missing field: {key}")
        elif not isinstance(case[key], typ) or isinstance(case[key], bool):
            problems.append(f"wrong type for {key}")
    for key in case:
        if key not in REQUIRED and key not in OPTIONAL:
            problems.append(f"unknown field: {key}" + (" (no practice durations: time logs are unreliable)"
                                                        if any(h in key.lower() for h in FORBIDDEN_HINTS) else ""))
    if not problems:
        if case["grade"] not in (9, 10, 11, 12):
            problems.append("grade must be 9, 10, 11 or 12")
        if case["active_days_30d"] > 30 or case["active_days_30d"] < 0:
            problems.append("active_days_30d must be 0-30")
        if case["attempts_after_pass"] > case["attempts_30d"]:
            problems.append("attempts_after_pass cannot exceed attempts_30d")
        for k in ("accuracy_first_pct", "accuracy_latest_pct"):
            if not 0 <= case[k] <= 100:
                problems.append(f"{k} must be 0-100")
    return problems


def load_case(path):
    case = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(case)
    if problems:
        raise ValueError(f"{Path(path).name}: " + "; ".join(problems))
    return case


def load_folder(folder):
    return [load_case(p) for p in sorted(Path(folder).glob("*.json"))]


if __name__ == "__main__":  # python3 earmaster_cases.py earmaster_cases/
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "earmaster_cases")
    bad = 0
    for p in sorted(folder.glob("*.json")):
        try:
            load_case(p)
            print(f"ok    {p.name}")
        except (ValueError, json.JSONDecodeError) as e:
            bad += 1
            print(f"FAIL  {e}")
    sys.exit(1 if bad else 0)
