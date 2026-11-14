"""One Chrome session that collects everything outside OneNote for one Teams assignment.

Usage (from the repo folder, tools venv):
  python skills/assignment-followup/scripts/assignment_collect.py OUT_DIR REQUEST.json
REQUEST.json: {"class": "RCS - H - Q1 ICT 9 [2026-27]", "title": "Task 3: Prototype & Test",
               "students": ["Chan, Joshua", ...], "tabs": ["To return", "Returned"],
               "codeorg": {"section": "6708169", "lesson_url": "https://studio.code.org/courses/.../sublevel/5"}}   # codeorg optional
Writes OUT_DIR/attachments.json (per student: attachment names, popups with url + text, downloaded Word text) and
OUT_DIR/codeorg.json (per roster student: code length, last saved), plus screenshots in OUT_DIR/shots/.
Read-only: nothing is typed, returned or changed. Sign-in problems stop the run with a clear message (never enter passwords).
"""
import base64, json, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))      # the repo folder
import teams_read as T
import teams_batch as B
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); (out / "shots").mkdir(exist_ok=True)
req = json.loads(Path(sys.argv[2]).read_text())
safe = lambda s: re.sub(r"\W+", "_", s)
GET_DOCX = """async () => { const u = new URL(location.href); u.searchParams.set('download','1');
  const r = await fetch(u.toString(), {credentials:'include'}); const b = new Uint8Array(await r.arrayBuffer());
  let s=''; for (let i=0;i<b.length;i+=8192) s+=String.fromCharCode.apply(null,b.subarray(i,i+8192)); return r.status+':'+btoa(s); }"""


def read_popup(ctx, pg, name, k):
    """Text of an opened attachment page. Word on SharePoint is downloaded and converted; others are screenshotted."""
    pg.wait_for_function("document.readyState==='complete'", timeout=20000)
    pg.wait_for_timeout(4000)
    item = {"url": pg.url[:300]}
    pg.screenshot(path=str(out / "shots" / f"{safe(name)}_{k}.png"))
    if "sharepoint.com" in pg.url:
        st, _, data = pg.evaluate(GET_DOCX).partition(":")
        raw = base64.b64decode(data)
        if raw[:2] == b"PK":
            f = out / f"{safe(name)}_{k}.docx"; f.write_bytes(raw)
            item["word_text"] = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(f)], capture_output=True, text=True).stdout
    else:
        item["page_text"] = pg.evaluate("document.body.innerText")[:6000]      # Canva/Google render on canvas: rely on the screenshot
    return item


def attachments(page, ctx):
    s = T.Session(page, 60); s.t0 = time.time()
    _, _, ids = s.open_one(req["class"], req["title"])
    res = {}
    for tab in req.get("tabs", ["To return"]):
        B.show_tab(s.frame(), page, tab)
        for i, name in enumerate(req["students"]):
            f = s.frame()
            try:
                panel, _e, _sid, _x = B.open_panel(page, f, {"source": ids}, {"target_name": name}, i == 0)
            except Exception:
                continue                                              # this student is on the other tab
            page.wait_for_timeout(1200)
            tabs = panel.get_by_role("tablist", name="Attachment")
            rec = res.setdefault(name, {"status": panel.inner_text()[:400], "attachments": []})
            for k in range(tabs.first.get_by_role("tab").count() if tabs.count() else 0):
                item = tabs.first.get_by_role("tab").nth(k)
                label = item.inner_text().strip()
                try:
                    with ctx.expect_page(timeout=6000) as np:
                        item.click()
                    pg = np.value
                    entry = {"name": label, **read_popup(ctx, pg, name, k)}; pg.close()
                except Exception:                                     # opens inside the panel (Word editor frame, Class Notebook add-in)
                    page.wait_for_timeout(5000)
                    entry = {"name": label, "inline": [fr.url[:120] for fr in page.frames if "wordeditor" in fr.url or "classnotebook" in fr.url]}
                    for fr in page.frames:
                        if "wordeditorframe" in fr.url:
                            entry["word_text"] = fr.locator("body").inner_text(timeout=8000)
                rec["attachments"].append(entry)
            B.close_panel(page, B.s_frame(page, f))
    (out / "attachments.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


def codeorg(page):
    cfg = req["codeorg"]
    page.goto(f"https://studio.code.org/teacher_dashboard/sections/{cfg['section']}/progress", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    if "sign_in" in page.url or page.locator("input[type=password]").count():
        raise SystemExit("Code.org needs a sign-in: ask the teacher to sign in in the app's Chrome window, then run again.")
    roster = json.loads(page.evaluate(f"async()=>await (await fetch('/dashboardapi/sections/{cfg['section']}/students',{{credentials:'include'}})).text()"))
    rows = []
    for s in roster:
        page.goto(f"{cfg['lesson_url']}?section_id={cfg['section']}&user_id={s['id']}", wait_until="domcontentloaded")
        try: page.wait_for_function("window.appOptions && window.appOptions.level && String(window.appOptions.level.lastAttempt||'').length>0", timeout=9000)   # code arrives after the page shell
        except Exception: pass                                      # an empty project never gets code: bounded wait, then it counts as empty
        r = page.evaluate("""()=>{const o=window.appOptions||{}; const la=String((o.level&&o.level.lastAttempt)||''); const m=document.body.innerText.match(/(Saved[^\\n]*)/);
          return {channel:o.channel||'', code_chars:la.length, saved:m?m[1]:'', setScreens:(la.match(/setScreen/g)||[]).length}}""")
        rows.append({"codeorg_name": s["name"], "id": s["id"], **r})
    (out / "codeorg.json").write_text(json.dumps(rows, indent=1))


with T.BrowserLock(), sync_playwright() as p:
    ctx = T._launch(p)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(4000)
        attachments(page, ctx)
        if req.get("codeorg"): codeorg(page)
    finally:
        ctx.close()
print("done", out)
