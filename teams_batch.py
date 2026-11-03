"""Teams posting in ONE browser session, for one student or a whole class.

The one-student pilot (teams_post.py) starts Chrome, loads Teams and finds the assignment for every student. This does that
once, then walks the roster: for each student it opens their panel, reads or writes the feedback, and moves on.
The safety rules are the pilot's, applied per student:
  * inspect_many only reads (existing feedback); a student already Returned is reported, never touched;
  * save_many writes only after the parent confirms that student's approval is still current (one "authorize" round trip
    per student), only if the feedback in Teams is still what the preview showed, and counts a student as done only when the
    roster lists them under Returned;
  * the first problem stops the run (the students after it are not attempted);
  * dry_many does everything except type and click Return, to test the navigation without changing anything.
Messages are fixed text; page text and names are never logged.
"""
import contextlib
import json
import os
import re
import sys
import time
import teams_read as T
from teams_post import PilotError, display_name, validate_current, return_button
from urllib.parse import urlsplit


def _selected(tab):
    return tab.get_attribute('aria-selected') == 'true'


def show_tab(f, page, name):
    """Make the roster show one of its tabs ('To return' / 'Returned')."""
    tab = f.get_by_role('tab', name=re.compile(name, re.I))
    if tab.count() != 1:
        raise PilotError('The roster has no ' + name + ' tab. Nothing was posted.')
    if not _selected(tab):
        try:
            page.mouse.move(2, 2)                    # a tooltip from the last hover can sit over the tab and swallow the click
            tab.click(timeout=3000)
        except Exception:
            tab.dispatch_event('click')              # click the tab itself, past whatever is drawn over it
        end = time.time() + 8
        while time.time() < end and not _selected(tab):
            page.wait_for_timeout(250)
    page.wait_for_timeout(600)


def on_tab(f, name, wait_ms):
    loc = f.get_by_text(name, exact=True)
    try:
        loc.wait_for(state='visible', timeout=wait_ms)
        return True
    except Exception:
        return False


def open_panel(page, f, req, st, first):
    """From the roster's To return tab: open this student's panel. Returns (panel, editor, submission_id, existing)."""
    name = st['target_name']
    if not on_tab(f, name, 40000 if first else 15000):
        return None
    rows = f.get_by_role('row').filter(has=f.get_by_text(name, exact=True))
    if rows.count() != 1:
        raise PilotError('The exact student was not found once in the To return list. Nothing was posted.')
    links = rows.first.locator('a[id^="submission-row-speed-grader-"]')
    if links.count() != 1:
        raise PilotError('The student work link differs from the supported panel. Nothing was posted.')
    m = re.search(r'/submissions/([0-9a-f-]{36})(?:/|\?|$)', links.get_attribute('href') or '')
    if not m:
        raise PilotError('The student submission identity could not be read. Nothing was posted.')
    links.click()
    anchor = f.locator('#editorAnchor')
    anchor.wait_for(state='attached', timeout=20000)
    panel = f.get_by_role('dialog').filter(has=anchor)
    if panel.count() != 1:
        panel = f.get_by_role('complementary').filter(has=anchor)
    if panel.count() != 1:
        raise PilotError('The grading panel differs from the inspected layout. Nothing was posted.')
    panel.wait_for(state='visible', timeout=20000)
    if f.get_by_role('button', name='Currently selected student: ' + display_name(name), exact=True).count() != 1:
        raise PilotError('The grading panel does not show the expected student. Nothing was posted.')
    editor = panel.get_by_role('textbox', name='Feedback', exact=True)
    if editor.count() != 1 or editor.get_attribute('contenteditable') != 'true':
        raise PilotError('The Feedback editor differs from the inspected panel. Nothing was posted.')
    if T.ids_from_url(f.url) != req['source'] or '/submissions/' + m[1] not in urlsplit(f.url).path:
        raise PilotError('The grading panel address differs from the selected submission. Nothing was posted.')
    return panel, editor, m[1], editor.inner_text().strip()


def close_panel(page, f):
    """Back from a student's panel to the roster (the roster's To return tab shows again)."""
    btn = f.get_by_role('button', name=re.compile(r'^close( viewer)?$', re.I))     # its accessible name is 'close viewer'
    if btn.count() < 1:
        raise PilotError('The grading panel has no Close button, so the next student cannot be reached. Check Teams.')
    btn.first.click(timeout=8000)
    f.get_by_role('tab', name=re.compile('To return', re.I)).wait_for(state='visible', timeout=20000)
    page.wait_for_timeout(800)


def in_returned_tab(page, f, name):
    """Read-only: is this student listed under Returned with a Returned status? Leaves the roster on To return."""
    show_tab(f, page, 'Returned')
    try:
        if not on_tab(f, name, 15000):
            return False
        rows = f.get_by_role('row').filter(has=f.get_by_text(name, exact=True))
        return rows.count() == 1 and any(l.strip().lower() == 'returned' for l in rows.first.inner_text().splitlines())
    finally:
        show_tab(f, page, 'To return')


def s_frame(page, f):
    """The roster frame as it is now (the old handle can go stale after navigating between tabs and panels)."""
    for fr in page.frames:
        if T.FRAME_HOST in T._host(fr.url):
            return fr
    return f


def tab_names(page, s, name):
    """The names listed under one roster tab, once its rows add up to the tab's own count; None if that never happens."""
    show_tab(s.frame(), page, name)
    end = time.time() + 25
    while time.time() < end:
        got = T.parse_roster_students(s.text())
        if got['complete']:
            return {r['name'].strip().lower() for r in got['students']}
        page.wait_for_timeout(700)
    return None


def saved_feedback(page, f, name):
    """Read-only: open this Returned student's panel from the Returned tab and read the feedback Teams actually kept.
    Returns the text, or None if the panel could not be read. Leaves the roster on To return."""
    try:
        show_tab(f, page, 'Returned')
        if not on_tab(f, name, 15000):
            return None
        page.mouse.move(2, 2)
        cell = f.get_by_text(name, exact=True).first
        try:
            cell.click(timeout=4000)
        except Exception:
            cell.dispatch_event('click')
        anchor = f.locator('#editorAnchor')
        anchor.wait_for(state='attached', timeout=20000)
        box = f.get_by_role('textbox', name='Feedback', exact=True)
        if box.count() != 1:
            raise PilotError('Feedback box not found.')
        text = box.inner_text()
        close_panel(page, f)
        return text
    except Exception:
        return None
    finally:
        try:
            show_tab(f, page, 'To return')
        except Exception:
            pass


def one_student(page, f, req, st, mode, ask, known):
    """known: (names under To return, names under Returned) read once at the start; either may be None."""
    sid, key = st['student_id'], st['target_name'].strip().lower()
    to_return, returned = known
    if to_return is not None and returned is not None and key not in to_return:       # decided from the lists, no waiting
        if key in returned:
            return {'student_id': sid, 'skipped': 'Returned in Teams'}
        raise PilotError('The exact student was not found on the Teams roster (class: ' + req['class'] + '). Check the name. Nothing was posted.')
    if not on_tab(f, st['target_name'], 15000):                      # lists unknown: fall back to looking
        if in_returned_tab(page, f, st['target_name']):
            return {'student_id': sid, 'skipped': 'Returned in Teams'}
        raise PilotError('The exact student was not found on the Teams roster (class: ' + req['class'] + '). Check the name. Nothing was posted.')
    got = open_panel(page, f, req, st, False)
    if got is None:
        raise PilotError('The exact student was not found in the To return list. Nothing was posted.')
    panel, editor, submission_id, existing = got
    button = return_button(panel)
    if mode == 'inspect':
        out = {'student_id': sid, 'submission_id': submission_id, 'existing': existing, 'read_at': time.time()}
        close_panel(page, f)
        return out
    if button.count() != 1 or not button.is_enabled():
        raise PilotError('Return is unavailable for this student. Nothing was posted.')
    if mode == 'dry':
        close_panel(page, f)
        return {'student_id': sid, 'submission_id': submission_id, 'existing': existing, 'dry_run': True, 'read_at': time.time()}
    # ---- save: the feedback in Teams must still be what the preview showed; the parent confirms the approval is still current
    if existing != st['preview_existing'].strip():
        raise PilotError('The feedback in Teams changed after the preview. Nothing was posted.')
    ask(sid)
    one = dict(req, target_name=st['target_name'], feedback=st['feedback'])
    validate_current(page, one, submission_id)
    editor.fill(st['feedback'])
    if editor.inner_text().strip() != st['feedback'].strip():
        raise PilotError('The editor did not retain the approved feedback. Check Teams; Return was not clicked.')
    end = time.time() + 10
    while button.count() == 1 and not button.is_enabled() and time.time() < end:
        page.wait_for_timeout(250)
    if button.count() != 1 or not button.is_enabled():
        raise PilotError('Return is unavailable. Feedback may be saved as a draft; check Teams.')
    validate_current(page, one, submission_id)
    button.click()
    page.wait_for_timeout(2500)
    try:
        close_panel(page, f)
        done = in_returned_tab(page, f, st['target_name'])
    except Exception:
        raise PilotError('Return may have run, but Teams could not be read back to confirm it. Check Teams before trying again.') from None
    if not done:
        raise PilotError('Return may have run, but the roster does not list this student under Returned. Check Teams before trying again.')
    # Two different checks: the editor was verified before Return (what was entered); now what Teams KEPT is read back.
    kept = saved_feedback(page, s_frame(page, f), st['target_name']) or saved_feedback(page, s_frame(page, f), st['target_name'])
    if kept is None:
        raise PilotError('Returned, but the feedback Teams saved could not be read back to confirm it. Check this student in Teams before trying again.')
    if ' '.join(kept.split()) != ' '.join(st['feedback'].split()):
        raise PilotError('Returned, but the feedback saved in Teams does not match the approved text. Check this student in Teams.')
    return {'student_id': sid, 'submission_id': submission_id, 'verified': True, 'feedback_matches': True, 'read_at': time.time()}


def run_many(req, ask, emit):
    """req: {mode: inspect|dry|save, class, title, source, students: [{student_id, target_name, ...}]}. One Chrome session."""
    if os.environ.get('SF_FORBID_BROWSER'):
        raise PilotError('Browser use is switched off for tests.')
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    mode = req['mode']
    try:
        with T.BrowserLock(), sync_playwright() as p:
            ctx = T._launch(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(T.TEAMS, wait_until='domcontentloaded')
                page.wait_for_timeout(4000)
                s = T.Session(page, 60); s.t0 = time.time()
                _, _, ids = s.open_one(req['class'], req['title'])
                if any(ids.get(k) != req['source'].get(k) for k in ('class_id', 'assignment_id')):
                    raise PilotError('Teams assignment identity differs from the saved import. Nothing was posted.')
                known = (tab_names(page, s, 'To return'), tab_names(page, s, 'Returned'))
                show_tab(s.frame(), page, 'To return')
                for st in req['students']:
                    f = s.frame()
                    try:
                        emit({'item': one_student(page, f, req, st, mode, ask, known)})
                    except PilotError as e:
                        emit({'item': {'student_id': st['student_id'], 'error': str(e)}})
                        if mode == 'save':
                            return                       # a problem while writing stops the run
                        try:                              # reading goes on: get back to the roster for the next student
                            f = s.frame()
                            if f.get_by_role('button', name=re.compile(r'^close( viewer)?$', re.I)).count():
                                close_panel(page, f)
                        except Exception:
                            pass
            finally:
                ctx.close()
    except PilotError:
        raise
    except T.ReadError as e:
        raise PilotError(str(e)[:300]) from None
    except Exception as e:
        raise PilotError('Teams stopped (' + type(e).__name__ + '). If a Return may have run, check Teams before trying again.') from None


def main():
    def ask(sid):
        print(json.dumps({'authorize': sid}), flush=True)
        if sys.stdin.readline().strip() != 'allow':
            raise PilotError('Approval changed or the job was cancelled. Nothing was posted.')
    def emit(msg):
        print(json.dumps(msg), flush=True)
    try:
        run_many(json.loads(sys.stdin.readline()), ask, emit)
        print(json.dumps({'ok': True, 'done': True}), flush=True)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e) if isinstance(e, PilotError) else 'Teams batch stopped. Check Teams before retrying.'}), flush=True)


if __name__ == '__main__':
    main()
