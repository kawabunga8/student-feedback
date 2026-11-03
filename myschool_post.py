"""One-student MySchool pilot. Browser UI only; inspect first, explicit save second.
No publishing controls are changed. Live saves are not yet verified. All errors are
fixed messages: page text, names, comments and authenticated URLs are never logged.
"""
import contextlib
import hashlib
import json
import re
import time
from urllib.parse import urlsplit, parse_qs

HOST = 'rcs.myschoolmanagement.com'
PATH = '/content/assignment/assignment_edit.php'
LEVELS = {'Emerging':'EMG', 'Developing':'DEV', 'Proficient':'PRF', 'Extending':'EXT'}

class PilotError(ValueError):
    pass

def canonical_url(url):
    try:
        p = urlsplit(url)
        ids = parse_qs(p.query).get('exercise_id', [])
        if p.scheme != 'https' or p.netloc != HOST or p.path != PATH or len(ids) != 1 or not re.fullmatch(r'\d+', ids[0]):
            raise ValueError()
        if set(parse_qs(p.query)) != {'exercise_id'}:
            raise ValueError()
        return f'https://{HOST}{PATH}?exercise_id={ids[0]}'
    except (ValueError, TypeError):
        raise PilotError('Paste the MySchool assignment edit address with its exercise_id only.') from None

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def parse_codes(value):
    """Levels for the criteria in page order: 'PRF, EXT+' or ['PRF','EXT+']. Only the four proficiency codes, optional '+'."""
    items = re.split(r'[\s,;]+', value.strip()) if isinstance(value, str) else [str(x).strip() for x in (value or [])]
    items = [x.upper() for x in items if x]
    if not items or len(items) > 12 or any(not re.fullmatch(r'(?:EMG|DEV|PRF|EXT)\+?', x) for x in items):
        raise PilotError('Levels must be EMG, DEV, PRF or EXT (optionally with +), one per MySchool criterion, in page order.')
    return items

def level_code(level):
    base = level[:-1] if level.endswith('+') else level
    if base not in LEVELS:
        raise PilotError('Choose a teacher proficiency level before posting.')
    return LEVELS[base] + ('+' if level.endswith('+') else '')

# DOM-backed evidence only. No internal application APIs, hidden tokens or source dumps.
INSPECT = r'''() => {
 const val = e => e ? e.value : '';
 const course = document.querySelector('input[name="course_id"]:checked');
 const pub = document.querySelector('#publication_status_id');
 return {title: val(document.querySelector('#exercise_label')),
   course: course ? course.parentElement.textContent.trim() : '', publication: val(pub),
   students: [...document.querySelectorAll('.evaluation_group')].map(root => {
     const comment = root.querySelector('textarea[id^="submission_comment_"]');
     const status = root.querySelector('select[id^="submission_status_"]');
     return {id: comment ? comment.id.replace('submission_comment_', '') : '',
       name: root.querySelector('img[alt]')?.getAttribute('alt') || '',
       comment: val(comment), status: val(status),
       criteria: [...root.querySelectorAll('.assessment')].map(a => {
         const input = a.querySelector('input[type="hidden"][name^="grade["]');
         const lab = a.querySelector('.criterion_name, .criteria_name, .assessment_label, label, h4, strong, .name');
         return {input: input?.id || '', selected: val(input), label: lab ? lab.textContent.trim().slice(0, 80) : '',
           options: [...a.querySelectorAll('.scale_option')].map(o => ({code:o.textContent.trim(), value:o.getAttribute('value')}))};
       })};
   })};
}'''

def target_of(state, request):
    if state.get('title') != request['title'] or state.get('course') != request['course']:
        raise PilotError('MySchool assignment title or course does not exactly match. Nothing was saved.')
    if state.get('publication') not in ('0','1','2','3'):
        raise PilotError('MySchool publication controls differ from the supported page. Nothing was saved.')
    matches = [s for s in state.get('students', []) if s.get('name') == request['target_name']]
    if len(matches) != 1:
        raise PilotError('The exact MySchool student name was missing or repeated. Nothing was saved.')
    student = matches[0]
    codes = request.get('codes') or [request['code']]
    n = len(student.get('criteria', []))
    if not re.fullmatch(r'\d+', student.get('id','')) or n < 1:
        raise PilotError('This student has no criteria on the MySchool page. Nothing was saved.')
    if n != len(codes):
        names = '; '.join((c.get('label') or '(unnamed)') for c in student['criteria'])[:160]
        raise PilotError(f'This student has {n} criteria on the MySchool page ({names}) but {len(codes)} level(s) were given. Give one level per criterion, in that order. Nothing was saved.')
    values = []
    for criterion, code in zip(student['criteria'], codes):
        if not re.fullmatch(r'grade_\d+_\d+', criterion.get('input','')):
            raise PilotError('A level control differs from the supported page. Nothing was saved.')
        options = [o for o in criterion['options'] if o['code'] == code]
        if len(options) != 1 or not options[0].get('value'):
            raise PilotError('The approved level is not available exactly once. Nothing was saved.')
        values.append(options[0]['value'])
    return student, values

def proposed(student, req, value):
    return {'levels':value, 'comment':req['comment'], 'status':'2' if req.get('mark_graded') else student['status']}

def matches(student, desired):
    return ([c['selected'] for c in student['criteria']] == desired['levels'] and student['comment'] == desired['comment'] and student['status'] == desired['status'])

def open_assessment(page, request):
    url = canonical_url(request['url'])
    page.goto(url, wait_until='domcontentloaded')
    # Normal staff SSO is a UI click; no credentials are read or supplied.
    if urlsplit(page.url).path == '/saml/discover':
        page.get_by_role('link', name='Staff', exact=True).click()
    end = time.time() + 120
    while urlsplit(page.url).hostname != HOST or urlsplit(page.url).path.startswith('/saml'):
        if time.time() > end:
            raise PilotError('Sign in to MySchool in the opened Chrome window, then create a fresh preview.')
        page.wait_for_timeout(1000)
    if page.url.split('#')[0] != url:
        page.goto(url, wait_until='domcontentloaded')
    page.locator('#exercise_label').wait_for(state='attached', timeout=20000)
    page.get_by_role('link', name='Assessment', exact=True).click()
    page.locator('#student_grid').wait_for(state='visible', timeout=20000)
    page.locator('.evaluation_group textarea[id^="submission_comment_"]').first.wait_for(state='visible', timeout=20000)
    if canonical_url(page.url) != url:
        raise PilotError('MySchool navigated to a different assignment. Nothing was saved.')
    count, steady, end = -1, 0, time.time() + 12       # the cards can keep arriving after the first one is visible
    while steady < 3 and time.time() < end:
        now = page.locator('.evaluation_group').count()
        steady = steady + 1 if now == count else 0
        count = now
        page.wait_for_timeout(600)
    return page.evaluate(INSPECT)

def operate(page, request, authorize=contextlib.nullcontext):
    state = open_assessment(page, request)
    student, value = target_of(state, request)
    desired = proposed(student, request, value)
    baseline = digest(state)
    if request['op'] == 'inspect':
        code_of = lambda c: next((o['code'] for o in c['options'] if o['value'] == c['selected']), '')
        codes = request.get('codes') or [request['code']]
        return {'snapshot':baseline, 'target_id':student['id'],
                'existing':{'levels':[code_of(c) for c in student['criteria']], 'comment':student['comment'], 'status':student['status']},
                'criteria':[{'label':c.get('label',''), 'existing':code_of(c), 'chosen':k} for c, k in zip(student['criteria'], codes)],
                'desired':desired, 'publication':state['publication'], 'read_at':time.time()}
    if request['op'] != 'save':
        raise PilotError('Unknown MySchool operation.')
    preview = request['preview']
    if time.time() - preview['read_at'] > 600:
        raise PilotError('The preview expired. Read MySchool again before saving.')
    if student['id'] != preview['target_id'] or state['publication'] != preview['publication']:
        raise PilotError('The destination changed. Read MySchool again; nothing was saved.')
    # Recover safely after a lost response: no second save when the exact values already exist.
    if matches(student, preview['desired']):
        with authorize():
            return {'verified':True, 'already_matching':True, 'publication':state['publication']}
    if baseline != preview['snapshot'] or desired != preview['desired']:
        raise PilotError('MySchool changed since the preview. Read it again; nothing was saved.')
    before_other = [s for s in state['students'] if s['id'] != student['id']]
    with authorize():             # server rechecks approval and cancellation immediately before any edits/save
        group = page.locator('.evaluation_group').filter(has=page.locator('#submission_comment_'+student['id']))
        if group.count() != 1:
            raise PilotError('The student card is not unique. Nothing was saved.')
        for i, code in enumerate(request.get('codes') or [request['code']]):
            group.locator('.assessment').nth(i).locator('.scale_option').filter(has_text=re.compile('^'+re.escape(code)+'$')).click()
        group.locator('#submission_comment_'+student['id']).fill(request['comment'])
        if request.get('mark_graded'):
            group.locator('#submission_status_'+student['id']).select_option(label='Graded')
        staged = page.evaluate(INSPECT)
        selected, _ = target_of(staged, request)
        if not matches(selected, desired) or staged['publication'] != state['publication'] or [s for s in staged['students'] if s['id'] != student['id']] != before_other:
            raise PilotError('The staged values differ from the approved preview. Nothing was saved.')
        save = page.get_by_role('button', name=re.compile('^save$', re.I))
        if save.count() != 1:
            raise PilotError('A unique Save button was not found. Nothing was saved.')
        if canonical_url(page.url) != canonical_url(request['url']):      # same check as Teams: the page must still be this assignment
            raise PilotError('MySchool moved to a different assignment before Save. Nothing was saved.')
        # Do not retry this click. A connection failure after it is an uncertain outcome.
        save.click()
        page.wait_for_timeout(1500)
        unverified = 'Save may have run, but MySchool could not be read back to confirm it. Check MySchool before trying again.'
        try:
            after = open_assessment(page, request)
            saved, _ = target_of(after, request)
        except PilotError:
            raise PilotError(unverified) from None      # these checks' own messages say "Nothing was saved", which is no longer known
        if not matches(saved, desired) or after['publication'] != state['publication'] or [s for s in after['students'] if s['id'] != student['id']] != before_other:
            raise PilotError('Save could not be verified. Check MySchool before trying again.')
        return {'verified':True, 'already_matching':False, 'publication':after['publication']}

def run(request, authorize=contextlib.nullcontext):
    import os
    if os.environ.get('SF_FORBID_BROWSER'):
        raise PilotError('Browser use is switched off for tests.')
    canonical_url(request['url'])
    import teams_read as T
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    try:
        with T.BrowserLock(), sync_playwright() as p:
            ctx = T._launch(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                return operate(page, request, authorize)
            finally:
                ctx.close()
    except PilotError:
        raise
    except Exception:
        raise PilotError('MySchool browser step failed. If Save may have run, check MySchool before trying again. No automatic retry was made.') from None


def main():
    import sys
    @contextlib.contextmanager
    def authorize():
        print(json.dumps({'authorize':True}), flush=True)
        if sys.stdin.readline().strip() != 'allow':
            raise PilotError('Approval changed or the job was cancelled. Nothing was saved.')
        yield
    try:
        request = json.loads(sys.stdin.readline())
        result = run(request, authorize)
        print(json.dumps({'ok':True, 'result':result}), flush=True)
    except Exception as e:
        message = str(e) if isinstance(e, PilotError) else 'MySchool pilot failed. Check the destination before retrying.'
        print(json.dumps({'ok':False, 'error':message}), flush=True)

if __name__ == '__main__':
    main()
