"""Unpublished assignment creation, entirely synthetic: no Teams or real profile."""
import contextlib, copy, json, os, sys, tempfile, threading, time
from _common import APPDIR, LAUNCH, guard, guard_app
home=tempfile.mkdtemp();os.environ['HOME']=home;guard(home);sys.path.insert(0,APPDIR)
import app as A, teams_create as C
from playwright.sync_api import sync_playwright
from http.server import ThreadingHTTPServer
checks=[]
def check(label,v):
 checks.append(bool(v));print(('PASS ' if v else 'FAIL ')+label,flush=True)
def refuses(fn,part=''):
 try:fn();return False
 except (ValueError,FileNotFoundError) as e:return not part or part in str(e)
rec={'title':'Synthetic rhythm reflection','instructions':'Explain your rhythm.\nName one next step.','design':{'teamsClass':'Synthetic Band','submission':{'type':'notebook'},'teacherNotes':'PRIVATE NOTE'},'focus':['PRIVATE FOCUS']}
req=C.payload(rec)
check('only student-facing class, title and instructions cross the boundary',set(req)=={'class','title','instructions'} and 'PRIVATE' not in json.dumps(req))
check('missing class refused',refuses(lambda:C.payload({**rec,'design':{}})))
check('empty instructions refused',refuses(lambda:C.payload({**rec,'instructions':''})))
check('Forms quiz cannot become ordinary assignment',refuses(lambda:C.payload({**rec,'design':{**rec['design'],'submission':{'type':'forms'}}}),'New quiz'))
check('teacher-only focus marker refused',refuses(lambda:C.payload({**rec,'instructions':"Teacher's feedback focus (not shown to students): secret"})))
check('live browser guard refuses launch',refuses(lambda:C.run(req),'switched off'))
base='https://assignments.edu.cloud.microsoft/classes/11111111-1111-1111-1111-111111111111'
editor=base+'/assignment-editor/22222222-2222-2222-2222-222222222222'
check('editor identity accepts query without trusting it',C.editor_id(editor+'?returnPath=example')['assignment_id'].startswith('2222'))
check('rich-text spacing is ignored but missing words are refused',C.same_text('First.\n\nNext.', 'First.\nNext.') and not C.same_text('First. Next.', 'First.'))
check('foreign host rejected',refuses(lambda:C.editor_id(editor.replace('assignments.edu.cloud.microsoft','example.com'))))
check('non-editor route rejected',refuses(lambda:C.editor_id(base+'/assignment-review/22222222-2222-2222-2222-222222222222')))
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page(); saved={}; state={'published':0,'save':0,'created':0,'corrupt':False}
 def render(route):
  path=route.request.url
  if '/assignment-editor/' in path:
   title=saved.get('title',''); ins=saved.get('instructions','')
   if state['corrupt'] and title:ins='Changed remotely'
   import html
   body='<h1>New assignment</h1><input role="combobox" aria-label="Assign to" placeholder="Synthetic Band"><input aria-label="Enter title" value="'+html.escape(title,quote=True)+'"><div hidden style="white-space:pre-wrap" role="textbox" contenteditable="true" aria-label="Enter instructions">'+html.escape(ins)+'</div><div><a role="link" aria-disabled="true">Student view</a><button onclick="setTimeout(()=>document.getElementById(\'menu\').hidden=false,150)">More options</button></div><div role="menu" id="menu" hidden><button role="menuitem" id="save">Save as draft</button><button role="menuitem" id="assign">Assign</button></div>'
   body+='''<script>setTimeout(()=>document.querySelector('[contenteditable]').hidden=false,150);document.querySelector('#save').onclick=async()=>{await fetch('/save',{method:'POST',body:JSON.stringify({title:document.querySelector('input[aria-label=\"Enter title\"]').value,instructions:document.querySelector('[contenteditable]').innerText})});location.href='/classes/all/list'};document.querySelector('#assign').onclick=()=>fetch('/publish',{method:'POST'});</script>'''
  else:
   import html
   row='<div role="listitem"><span>'+html.escape(saved['title'])+'</span></div>' if saved else ''
   body='''<nav aria-label="Apps"><button>Assignments</button></nav><h1>Assignments</h1><button role="tab">Drafts</button><button id="new">Create assignment</button><button role="menuitem" id="newAssignment" hidden>New assignment</button><div role="dialog" aria-label="Create an assignment" hidden><button role="option">Synthetic Band Synthetic Band</button><button id="create">Create</button></div>'''+row
   body+='''<script>document.querySelector('#new').onclick=()=>document.querySelector('#newAssignment').hidden=false;document.querySelector('#newAssignment').onclick=()=>document.querySelector('[role=dialog]').hidden=false;document.querySelector('#create').onclick=async()=>{await fetch('/created',{method:'POST'});location.href='''+json.dumps(editor)+'''};const row=document.querySelector('[role=listitem]');if(row)row.onclick=()=>location.href='''+json.dumps(editor)+''';</script>'''
  route.fulfill(content_type='text/html',body=body)
 def route(r):
  path=r.request.url
  if path.endswith('/save'):saved.update(json.loads(r.request.post_data));state['save']+=1;r.fulfill(body='ok')
  elif path.endswith('/publish'):state['published']+=1;r.fulfill(body='ok')
  elif path.endswith('/created'):state['created']+=1;r.fulfill(body='ok')
  else:render(r)
 pg.route('**/*',route)
 original=C.T.Session
 class Session:
  def __init__(self,page,wait):self.page=page
  def frame(self):return self.page
  def wait_for(self,*a):return ''
 C.T.Session=Session
 pg.goto('https://assignments.edu.cloud.microsoft/classes/all/list')
 @contextlib.contextmanager
 def denied():raise C.DraftError('revoked');yield
 check('revoked authorization stops before Create and autosave',refuses(lambda:C.operate(pg,req,denied),'revoked') and state['created']==0)
 pg.goto('https://assignments.edu.cloud.microsoft/classes/all/list');calls=[]
 @contextlib.contextmanager
 def allow():calls.append(True);yield
 out=C.operate(pg,req,allow)
 check('one Create and one draft Save with no publish',state['created']==1 and state['save']==1 and state['published']==0 and len(calls)==1)
 check('full instructions survive save and reopened read-back',saved=={'title':req['title'],'instructions':req['instructions']} and out['verified'] and out['unpublished'])
 check('receipt identifies the created editor',out['url']==editor)
 # Unexpected editor content must not be overwritten.
 pg.goto('https://assignments.edu.cloud.microsoft/classes/all/list')
 check('nonempty editor refused without overwriting',refuses(lambda:C.operate(pg,req,allow),'not empty') and state['save']==1)
 pg.goto('https://assignments.edu.cloud.microsoft/classes/all/list');before_created=state['created']
 recovered=C.operate(pg,{**req,'recovery_url':editor},allow)
 check('recovery reuses matching existing draft without another Create',state['created']==before_created and recovered['verified'])
 pg.goto('https://assignments.edu.cloud.microsoft/classes/all/list')
 check('recovery refuses to overwrite different existing text',refuses(lambda:C.operate(pg,{**req,'title':'Different title','recovery_url':editor},allow),'not empty'))
 C.T.Session=original;b.close()

# Server requests are constructed only from the current saved record; journal has no instructions.
guard_app(A,home);A.course_data=lambda:{'courses':[{'name':'Synthetic Band','grades':[10],'department':''}],'quarters':[{'label':'Q2','start':'2026-11-01','end':'2027-01-01'}],'school_year':'2026-27'}
r=A.save_assignment_record(rec);aid=r['id'];A.start_worker(); seen=[]
def fake(request,authorize):
 with authorize():seen.append(copy.deepcopy(request))
 return {'verified':True,'unpublished':True,'url':editor,'class':request['class'],'title':request['title']}
A.TEAMS_CREATE_RUNNER=fake
check('confirmation required',refuses(lambda:A.enqueue_teams_create_job({'assignment':aid,'version':r['version']}),'confirm'))
check('stale version refused',refuses(lambda:A.enqueue_teams_create_job({'assignment':aid,'version':999,'confirm':True}),'current saved'))
check('unknown assignment refused',refuses(lambda:A.enqueue_teams_create_job({'assignment':'asg-not-found','version':1,'confirm':True})))
j=A.enqueue_teams_create_job({'assignment':aid,'version':r['version'],'confirm':True,'instructions':'INJECTED'})
end=time.time()+10
while time.time()<end and A.QUEUE.get(j['id'])['state'] in ('queued','running'):time.sleep(.05)
job=A.QUEUE.get(j['id'])
check('job completes from saved content, ignoring supplied instructions',job['state']=='completed' and seen[0]['instructions']==rec['instructions'])
check('repeat request blocked after success',refuses(lambda:A.enqueue_teams_create_job({'assignment':aid,'version':r['version'],'confirm':True}),'already requested'))
check('journal metadata contains no instructions',rec['instructions'] not in str({k:v for k,v in job.items() if k not in ('drafts','items')}))
# Current record changing before the child's authorization stops creation.
r2=A.save_assignment_record({**rec,'title':'Another synthetic task'});old=A.TEAMS_CREATE_RUNNER
def stale(request,authorize):
 A.save_assignment_record({**r2,'instructions':'Edited later'},r2['version'])
 with authorize():raise AssertionError('must not reach editor')
A.TEAMS_CREATE_RUNNER=stale
j=A.enqueue_teams_create_job({'assignment':r2['id'],'version':r2['version'],'confirm':True});end=time.time()+10
while time.time()<end and A.QUEUE.get(j['id'])['state'] in ('queued','running'):time.sleep(.05)
check('saved edit voids authorization before editor creation',any(i['state']=='failed' for i in A.QUEUE.get(j['id'])['items']))
check('failure before authorization releases duplicate claim',r2['id'] not in A._read_json(A.APP_DATA / 'teams-draft-claims.json',{}))
A.TEAMS_CREATE_RUNNER=old
r3=A.save_assignment_record({**rec,'title':'UI synthetic task','design':{**rec['design'],'directions':'Explain your rhythm.'}})
# Page integration uses the new enabled button and explicit preview.
A.PORT=18869;A.ALLOWED_HOSTS={'127.0.0.1:18869','localhost:18869'};A.load_standards=lambda:{}
http=ThreadingHTTPServer(('127.0.0.1',18869),A.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page();pg.on('pageerror',lambda e:print('PAGE ERROR',e,flush=True));pg.goto('http://127.0.0.1:18869');pg.wait_for_timeout(1000)
 pg.on('dialog',lambda d:d.accept());pg.locator('#asg-pick').select_option(r3['id']);pg.wait_for_timeout(500);pg.locator('.step').nth(0).click();btn=pg.get_by_role('button',name='Create draft in Teams',exact=True);btn.wait_for(state='attached',timeout=15000)
 check('Design button is enabled',btn.count()==1 and btn.is_enabled())
 check('draft preview requires explicit checkbox',pg.get_by_role('dialog',name='Create Teams draft',include_hidden=True).count()==1 and pg.get_by_role('button',name='Create unpublished draft',include_hidden=True).is_disabled())
 before=len(seen);btn.click();dialog=pg.get_by_role('dialog',name='Create Teams draft');dialog.wait_for(state='visible')
 check('preview shows full student-facing text and excludes private notes','UI synthetic task' in dialog.inner_text() and 'Explain your rhythm.' in dialog.inner_text() and 'PRIVATE' not in dialog.inner_text() and len(seen)==before)
 dialog.get_by_role('checkbox').check();dialog.get_by_role('button',name='Create unpublished draft').click()
 pg.wait_for_function("document.querySelector('dialog[aria-label=\"Create Teams draft\"] [role=status]').textContent.startsWith('Verified in Teams Drafts:')",timeout=15000)
 check('explicit confirmation runs background job and shows verified unpublished receipt',len(seen)==before+1 and 'Unpublished' in dialog.inner_text())
 dialog.get_by_role('button',name='Close',exact=True).click();btn.click()
 pg.wait_for_function("document.querySelector('dialog[aria-label=\"Create Teams draft\"] [role=status]').textContent.startsWith('Previously verified unpublished draft:')",timeout=15000)
 dialog.get_by_role('checkbox').check()
 check('reopening restores receipt and prevents duplicate creation',dialog.get_by_role('button',name='Create unpublished draft').is_disabled() and len(seen)==before+1)
 b.close()
http.shutdown();A.QUEUE.stop()
print(f'{sum(checks)}/{len(checks)} checks passed')
sys.exit(0 if all(checks) else 1)
