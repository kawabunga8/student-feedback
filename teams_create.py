"""Create one unpublished Teams assignment. No Assign/publish action is implemented."""
import contextlib
import json
import os
import re
import sys
import time
from urllib.parse import urlsplit
import teams_read as T


class DraftError(ValueError):
    pass


def payload(rec):
    """Only saved student-facing fields cross the browser boundary."""
    design = rec.get('design') or {}
    if (design.get('submission') or {}).get('type') == 'forms':
        raise DraftError('Forms quizzes need the New quiz flow; this prototype creates ordinary assignments only.')
    data = {'class': str(design.get('teamsClass') or '').strip(),
            'title': str(rec.get('title') or '').strip(), 'instructions': str(rec.get('instructions') or '').strip()}
    for key, limit in (('class', 200), ('title', 300), ('instructions', 20000)):
        if not data[key] or len(data[key]) > limit:
            raise DraftError('Save a Teams class, title and student-facing instructions within the supported limits.')
    if "Teacher's feedback focus (not shown to students):" in data['instructions']:
        raise DraftError('Remove teacher-only feedback guidance from the student-facing instructions.')
    return data


def same_text(a, b):
    # Teams rich text inserts paragraph spacing and non-breaking spaces. Preserve every word/symbol.
    return re.sub(r'\s+', ' ', a).strip() == re.sub(r'\s+', ' ', b).strip()


def editor_id(url):
    p = urlsplit(url)
    m = re.fullmatch(r'/classes/([0-9a-f-]{36})/assignment-editor/([0-9a-f-]{36})', p.path)
    if p.hostname != T.FRAME_HOST or not m:
        raise DraftError('The draft editor address differs. Check Teams before retrying.')
    return {'class_id': m[1], 'assignment_id': m[2]}


def click(locator):
    locator.wait_for(state='visible', timeout=15000)
    if locator.count() != 1:
        raise DraftError('An expected draft control is missing or duplicated. Nothing further was clicked.')
    locator.click(timeout=5000)


def draft_action(frame):
    direct = frame.get_by_role('button', name='Save as draft', exact=True)
    if direct.count() == 1 and direct.is_visible():
        return direct
    # The inspected narrow layout puts draft saving in the footer, beside Student view.
    footer = frame.get_by_role('link', name='Student view', exact=True).locator('..')
    click(footer.get_by_role('button', name='More options', exact=True))
    return frame.get_by_role('menuitem', name='Save as draft', exact=True)


def operate(page, req, authorize=contextlib.nullcontext):
    s = T.Session(page, 60); s.t0 = time.time()
    # Open the global list even if there are no upcoming assignments.
    click(page.get_by_role('navigation', name='Apps', exact=True).get_by_role('button', name='Assignments', exact=True))
    s.wait_for('global assignments', lambda text: 'Assignments' in text and 'Drafts' in text)
    f = s.frame()
    recovery = req.get('recovery_url', '')
    if recovery:
        editor_id(recovery)
    else:
        click(f.get_by_role('button', name='Create assignment', exact=True))
        click(f.get_by_role('menuitem', name='New assignment', exact=True))
        dialog = f.get_by_role('dialog', name='Create an assignment', exact=True)
        dialog.wait_for(state='visible', timeout=15000)
        cls = re.escape(req['class'])
        option = dialog.get_by_role('option', name=re.compile(r'^' + cls + r'(?:\s+' + cls + r')?$'))
        click(option)
    # Creating the editor can autosave an empty draft: authorization starts before Create.
    with authorize():
        if recovery:
            f.goto(recovery, wait_until='domcontentloaded')
        else:
            click(dialog.get_by_role('button', name='Create', exact=True))
        end = time.time() + 20
        while time.time() < end:
            f = s.frame()
            if f and re.search(r'/assignment-editor/[0-9a-f-]{36}', urlsplit(f.url).path):
                break
            page.wait_for_timeout(250)
        ids = editor_id(f.url)
        title = f.get_by_role('textbox', name='Enter title', exact=True)
        title.wait_for(state='visible', timeout=15000)
        ins = f.get_by_role('textbox', name='Enter instructions', exact=True)
        ins.wait_for(state='visible', timeout=15000)
        if title.count() != 1 or ins.count() != 1 or ins.get_attribute('contenteditable') != 'true':
            raise DraftError('Draft fields differ. Check Teams; an empty draft may exist.')
        if (title.input_value().strip() or ins.inner_text().strip()) and not (recovery and title.input_value() == req['title'] and same_text(ins.inner_text(), req['instructions'])):
            raise DraftError('The new editor was not empty or the recovery draft differs. Nothing was overwritten; check Teams.')
        assigned_class = f.get_by_role('combobox', name='Assign to', exact=True)
        if assigned_class.count() != 1 or assigned_class.get_attribute('placeholder') != req['class']:
            raise DraftError('The editor did not show the selected class. Nothing was filled.')
        page.wait_for_timeout(1000)
        title.fill(req['title']); title.press('Tab'); page.wait_for_timeout(500)
        ins.fill(req['instructions']); ins.press('Tab')
        end = time.time() + 10
        while time.time() < end and not (title.input_value() == req['title'] and same_text(ins.inner_text(), req['instructions'])):
            page.wait_for_timeout(250)
        if editor_id(f.url) != ids or title.input_value() != req['title'] or not same_text(ins.inner_text(), req['instructions']):
            raise DraftError('Draft contents differ. Check this unpublished editor before retrying: ' + f.url.split('?')[0])
        click(draft_action(f))
        f.get_by_role('tab', name='Drafts', exact=True).wait_for(state='visible', timeout=15000)
        click(f.get_by_role('tab', name='Drafts', exact=True))
        rows = f.get_by_role('listitem').filter(has=f.get_by_text(req['title'], exact=True))
        rows.first.wait_for(state='visible', timeout=15000)
        if rows.count() != 1:
            raise DraftError('The draft title is not unique in Drafts. Check Teams; do not create another.')
        click(rows.get_by_text(req['title'], exact=True))
        title = f.get_by_role('textbox', name='Enter title', exact=True)
        title.wait_for(state='visible', timeout=15000)
        f.get_by_role('textbox', name='Enter instructions', exact=True).wait_for(state='visible', timeout=15000)
        if (editor_id(f.url) != ids or title.input_value() != req['title'] or
                not same_text(f.get_by_role('textbox', name='Enter instructions', exact=True).inner_text(), req['instructions'])):
            raise DraftError('Saved draft read-back differs. Check Teams; do not create another.')
        return {**ids, 'verified': True, 'unpublished': True, 'title': req['title'], 'class': req['class'],
                'url': f.url.split('?')[0], 'read_at': time.time()}


def run(req, authorize=contextlib.nullcontext):
    if os.environ.get('SF_FORBID_BROWSER'):
        raise DraftError('Browser use is switched off for tests.')
    from playwright.sync_api import sync_playwright
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(T.TEAMS, wait_until='domcontentloaded'); page.wait_for_timeout(4000)
            if T._host(page.url) in T.LOGIN_HOSTS:
                raise DraftError('Sign in to Teams in the app Chrome profile first, using List my assignments. No draft was requested.')
            return operate(page, req, authorize)
        except DraftError:
            raise
        except Exception:
            raise DraftError('Draft creation stopped. Teams may have autosaved a draft. Check Drafts before any retry; nothing was published by this worker.') from None
        finally:
            ctx.close()


def main():
    @contextlib.contextmanager
    def authorize():
        print(json.dumps({'authorize': True}), flush=True)
        if sys.stdin.readline().strip() != 'allow':
            raise DraftError('The saved assignment changed or the job was cancelled. Creation stopped.')
        yield
    try:
        result = run(json.loads(sys.stdin.readline()), authorize)
        print(json.dumps({'ok': True, 'result': result}), flush=True)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e) if isinstance(e, (DraftError, T.ReadError)) else 'Draft creation stopped. Check Teams before retrying.'}), flush=True)


if __name__ == '__main__':
    main()
