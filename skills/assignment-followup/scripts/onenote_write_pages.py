"""Create a titled page with text in students' ClassNotebook sections, from an approved plan.

Usage (from the repo folder, tools venv):
  python skills/assignment-followup/scripts/onenote_write_pages.py PLAN.json OUT_DIR
PLAN.json: {"base": "<any notebook page address>", "section": "Homework", "title": "Task 3: Prototype & Test",
            "pages": [{"student": "First Last", "lines": ["note line", "text..."]}]}
This WRITES into students' notebooks. Run it only on a plan the teacher approved (students, title, text). It never deletes:
OneNote's Delete Page is permanent, so a mistaken duplicate is left for the teacher to remove.
Safety: the opened address must name this student and section; a student who already has a page with the title (or a
Task/Stage number match) is skipped; the section's page list must be stable before and after; a screenshot of each result is saved.
Lessons built in: edit mode needs action=edit; on a fresh page click the body area and use keyboard.type for the first line before
insert_text (otherwise text silently goes nowhere); the title is set last by clicking it at the top of the page.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import teams_read as T
import onenote_class as C
from playwright.sync_api import sync_playwright

plan = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
title, section = plan["title"], plan.get("section", "Homework")
num = re.search(r"\d+", title)
res = {}
with T.BrowserLock(), sync_playwright() as p:
    ctx = T._launch(p)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for item in plan["pages"]:
            name, lines = item["student"], [l.strip() for l in item["lines"] if l.strip()]
            try:
                f = C.open_section(page, plan["base"], name, section, lambda pg, u: None)
                if f is None or f == "nosection":
                    res[name] = "SKIPPED: no " + section + " section"; print(name, res[name], flush=True); continue
                page.goto(page.url.replace("action=view", "action=edit"), wait_until="domcontentloaded"); page.wait_for_timeout(8000)
                ident = C.resolved_identity(page.url)
                if not (ident and C.same_name(ident["student"], name) and C.same_name(ident["section"], section)):
                    res[name] = "SKIPPED: wrong section opened " + str(ident); print(name, res[name], flush=True); continue
                fr = C._frame(page); pages = C.list_pages(page, fr, name, section)
                if pages is None:
                    res[name] = "SKIPPED: page list did not settle"; print(name, res[name], flush=True); continue
                if any(C.norm_tokens(x) == C.norm_tokens(title) or (num and re.search(r"(task|stage|part)\s*" + num.group() + r"\b", x, re.I)) for x in pages):
                    res[name] = "SKIPPED: already has a matching page " + str(pages); print(name, res[name], flush=True); continue
                fr.get_by_role("button", name="Add page").first.click(); page.wait_for_timeout(5000)
                page.mouse.click(700, 300); page.wait_for_timeout(1000)
                page.keyboard.type(lines[0], delay=15); page.keyboard.press("Enter")
                for l in lines[1:]:
                    page.keyboard.insert_text(l); page.keyboard.press("Enter")
                page.mouse.move(800, 400); page.mouse.wheel(0, -20000); page.wait_for_timeout(800)
                page.mouse.click(600, 160); page.keyboard.type(title, delay=15); page.wait_for_timeout(3000)
                after = C.list_pages(page, C._frame(page), name, section)
                page.screenshot(path=str(out / (re.sub(r"\W+", "_", name) + ".png")))
                made = [x for x in (after or []) if C.norm_tokens(x) == C.norm_tokens(title)]
                res[name] = "WRITTEN: check the screenshot" if len(made) == 1 else "CHECK BY HAND: titles now " + str(after)
            except Exception as e:
                res[name] = "ERROR " + type(e).__name__ + " " + str(e)[:80]
            print(name, res[name], flush=True)
    finally:
        ctx.close()
(out / "result.json").write_text(json.dumps(res, indent=1))
