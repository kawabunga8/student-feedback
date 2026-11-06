"""Synthetic extraction, enqueue, per-student retry/reuse, privacy and job-handler checks. No school access."""
import io,json,os,sys,tempfile,zipfile
from pathlib import Path
from _common import APPDIR,guard,guard_app
home=tempfile.mkdtemp(prefix='sf-attachment-tests-');os.environ['HOME']=home;guard(home)
sys.path.insert(0,APPDIR)
import app,attachment_collect as A,jobs

def docx(xml):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('word/document.xml',xml)
    return b.getvalue()
raw=docx('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic student evidence</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>')
assert A.docx_text(raw)=='Synthetic student evidence\nSecond paragraph'
assert A.web_url('https://example.org/work') and not A.web_url('javascript:alert(1)') and not A.web_url('https://user:password@example.org')
old=A.MAX_BYTES;A.MAX_BYTES=100
try:
    try:A.docx_text(raw);raise AssertionError('oversize accepted')
    except ValueError:pass
finally:A.MAX_BYTES=old
# Use a real journal and assignment sidecar, under a fresh HOME.
guard_app(app,home)
source={'class_id':'11111111-2222-4333-8444-555555555555','assignment_id':'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'}
rec=app.save_assignment_record({'title':'Synthetic design','course':{'name':'Synthetic','label':'Synthetic','schoolYear':'2026-27'},'term':'Q1','teams':{'className':'Synthetic Teams','title':'Synthetic design','source':source}})
app.roster_for=lambda *_:[{'id':'s1','first':'Alex','last':'Example'},{'id':'s2','first':'Blair','last':'Example'}]
app.QUEUE=jobs.JobQueue(Path(home)/'journal.sqlite',{'attachment_collect':app._run_attachment_job},lambda rel:app.ASSESSMENT/rel,app._atomic_write_json,app._read_json)
for selected in [[{'student_id':'foreign'}],[{'student_id':'s1'},{'student_id':'s1'}],[]]:
    try:app.enqueue_attachment_job({'assignment':rec['id'],'students':selected});raise AssertionError('bad identity accepted')
    except ValueError:pass
job=app.enqueue_attachment_job({'assignment':rec['id'],'students':[{'student_id':'s1'},{'student_id':'s2'}]})
try:app.enqueue_attachment_job({'assignment':rec['id'],'students':[{'student_id':'s1'}]});raise AssertionError('parallel job accepted')
except ValueError:pass
seen=[]
def runner(req,item):
    seen.append(req)
    item({'student_id':'not-requested','source':source,'attachments':[]})
    item({'student_id':'s1','name':'Alex Example','source':source,'submission_id':'submission-1','attachments':[{'name':'draft.docx','state':'text','text':'PRIVATE SYNTHETIC EVIDENCE','url':'https://example.org/doc'}]})
    # A missing student result must be reported as failure, never as no submission.
    return {}
app.ATTACHMENT_RUNNER=runner
app._run_attachment_job(app.QUEUE,job)
app.QUEUE._finish(job['id'],'completed')
finished=app.QUEUE.get(job['id'],with_results=True)
assert finished['counts']['done']==1 and finished['counts']['failed']==1
assert finished['drafts'][0]['attachments']['attachments'][0]['text']=='PRIVATE SYNTHETIC EVIDENCE'
assert b'PRIVATE SYNTHETIC EVIDENCE' not in (Path(home)/'journal.sqlite').read_bytes()
assert b'Alex Example' not in (Path(home)/'journal.sqlite').read_bytes()
retry=app.enqueue_attachment_job({'assignment':rec['id'],'students':[{'student_id':'s1'}],'reuse_job':job['id']})
req=app.QUEUE.request_of(retry)['request']
assert len(req['students'])==1 and req['students'][0]['previous_submission']=='submission-1'
assert req['students'][0]['previous'][0]['text']=='PRIVATE SYNTHETIC EVIDENCE'
# Destination changes must prevent stale collection from starting.
changed=app.load_assignment_record(rec['id']);changed['teams']['source']['assignment_id']='bbbbbbbb-bbbb-4ccc-8ddd-eeeeeeeeeeee';app.save_assignment_record(changed,changed['version'])
try:app._run_attachment_job(app.QUEUE,retry);raise AssertionError('changed destination accepted')
except jobs.JobFailed:pass
# The browser runner itself must remain blocked in test mode.
try:A.run({},lambda _:None);raise AssertionError('live browser attempted')
except A.T.ReadError as e:assert e.kind=='setup'
print('PASS extraction/size limits, URL checks, roster identities, duplicate jobs, partial results, journal privacy, subset reuse, destination binding and browser guard')
# A retry reuses successful attachments only when the whole list's names/order still match.
from unittest.mock import patch
class Control:
    def __init__(self,ctx,name):self.ctx,self.name=ctx,name
    def inner_text(self):return self.name
    def click(self,**kw):self.ctx.clicks.append(self.name);self.ctx.event.value=self.name
class Controls:
    def __init__(self,ctx):self.ctx=ctx
    def count(self):return 2
    def nth(self,i):return Control(self.ctx,['one.docx','two.docx'][i])
class Tabs:
    def __init__(self,ctx):self.ctx=ctx;self.first=self
    def count(self):return 1
    def get_by_role(self,*a,**kw):return Controls(self.ctx)
class Panel:
    def __init__(self,ctx):self.ctx=ctx
    def get_by_role(self,*a,**kw):return Tabs(self.ctx)
class Event:
    def __enter__(self):return self
    def __exit__(self,*a):return False
class Context:
    def __init__(self):self.clicks=[]
    def expect_page(self,**kw):self.event=Event();return self.event
class Pg:
    frames=[]
ctx=Context();panel=Panel(ctx)
class Popup:
    def __init__(self,name):self.name=name
    def close(self):pass
# Give the opened object a close method without involving a real browser.
original=Control.click
def click(self,**kw):self.ctx.clicks.append(self.name);self.ctx.event.value=Popup(self.name)
Control.click=click
original_open=A.open_attachment
def fake_open(page,item):
    with item.ctx.expect_page() as event:item.click()
    return event.value,None
A.open_attachment=fake_open
with patch.object(A,'read_attachment_page',lambda pg:{'state':'text' if pg.name=='one.docx' else 'blocked','url':'https://example.org/'+pg.name,'text':'synthetic' if pg.name=='one.docx' else ''}):
    first,_=A.collect_attachments(Pg(),ctx,panel)
assert ctx.clicks==['one.docx','two.docx']
ctx.clicks=[]
with patch.object(A,'read_attachment_page',lambda pg:{'state':'text','url':'https://example.org/'+pg.name,'text':'synthetic'}):
    second,_=A.collect_attachments(Pg(),ctx,panel,first)
assert ctx.clicks==['two.docx'] and second[0]['reused'] and second[1]['state']=='text'
ctx.clicks=[]
with patch.object(A,'read_attachment_page',lambda pg:{'state':'text','url':'https://example.org/'+pg.name,'text':'synthetic'}):
    A.collect_attachments(Pg(),ctx,panel,list(reversed(second)))
assert ctx.clicks==['one.docx','two.docx']
A.open_attachment=original_open
assert '/ui/attachments.js' in app.PAGE
print('PASS one opening per attachment, successful-result reuse on retry, and cache invalidation for changed attachment lists')
# Classify a document, a blocked page and a screenshot-only page without inferring body text as evidence.
import base64
class Body:
    def __init__(self,text):self.text=text
    def inner_text(self,**kw):return self.text
    def count(self):return 0
class AttachmentPage:
    def __init__(self,address,text='Viewer controls',data=None):self.url=address;self.text=text;self.data=data;self.shots=0
    def wait_for_load_state(self,*a,**kw):pass
    def locator(self,selector):return Body(self.text if selector=='body' else '')
    def evaluate(self,*args):return {'data':base64.b64encode(self.data or b'not a document').decode()}
    def screenshot(self,**kw):self.shots+=1;return b'fake synthetic screenshot'
pg=AttachmentPage('https://school.sharepoint.com/doc.aspx',data=raw)
assert A.read_attachment_page(pg)['state']=='text' and pg.shots==0
pg=AttachmentPage('https://example.org/project','Verify you are human')
assert A.read_attachment_page(pg)['state']=='blocked' and pg.shots==0
pg=AttachmentPage('https://example.org/project','Editor controls and buttons')
r=A.read_attachment_page(pg)
assert r['state']=='screenshot' and not r.get('text') and 'Viewport' in r['note']
print('PASS Word text extraction, blocked-page classification and screenshot-only evidence without editor-body text')
