"""Teams posting pilot: synthetic DOM and local server only, no school contact."""
import contextlib, copy, json, os, sys, tempfile, threading, time
from _common import APPDIR, LAUNCH, guard, guard_app
HOME=tempfile.mkdtemp();os.environ['HOME']=HOME;guard(HOME);sys.path.insert(0,APPDIR)
import app as A, teams_post as P
from playwright.sync_api import sync_playwright
from http.server import ThreadingHTTPServer
ok=[]
def check(label,v):ok.append(bool(v));print(('PASS ' if v else 'FAIL ')+label,flush=True)
def refuses(fn,part=''):
 try:fn();return False
 except (ValueError,PermissionError) as e:return not part or part in str(e)
source={'class_id':'11111111-1111-1111-1111-111111111111','assignment_id':'22222222-2222-2222-2222-222222222222'}
REQ={'op':'inspect','class':'Synthetic class','title':'Synthetic task','source':source,'target_name':'Example, Alex','feedback':'Your counted rest is clear. Next, compare both attempts.'}
check('browser guard stops the live runner',refuses(lambda:P.run(REQ),'switched off'))
check('roster name maps to the panel identity',P.display_name('Example, Alex')=='Alex Example')
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page();pg.set_content('<div role="dialog"><div contenteditable="true" role="textbox" aria-label="Feedback">Earlier feedback</div><button>Return</button></div>')
 panel=pg.get_by_role('dialog');editor=panel.get_by_role('textbox',name='Feedback');pg.get_by_role('button',name='Return').evaluate("e=>e.onclick=()=>e.dataset.clicked='yes'")
 original=P.open_target;original_validate=P.validate_current;P.validate_current=lambda *args:None;fail_read=[False];opens=[]
 def open_target(page,req,returned=False):
  opens.append(returned)
  if returned and fail_read[0]:raise P.PilotError('Return could not be verified.')
  return panel,editor,{'source':source,'submission_id':'33333333-3333-3333-3333-333333333333','existing':editor.inner_text().strip(),'returned':returned}
 P.open_target=open_target
 preview=P.operate(pg,REQ)
 check('preview returns existing feedback without editing or Return',preview['existing']=='Earlier feedback' and not pg.get_by_role('button',name='Return').get_attribute('data-clicked'))
 calls=[]
 @contextlib.contextmanager
 def authorized():calls.append(True);yield
 req={**REQ,'op':'save','preview':preview}
 @contextlib.contextmanager
 def denied():raise P.PilotError('Approval revoked');yield
 check('revoked approval stops before editor changes',refuses(lambda:P.operate(pg,req,denied),'revoked') and editor.inner_text()=='Earlier feedback')
 editor.fill('Changed elsewhere')
 check('changed remote feedback rejects stale preview',refuses(lambda:P.operate(pg,req,authorized),'changed') and not calls)
 editor.fill('Earlier feedback')
 check('expired preview rejects before edits',refuses(lambda:P.operate(pg,{**req,'preview':{**preview,'read_at':0}},authorized),'expired'))
 out=P.operate(pg,req,authorized)
 check('approved feedback is filled and Return is clicked once',len(calls)==1 and editor.inner_text()==REQ['feedback'] and pg.get_by_role('button',name='Return').get_attribute('data-clicked')=='yes')
 check('verification reopens Returned and checks the same submission',out['verified'] and opens[-1] is True)
 preview=P.operate(pg,REQ);fail_read[0]=True
 check('a Return click without read-back is not success',refuses(lambda:P.operate(pg,{**req,'preview':preview},authorized),'verified'))
 P.open_target=original;P.validate_current=original_validate;b.close()

# Match actual inspected selector shapes, with a synthetic roster and panel.
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page()
 url='https://assignments.edu.cloud.microsoft/classes/'+source['class_id']+'/assignment-review/'+source['assignment_id']+'/submissions/33333333-3333-3333-3333-333333333333'
 markup='<table><tr><td>Example, Alex</td><td><a id="submission-row-speed-grader-0" aria-label="The student has Returned the assignment" href="'+url+'">Returned</a></td></tr></table><button role="tab" aria-selected="true">Returned (1)</button><button aria-label="Currently selected student: Alex Example">Selected student</button><div role="dialog"><div id="editorAnchor" role="textbox" contenteditable="true" aria-label="Feedback">Earlier feedback</div><button>Return</button></div>'
 pg.route('**/*',lambda r:r.fulfill(content_type='text/html',body=markup));pg.goto(url)
 original_session=P.T.Session
 class Session:
  def __init__(self,page,wait):self.page=page
  def open_one(self,cls,title):return {},'',source
  def frame(self):return self.page
 P.T.Session=Session
 _,_,actual=P.open_target(pg,REQ)
 check('inspected panel selectors bind the exact student and submission',actual['submission_id']=='33333333-3333-3333-3333-333333333333' and actual['existing']=='Earlier feedback')
 P.validate_current(pg,REQ,actual['submission_id'])
 check('a different submission is refused immediately before edits',refuses(lambda:P.validate_current(pg,REQ,'other-submission'),'selected Teams student'))
 check('saved assignment identity mismatch stops navigation',refuses(lambda:P.open_target(pg,{**REQ,'source':{**source,'assignment_id':'other'}}),'identity differs'))
 _,_,actual=P.open_target(pg,REQ,returned=True)
 check('Returned verification requires the returned roster status',actual['returned'])
 markup=markup.replace('has Returned','has Viewed')
 pg.goto(url)
 check('To-return status cannot masquerade as Returned',refuses(lambda:P.open_target(pg,REQ,returned=True),'did not confirm'))
 markup=markup.replace('Currently selected student: Alex Example','Currently selected student: Someone Else');pg.goto(url)
 check('different selected student stops before editing',refuses(lambda:P.open_target(pg,REQ),'expected student'))
 P.T.Session=original_session;b.close()

# Server guards + UI, with scripted destination reader. No live browser or model runner.
guard_app(A,HOME);A.PORT=18866;A.ALLOWED_HOSTS={'127.0.0.1:18866','localhost:18866'}
A.course_data=lambda:{'courses':[{'name':'Synthetic Band 10','grades':[10],'department':''}],'quarters':[{'label':'Q2','start':'2026-11-01','end':'2027-01-01'}],'school_year':'2026-27'}
A.load_standards=lambda:{};A.roster_for=lambda *a:[]
rec=A.save_assignment_record({'title':'Synthetic task','instructions':'Explain a rhythm.','course':{'name':'Synthetic Band 10','label':'Synthetic Band 10','sectionIds':[],'schoolYear':'2026-27'},'grade':'Grade 10','term':'Q2','standards':[],'teams':{'className':'Synthetic class','title':'Synthetic task','source':source}})
aid=rec['id'];st={'student_id':'CH-1','name':'Alex Example','grade':'Grade 10','work':'I counted the rest.','notes':'','level':'Proficient','feedback':REQ['feedback'],'myschool_comment':'A clear counted rest.','posting':{}}
bound={k:st[k] for k in ['student_id','name','work','notes','level','grade','feedback','myschool_comment']};bound.update(assignment=rec['title'],instructions=rec['instructions'],course='Synthetic Band 10',school_year='2026-27',quarter='Q2',standards=[])
st['approval']={'bound':json.dumps(bound),'at':'2026-11-02'};A.save_session(aid,[st],None)
A.start_worker();seen=[]
def fake(req,authorize):
 seen.append(copy.deepcopy(req))
 if req['op']=='inspect':return {'snapshot':'synthetic','existing':'Earlier feedback','read_at':time.time(),'submission_id':'33333333-3333-3333-3333-333333333333'}
 with authorize():return {'verified':True,'returned':True}
A.TEAMS_POST_RUNNER=fake
body={'op':'inspect','assignment':aid,'student_id':'CH-1','target_name':'Example, Alex'}
def waitjob(j):
 end=time.time()+10
 while time.time()<end:
  x=A.QUEUE.get(j['id'],with_results=True)
  if x['state'] not in ('queued','running'):return x
  time.sleep(.1)
 raise AssertionError('Job did not finish')
check('bulk posting remains off',refuses(lambda:A.approved_for_posting(aid),'disabled'))
check('unapproved student is refused before queueing',refuses(lambda:A.enqueue_teams_post_job({**body,'student_id':'other'}),'reviewed'))
check('missing saved Teams identity is refused',refuses(lambda:A.teams_destination({'teams':{}}),'Read this assignment'))
j=waitjob(A.enqueue_teams_post_job(body));preview=j['drafts'][0]['teams_post'];pid=j['id']
check('server uses approved feedback and saved destination, not browser input',preview['feedback']==st['feedback'] and preview['source']==source and preview['class']=='Synthetic class')
check('job journal excludes names and feedback',b'Alex' not in (A.APP_DATA/'jobs.sqlite').read_bytes() and st['feedback'].encode() not in (A.APP_DATA/'jobs.sqlite').read_bytes())
save={'op':'save','assignment':aid,'preview_id':pid,'confirm':True}
check('Return needs separate confirmation',refuses(lambda:A.enqueue_teams_post_job({**save,'confirm':False}),'Confirm'))
check('malformed preview identity is refused',refuses(lambda:A.enqueue_teams_post_job({**save,'preview_id':'not-a-job'})))
other=A.save_assignment_record({**{k:v for k,v in rec.items() if k not in ('id','version')},'title':'Other synthetic assignment'})
check('preview from another assignment is refused',refuses(lambda:A.enqueue_teams_post_job({**save,'assignment':other['id']}),'not a completed preview'))
j=waitjob(A.enqueue_teams_post_job(save));check('explicit confirmed job returns verified result',j['drafts'][0]['teams_post']['verified'])
check('used preview cannot post twice',refuses(lambda:A.enqueue_teams_post_job(save),'already used'))
j=waitjob(A.enqueue_teams_post_job(body));pid2=j['id']
saved=A.load_session(aid)['session'];changed=copy.deepcopy(st);changed['work']='Changed work';A.save_session(aid,[changed],saved['version'])
check('changed student work invalidates posting approval',refuses(lambda:A.enqueue_teams_post_job({**save,'preview_id':pid2}),'reviewed'))
saved=A.load_session(aid)['session'];A.save_session(aid,[st],saved['version'])
j=waitjob(A.enqueue_teams_post_job(body));pid3=j['id']
def revoke(req,authorize):
 saved=A.load_session(aid)['session'];A.save_session(aid,[changed],saved['version'])
 with authorize():raise AssertionError('must not enter edits')
A.TEAMS_POST_RUNNER=revoke
j=waitjob(A.enqueue_teams_post_job({**save,'preview_id':pid3}))
check('server rechecks approval immediately before edits',j['counts']['failed']==1 and not j['drafts'])
A.TEAMS_POST_RUNNER=fake;saved=A.load_session(aid)['session'];A.save_session(aid,[st],saved['version'])
server=ThreadingHTTPServer(('127.0.0.1',18866),A.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page();errors=[];pg.on('pageerror',lambda e:errors.append(str(e)))
 pg.route('**/api/models',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'models':[{'id':'fake','name':'fake','engine':'Ollama'}],'default':'fake','offline':[]})))
 pg.goto('http://127.0.0.1:18866/');pg.locator('#asg-pick').select_option(aid);time.sleep(1)
 pg.get_by_role('button',name='4 Draft & review').click();pg.get_by_role('button',name='Mark reviewed',exact=True).click();time.sleep(2.2)
 pg.get_by_role('button',name='5 Export & posting').click();
 try:pg.get_by_role('button',name='Post reviewed feedback to Teams…').click(timeout=5000)
 except Exception:
  print('LAUNCH diagnostic:',errors,pg.locator('.teams-post-pilot').count(),pg.locator('#step-delivery').get_attribute('hidden'),pg.locator('nav.steps').inner_text(),flush=True);raise
 dlg=pg.get_by_role('dialog',name='Teams posting pilot')
 try:dlg.get_by_label('Reviewed student',exact=True).select_option('CH-1',timeout=5000)
 except Exception:
  print('LOAD diagnostic:',dlg.locator('[role=status]').inner_text(),pg.evaluate("feedbackWorkspace.cards().map(c=>({p:feedbackWorkspace.payload(c),valid:feedbackWorkspace.valid(c)}))"),A.load_session(aid)['status'],flush=True);raise
 dlg.get_by_label('Exact student name in the Teams roster').fill('Example, Alex');dlg.get_by_role('button',name='Read Teams destination and preview').click()

 try:dlg.locator('.teams-post-preview h4').wait_for(timeout=15000)
 except Exception:
  print('UI diagnostic:',dlg.locator('[role=status]').inner_text(),errors,flush=True);raise
 check('UI preview shows destination and full approved feedback',st['feedback'] in dlg.locator('.teams-post-preview').inner_text() and 'Example, Alex' in dlg.locator('.teams-post-preview').inner_text())
 button=dlg.get_by_role('button',name='Post feedback and Return',exact=True)
 check('UI Return stays disabled until explicit confirmation',button.is_disabled())
 dlg.locator('input[type=checkbox]').check();button.click();dlg.get_by_text('Verified: feedback matches',exact=False).wait_for(timeout=15000)
 check('UI displays read-back result after posting',dlg.get_by_text('Verified: feedback matches',exact=False).is_visible())
 check('UI has no script errors',not errors)
 b.close()
A.QUEUE.stop();server.shutdown()
print(f'{sum(ok)}/{len(ok)} checks passed');sys.exit(0 if all(ok) else 1)
