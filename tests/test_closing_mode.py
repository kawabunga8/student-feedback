"""End-of-term feedback: within a week of the term's last day (or after it) drafts only look back, with no next steps.
The model is a scripted stand-in; nothing contacts Course Hub, Teams or a real model. All names and wording are invented."""
import datetime as dt, os, sys, tempfile
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, feedback as fb, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))

fb.http_json = lambda *a, **k: (_ for _ in ()).throw(AssertionError("tried to reach a model server"))
END = dt.date(2026, 11, 13)

# 1 the date rule
D = lambda n: END - dt.timedelta(days=n)
check("1 normal wording well before the term ends", not fb.is_closing("2026-11-13", D(30)) and not fb.is_closing("2026-11-13", D(8)))
check("  end-of-term wording from 7 days before, on the last day, and after it", fb.is_closing("2026-11-13", D(7)) and fb.is_closing("2026-11-13", END) and fb.is_closing("2026-11-13", END + dt.timedelta(days=20)))
check("  an unreadable or missing date means normal wording", not fb.is_closing("") and not fb.is_closing("soon") and not fb.is_closing(None))

# 2 the prompt
normal, closing = fb.system_prompt("paragraph", "Grade 9"), fb.system_prompt("paragraph", "Grade 9", closing=True)
check("2 the normal prompt still asks for a next step and one thing to try", "next step" in normal and "one small thing to try" in normal and "END OF TERM" not in normal)
check("  the end-of-term prompt forbids advice and replaces the forward format", "END OF TERM" in closing and "NO next steps" in closing and "one small thing to try" not in closing and "what the work did not yet show" in closing)
det = fb.system_prompt("detailed", "Grade 9", closing=True)
check("  the detailed end-of-term format has Strengths and Not yet shown, and no Next steps or One thing to try heading", "**Not yet shown**" in det and "**Next steps** -" not in det and "**One thing to try** -" not in det)

# 3 the deterministic level sentence loses its forward half
lead_n, lead_c = fb.level_line("Developing"), fb.level_line("Developing", closing=True)
check("3 the level sentence keeps its wording but drops 'To reach X'", "To reach" in lead_n and "To reach" not in lead_c and lead_c.startswith("This work is at the Developing level"), lead_c)

# 4 the advice check, ignoring quoted student text
check("4 advice wording is caught", {"next step", "try adding"} <= set(fb.forward_phrases("Your app works. The next step is to try adding a back button.")) and fb.forward_phrases("You should consider more screens.") != [])
check("  a purely backward-looking comment is clean", fb.forward_phrases("Your app has three working screens, and your reflection names the loop you built. The work did not show any client testing.") == [])
check("  quoted student words don't count", fb.forward_phrases('You wrote "next time I will add a timer", which shows planning.') == [])

# 5 generate(): a forward-looking draft is retried and a backward-looking one accepted
WORK = "I built a hockey app with three screens. I used a loop to move the target. I tested it with my brother."
FORWARD_REPLY = "You built three working screens and used a loop to move the target. The next step is to test with more clients. Try adding a score screen."
BACK_REPLY = "You built three working screens and used a loop to move the target, which shows a working use of repetition. Your testing was with one person. The work did not show how the feedback changed the app."
seen = []
def stub(replies):
    state = {"i": 0}
    def chat(model, messages, temperature):
        seen.append(messages); r = replies[min(state["i"], len(replies) - 1)]; state["i"] += 1; return r
    return chat
REAL = fb.chat
try:
    fb.chat = stub([FORWARD_REPLY, BACK_REPLY]); seen.clear()
    out = fb.generate("m", "Assignment: build an app.", "Grade 9", "student", WORK, closing=True)
    check("5 an end-of-term draft with advice is retried once, then the backward-looking one is used", len(seen) == 2 and out.startswith("You built three working screens") and "next step" not in out.lower(), out)
    check("  the retry names the problem, and the system prompt carried the end-of-term rule", "gives advice" in seen[1][1]["content"] and "END OF TERM" in seen[0][0]["content"])
    fb.chat = stub([FORWARD_REPLY]); seen.clear()
    out = fb.generate("m", "Assignment: build an app.", "Grade 9", "student", WORK, closing=True)
    check("  a model that keeps giving advice is still accepted after three tries (advice is a soft rule, not a refusal)", len(seen) == 3 and isinstance(out, str) and out)
    fb.chat = stub([FORWARD_REPLY]); seen.clear()
    out = fb.generate("m", "Assignment: build an app.", "Grade 9", "student", WORK)
    check("  normal mode is unchanged: advice is expected and accepted on the first try", len(seen) == 1 and "next step" in out.lower() and "END OF TERM" not in seen[0][0]["content"])
    DET = "**Strengths**\nYou built three screens.\n\n**Not yet shown**\nThe work did not show any client testing."
    fb.chat = stub([DET]); seen.clear()
    out = fb.generate("m", "Assignment: build an app.", "Grade 9", "student", WORK, length="detailed", closing=True)
    check("6 detailed end-of-term drafts keep both headings", len(seen) == 1 and "**Strengths**" in out and "**Not yet shown**" in out and "Next steps" not in out, out)
    fb.chat = stub([BACK_REPLY]); seen.clear()
    out = fb.generate("m", "Assignment: build an app.", "Grade 9", "student", WORK, level="Developing+", closing=True)
    check("7 with a teacher level, the opening sentence has no 'To reach' line", out.startswith("This work is at the Developing+ level") and "To reach" not in out, out)
finally:
    fb.chat = REAL

# 8 the app picks the mode from the saved quarter dates
app.course_data = lambda: {"quarters": [{"label": "Q1", "start": "2026-09-08", "end": "2026-11-13"}, {"label": "Q2", "start": "2026-11-16", "end": "2027-01-29"}]}
check("8 the app uses end-of-term wording for Q1 on Nov 10, not for Q2", app.term_is_closing("Q1", dt.date(2026, 11, 10)) and not app.term_is_closing("Q2", dt.date(2026, 11, 10)))
check("  an unknown term, a blank term, or a failed course lookup means normal wording", not app.term_is_closing("Q9", END) and not app.term_is_closing("", END))
def boom(): raise RuntimeError("down")
app.course_data = boom
check("  Course Hub being down never blocks drafting", app.term_is_closing("Q1", END) is False)

# 9 draft_for passes the flag through
captured = {}
app.course_data = lambda: {"quarters": [{"label": "Q1", "start": "2026-09-08", "end": "2026-11-13"}]}
app.fb.generate = lambda *a, **k: captured.update(k) or "ok"
app.term_is_closing = (lambda orig: (lambda label, today=None: orig(label, dt.date(2026, 11, 10))))(app.term_is_closing)
app.draft_for({"model": "m", "rubric": "Assignment: x.", "work": "w", "term": "Q1"})
check("9 draft_for hands closing=True to the generator for a term that is ending", captured.get("closing") is True, captured)

print(f"\n{sum(ok)}/{len(ok)} passed")
sys.exit(0 if all(ok) else 1)
