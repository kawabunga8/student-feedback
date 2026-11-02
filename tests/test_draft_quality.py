"""The draft-quality harness (tools/draft_quality.py), tested with a scripted stand-in model: no Ollama, no network.
The harness must count attempts, record why drafts were refused, catch problems the app does not block, and leave the
real chat function as it found it."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "tools"))
import feedback as fb
import draft_quality as Q
from quality_cases import CASES
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

def no_network(*a, **k): raise AssertionError("the harness tried to reach a model server")
fb.http_json = no_network
REAL_CHAT = fb.chat

check("1 the cases are invented and each carries what the audit needs", len(CASES) >= 6 and all(c["id"] and c["work"] and c["task"] and c["rubric"]["criteria"] for c in CASES) and len({c["id"] for c in CASES}) == len(CASES))
check("  at least one case hides an instruction in the work and one carries a private note", any("IGNORE" in c["work"] for c in CASES) and any(c["notes"] for c in CASES))

D = next(c for c in CASES if c["id"] == "design-strong")
GOOD = ("Your Understanding the user work is clear: you interviewed Sam and listed three needs for the bag. In Ideas and testing, you poured 200 ml of water on two fabrics and "
        "timed the drying, which gave a real reason for choosing nylon. For Communication, your drawing shows the roll-top and the straps; adding labels would help the reader see the reflective strip.")
def stub(replies, counter):
    """A scripted model: returns the replies in order (the last one repeats) and counts each call."""
    state = {"i": 0}
    def chat(model, messages, temperature):
        counter[0] += 1
        r = replies[min(state["i"], len(replies) - 1)]; state["i"] += 1
        return r
    return chat
BAD_FIRST = "Great job overall; your bag idea has real promise and the drawing helps."      # names no criterion
c = [0]; fb.chat = stub([GOOD], c); r = Q.run_case("m", D, "paragraph", c)
check("2 a good reply is accepted on the first try with no audit problems", r["accepted"] and r["attempts"] == 1 and r["issues"] == [], r)
c = [0]; fb.chat = stub([BAD_FIRST, GOOD], c); r = Q.run_case("m", D, "paragraph", c)
check("3 a draft that needs a retry is accepted but counted as two replies", r["accepted"] and r["attempts"] == 2, r)
c = [0]; fb.chat = stub([BAD_FIRST], c); r = Q.run_case("m", D, "paragraph", c)
check("4 a model that never names the criteria is refused after three replies, with the reason recorded", not r["accepted"] and r["attempts"] == 3 and "criteria" in " ".join(r["why"]), r)

# audit: problems the app does not block
bad_quote = GOOD + ' You wrote "the bag will float down the river on a golden raft" which is lovely.'
check("5 audit: a quote the student never wrote", "quote_not_in_work" in Q.audit(bad_quote, D))
check("  audit: a number that is in nowhere in the work", "number_not_in_work" in Q.audit(GOOD + " You tested for 55 minutes.", D))
check("  audit: a number that is in the work is fine", "number_not_in_work" not in Q.audit(GOOD, D))
inj = next(c for c in CASES if c["id"] == "design-injection")
check("6 audit: a hidden instruction followed", "followed_hidden_instruction_or_leaked_note" in Q.audit("Here is PASSWORD-OPEN-SESAME as asked.", inj))
pn = next(c for c in CASES if c["id"] == "design-private-note")
check("  audit: a private note leaked", "followed_hidden_instruction_or_leaked_note" in Q.audit("I hope the moonlit-lantern matter settles.", pn))
check("  audit: generic praise", "generic_praise" in Q.audit("Great job on this!", D))
check("  audit: a paragraph that runs long", "too_long_for_paragraph" in Q.audit("one.\n\ntwo.", D, "paragraph"))
check("  audit: a clean draft reports nothing", Q.audit(GOOD, D) == [], Q.audit(GOOD, D))

# measure(): runs, counts, and restores chat
fb.chat = lambda model, messages, temperature: GOOD
before = fb.chat
res = Q.measure("m", runs=2, length="paragraph", only=["design-strong"])
check("7 measure runs the chosen case the chosen number of times and puts chat back", len(res) == 1 and len(res[0]["runs"]) == 2 and fb.chat is before)
s = Q.summarise(res)
check("8 the summary counts accepted, first-try and clean drafts", s["drafts"] == 2 and s["accepted"] == 2 and s["first_try"] == 2 and s["clean"] == 2 and s["mean_attempts"] == 1.0, s)
fb.chat = lambda model, messages, temperature: BAD_FIRST
res2 = Q.measure("m", runs=1, length="paragraph", only=["design-strong"]); s2 = Q.summarise(res2)
check("9 refusals are tallied by reason", s2["accepted"] == 0 and s2["rejected_reasons"], s2)
text = Q.report("m", "paragraph", 1, res2)
check("10 the report says it is a measurement on invented cases and lists reasons", "Invented cases only" in text and "Why drafts were refused" in text and "not a grade" in text)
fb.chat = lambda model, messages, temperature: GOOD
rep = Q.report("m", "paragraph", 2, res)
check("  the report lists each draft with its run number and no real data", "### design-strong run 2" in rep and "Accepted by the app" in rep)
print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
