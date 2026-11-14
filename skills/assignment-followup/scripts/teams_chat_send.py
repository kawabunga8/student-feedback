"""Send approved Teams chat messages, one chat per student, through Teams web in the app's signed-in Chrome.

Usage (from the repo folder, tools venv):
  python skills/assignment-followup/scripts/teams_chat_send.py PLAN.json RESULT.json
PLAN.json: [{"name": "First Last", "messages": ["first paragraph", "second paragraph"]}, ...]
This is a write operation. Run it only on a plan the teacher has approved line by line (recipients and exact text).
Safety: a student is messaged only when exactly one directory result is a *Student* with exactly that name; the full approved text
must appear one more time in the page after sending (a new message, not an older one); a send that cannot be confirmed is reported
as UNVERIFIED and is NEVER repeated automatically. Results: SENT / SKIPPED (why) / UNVERIFIED / ERROR.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import teams_read as T
from playwright.sync_api import sync_playwright

plan = json.loads(Path(sys.argv[1]).read_text())
for item in plan:
    if not item.get("name") or not item.get("messages") or not all(isinstance(m, str) and m.strip() for m in item["messages"]):
        raise SystemExit("Bad plan entry: " + json.dumps(item)[:120])
TO_BOX = "Enter name, chat, channel, email or tag"
res = {}


def count(page, text):
    return page.inner_text("body").count(text)


with T.BrowserLock(), sync_playwright() as p:
    ctx = T._launch(p)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://teams.microsoft.com/v2/", wait_until="domcontentloaded")
        page.get_by_role("button", name=re.compile(r"^Chat", re.I)).first.wait_for(timeout=45000)
        page.get_by_role("button", name=re.compile(r"^Chat", re.I)).first.click()
        for item in plan:
            name, msgs = item["name"], item["messages"]
            try:
                page.get_by_role("button", name="New message").first.click(timeout=8000)
                box = page.get_by_placeholder(TO_BOX).first
                box.click(timeout=8000)
                page.keyboard.type(name, delay=15)
                try: page.get_by_role("option").first.wait_for(timeout=8000)                  # wait for results, not a fixed pause
                except Exception: pass
                page.wait_for_timeout(800)                                                  # let the list stop changing
                texts = page.evaluate("[...document.querySelectorAll('[role=option]')].map(o => o.innerText)")
                good = [x for x in texts if x.split("\n")[0].strip().lower() == name.lower() and "student" in x.lower()]
                if len(good) != 1:
                    res[name] = "SKIPPED: " + str([x.replace("\n", " / ")[:60] for x in texts])
                    page.keyboard.press("Escape"); print(name, res[name], flush=True); continue
                page.get_by_role("option").filter(has_text=good[0].split("\n")[0].strip()).first.click()
                compose = page.get_by_role("textbox", name=re.compile(r"type a message", re.I)).last
                compose.wait_for(timeout=8000); compose.click()
                probes = [m.strip() for m in msgs]
                before = [count(page, m) for m in probes]
                for i, m in enumerate(msgs):
                    if i: page.keyboard.press("Shift+Enter"); page.keyboard.press("Shift+Enter")
                    page.keyboard.insert_text(m)
                page.keyboard.press("Enter")
                try:
                    page.wait_for_function("([ts, bs]) => ts.every((t, i) => document.body.innerText.split(t).length - 1 > bs[i])", arg=[probes, before], timeout=12000)
                    res[name] = "SENT"
                except Exception:
                    res[name] = "UNVERIFIED: the approved text did not appear as a new message; check the chat by hand, do not resend blindly"
            except Exception as e:
                res[name] = "ERROR " + type(e).__name__ + " " + str(e)[:80]
            print(name, res[name], flush=True)
    finally:
        ctx.close()
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
