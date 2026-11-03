"""Create one unpublished MySchool assignment through its inspected browser form."""
import contextlib
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import os
import re
import sys
import time
from urllib.parse import urlsplit
import teams_read as T
from myschool_post import HOST, PATH, PilotError, canonical_url, digest
from teams_create import same_text

NEW_URL = 'https://' + HOST + PATH
MANAGEMENT_URL = 'https://' + HOST + '/content/assignment/assignment_management.php'


def same_weight(a,b):
    try:
        return Decimal(str(a)).is_finite() and Decimal(str(b)).is_finite() and Decimal(str(a))==Decimal(str(b))
    except (InvalidOperation,ValueError):
        return False


def payload(rec):
    data = {k:str(rec.get(k) or '').strip() for k in ('title','instructions')}
    if not data['title'] or len(data['title']) > 300 or not data['instructions'] or len(data['instructions']) > 20000:
        raise PilotError('Save an assignment title and student-facing instructions first (300 / 20,000 character limits).')
    if "Teacher's feedback focus (not shown to students):" in data['instructions']:
        raise PilotError('Teacher-only feedback guidance must stay out of the student-facing instructions.')
    return data


def validate_choices(req):
    if not isinstance(req.get('course'),str) or not req['course'].strip() or len(req['course']) > 200:
        raise PilotError('Choose the exact MySchool course.')
    if req.get('kind') not in ('Formative','Summative'):
        raise PilotError('Choose Formative or Summative yourself.')
    try:
        if date.fromisoformat(req['due']).isoformat() != req['due']:
            raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise PilotError('Choose a valid due date.') from None


def check_new(page):
    p=urlsplit(page.url)
    if p.scheme != 'https' or p.netloc != HOST or p.path != PATH or p.query:
        raise PilotError('The page is not a new MySchool assignment. No existing assignment was edited.')


def open_new(page):
    page.goto(NEW_URL,wait_until='domcontentloaded')
    if urlsplit(page.url).path == '/saml/discover':
        page.get_by_role('link',name='Staff',exact=True).click()
    end=time.time()+120
    while urlsplit(page.url).hostname != HOST or urlsplit(page.url).path.startswith('/saml'):
        if time.time()>end:
            raise PilotError('Sign in to MySchool in Chrome, then create a fresh preview. Nothing was saved.')
        page.wait_for_timeout(1000)
    if page.url.split('#')[0] != NEW_URL:
        page.goto(NEW_URL,wait_until='domcontentloaded')
    page.locator('#exercise_label').wait_for(state='visible',timeout=20000)
    check_new(page)
    if page.locator('#exercise_label').input_value().strip():
        raise PilotError('The new assignment title is not empty. Nothing was overwritten.')


def radios(page,name):
    return page.locator('input[type="radio"][name="'+name+'"]').evaluate_all('els=>els.filter(e=>e.labels?.[0]?.getClientRects().length).map(e=>({id:e.id,value:e.value,label:e.labels[0].textContent.trim()}))')


def choose_radio(page,name,label):
    hits=[r for r in radios(page,name) if r['label']==label]
    if len(hits)!=1 or not hits[0]['id'] or not hits[0]['value'].isdigit():
        raise PilotError('The exact course or assignment type was not found once. Nothing was saved.')
    control=page.locator('input[name="'+name+'"][value="'+hits[0]['value']+'"]')
    label=page.locator('label[for="'+hits[0]['id']+'"]')
    label.wait_for(state='visible',timeout=20000)
    if label.count()!=1:
        raise PilotError('The visible course/type label is not unique. Nothing was saved.')
    label.click()
    if not control.is_checked():
        raise PilotError('The course/type choice did not stick. Nothing was saved.')
    return hits[0]['value']


def groups(page):
    return page.locator('#learning_outcome_tree .dynatree-folder > a.dynatree-title').all_text_contents()


def options_state(page):
    return page.evaluate('''()=>({scale:document.querySelector('#scale_group_id')?.selectedOptions[0]?.textContent.trim(),
      weight:document.querySelector('#exercise_weight')?.value,
      submissions:document.querySelector('#submission_type_id')?.selectedOptions[0]?.textContent.trim(),
      outcomes:[...document.querySelectorAll('#learning_outcome_tree .dynatree-folder > a.dynatree-title')].map(a=>({label:a.textContent.trim(),selected:a.parentElement.classList.contains('dynatree-selected')}))})''')


def planning_state(page):
    return page.evaluate('''()=>({title:document.querySelector('#exercise_label')?.value,
      course:document.querySelector('input[name=course_id]:checked')?.value,
      kind:document.querySelector('input[name=exercise_type_id]:checked')?.value,
      due:document.querySelector('#exercise_due_date')?.value,
      publication:document.querySelector('#publication_status_id')?.value,
      scheduled:document.querySelector('#unpublish_date')?.value,
      email:document.querySelector('#email_students')?.checked ?? null})''')


def editor(page):
    loc=page.frame_locator('#exercise_comment_ifr').locator('#tinymce')
    loc.wait_for(state='visible',timeout=20000)
    if loc.get_attribute('contenteditable')!='true':
        raise PilotError('The MySchool instructions editor differs. Nothing was saved.')
    return loc


def form_preview(page,req):
    req['_stage']='opening new form'
    open_new(page)
    courses=radios(page,'course_id')
    if req['op']=='list':
        return {'courses':[r['label'] for r in courses]}
    validate_choices(req)
    req['_stage']='selecting course'
    course_id=choose_radio(page,'course_id',req['course'])
    req['_stage']='waiting for assignment types'
    page.locator('input[type="radio"][name="exercise_type_id"]').first.wait_for(state='attached',timeout=20000)
    req['_stage']='selecting assignment type'
    kind_id=choose_radio(page,'exercise_type_id',req['kind'])
    req['_stage']='waiting for instructions editor'
    editor(page)
    state=planning_state(page)
    if state['publication']!='0' or state['email'] or state['scheduled']:
        raise PilotError('The new form is not unpublished with email off and no scheduled publication. Nothing was saved.')
    req['_stage']='opening Options'
    page.get_by_role('link',name='Options',exact=True).click()
    req['_stage']='waiting for course options'
    page.locator('#scale_group_id').wait_for(state='visible',timeout=15000)
    req['_stage']='reading course defaults'
    opts=options_state(page)
    if not opts['scale'] or opts['weight']!='1' or opts['submissions']!='Do not accept':
        raise PilotError('MySchool defaults differ (scale, weight or submissions). Nothing was saved.')
    names=[g['label'] for g in opts['outcomes']]
    if len(names)!=len(set(names)) or any(g['selected'] for g in opts['outcomes']):
        raise PilotError('Learning outcomes differ from the supported blank form. Nothing was saved.')
    data={'course_id':course_id,'kind_id':kind_id,'available_outcomes':names,'scale':opts['scale'],'weight':opts['weight'],'submissions':opts['submissions']}
    return {**data,'snapshot':digest(data),'read_at':time.time()}


def operate(page,req,authorize=contextlib.nullcontext):
    if req['op']=='verify':
        return verify_saved(page,req,req['preview'])
    preview=form_preview(page,req)
    if req['op'] in ('list','inspect'):
        return preview
    if req['op']!='save':
        raise PilotError('Choose preview or save unpublished assignment.')
    if time.time()-req['preview']['read_at']>600 or preview['snapshot']!=req['preview']['snapshot']:
        raise PilotError('The MySchool preview expired or the course settings changed. Read a fresh preview.')
    outcomes=req.get('outcomes')
    if not isinstance(outcomes,list) or not outcomes or len(outcomes)>12 or len(set(outcomes))!=len(outcomes) or any(x not in preview['available_outcomes'] for x in outcomes):
        raise PilotError('Choose at least one available learning outcome, without duplicates.')
    with authorize():
        req['_stage']='staging new assignment'
        check_new(page)
        for name in outcomes:
            page.get_by_role('link',name=name,exact=True).click()
        opts=options_state(page)
        if set(g['label'] for g in opts['outcomes'] if g['selected'])!=set(outcomes):
            raise PilotError('Selected learning outcomes do not match the preview. Nothing was saved.')
        page.get_by_role('link',name='Planning',exact=True).click()
        page.locator('#exercise_label').fill(req['title'])
        text=editor(page);text.fill(req['instructions']);text.press('Tab')
        page.locator('#exercise_due_date').fill(req['due']);page.locator('#exercise_due_date').press('Tab')
        # Explicitly set the inspected unpublished/no-notification controls, then read them back.
        page.locator('#publication_status_id').select_option('0')
        page.locator('#unpublish_date').fill('');page.locator('#email_students').uncheck()
        state=planning_state(page)
        expected={'title':req['title'],'course':preview['course_id'],'kind':preview['kind_id'],'due':req['due'],'publication':'0','scheduled':'','email':False}
        if state!=expected or not same_text(text.inner_text(),req['instructions']):
            raise PilotError('Staged title, instructions or unpublished settings differ. Nothing was saved.')
        check_new(page)
        save=page.locator('button[data-test="save"]')
        if save.count()!=1:
            raise PilotError('A unique Save control was not found. Nothing was saved.')
        req['_stage']='Save and read-back'
        save.click()  # exactly once; never retry an uncertain Save
        end=time.time()+30
        while time.time()<end:
            if urlsplit(page.url).path=='/content/assignment/assignment_management.php' and page.get_by_role('button',name=re.compile(r'^view all assignments$',re.I)).count():
                break
            try:
                canonical_url(page.url);break
            except PilotError:
                page.wait_for_timeout(250)
        else:
            raise PilotError('Save outcome is unresolved. Use Verify previous Save; do not send another Save.')
        return verify_saved(page,req,preview)



def find_saved(page,req):
    # Save may return to the grade grid rather than expose the new ID in the URL.
    req['_stage']='opening assignment list'
    if urlsplit(page.url).path!='/content/assignment/assignment_management.php':
        page.goto(MANAGEMENT_URL,wait_until='domcontentloaded')
    button=page.get_by_role('button',name=re.compile(r'^view all assignments$',re.I))
    button.wait_for(state='visible',timeout=30000)
    req['_stage']='opening all assignments'
    button.click()
    grid=page.locator('#all_assignments_container')
    field=grid.get_by_placeholder('Title',exact=True);field.wait_for(state='visible',timeout=15000)
    req['_stage']='filtering saved assignment'
    field.fill(req['title']);field.press('Enter')
    rows=grid.locator('.slick-row').filter(has=page.get_by_role('link',name=req['title'],exact=True)).filter(has=page.get_by_text(req['course'],exact=True))
    rows.first.wait_for(state='visible',timeout=30000)
    req['_stage']='reading saved list row'
    if rows.count()!=1:
        raise PilotError('The saved title/course is missing or duplicated. Check MySchool; do not Save again.')
    cells=[x.strip() for x in rows.locator('.slick-cell').all_text_contents()]
    if cells[1:] != [req['title'],req['kind'],req['due'],req['course'],'No']:
        raise PilotError('The assignment list does not confirm the expected type, date, course and unpublished status.')
    href=rows.get_by_role('link',name=req['title'],exact=True).get_attribute('href') or ''
    match=re.fullmatch(r'javascript:loadAssignment\((\d+)\)',href)
    if not match:
        raise PilotError('The saved assignment link differs. No further action was taken.')
    return NEW_URL+'?exercise_id='+match[1]


def verify_saved(page,req,preview):
    req['_stage']='read-only destination verification'
    url=find_saved(page,req)
    req['_stage']='opening saved assignment'
    page.goto(url,wait_until='domcontentloaded')
    page.locator('#exercise_label').wait_for(state='visible',timeout=20000)
    req['_stage']='waiting for saved assignment type'
    page.locator('input[type="radio"][name="exercise_type_id"]:checked').wait_for(state='attached',timeout=30000)
    req['_stage']='waiting for saved instructions'
    text=editor(page);state=planning_state(page)
    # The email checkbox is a create-time action and can be absent on a saved form.
    email_state=state.pop('email')
    expected={'title':req['title'],'course':preview['course_id'],'kind':preview['kind_id'],'due':req['due'],'publication':'0','scheduled':''}
    if state!=expected or email_state not in (False,None) or not same_text(text.inner_text(),req['instructions']):
        raise PilotError('Saved assignment read-back differs. Check MySchool before any retry.')
    req['_stage']='opening saved options'
    page.get_by_role('link',name='Options',exact=True).click()
    page.locator('#scale_group_id').wait_for(state='visible',timeout=15000)
    after=options_state(page)
    if (set(g['label'] for g in after['outcomes'] if g['selected'])!=set(req['outcomes']) or
        any(after[k]!=preview[k] for k in ('scale','submissions')) or not same_weight(after['weight'],preview['weight'])):
        raise PilotError('Saved learning outcomes or settings differ. Check MySchool before any retry.')
    return {'verified':True,'unpublished':True,'email':False,'email_control_on_readback':email_state is not None,
            'url':url,'title':req['title'],'course':req['course'],'due':req['due'],'kind':req['kind'],
            'outcomes':req['outcomes'],'read_at':time.time()}


def run(req,authorize=contextlib.nullcontext):
    if os.environ.get('SF_FORBID_BROWSER'):
        raise PilotError('Browser use is switched off for tests.')
    from playwright.sync_api import sync_playwright
    with T.BrowserLock(),sync_playwright() as p:
        ctx=T._launch(p)
        try:
            page=ctx.pages[0] if ctx.pages else ctx.new_page()
            return operate(page,req,authorize)
        except PilotError:raise
        except Exception:
            stage=req.get('_stage','opening browser')
            if req.get('op')!='save':
                raise PilotError('MySchool preview stopped at '+stage+'. Nothing was saved; read a fresh preview.') from None
            raise PilotError('MySchool creation stopped at '+stage+'. Check assignments before retrying; Save may have completed. No automatic retry was made.') from None
        finally:ctx.close()


def main():
    @contextlib.contextmanager
    def authorize():
        print(json.dumps({'authorize':True}),flush=True)
        if sys.stdin.readline().strip()!='allow':raise PilotError('Saved assignment changed or job was cancelled. Nothing was saved.')
        yield
    try:print(json.dumps({'ok':True,'result':run(json.loads(sys.stdin.readline()),authorize)}),flush=True)
    except Exception as e:print(json.dumps({'ok':False,'error':str(e) if isinstance(e,(PilotError,T.ReadError)) else 'MySchool creation stopped. Check assignments.'}),flush=True)


if __name__=='__main__':main()
