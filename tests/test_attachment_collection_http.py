"""End-to-end HTTP job routing and result recovery with synthetic roster/reader, isolated ports and HOME."""
import json,os,sys,tempfile,threading,time,urllib.request,urllib.error
from _common import APPDIR,guard,guard_app
os.environ['HOME']=tempfile.mkdtemp(prefix='sf-attachment-http-');guard(os.environ['HOME']);sys.path.insert(0,APPDIR)
import app
guard_app(app,os.environ['HOME'])
source={'class_id':'11111111-2222-4333-8444-555555555555','assignment_id':'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'}
rec=app.save_assignment_record({'title':'Synthetic design','course':{'name':'Synthetic','label':'Synthetic'},'term':'Q1','teams':{'className':'Synthetic','title':'Synthetic design','source':source}})
app.roster_for=lambda *_:[{'id':'synthetic-1','first':'Alex','last':'Example'}]
def reader(req,item):
    item({'student_id':'synthetic-1','source':source,'name':'Alex Example','attachments':[{'name':'Work.docx','state':'text','url':'https://example.org/work','text':'SYNTHETIC HTTP EVIDENCE'}]});return {}
app.ATTACHMENT_RUNNER=reader;app.start_worker()
server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);app.PORT=server.server_port;app.ALLOWED_HOSTS={f'127.0.0.1:{app.PORT}'}
threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{app.PORT}'
def call(path,body=None,origin=None):
    headers={'Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(request) as r:return r.read()
try:
    assert b'Collect Teams attachments' in call('/ui/attachments.js')
    assert b'/ui/attachments.js' in call('/')
    request={'type':'attachment_collect','assignment':rec['id'],'students':[{'student_id':'synthetic-1'}]}
    try:call('/api/jobs',request,'https://foreign.example');raise AssertionError('foreign origin accepted')
    except urllib.error.HTTPError as e:assert e.code==403
    job=json.loads(call('/api/jobs',request))['job']
    for _ in range(100):
        result=json.loads(call('/api/jobs/'+job['id']))['job']
        if result['state']=='completed':break
        time.sleep(.05)
    assert result['state']=='completed',result['error']
    assert result['drafts'][0]['attachments']['attachments'][0]['text']=='SYNTHETIC HTTP EVIDENCE'
    assert json.loads(call('/api/jobs?assignment='+rec['id']))['jobs'][0]['id']==job['id']
    call('/api/jobs/'+job['id']+'/delivered',{'keys':['synthetic-1']})
    assert json.loads(call('/api/jobs/'+job['id']))['job']['drafts']==[]
    print('PASS HTTP: script route, page integration, origin protection, queued worker, recoverable evidence and delivery marker')
finally:
    server.shutdown();app.QUEUE.stop()
