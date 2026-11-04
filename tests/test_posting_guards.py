"""Guards on the posting engines, with stand-in pages (no network, no browser):
  A. MySchool: levels chosen for the previewed criteria are never applied if the criteria changed order or names;
  B. Teams: the feedback read back after Return only counts when the panel is this assignment, this submission and this student;
  C. interrupted Teams batches (like every posting job) can never be resumed from the old request."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import app, myschool_batch as M, teams_batch as B, teams_post
from myschool_post import PilotError

ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:200]) if extra != "" else ""))

# ---- A
def crit(i, label, sel="0"):
    return {"input": f"grade_1_{i}", "selected": sel, "label": label, "options": [{"code": c, "value": v} for c, v in (("EMG", "1"), ("DEV", "2"), ("PRF", "3"), ("EXT", "4"))]}
def state(labels):
    return {"title": "T", "course": "C", "publication": "0",
            "students": [{"id": "77", "name": "Alex Example", "comment": "", "status": "1", "criteria": [crit(i, l) for i, l in enumerate(labels)]}]}
req = {"url": "https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=5", "mark_graded": False}
st0 = {"student_id": "s1", "wanted": ["Alex Example"], "codes": ["PRF", "EXT"], "comment": "Good."}
pv = M.preview_of(state(["Design", "Testing"]), st0, req)
check("A1 the preview records which criteria the levels are for", pv["criteria_identity"] == [["grade_1_0", "Design"], ["grade_1_1", "Testing"]], pv.get("criteria_identity"))

class Untouchable:
    def __getattr__(self, n): raise AssertionError("the page was used: " + n)
class Reached(Exception): pass
class PageThatStopsAtFirstUse:
    def locator(self, *a, **k): raise Reached()
save_st = {"student_id": "s1", "comment": "Good.", "preview": pv}
def try_save(now, page):
    M.open_assessment = lambda page_, r: now
    asked = []
    try: M.save_one(page, req, save_st, asked.append); return "returned", asked
    except PilotError as e: return str(e), asked
    except Reached: return "reached the page", asked
msg, asked = try_save(state(["Testing", "Design"]), Untouchable())
check("A2 criteria that swapped places since the preview: nothing is asked, nothing is touched", "criteria" in msg and "changed" in msg and not asked, msg)
msg, asked = try_save(state(["Design", "Testing (new)"]), Untouchable())
check("  a renamed criterion is refused too", "criteria" in msg and not asked, msg)
msg, asked = try_save(state(["Design", "Testing"]), PageThatStopsAtFirstUse())
check("A3 the same criteria in the same order go on to the write step", msg == "reached the page" and asked == ["s1"], (msg, asked))
old = dict(pv); old.pop("criteria_identity")
save_st["preview"] = old
msg, asked = try_save(state(["Design", "Testing"]), Untouchable())
check("A4 a preview made without the criteria binding is refused", "criteria" in msg and not asked, msg)

# ---- B
class Loc:
    def __init__(self, n=1, text="", on_click=None): self.n, self.text, self.on_click = n, text, on_click; self.first = self
    def count(self): return self.n
    def inner_text(self): return self.text
    def click(self, **k): self.on_click and self.on_click()
    def dispatch_event(self, *a): self.on_click and self.on_click()
    def wait_for(self, **k): pass
class Frame:
    def __init__(self, url, selected, text="Great work."): self.url, self.selected, self.text = url, selected, text
    def get_by_text(self, *a, **k): return Loc()
    def locator(self, *a, **k): return Loc()
    def get_by_role(self, role, name=None, **k):
        if role == "button" and name and name.startswith("Currently selected student"): return Loc(1 if name.endswith(self.selected) else 0)
        if role == "textbox": return Loc(1, self.text)
        return Loc()
class Mouse:
    def move(self, *a): pass
class Page:
    mouse = Mouse()
SRC = {"class_id": "b59530ab-3264-4f4f-8cbe-77b0c299bc1e", "assignment_id": "214d98a7-da63-4087-ac36-1656825b6180"}
SUB = "0f0f0f0f-aaaa-bbbb-cccc-111122223333"
def panel_url(sub=SUB, ids=SRC): return f"https://assignments.example/classes/{ids['class_id']}/assignment-review/{ids['assignment_id']}/submissions/{sub}"
B.show_tab = lambda *a, **k: None; B.on_tab = lambda *a, **k: True; B.close_panel = lambda *a, **k: None
def read_back(frame):
    B.s_frame = lambda page, f: frame
    return B.saved_feedback(Page(), frame, "Example, Alex", {"source": SRC}, SUB)
# display_name turns the roster's "Example, Alex" into "Alex Example"
check("B1 the right assignment, submission and student: the text is returned", read_back(Frame(panel_url(), "Alex Example")) == "Great work.")
check("B2 another student's panel is not accepted", read_back(Frame(panel_url(), "Blair Example")) is None)
check("B3 another submission is not accepted", read_back(Frame(panel_url(sub="ffffffff-aaaa-bbbb-cccc-111122223333"), "Alex Example")) is None)
check("B4 another assignment is not accepted", read_back(Frame(panel_url(ids={"class_id": SRC["class_id"], "assignment_id": "00000000-0000-0000-0000-000000000000"}), "Alex Example")) is None)

# ---- C
resumable = lambda t: not t.startswith(app.NOT_RESUMABLE)
check("C1 no Teams or MySchool posting job type can be resumed from its old request",
      not any(resumable(t) for t in ("teams_batch_save", "teams_batch_dry", "teams_batch_inspect", "teams_post_save", "myschool_batch_save", "myschool_save", "teams_create")))
check("  drafting and reading jobs still can", all(resumable(t) for t in ("draft", "teams_read", "onenote_read", "onenote_class")))

print(f"\n{sum(ok_all)}/{len(ok_all)} passed")
sys.exit(0 if all(ok_all) else 1)
