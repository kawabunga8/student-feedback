"""Read-only: the file names each student attached to one Teams assignment ('Student Work' in the grading panel).

Opens each student's panel from the roster's To return tab, reads the attachment list's names, closes the panel. Nothing is typed,
returned or changed; the files themselves are not opened or downloaded. Output: one JSON line {"ok", "students": [{name, status, attachments}]}.
Request on stdin: {"class", "title", "students": ["Chan, Joshua", ...]}.
"""
import json
import sys
import time
import teams_read as T
import teams_batch as B


def attachments_of(panel):
    tabs = panel.get_by_role("tablist", name="Attachment")
    if tabs.count() == 0:
        return []
    return [l.strip() for l in tabs.first.inner_text().splitlines() if l.strip()]


def run(req, emit):
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(T.TEAMS, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            s = T.Session(page, 60); s.t0 = time.time()
            _, _, ids = s.open_one(req["class"], req["title"])
            B.show_tab(s.frame(), page, "To return")
            for i, name in enumerate(req["students"]):
                f = s.frame()
                try:
                    panel, _editor, _sid, _existing = B.open_panel(page, f, {"source": ids}, {"target_name": name}, i == 0)
                    page.wait_for_timeout(1200)
                    emit({"name": name, "attachments": attachments_of(panel)})
                    B.close_panel(page, B.s_frame(page, f))
                except Exception as e:
                    emit({"name": name, "error": type(e).__name__ + ": " + str(e)[:120]})
                    try:
                        f = s.frame()
                        if f.get_by_role("button", name=B.re.compile(r"^close( viewer)?$", B.re.I)).count():
                            B.close_panel(page, f)
                    except Exception:
                        pass
        finally:
            ctx.close()


def main():
    try:
        run(json.loads(sys.stdin.readline()), lambda m: print(json.dumps(m, ensure_ascii=False), flush=True))
        print(json.dumps({"ok": True}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": type(e).__name__ + ": " + str(e)[:200]}), flush=True)


if __name__ == "__main__":
    main()
