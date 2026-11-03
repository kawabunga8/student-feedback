"""One-student Teams pilot: preview, teacher confirmation, feedback + Return, read-back.
No points, rubric levels, revision, excused or Copilot controls are touched.
"""
import contextlib
import json
import os
import re
import time
from urllib.parse import urlsplit
import teams_read as T
from myschool_post import digest


class PilotError(ValueError):
    pass


def display_name(roster_name):
    parts = roster_name.split(',')
    return ' '.join([parts[1].strip(), parts[0].strip()]) if len(parts) == 2 else roster_name.strip()


def validate_current(page, req, submission_id):
    f = T.Session(page, 60).frame()
    if (not f or T.ids_from_url(f.url) != req['source'] or
            '/submissions/' + submission_id not in urlsplit(f.url).path or
            f.get_by_role('button', name='Currently selected student: ' + display_name(req['target_name']), exact=True).count() != 1):
        raise PilotError('The selected Teams student or assignment changed. Check Teams; posting was stopped.')


def open_target(page, req, returned=False):
    s = T.Session(page, 60)
    _, _, ids = s.open_one(req['class'], req['title'])
    if any(ids.get(k) != req['source'].get(k) for k in ('class_id', 'assignment_id')):
        raise PilotError('Teams assignment identity differs from the saved import. Nothing was posted.')
    f = s.frame()
    if returned:
        f.get_by_role('tab', name=re.compile(r'^Returned \(\d+\)$')).click()
    try:
        f.get_by_text(req['target_name'], exact=True).wait_for(state='visible', timeout=15000)
    except Exception:
        raise PilotError('The exact student was not found once in the expected Teams tab (class: ' + req['class'] +
                         '). Check the saved Teams class and the name. Nothing was posted.') from None
    rows = f.get_by_role('row').filter(has=f.get_by_text(req['target_name'], exact=True))
    if rows.count() != 1:
        raise PilotError('The exact student was not found once in the expected Teams tab. Nothing was posted.')
    row = rows.first
    links = row.locator('a[id^="submission-row-speed-grader-"]')
    if links.count() != 1:
        raise PilotError('The student work link differs from the supported panel.')
    href = links.get_attribute('href') or ''
    if returned and not re.search(r'\breturned\b', links.get_attribute('aria-label') or '', re.I):
        raise PilotError('The roster did not confirm Returned. Check Teams before retrying.')
    match = re.search(r'/submissions/([0-9a-f-]{36})(?:/|\?|$)', href)
    if not match:
        raise PilotError('The student submission identity could not be read.')
    links.click()
    panel = f.get_by_role('dialog').filter(has=f.locator('#editorAnchor'))
    panel.wait_for(state='visible', timeout=20000)
    identity = 'Currently selected student: ' + display_name(req['target_name'])
    if f.get_by_role('button', name=identity, exact=True).count() != 1:
        raise PilotError('The grading panel does not show the expected student.')
    editor = panel.get_by_role('textbox', name='Feedback', exact=True)
    if editor.count() != 1 or editor.get_attribute('contenteditable') != 'true':
        raise PilotError('The Feedback editor differs from the inspected panel.')
    frame_ids = T.ids_from_url(f.url)
    if frame_ids != ids or '/submissions/' + match[1] not in urlsplit(f.url).path:
        raise PilotError('The grading panel address differs from the selected submission.')
    return panel, editor, {'source':ids, 'submission_id':match[1], 'existing':editor.inner_text().strip(), 'returned':returned}


def operate(page, req, authorize=contextlib.nullcontext):
    panel, editor, state = open_target(page, req)
    if req['op'] == 'inspect':
        return {**state, 'snapshot':digest(state), 'read_at':time.time()}
    if req['op'] != 'save':
        raise PilotError('Choose preview or post.')
    if time.time() - req['preview']['read_at'] > 600 or digest(state) != req['preview']['snapshot']:
        raise PilotError('Teams changed or the preview expired. Create a fresh preview before posting.')
    with authorize():
        validate_current(page, req, state['submission_id'])
        if editor.inner_text().strip() != state['existing']:
            raise PilotError('Feedback changed after preview. Nothing was posted.')
        # Teams may autosave as soon as the editor changes. Authorization precedes all edits.
        editor.fill(req['feedback'])
        if editor.inner_text().strip() != req['feedback'].strip():
            raise PilotError('The editor did not retain the approved feedback. Check Teams; Return was not clicked.')
        button = panel.get_by_role('button', name='Return', exact=True)
        end = time.time() + 10
        while button.count() == 1 and not button.is_enabled() and time.time() < end:
            page.wait_for_timeout(250)
        if button.count() != 1 or not button.is_enabled():
            raise PilotError('Return is unavailable. Feedback may be saved as a draft; check Teams.')
        validate_current(page, req, state['submission_id'])
        button.click()
        # Reopen from the roster's Returned tab: the button click alone is never success.
        page.wait_for_timeout(2000)
        _, check_editor, after = open_target(page, req, returned=True)
        if after['submission_id'] != state['submission_id'] or check_editor.inner_text().strip() != req['feedback'].strip():
            raise PilotError('Return could not be verified. Check Teams before trying again.')
        return {'verified':True, 'returned':True, 'submission_id':after['submission_id'], 'read_at':time.time()}


def run(req, authorize=contextlib.nullcontext):
    if os.environ.get('SF_FORBID_BROWSER'):
        raise PilotError('Browser use is switched off for tests.')
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    try:
        with T.BrowserLock(), sync_playwright() as p:
            ctx = T._launch(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(T.TEAMS, wait_until='domcontentloaded')
                page.wait_for_timeout(4000)
                return operate(page, req, authorize)
            finally:
                ctx.close()
    except PilotError:
        raise
    except T.ReadError as e:
        if req.get('op') == 'inspect':   # a preview changes nothing in Teams, so the reader's own fixed message is safe to show
            raise PilotError(str(e)[:300]) from None
        raise PilotError('Teams step stopped. Feedback may have autosaved or Return may have run. Check Teams before a fresh preview; no automatic retry was made.') from None
    except Exception as e:
        if req.get('op') == 'inspect':
            raise PilotError('Teams preview stopped (' + type(e).__name__ + '); nothing was changed in Teams. Check that the saved Teams class and assignment are the ones for this course.') from None
        raise PilotError('Teams step stopped. Feedback may have autosaved or Return may have run. Check Teams before a fresh preview; no automatic retry was made.') from None


def main():
    import sys
    @contextlib.contextmanager
    def authorize():
        print(json.dumps({'authorize':True}), flush=True)
        if sys.stdin.readline().strip() != 'allow':
            raise PilotError('Approval changed or the job was cancelled. Nothing was posted.')
        yield
    try:
        result = run(json.loads(sys.stdin.readline()), authorize)
        print(json.dumps({'ok':True, 'result':result}), flush=True)
    except Exception as e:
        print(json.dumps({'ok':False, 'error':str(e) if isinstance(e, PilotError) else 'Teams pilot stopped. Check Teams before retrying.'}), flush=True)


if __name__ == '__main__':
    main()
