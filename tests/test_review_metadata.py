"""Metadata saves preserve exact approvals; content and reviewed values do not. No browser or network."""
import copy
import json
import os
import sys
import tempfile
from _common import APPDIR, guard, guard_app
home = tempfile.mkdtemp(prefix='sf-review-metadata-')
os.environ['HOME'] = home
guard(home)
sys.path.insert(0, APPDIR)
import app
guard_app(app, home)
rec = app.save_assignment_record(dict(title='Synthetic assignment', course={}, grade='9', term='1', instructions='Explain your design.', focus='', standards=[], teams=None))
st = dict(student_id='synthetic-1', name='Synthetic Student', grade='9', work='', nosub='Teacher checked Teams today', notes='', level='', feedback='Please submit your work.', myschool_comment='Please submit your work.')
bound = dict(st, assignment=rec['title'], instructions=rec['instructions'], course='', school_year='', quarter='1', standards=[], rubric={'use':False,'canon':''})
stamp = dict(assignment_version=rec['version'])
def current(record, student=st):
    return app.check_reviewed(json.dumps(bound), student, record, stamp)['current']
assert current(rec)
linked = copy.deepcopy(rec)
linked['teams'] = dict(classId='class-1', assignmentId='assignment-1', url='https://teams.microsoft.com/synthetic')
linked = app.save_assignment_record(linked, rec['version'])
assert linked['history'][-1]['kind'] == 'details' and current(linked)
assert app.load_assignment_record(linked['id'])['teams'] == linked['teams']
for field, value in [('instructions','Explain a different design.'),('title','Different assignment'),('standards',['Different criterion'])]:
    changed=copy.deepcopy(rec); changed.pop('id')
    changed=app.save_assignment_record(changed)
    fresh_stamp=dict(assignment_version=changed['version'])
    changed[field]=value
    changed=app.save_assignment_record(changed, changed['version'])
    assert not app.check_reviewed(json.dumps(bound), st, changed, fresh_stamp)['current'], field
# Exact student evidence and feedback still invalidate an approval even with metadata only.
for field in ('student_id','name','work','nosub','feedback','level'):
    changed=dict(st); changed[field]='Changed'
    assert not current(rec, changed), field
print('PASS metadata link persists and preserves review; content, identity and student edits remain bound')
