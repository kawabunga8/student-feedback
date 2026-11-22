#!/usr/bin/env python3
"""Download the video files students attached to one Teams assignment to a local folder.

Read-only on Teams: it opens each student's submission panel, finds attachments whose names end in a video extension, and uses
each attachment's own Download menu item. It never types, grades, saves or Returns, and it never opens a file's contents.
Uses the same signed-in Chrome profile and lock as the app's Teams readers, so close any other Teams browser job first.
Existing files are skipped, so it can be re-run. Output: <dest>/<First Last>/<attachment name>.

  ~/.venvs/student-feedback-tools/bin/python tools/download_teams_videos.py \
      --class "RCS - B - Biblical Perspectives 10 [2026-27]" --title "Live Well Commercial: A Skit Assignment" \
      --dest ~/Desktop/Teaching/Live-Well-videos [--only "Jane Student"] [--dry-run] [--limit N]

--dry-run lists each student's attachments and which are videos, and downloads nothing.
Videos are large (one phone video was about 200 MB): check free disk space first. Students are saved only under --dest.
"""
import argparse, json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import teams_read as T
import teams_batch as B
import attachment_collect as A
from teams_post import display_name

VIDEO_EXT = (".mov", ".mp4", ".m4v", ".webm", ".avi", ".mkv")


def safe(part):
    part = re.sub(r"[\x00-\x1f/\\:]", "_", part).strip().strip(".")
    return part if part else "_"


def is_video(label):
    return label.strip().lower().endswith(VIDEO_EXT)


def roster_names(page, session, tab):
    """Student names (as the roster prints them) listed under one roster tab; None if the tab can't be read completely."""
    B.show_tab(session.frame(), page, tab)
    end = time.time() + 25
    while time.time() < end:
        got = T.parse_roster_students(session.text())
        if got["complete"]:
            return [r["name"] for r in got["students"]]
        page.wait_for_timeout(700)
    return None


def attachment_controls(panel):
    """Names of the attachments in the open panel (Teams draws one 'Attachment' list per file), plus every button name in
    the panel (dry-run diagnostics only)."""
    tabs = panel.get_by_role("tablist", name="Attachment").get_by_role("tab")
    labels = [tabs.nth(i).inner_text().strip() for i in range(tabs.count())]
    buttons = []
    for b in panel.get_by_role("button").all():
        try:
            n = (b.get_attribute("aria-label", timeout=800) or b.inner_text(timeout=800) or "").strip()
        except Exception:
            continue
        if n:
            buttons.append(re.sub(r"\s+", " ", n)[:70])
    return labels, buttons


def download_one(page, panel, label, target, wait=600):
    """Open this attachment's options menu, click Download, and save the file to target. Returns the saved size in bytes."""
    btn = panel.get_by_role("button", name="Open options for resource: " + label, exact=True)
    if btn.count() != 1:
        raise ValueError("options button not found exactly once")
    btn.click(timeout=8000)
    item = None
    end = time.time() + 8
    while item is None and time.time() < end:
        for fr in [page] + list(page.frames):
            loc = fr.get_by_role("menuitem", name=re.compile(r"^\s*Download\s*$", re.I))
            if loc.count() == 1:
                item = loc; break
        page.wait_for_timeout(300)
    if item is None:
        raise ValueError("no single Download item in the menu")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    with page.expect_download(timeout=wait * 1000) as dl:
        item.click(timeout=8000)
    dl.value.save_as(str(tmp))
    os.replace(tmp, target)
    return target.stat().st_size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--only", action="append", help="only this student, as 'First Last' (repeat for several)")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many students")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dest = Path(a.dest).expanduser()
    from playwright.sync_api import sync_playwright
    out = []
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(4000)
            session = T.Session(page, 60); session.t0 = time.time()
            for attempt in (1, 2, 3, 4, 5):          # the first click on the assignment row is sometimes missed: reload and retry
                try:
                    want, _t, ids = session.open_one(a.cls, a.title); break
                except T.ReadError as e:
                    if attempt == 5 or e.kind != "differs":
                        raise
                    page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(4000)
            req = {"source": ids}
            plan = []
            for tab in ("To return", "Returned"):
                names = roster_names(page, session, tab)
                if names is None:
                    raise T.ReadError("differs", f"The {tab} tab could not be read completely; nothing was downloaded.")
                plan += [(tab, n) for n in names]
            if a.only:
                want_names = {n.casefold() for n in a.only}
                plan = [x for x in plan if display_name(x[1]).casefold() in want_names]
            if a.limit:
                plan = plan[:a.limit]
            print(f"{len(plan)} students to check", flush=True)
            for tab, name in plan:
                who = display_name(name)
                st = {"target_name": name, "name": who, "student_id": who}
                try:
                    panel, _sub = A.open_student(page, session, req, st, tab)
                    labels, buttons = attachment_controls(panel)
                    vids = [l for l in labels if is_video(l)]
                    if a.dry_run:
                        print(f"{who}: attachments={labels} videos={vids}", flush=True)
                        if vids:
                            print("   panel buttons:", buttons[:30], flush=True)
                        continue
                    for label in vids:
                        target = dest / safe(who) / safe(label)
                        if target.exists() and target.stat().st_size > 0:
                            print(f"{who}: {label}: already saved, skipped", flush=True); continue
                        try:
                            size = download_one(page, panel, label, target)
                            print(f"{who}: {label}: saved {size/1e6:.0f} MB", flush=True)
                        except Exception as e:
                            print(f"{who}: {label}: FAILED ({type(e).__name__}: {str(e)[:120]})", flush=True)
                    if not vids:
                        print(f"{who}: no video attachment ({len(labels)} attachments)", flush=True)
                except T.ReadError:
                    raise
                except Exception as e:
                    print(f"{who}: could not open the submission ({type(e).__name__}: {str(e)[:120]})", flush=True)
                finally:
                    try:
                        f = session.frame()
                        if f.get_by_role("button", name=re.compile(r"^close( viewer)?$", re.I)).count():
                            B.close_panel(page, f)
                    except Exception:
                        pass
        finally:
            ctx.close()


if __name__ == "__main__":
    try:
        main()
    except T.ReadError as e:
        print(f"STOPPED ({e.kind}): {e}")
        for l in (getattr(e, "extra", {}) or {}).get("log", [])[-12:]:
            print("  ", l)
        sys.exit(1)
