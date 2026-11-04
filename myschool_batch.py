"""MySchool in ONE browser session, for one student or a whole class.

Opens the assignment's Assessment tab once. Reading (read / inspect) takes everything from that one page: the assignment's own
title, course and publication state, the students listed on it, and each selected student's existing levels and comment. Student
names are matched automatically (Course Hub "Aiden Ching" / "Ching, Aiden" against MySchool's own spelling); a student who can't
be matched exactly once is reported, never guessed. Saving is per student, with the safeguards of the one-student pilot:
  * the parent re-checks that student's approval at the moment of writing (one "authorize" round trip per student);
  * MySchool must still show what the preview showed (the student's existing levels, comment and status, and the publication
    setting), and nothing is staged unless the staged form equals the approved values and no other student's card changed;
  * the Save click is never retried, and a student counts as saved only after the page is reopened and the levels, comment and
    status match, other students are unchanged and the publication setting is preserved;
  * the first problem stops the run. Messages are fixed text; page text and names are never logged.
"""
import json
import os
import re
import sys
import time
import teams_read as T
from myschool_post import (PilotError, canonical_url, open_assessment, target_of, proposed, matches, INSPECT)


def _norm(name):
    return ' '.join(sorted(re.findall(r'[a-z0-9]+', (name or '').lower())))


def match_student(state, wanted):
    """MySchool students whose name equals one of the wanted spellings, ignoring order, case and punctuation."""
    keys = {_norm(w) for w in wanted if w}
    return [s for s in state['students'] if _norm(s['name']) in keys]


def code_of(criterion):
    return next((o['code'] for o in criterion['options'] if o['value'] == criterion['selected']), '')


def header_of(state):
    first = (state.get('students') or [{}])[0]
    return {'title': state.get('title', ''), 'course': state.get('course', ''), 'publication': state.get('publication', ''),
            'criteria': [c.get('label', '') for c in first.get('criteria', [])], 'student_names': [s.get('name', '') for s in state.get('students', []) if s.get('name')],       # a blank card is a template, not a student
            'read_at': time.time()}


def criteria_identity(student):
    """Which criteria a student's levels are being chosen for: each criterion's control id and label, in page order. A preview is
    bound to this, so levels chosen for 'Design, Testing' are never applied if MySchool now lists 'Testing, Design'."""
    return [[c.get('input', ''), c.get('label', '')] for c in student['criteria']]


def preview_of(state, st, req):
    """One student's preview from the page already read (no further browsing)."""
    hits = match_student(state, st['wanted'])
    if not hits:
        raise PilotError('This student was not found on the MySchool page under a matching name. Nothing was saved.')
    if len(hits) > 1:
        raise PilotError('More than one student on the MySchool page matches this name. Nothing was saved.')
    name = hits[0]['name']
    one = {'title': state['title'], 'course': state['course'], 'target_name': name, 'codes': st['codes'], 'comment': st['comment'], 'mark_graded': req.get('mark_graded')}
    student, values = target_of(state, one)
    desired = proposed(student, one, values)
    return {'student_id': st['student_id'], 'target_name': name, 'target_id': student['id'], 'codes': st['codes'],
            'title': state['title'], 'course': state['course'], 'publication': state['publication'],
            'criteria': [{'label': c.get('label', ''), 'existing': code_of(c), 'chosen': k} for c, k in zip(student['criteria'], st['codes'])],
            'existing': {'levels': [code_of(c) for c in student['criteria']], 'comment': student['comment'], 'status': student['status']},
            'existing_selected': [c['selected'] for c in student['criteria']], 'criteria_identity': criteria_identity(student),
            'desired': desired, 'read_at': time.time()}


def save_one(page, req, st, ask):
    """Write one student, then reopen MySchool and verify. st carries the preview the teacher confirmed."""
    pv = st['preview']
    state = open_assessment(page, {'url': req['url']})
    if state['title'] != pv['title'] or state['course'] != pv['course']:
        raise PilotError('MySchool assignment title or course changed since the preview. Nothing was saved.')
    if state['publication'] != pv['publication']:
        raise PilotError('The publication setting changed since the preview. Read MySchool again; nothing was saved.')
    one = {'title': pv['title'], 'course': pv['course'], 'target_name': pv['target_name'], 'codes': pv['codes'], 'comment': st['comment'], 'mark_graded': req.get('mark_graded')}
    student, values = target_of(state, one)
    if student['id'] != pv['target_id']:
        raise PilotError('The destination student changed since the preview. Read MySchool again; nothing was saved.')
    if criteria_identity(student) != pv.get('criteria_identity'):
        raise PilotError('The criteria on the MySchool page changed (names or order) since the preview. Read MySchool again; nothing was saved.')
    desired = proposed(student, one, values)
    if desired != pv['desired']:
        raise PilotError('The values to save changed since the preview. Read MySchool again; nothing was saved.')
    if matches(student, desired):                                          # already exactly there (a lost response, or saved earlier)
        ask(st['student_id'])
        return {'student_id': st['student_id'], 'verified': True, 'already_matching': True}
    if [c['selected'] for c in student['criteria']] != pv['existing_selected'] or student['comment'] != pv['existing']['comment'] or student['status'] != pv['existing']['status']:
        raise PilotError('MySchool changed for this student since the preview. Read MySchool again; nothing was saved.')
    before_other = [s for s in state['students'] if s['id'] != student['id']]
    ask(st['student_id'])
    group = page.locator('.evaluation_group').filter(has=page.locator('#submission_comment_' + student['id']))
    if group.count() != 1:
        raise PilotError('The student card is not unique. Nothing was saved.')
    for i, code in enumerate(pv['codes']):
        group.locator('.assessment').nth(i).locator('.scale_option').filter(has_text=re.compile('^' + re.escape(code) + '$')).click()
    group.locator('#submission_comment_' + student['id']).fill(st['comment'])
    if req.get('mark_graded'):
        group.locator('#submission_status_' + student['id']).select_option(label='Graded')
    staged = page.evaluate(INSPECT)
    selected, _ = target_of(staged, one)
    if not matches(selected, desired) or staged['publication'] != state['publication'] or [s for s in staged['students'] if s['id'] != student['id']] != before_other:
        raise PilotError('The staged values differ from the approved preview. Nothing was saved.')
    save = page.get_by_role('button', name=re.compile('^save$', re.I))
    if save.count() != 1:
        raise PilotError('A unique Save button was not found. Nothing was saved.')
    if canonical_url(page.url) != canonical_url(req['url']):
        raise PilotError('MySchool moved to a different assignment before Save. Nothing was saved.')
    save.click()                                                           # never retried: a failure after this is an uncertain outcome
    page.wait_for_timeout(1500)
    try:
        after = open_assessment(page, {'url': req['url']})
        saved, _ = target_of(after, one)
    except PilotError:
        raise PilotError('Save may have run, but MySchool could not be read back to confirm it. Check MySchool before trying again.') from None
    if not matches(saved, desired) or after['publication'] != state['publication'] or [s for s in after['students'] if s['id'] != student['id']] != before_other:
        raise PilotError('Save could not be verified. Check MySchool before trying again.')
    return {'student_id': st['student_id'], 'verified': True}


def run_many(req, ask, emit):
    """req: {mode: read|inspect|save, url, title?, course?, mark_graded, students: [...]}. One Chrome session."""
    if os.environ.get('SF_FORBID_BROWSER'):
        raise PilotError('Browser use is switched off for tests.')
    canonical_url(req['url'])
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    mode = req['mode']
    try:
        with T.BrowserLock(), sync_playwright() as p:
            ctx = T._launch(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                state = open_assessment(page, {'url': req['url']})
                if (req.get('title') and req['title'] != state['title']) or (req.get('course') and req['course'] != state['course']):
                    raise PilotError('MySchool assignment title or course does not match what you entered. Nothing was saved.')
                emit({'header': header_of(state)})
                if mode == 'read':
                    return
                for st in req['students']:
                    try:
                        if mode == 'inspect':
                            emit({'item': preview_of(state, st, req)})
                        else:
                            emit({'item': save_one(page, req, st, ask)})
                    except PilotError as e:
                        emit({'item': {'student_id': st['student_id'], 'error': str(e)}})
                        if mode == 'save':
                            return                                          # a problem while writing stops the run
            finally:
                ctx.close()
    except PilotError:
        raise
    except T.ReadError as e:
        raise PilotError(str(e)[:300]) from None
    except Exception as e:
        raise PilotError('MySchool stopped (' + type(e).__name__ + '). If a Save may have run, check MySchool before trying again.') from None


def main():
    def ask(sid):
        print(json.dumps({'authorize': sid}), flush=True)
        if sys.stdin.readline().strip() != 'allow':
            raise PilotError('Approval changed or the job was cancelled. Nothing was saved.')
    def emit(msg):
        print(json.dumps(msg), flush=True)
    try:
        run_many(json.loads(sys.stdin.readline()), ask, emit)
        print(json.dumps({'ok': True, 'done': True}), flush=True)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e) if isinstance(e, PilotError) else 'MySchool batch stopped. Check MySchool before retrying.'}), flush=True)


if __name__ == '__main__':
    main()
