"""Real job journal: stop preserves the current result; importing text keeps other evidence recoverable."""
import os,sys,tempfile,time
from pathlib import Path
from _common import APPDIR,guard,guard_app
os.environ['HOME']=tempfile.mkdtemp(prefix='sf-collection-lifecycle-');guard(os.environ['HOME']);sys.path.insert(0,APPDIR)
import app,jobs
guard_app(app,os.environ['HOME'])
source={'class_id':'11111111-2222-4333-8444-555555555555','assignment_id':'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'}
rec=app.save_assignment_record({'title':'Synthetic','course':{'name':'Synthetic','label':'Synthetic'},'teams':{'className':'Synthetic','title':'Synthetic','source':source}})
app.roster_for=lambda *_:[{'id':'s1','first':'Alex','last':'Example'},{'id':'s2','first':'Blair','last':'Example'}]
app.QUEUE=jobs.JobQueue(Path(os.environ['HOME'])/'journal.sqlite',{'attachment_collect':app._run_attachment_job},lambda rel:app.ASSESSMENT/rel,app._atomic_write_json,app._read_json)
q=app.QUEUE
job=app.enqueue_attachment_job({'assignment':rec['id'],'students':[{'student_id':'s1'},{'student_id':'s2'}]})
visited=[]
def runner(req,item):
    visited.append('s1');q.cancel(job['id'])
    item({'student_id':'s1','source':source,'attachments':[{'name':'Work.docx','state':'text','text':'synthetic','url':'https://example.org/work'},{'name':'Project','state':'blocked','url':'https://example.org/project'}]})
    visited.append('s2')
    raise AssertionError('next student was visited after stop')
app.ATTACHMENT_RUNNER=runner;q.start()
try:
    for _ in range(100):
        current=q.get(job['id'],True)
        if current['state'] in ('cancelled','failed','completed'):break
        time.sleep(.02)
    assert current['state']=='cancelled',current
    assert current['counts']['done']==1 and current['counts']['cancelled']==1
    assert visited==['s1']
    assert len(current['drafts'][0]['attachments']['attachments'])==2
    q.mark_attachment_imported(job['id'],'s1',[0])
    # Reopening the journal must preserve both sources and the precise import state.
    reopened=jobs.JobQueue(q.db_path,q.handlers,q.resolve_folder,q.write_json,q.read_json)
    attachments=reopened.get(job['id'],True)['drafts'][0]['attachments']['attachments']
    assert attachments[0]['imported_at'] and not attachments[1].get('imported_at') and attachments[1]['state']=='blocked'
    try:q.mark_attachment_imported(job['id'],'s1',[1]);raise AssertionError('blocked evidence marked imported')
    except ValueError:pass
    # Compatibility with old clients: a student-level delivered bit may not hide source previews.
    q.mark_delivered(job['id'],['s1'])
    assert len(q.get(job['id'],True)['drafts'][0]['attachments']['attachments'])==2
    print('PASS stop saves the current student, cancels remaining students, and never runs the next; per-file import and blocked previews survive reopening and legacy delivery')
finally:q.stop()
# Actual child-side protocol: stop unwinds cleanup before another student can be visited.
import io,json,contextlib
from unittest.mock import patch
import attachment_collect as A
visits=[]
def fake_collection(req,emit):
    try:
        visits.append('first');emit({'item':{'student_id':'s1'}})
        visits.append('second')
    finally:visits.append('cleanup')
output=io.StringIO()
with patch.object(A,'run',fake_collection),patch.object(A.sys,'stdin',io.StringIO('{"acknowledge":true}\nstop\n')),contextlib.redirect_stdout(output):A.main()
assert visits==['first','cleanup'] and json.loads(output.getvalue().splitlines()[-1])['stopped']
# Actual parent process: send stop and allow cleanup before raising cancellation to the journal.
script=Path(os.environ['HOME'])/'synthetic_worker.py';proof=script.with_suffix('.json')
script.write_text('import sys,json\nfrom pathlib import Path\nrequest=json.loads(sys.stdin.readline())\nprint(json.dumps({"item":{"student_id":"s1"}}),flush=True)\nanswer=sys.stdin.readline().strip()\nPath(__file__).with_suffix(".json").write_text(json.dumps({"answer":answer,"acknowledge":request.get("acknowledge")}))\n')
def stop_current(msg):raise jobs.JobCancelled('Synthetic stop')
with patch.dict(os.environ,{'SF_FORBID_BROWSER':''}):
    try:app.browser_collection_runner({},stop_current,str(script),'Synthetic',acknowledge=True);raise AssertionError('stop ignored')
    except jobs.JobCancelled:pass
assert json.loads(proof.read_text())=={'answer':'stop','acknowledge':True}
print('PASS child stop acknowledgement unwinds cleanup and parent waits for cooperative exit')
