"""R3 coded reflection fields: validator, rules, and the AI mode never sees them. Invented cases only."""
import copy, sys
from _common import APPDIR
sys.path.insert(0, APPDIR)
import earmaster_cases as C, earmaster_rules as R, earmaster_feedback as F
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))

BASE = {"case_id": "T01", "grade": 10, "lessons_completed": ["L1"], "self_chosen_exercises": [], "attempts_30d": 10, "active_days_30d": 4,
        "attempts_after_pass": 2, "accuracy_first_pct": 60, "accuracy_latest_pct": 80,
        "journal_entry": "Q1: What is your goal?\nA: Get my rhythm steadier.\nQ2: What will you practise?\nA: Clapping with the click."}
CODED = dict(BASE, goal_stated="yes", area_named="rhythm", prompts_answered=2, prompts_on_page=3)
def with_(**kw): c = copy.deepcopy(CODED); c.update(kw); return c

check("1 a case with no coded fields is still valid", C.validate(BASE) == [])
check("2 a case with all four coded fields is valid", C.validate(CODED) == [], C.validate(CODED))
check("3 area_named may be empty", C.validate(with_(area_named="")) == [])
check("4 goal_stated must be yes or no", any("goal_stated" in p for p in C.validate(with_(goal_stated="maybe"))))
check("5 prompts must be numbers, not text or true/false", C.validate(with_(prompts_answered="2")) != [] and C.validate(with_(prompts_answered=True)) != [])
check("6 the two prompt counts go together", any("go together" in p for p in C.validate(dict(BASE, prompts_answered=2))))
check("7 answered cannot exceed the prompts on the page", any("between" in p for p in C.validate(with_(prompts_answered=4))))
check("8 area_named must be short", any("short" in p for p in C.validate(with_(area_named="x" * 31))))

rules = [{"status": "", "rule_id": "r1", "condition_1_field": "goal_stated", "condition_1_operator": "==", "condition_1_value": "yes",
          "condition_2_field": "area_named", "condition_2_operator": "==", "condition_2_value": "rhythm", "message_to_student": "You named {area_named}."},
         {"status": "", "rule_id": "r2", "condition_1_field": "prompts_answered", "condition_1_operator": "<", "condition_1_value": "3",
          "condition_2_field": "", "condition_2_operator": "", "condition_2_value": "", "message_to_student": "Try all {prompts_on_page} prompts."}]
fired = [rid for rid, _ in R.apply(rules, CODED)]
check("9 the rules can test the coded fields", fired == ["r1", "r2"], R.apply(rules, CODED))
check("10 data from a coded field can go into the message", R.apply(rules, CODED)[0][1] == "You named rhythm.")
check("11 an uncoded case fires none of those rules and raises no error", R.apply(rules, BASE) == [], R.apply(rules, BASE))

facts, used = F.facts_block(CODED)
msgs, _ = F.build_messages(CODED)
sent = " ".join(m["content"] for m in msgs)
check("12 the facts the AI gets are identical with or without the codes", F.facts_block(BASE) == (facts, used))
check("13 the AI prompt is identical with or without the codes", F.build_messages(BASE)[0] == msgs)
check("14 none of the code names or values reach the AI prompt", not any(k in sent for k in ("goal_stated", "area_named", "prompts_answered", "prompts_on_page")))
check("15 each question label stays above its answer in what the AI reads", "Q1: What is your goal?\nA: Get my rhythm steadier." in sent)
print(f"{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
