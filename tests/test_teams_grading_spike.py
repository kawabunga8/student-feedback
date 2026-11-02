"""The read-only grading-panel spike: the report never holds student work, feedback text or the student's name; it describes
control names, roles and lengths. Synthetic panel served from memory; nothing contacts Teams."""
import json, os, subprocess, sys, tempfile
from _common import APPDIR, LAUNCH, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "tools"))
import spike_teams_grading_panel as S
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

check("1 every part of the name is masked, in any case", S.mask_names("Previous: Test, Alpha (alpha test)", "Test, Alpha") == "Previous: <student>, <student> (<student> <student>)")
check("  short fragments are left alone", S.mask_names("Go to my work", "Li Wu") == "Go to my work")
check("  short names are masked at word boundaries", S.mask_names("Previous: Li Wu; lines", "Li Wu") == "Previous: <student> <student>; lines")
PANEL = """<html><body><h2>Student work</h2>
<button aria-label="Previous student: Test, Alpha">‹</button><button>Next student</button>
<div id="fb" contenteditable="true" aria-label="Feedback">SECRET-FEEDBACK-TEXT written earlier for Alpha</div>
<input aria-label="Points" value=""><button aria-label="Feedback with Copilot" role="switch" aria-checked="false">Copilot</button>
<button>Return</button><button aria-haspopup="menu" aria-expanded="false" aria-label="More return options">v</button>
<p>SECRET-WORK-TEXT: the student's own writing about Alpha Test</p><button style="display:none">Hidden thing</button></body></html>"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); pg = b.new_page(); pg.set_content(PANEL)
    info = pg.evaluate(S.PANEL_JS)
    pg.set_content('<div contenteditable="true">PRIVATE-UNLABELLED-FEEDBACK</div><textarea>PRIVATE-TEXTAREA</textarea><input value="PRIVATE-INPUT">')
    private = S.safe_report(pg.evaluate(S.PANEL_JS), "Li Wu", "/masked")
    check("  unlabelled fields report no feedback or input values", "PRIVATE" not in json.dumps(private) and all(not e['label'] for e in private['editors']) and not private['inputs'][0]['label'])
    b.close()
rep = S.safe_report(info, "Test, Alpha", "/classes/<id>/assignment-review/<id>/grade")
blob = json.dumps(rep)
check("2 the report has no student work, no feedback text and no student name", "SECRET" not in blob and "Alpha" not in blob and "Test" not in blob.replace("test", "").replace("Test, ", ""), blob[:200])
check("  the name is masked in control names", any(x["name"].startswith("Previous student: <student>") for x in rep["buttons"]), [x["name"] for x in rep["buttons"]])
check("  the Feedback editor is described by kind, label and LENGTH only", rep["editors"] == [{"kind": "div[contenteditable]", "role": "", "label": "Feedback", "text_length": len("SECRET-FEEDBACK-TEXT written earlier for Alpha"), "placeholder": ""}] , rep["editors"])
check("  hidden elements are not reported", all(x["name"] != "Hidden thing" for x in rep["buttons"]))
f = S.summarise(rep)
check("3 the findings name what the posting design depends on", f["feedback_editors"] == 1 and f["feedback_editor_empty"] is False and f["return_buttons"] == ["Return"] and f["copilot_controls"] and f["points_controls"] and len(f["move_between_students"]) == 2, f)
check("  an extra return-related control (the dropdown) is listed separately", "More return options" in f["other_return_controls"] and "Return" in f["other_return_controls"], f["other_return_controls"])
check("  an empty box is reported as empty", S.summarise({"buttons": [], "editors": [{"text_length": 0, "label": "", "placeholder": "", "kind": "div"}], "inputs": [], "headings": [], "address_shape": ""})["feedback_editor_empty"] is True)
r = subprocess.run([sys.executable, os.path.join(APPDIR, "tools", "spike_teams_grading_panel.py"), "--class", "C", "--title", "T", "--student", "Test, Alpha"], capture_output=True, text=True, env={**os.environ, "SF_FORBID_BROWSER": "1"})
out = json.loads(r.stdout.strip().splitlines()[-1])
check("4 with browser use switched off it refuses before opening anything (exit 3) and the message has no name", r.returncode == 3 and out["kind"] == "setup" and "Alpha" not in r.stdout, r.stdout[:150])
src = open(os.path.join(APPDIR, "tools", "spike_teams_grading_panel.py")).read()
check("5 the spike's source never types, fills or presses keys, and clicks only the one roster row", not any(w in src for w in (".fill(", ".type(", "keyboard", ".press(", "select_option", ".check(", "dispatch_event")) and src.count(".click(") == 1)
print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
