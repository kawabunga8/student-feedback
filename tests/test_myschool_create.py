"""Unpublished MySchool creation: invented browser pages and isolated local app only."""
import contextlib, copy, html, json, os, sys, tempfile, threading, time
from _common import APPDIR, LAUNCH, guard, guard_app
home=tempfile.mkdtemp();os.environ['HOME']=home;guard(home);sys.path.insert(0,APPDIR)
import app as A, myschool_create as M
from playwright.sync_api import sync_playwright
from http.server import ThreadingHTTPServer
checks=[]
def check(label,v):checks.append(bool(v));print(('PASS ' if v else 'FAIL ')+label,flush=True)
def refuses(fn,part=''):
 try:fn();return False
 except (ValueError,FileNotFoundError) as e:return not part or part in str(e)
rec={'title':'Synthetic rhythm reflection','instructions':'Describe your first attempt.\nExplain your next step.','design':{'directions':'Describe your first attempt.','teacherNotes':'PRIVATE NOTE'},'focus':['PRIVATE FOCUS']}
req={**M.payload(rec),'course':'Synthetic Band 10','kind':'Formative','due':'2026-11-10','op':'inspect'}
check('payload excludes private focus and notes',set(M.payload(rec))=={'title','instructions'} and 'PRIVATE' not in json.dumps(M.payload(rec)))
check('empty title refused',refuses(lambda:M.payload({**rec,'title':''})))
check('teacher-only instructions refused',refuses(lambda:M.payload({**rec,'instructions':"Teacher's feedback focus (not shown to students): private"})))
check('invalid date refused',refuses(lambda:M.validate_choices({**req,'due':'2026-02-30'}),'due date'))
check('teacher must choose assignment type',refuses(lambda:M.validate_choices({**req,'kind':'AI choice'}),'yourself'))
check('exact course required',refuses(lambda:M.validate_choices({**req,'course':''})))
check('weight formatting preserves value but a changed weight is refused',M.same_weight('1.00','1') and not M.same_weight('2','1') and not M.same_weight('NaN','1'))
check('browser-off guard blocks real profile',refuses(lambda:M.run(req),'switched off'))

with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page();saved={};state={'saves':0,'bad_readback':False,'unsafe':False};events=[]
 def route(r):
  url=r.request.url
  if '/save-local' in url:
   saved.update(json.loads(r.request.post_data));state['saves']+=1;r.fulfill(body='ok');return
  if '/assignment_management.php' in url:
   esc=lambda s:html.escape(str(s),quote=True)
   cells=['',saved.get('title',''),'Formative',saved.get('due',''),'Synthetic Band 10','No']
   row='<div class="slick-row">'+''.join('<div class="slick-cell">'+('<a href="javascript:loadAssignment(12345)">'+esc(c)+'</a>' if i==1 else esc(c))+'</div>' for i,c in enumerate(cells))+'</div>'
   r.fulfill(content_type='text/html',body='<button>View all assignments</button><div id="all_assignments_container"><input placeholder="Title">'+row+'</div>');return
  current=saved if 'exercise_id=' in url else {}
  esc=lambda s:html.escape(str(s),quote=True)
  body='<style>input[type=radio]{position:absolute;clip:rect(0,0,0,0);width:1px;height:1px}</style><h2>New assignment</h2><a href="#" id="planningLink">Planning</a><a href="#" id="optionsLink">Options</a><section id="planning"><input id="exercise_label" value="'+esc(current.get('title',''))+'">'
  body+='<div><input type="radio" name="course_id" id="course1" value="11" '+('checked' if current else '')+'><label role="button" for="course1">Synthetic Band 10</label></div>'
  body+='<div><input type="radio" name="course_id" id="course2" value="12"><label role="button" for="course2">Synthetic Band 12</label></div>'
  body+='<div id="kinds"><input type="radio" name="exercise_type_id" id="kind1" value="21" '+('checked' if current else '')+'><label role="button" for="kind1">Formative</label><input type="radio" name="exercise_type_id" id="kind2" value="22"><label role="button" for="kind2">Summative</label></div>'
  text=current.get('instructions','')+(' CHANGED' if current and state['bad_readback'] else '')
  frame='<body id="tinymce" contenteditable="true" style="white-space:pre-wrap">'+esc(text)+'</body>'
  body+='<iframe id="exercise_comment_ifr" srcdoc="'+esc(frame)+'"></iframe>'
  body+='<input id="exercise_due_date" value="'+esc(current.get('due',''))+'"><select id="publication_status_id"><option value="0">No</option><option value="2">Assignment &amp; grades</option></select><input id="unpublish_date"><input type="checkbox" id="email_students"></section>'
  body+='<section id="options" hidden><select id="scale_group_id"><option>SC - Proficiency</option></select><input id="exercise_weight" value="1"><select id="submission_type_id"><option>Do not accept</option></select><div id="learning_outcome_tree"><ul>'
  for label in ('Applying Skills','Analyzing'):
   body+='<li><span class="dynatree-node dynatree-folder'+(' dynatree-selected' if label in current.get('outcomes',[]) else '')+'"><a class="dynatree-title" href="#">'+label+'</a></span></li>'
  body+='</ul></div></section><button data-test="save">save</button>'
  if current:body=body.replace('<input type="checkbox" id="email_students">','').replace('id="exercise_weight" value="1"','id="exercise_weight" value="1.00"')
  body+='''<script>document.querySelector('#planningLink').onclick=e=>{e.preventDefault();planning.hidden=false;options.hidden=true};document.querySelector('#optionsLink').onclick=e=>{e.preventDefault();planning.hidden=true;options.hidden=false};document.querySelectorAll('.dynatree-title').forEach(a=>a.onclick=e=>{e.preventDefault();a.parentElement.classList.toggle('dynatree-selected')});document.querySelector('[data-test=save]').onclick=async()=>{const d={title:exercise_label.value,instructions:document.querySelector('iframe').contentDocument.body.innerText,due:exercise_due_date.value,publication:publication_status_id.value,email:email_students.checked,outcomes:[...document.querySelectorAll('.dynatree-selected a')].map(a=>a.textContent)};await fetch('/save-local',{method:'POST',body:JSON.stringify(d)});location.href='''+json.dumps(M.MANAGEMENT_URL)+'''};</script>'''
  if state['unsafe']:body=body.replace('<option value="2">','<option selected value="2">')
  r.fulfill(content_type='text/html',body=body)
 pg.route('**/*',route)
 listed=M.operate(pg,{**req,'op':'list'})
 check('course listing exposes only course labels and performs no save',listed=={'courses':['Synthetic Band 10','Synthetic Band 12']} and state['saves']==0)
 state['unsafe']=True
 check('unsafe publication default blocks preview before writes',refuses(lambda:M.operate(pg,req),'not unpublished') and state['saves']==0)
 state['unsafe']=False
 preview=M.operate(pg,req)
 check('preview lists actual outcomes, scale and defaults',preview['available_outcomes']==['Applying Skills','Analyzing'] and preview['scale']=='SC - Proficiency' and preview['weight']=='1' and preview['submissions']=='Do not accept')
 check('preview performs no Save and does not fill assignment title',state['saves']==0 and pg.locator('#exercise_label').input_value()=='')
 save_req={**req,'op':'save','preview':preview,'outcomes':['Applying Skills','Analyzing']}
 @contextlib.contextmanager
 def denied():raise M.PilotError('revoked');yield
 check('authorization revoked before writes prevents Save',refuses(lambda:M.operate(pg,save_req,denied),'revoked') and state['saves']==0)
 check('expired preview prevents Save',refuses(lambda:M.operate(pg,{**save_req,'preview':{**preview,'read_at':0}}),'expired') and state['saves']==0)
 check('unknown outcome refused',refuses(lambda:M.operate(pg,{**save_req,'outcomes':['Invented outcome']}),'available') and state['saves']==0)
 check('duplicate outcomes refused',refuses(lambda:M.operate(pg,{**save_req,'outcomes':['Applying Skills']*2}),'available'))
 result=M.operate(pg,save_req)
 check('one Save produces verified unpublished assignment with email off',state['saves']==1 and result['verified'] and result['unpublished'] and result['email'] is False)
 check('title, full instructions, date and selected outcomes read back',saved['title']==req['title'] and saved['instructions']==req['instructions'] and saved['due']==req['due'] and result['outcomes']==save_req['outcomes'])
 check('saved form may omit create-time email control',result['email_control_on_readback'] is False)
 verified=M.operate(pg,{**save_req,'op':'verify'})
 check('read-only verification never repeats Save',verified['verified'] and state['saves']==1)
 check('receipt uses canonical saved assignment URL',result['url']==M.NEW_URL+'?exercise_id=12345')
 state['bad_readback']=True
 check('changed saved instructions are not reported as success',refuses(lambda:M.operate(pg,save_req),'read-back differs'))
 pg.goto('https://example.com/content/assignment/assignment_edit.php')
 check('foreign page rejected before writes',refuses(lambda:M.check_new(pg),'not a new'))
 b.close()

guard_app(A,home);A.course_data=lambda:{'courses':[{'name':'Synthetic Band 10','grades':[10],'department':''}],'quarters':[{'label':'Q2','start':'2026-11-01','end':'2027-01-01'}],'school_year':'2026-27'};A.load_standards=lambda:{}
r=A.save_assignment_record(rec);aid=r['id'];A.start_worker();calls=[]
def fake(request,authorize):
 calls.append(copy.deepcopy(request))
 if request['op']=='list':return {'courses':['Synthetic Band 10']}
 if request['op']=='inspect':return {**preview,'read_at':time.time()}
 with authorize():return {**result,'title':request['title'],'course':request['course'],'due':request['due'],'kind':request['kind'],'outcomes':request['outcomes']}
A.MYSCHOOL_CREATE_RUNNER=fake

def follow(j):
 end=time.time()+10
 while time.time()<end:
  out=A.QUEUE.get(j['id'],with_results=True)
  if out['state'] not in ('queued','running'):return out
  time.sleep(.05)
 raise AssertionError('timeout')
base={'type':'myschool_create','assignment':aid,'version':r['version']}
check('stale saved version refused',refuses(lambda:A.enqueue_myschool_create_job({**base,'op':'list','version':999}),'changed'))
check('unknown assignment refused',refuses(lambda:A.enqueue_myschool_create_job({**base,'op':'list','assignment':'asg-invalid'})))
ins=follow(A.enqueue_myschool_create_job({**base,'op':'inspect','course':req['course'],'kind':req['kind'],'due':req['due']}))
check('server preview uses saved instructions, not arbitrary page text',calls[-1]['instructions']==rec['instructions'])
body={**base,'op':'save','preview_id':ins['id'],'outcomes':['Applying Skills'],'confirm':True}
check('explicit Save confirmation required',refuses(lambda:A.enqueue_myschool_create_job({**body,'confirm':False}),'Confirm'))
check('server rejects unavailable outcomes',refuses(lambda:A.enqueue_myschool_create_job({**body,'outcomes':['Fake']}),'available'))
done=follow(A.enqueue_myschool_create_job(body))
check('server Save completes with only reviewed preview fields',done['drafts'][0]['myschool_create']['verified'] and calls[-1]['course']==req['course'])
verify_job=follow(A.enqueue_myschool_create_job({**base,'op':'verify','previous_id':done['id']}))
check('server can verify previous Save without authorizing another Save',verify_job['drafts'][0]['myschool_create']['verified'] and calls[-1]['op']=='verify')
check('duplicate Save blocked for same assignment and course',refuses(lambda:A.enqueue_myschool_create_job(body),'already requested'))
r3=A.save_assignment_record({**rec,'title':'Changed-before-Save synthetic task'})
b3={**base,'assignment':r3['id'],'version':r3['version']}
p3=follow(A.enqueue_myschool_create_job({**b3,'op':'inspect','course':req['course'],'kind':req['kind'],'due':req['due']}))
original=A.MYSCHOOL_CREATE_RUNNER
saved_calls=[]
def changed(request,authorize):
 A.save_assignment_record({**r3,'instructions':'Changed after preview'},r3['version'])
 with authorize():saved_calls.append(True)
 return result
A.MYSCHOOL_CREATE_RUNNER=changed
failed=follow(A.enqueue_myschool_create_job({**b3,'op':'save','preview_id':p3['id'],'outcomes':['Analyzing'],'confirm':True}))
check('saved edit revokes authorization immediately before MySchool save',any(i['state']=='failed' for i in failed['items']) and not saved_calls)
check('failure before Save authorization releases claim',r3['id']+':'+preview['course_id'] not in A._read_json(A.APP_DATA/'myschool-assignment-claims.json',{}))
A.MYSCHOOL_CREATE_RUNNER=original
# GUI full preview/confirm/save workflow, a second synthetic local record.
r2=A.save_assignment_record({**rec,'title':'UI synthetic MySchool task'});A.PORT=18870;A.ALLOWED_HOSTS={'127.0.0.1:18870','localhost:18870'}
http=ThreadingHTTPServer(('127.0.0.1',18870),A.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
with sync_playwright() as p:
 b=p.chromium.launch(**LAUNCH);pg=b.new_page();errors=[];pg.on('pageerror',lambda e:errors.append(str(e)));pg.on('dialog',lambda d:d.accept());pg.goto('http://127.0.0.1:18870');pg.locator('#asg-pick').select_option(r2['id']);pg.wait_for_timeout(500);pg.locator('.step').nth(0).click()
 pg.get_by_role('button',name='Create assignment in MySchool',exact=True).click();dlg=pg.get_by_role('dialog',name='Create MySchool assignment');dlg.wait_for(state='visible')
 check('GUI preview excludes private notes','UI synthetic MySchool task' in dlg.inner_text() and 'PRIVATE' not in dlg.inner_text())
 dlg.get_by_role('button',name='Load MySchool courses').click();pg.wait_for_function("document.querySelector('select[aria-label=\"MySchool course\"]').options.length>1")
 dlg.get_by_label('MySchool course',exact=True).select_option('Synthetic Band 10');dlg.get_by_label('Assignment type',exact=True).select_option('Formative');dlg.get_by_label('MySchool due date',exact=True).fill('2026-11-10')
 dlg.get_by_role('button',name='Read MySchool form and preview').click();dlg.get_by_label('Applying Skills',exact=True).wait_for(state='visible')
 check('Save stays disabled until outcome and confirmation',dlg.get_by_role('button',name='Save unpublished assignment to MySchool').is_disabled())
 dlg.get_by_label('Applying Skills',exact=True).check();dlg.get_by_role('checkbox',name='I checked',exact=False).check();dlg.get_by_role('button',name='Save unpublished assignment to MySchool').click()
 pg.wait_for_function("document.querySelector('dialog[aria-label=\"Create MySchool assignment\"] [role=status]').textContent.startsWith('Verified unpublished in MySchool:')",timeout=15000)
 check('GUI completes explicit unpublished Save and displays receipt','Email off' in dlg.locator('[role=status]').inner_text() and not errors)
 b.close()
http.shutdown();A.QUEUE.stop()
print(f'{sum(checks)}/{len(checks)} checks passed');sys.exit(0 if all(checks) else 1)
