"""One-student MySchool prototype: invented DOM, temporary HOME, no live browser profile.
Uses an alternate local port; production Student Feedback and Ollama may keep running.
"""
import contextlib, copy, html, json, os, sys, tempfile, threading, time, urllib.request, urllib.error
from _common import APPDIR, LAUNCH, guard, guard_app
HOME=tempfile.mkdtemp();os.environ['HOME']=HOME;guard(HOME);sys.path.insert(0,APPDIR)
import app as A, myschool_post as M
from playwright.sync_api import sync_playwright
from http.server import ThreadingHTTPServer
ok=[]
def check(label, cond):
 ok.append(bool(cond));print(('PASS ' if cond else 'FAIL ')+label,flush=True)
def refuses(fn, text=''):
 try:fn();return False
 except (ValueError,PermissionError) as e:return not text or text in str(e)
URL='https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=123'
REQ={'op':'inspect','url':URL,'title':'Synthetic Rhythm','course':'D Synthetic Band 10','target_name':'Example, Alex','code':'PRF','comment':'Your counted rest is clear. Next, compare both attempts.','mark_graded':True}
check('URL rejects off-host, credentials, HTTP, extra parameters and wrong paths',all(refuses(lambda u=u:M.canonical_url(u)) for u in ['https://evil.example/'+M.PATH,URL+'&token=x',URL.replace('https:','http:'),URL.replace('rcs.myschoolmanagement.com','user@rcs.myschoolmanagement.com'),URL.replace('assignment_edit.php','dashboard.php')]))
check('URL canonicalises expected assignment and ignores section fragment',M.canonical_url(URL+'#section_3')==URL)
check('teacher level mapping preserves plus',M.level_code('Proficient+')=='PRF+' and refuses(lambda:M.level_code('')))
check('browser-off guard prevents all live launches',refuses(lambda:M.run(REQ),'switched off'))

def base_state():
 return {'title':REQ['title'],'course':REQ['course'],'publication':'0','students':[{'id':'101','name':'Example, Alex','comment':'Old comment','status':'1','criteria':[{'input':'grade_101_501','selected':'','options':[{'code':'EMG','value':'1'},{'code':'DEV','value':'2'},{'code':'PRF','value':'3'},{'code':'EXT','value':'4'}]}]},{'id':'102','name':'Example, Bailey','comment':'Leave unchanged','status':'1','criteria':[{'input':'grade_102_501','selected':'2','options':[{'code':'EMG','value':'1'},{'code':'DEV','value':'2'},{'code':'PRF','value':'3'},{'code':'EXT','value':'4'}]}]}]}
state=base_state();posts=[]
def markup():
 esc=html.escape
 rows=[]
 for s in state['students']:
  assessments=''.join('<div class="assessment"><input type="hidden" name="grade['+s['id']+'][501]" id="'+c['input']+'" value="'+c['selected']+'">'+''.join('<span class="scale_option" value="'+o['value']+'">'+o['code']+'</span>' for o in c['options'])+'</div>' for c in s['criteria'])
  rows.append('<div class="evaluation_group"><img alt="'+esc(s['name'])+'">'+assessments+'<textarea id="submission_comment_'+s['id']+'">'+esc(s['comment'])+'</textarea><select id="submission_status_'+s['id']+'"><option value="1" '+('selected' if s['status']=='1' else '')+'>Not yet graded</option><option value="2" '+('selected' if s['status']=='2' else '')+'>Graded</option></select></div>')
 return '''<html><body><input id="exercise_label" value="'''+esc(state['title'])+'''"><div><input name="course_id" type="radio" checked>'''+esc(state['course'])+'''</div><select id="publication_status_id"><option value="0" selected>No</option></select><a href="#section_3">Assessment</a><div id="student_grid">'''+''.join(rows)+'''</div><button type="button" id="save">save</button><script>
 document.querySelectorAll('.scale_option').forEach(e=>e.onclick=()=>e.parentElement.querySelector('input').value=e.getAttribute('value'));
 document.querySelector('#save').onclick=async()=>{await fetch(location.href,{method:'POST',body:JSON.stringify([...document.querySelectorAll('.evaluation_group')].map(r=>({id:r.querySelector('textarea').id.replace('submission_comment_',''),comment:r.querySelector('textarea').value,status:r.querySelector('select').value,selected:r.querySelector('.assessment input').value})))});};
 </script></body></html>'''
def route(r):
 if r.request.method=='POST':
  data=json.loads(r.request.post_data);posts.append(data)
  for item in data:
   s=next(s for s in state['students'] if s['id']==item['id']);s['comment']=item['comment'];s['status']=item['status'];s['criteria'][0]['selected']=item['selected']
  return r.fulfill(status=200,body='ok')
 return r.fulfill(status=200,content_type='text/html',body=markup())
with sync_playwright() as p:
 browser=p.chromium.launch(**LAUNCH);page=browser.new_page();page.route('**/*',route)
 pre=M.operate(page,REQ)
 check('inspect returns current destination and sends no POST',pre['target_id']=='101' and pre['existing']['comment']=='Old comment' and not posts)
 check('preview retains unpublished state',pre['publication']=='0')
 check('wrong title stops',refuses(lambda:M.operate(page,{**REQ,'title':'Wrong'}),'title or course'))
 check('wrong course stops',refuses(lambda:M.operate(page,{**REQ,'course':'Wrong'}),'title or course'))
 check('unknown student stops',refuses(lambda:M.operate(page,{**REQ,'target_name':'Unknown'}),'student'))
 state['students'][0]['criteria'].append(copy.deepcopy(state['students'][0]['criteria'][0]))
 check('multiple criteria refused instead of assigning a blanket level',refuses(lambda:M.operate(page,REQ),'exactly one'))
 state=base_state()
 pre=M.operate(page,REQ);denied=[]
 @contextlib.contextmanager
 def deny():
  denied.append(True);raise M.PilotError('Approval changed');yield
 check('approval revoked just before save prevents edits and POST',refuses(lambda:M.operate(page,{**REQ,'op':'save','preview':pre},deny),'Approval changed') and not posts)
 state['students'][1]['comment']='Another teacher edited this'
 check('any remote change after preview refuses Save',refuses(lambda:M.operate(page,{**REQ,'op':'save','preview':pre}),'changed since') and not posts)
 state=base_state();pre=M.operate(page,REQ)
 check('expired preview refuses Save',refuses(lambda:M.operate(page,{**REQ,'op':'save','preview':{**pre,'read_at':time.time()-601}}),'expired'))
 allowed=[]
 @contextlib.contextmanager
 def allow():allowed.append(True);yield
 result=M.operate(page,{**REQ,'op':'save','preview':pre},allow)
 check('explicit save is read back and verified',result['verified'] and len(posts)==1 and allowed)
 check('approved level, comment and optional Graded status persist',state['students'][0]['criteria'][0]['selected']=='3' and state['students'][0]['comment']==REQ['comment'] and state['students'][0]['status']=='2')
 check('other students and publication unchanged',state['students'][1]==base_state()['students'][1] and state['publication']=='0')
 result=M.operate(page,{**REQ,'op':'save','preview':pre},allow)
 check('retry of exact saved values verifies without another Save',result['already_matching'] and len(posts)==1)
 state=base_state();state['students'].append(copy.deepcopy(state['students'][0]))
 check('duplicate destination names are refused',refuses(lambda:M.operate(page,REQ),'repeated'))
 state=base_state();pre=M.operate(page,REQ);n=len(posts)
 def ignore_save(r):
  if r.request.method=='POST':posts.append('ignored');return r.fulfill(status=200,body='ok')
  return route(r)
 page.unroute('**/*');page.route('**/*',ignore_save)
 check('a save that does not persist is not reported as verified',refuses(lambda:M.operate(page,{**REQ,'op':'save','preview':pre},allow),'could not be verified') and len(posts)==n+1)
 browser.close()

# Server: real approval validation, stand-in MySchool runner.
guard_app(A,HOME);A.PORT=18865;A.ALLOWED_HOSTS={'127.0.0.1:18865','localhost:18865'}
A.course_data=lambda:{'courses':[{'name':'Synthetic Band 10','grades':[10],'sections':[{'id':'S1'}],'department':''}],'quarters':[{'label':'Q2','start':'2026-11-01','end':'2027-01-01'}],'school_year':'2026-27','source':'live','note':'Synthetic'}
A.load_standards=lambda:{};A.roster_for=lambda *a:[]
rec=A.save_assignment_record({'title':'Synthetic Rhythm','instructions':'Explain a rhythm.','course':{'name':'Synthetic Band 10','label':'Synthetic Band 10','sectionIds':['S1'],'schoolYear':'2026-27'},'grade':'Grade 10','term':'Q2','standards':[],'length':'paragraph'})
aid=rec['id'];st={'student_id':'CH-1','name':'Alex Example','grade':'Grade 10','work':'I counted the rest.','notes':'','level':'Proficient','feedback':'Your counted rest is clear.','myschool_comment':REQ['comment'],'posting':{}}
bound={k:st[k] for k in ['student_id','name','work','notes','level','grade','feedback','myschool_comment']};bound.update(assignment=rec['title'],instructions=rec['instructions'],course='Synthetic Band 10',school_year='2026-27',quarter='Q2',standards=[])
st['approval']={'bound':json.dumps(bound),'at':'2026-11-01'};A.save_session(aid,[st],None)
check('bulk automated posting remains disabled',refuses(lambda:A.approved_for_posting(aid),'disabled'))
check('pilot reads current server-validated approvals only',len(A.approved_for_posting(aid,destination='myschool_pilot'))==1)
calls=[]
def fake(req,authorize):
 calls.append(req['op'])
 if req['op']=='inspect':return {'snapshot':'synthetic','target_id':'101','read_at':time.time(),'existing':{'level':'','comment':'','status':'1'},'desired':{'level':'3','comment':req['comment'],'status':'2' if req['mark_graded'] else '1'},'publication':'0'}
 with authorize():return {'verified':True,'already_matching':False,'publication':'0'}
A.MYSCHOOL_RUNNER=fake;A.start_worker()
server=ThreadingHTTPServer(('127.0.0.1',18865),A.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
def call(method,path,data=None,origin=None):
 q=urllib.request.Request('http://127.0.0.1:18865'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Origin':origin} if origin else {})},method=method)
 try:
  with urllib.request.urlopen(q) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def wait_job(j):
 for _ in range(100):
  d=call('GET','/api/jobs/'+j['id'])[1]['job']
  if d['state'] in ('completed','failed'):return d
  time.sleep(.05)
 raise AssertionError('job timeout')
body={**REQ,'type':'myschool','assignment':aid,'student_id':'CH-1'}
_,out=call('POST','/api/jobs',body);j=wait_job(out['job']);pid=j['id']
check('preview job stores approved comment and target in sidecar',j['drafts'][0]['myschool']['comment']==REQ['comment'] and calls==['inspect'])
_,out=call('POST','/api/jobs',{'type':'myschool','op':'save','assignment':aid,'preview_id':pid})
check('Save without explicit confirmation refused', 'Confirm' in out.get('error',''))
check('cross-origin Save refused',call('POST','/api/jobs',body,'http://evil.example')[0]==403)
_,out=call('POST','/api/jobs',{'type':'myschool','op':'save','assignment':aid,'preview_id':pid,'confirm':True});j=wait_job(out['job'])
check('explicit Save job verifies with approval guard',j['drafts'][0]['myschool']['verified'] and calls==['inspect','save'])
_,out=call('POST','/api/jobs',{'type':'myschool','op':'save','assignment':aid,'preview_id':pid,'confirm':True})
check('reusing a consumed preview is refused', 'already used' in out.get('error',''))
_,out=call('POST','/api/jobs/'+j['id']+'/resume',{})
check('Save jobs never resume automatically or on generic resume', 'not resumed' in out.get('error',''))
saved=A.load_session(aid)['session'];changed=copy.deepcopy(saved['students']);changed[0]['myschool_comment']='Changed after approval';A.save_session(aid,changed,saved['version'])
_,out=call('POST','/api/jobs',body)
check('stale approval refused at enqueue', 'current approval' in out.get('error',''))
# Revoke approval while the simulated browser is open: the final guard must stop Save.
saved=A.load_session(aid)['session'];A.save_session(aid,[st],saved['version'])
_,out=call('POST','/api/jobs',body);preview=wait_job(out['job'])
old_runner=A.MYSCHOOL_RUNNER
saved_before=[]
def revoke_before_save(req,authorize):
 saved=A.load_session(aid)['session'];rows=copy.deepcopy(saved['students']);rows[0]['work']='Changed while the browser was open';A.save_session(aid,rows,saved['version'])
 with authorize():saved_before.append(True);return {'verified':True}
A.MYSCHOOL_RUNNER=revoke_before_save
_,out=call('POST','/api/jobs',{'type':'myschool','op':'save','assignment':aid,'preview_id':preview['id'],'confirm':True});revoked=wait_job(out['job'])
check('server rechecks approval immediately before browser Save',revoked['counts']['failed']==1 and not saved_before)
A.MYSCHOOL_RUNNER=old_runner
journal=A.APP_DATA/'jobs.sqlite'
check('job journal contains no student names or approved comment',REQ['comment'].encode() not in journal.read_bytes() and REQ['target_name'].encode() not in journal.read_bytes())
# Restore original, then exercise the GUI's review/save/preview path with synthetic local data.
saved=A.load_session(aid)['session'];A.save_session(aid,[st],saved['version'])
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page()
 pg.route('**/api/models',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'models':[{'id':'fake','name':'fake','engine':'Ollama'}],'default':'fake'})))
 pg.goto('http://127.0.0.1:18865/');pg.locator('#asg-pick').select_option(aid);time.sleep(1)
 pg.get_by_role('button',name='4 Draft & review').click();pg.get_by_role('button',name='Mark reviewed',exact=True).click();time.sleep(2.2)
 pg.get_by_role('button',name='5 Export & posting').click();pg.get_by_role('button',name='Post reviewed assessment to MySchool…').click()
 pg.get_by_label('Reviewed student',exact=True).select_option('CH-1')
 pg.get_by_label('Exact student name shown in MySchool',exact=True).fill('Previous destination')
 pg.get_by_label('Reviewed student',exact=True).select_option('')
 check('changing reviewed student clears the previous MySchool identity',pg.get_by_label('Exact student name shown in MySchool',exact=True).input_value()=='')
 pg.get_by_label('Reviewed student',exact=True).select_option('CH-1')
 pg.get_by_label('MySchool assignment address',exact=True).fill(URL)
 pg.get_by_label('Exact MySchool assignment title',exact=True).fill(REQ['title']);pg.get_by_label('Exact MySchool course name',exact=True).fill(REQ['course']);pg.get_by_label('Exact student name shown in MySchool',exact=True).fill(REQ['target_name'])
 pg.get_by_role('button',name='Read destination and preview',exact=True).click();pg.wait_for_selector('.myschool-preview h4',timeout=15000)
 check('GUI preview displays exact approved comment and destination',REQ['comment'] in pg.locator('.myschool-preview').inner_text() and REQ['target_name'] in pg.locator('.myschool-preview').inner_text())
 save=pg.get_by_role('button',name='Save this approved assessment to MySchool',exact=True)
 check('GUI Save disabled until explicit confirmation',save.is_disabled())
 pg.locator('dialog[aria-label="MySchool posting pilot"] input[type="checkbox"]').last.check();save.click()
 pg.get_by_text('Verified by reopening MySchool:',exact=False).wait_for(timeout=15000)
 check('GUI shows verified receipt after one-student Save',pg.get_by_text('Verified by reopening MySchool:',exact=False).is_visible())
 b.close()
A.QUEUE._stop=True;server.shutdown()
print(f'{sum(ok)}/{len(ok)} checks passed');sys.exit(0 if all(ok) else 1)
