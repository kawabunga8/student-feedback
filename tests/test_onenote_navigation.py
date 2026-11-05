"""Deterministic OneNote navigation tests. Synthetic pages, no browser or network."""
import os
import sys
import tempfile
from unittest.mock import patch
from _common import APPDIR, guard
os.environ['HOME']=tempfile.mkdtemp(prefix='sf-onenote-navigation-');guard(os.environ['HOME'])
sys.path.insert(0,APPDIR)
import onenote_class as C
from urllib.parse import quote

def url(student, title='Task 3'):
    return 'https://example.sharepoint.com/Doc.aspx?sourcedoc={test}&wd=target('+quote(student,safe='')+'%2FHomework.one%7Csection-id%2F'+quote(title,safe='')+'%7Cpage-id%2F)'
class Page:
    def __init__(self, identity, titles):
        self.tick=0;self.identity=identity;self.titles=titles;self.clicked=False
    @property
    def url(self):return self.identity(self)
    def wait_for_timeout(self,ms):self.tick+=ms/1000
    def evaluate(self,js):return self.titles(self)
    def locator(self,selector):return self
    def count(self):return len(self.titles(self))
    def nth(self,index):return self
    def click(self):self.clicked=True

def listed(page):
    with patch.object(C,'_frame',lambda _:page), patch.object(C.time,'monotonic',lambda:page.tick):
        return C.list_pages(page,page,'Blair Example','Homework')
# A stable list from another student's resolved address must time out, not mean no work.
p=Page(lambda p:url('Alex Example'),lambda p:['Task 3'])
assert listed(p) is None
# Correct address, but old list omits the current page. Wait until the list catches up.
p=Page(lambda p:url('Blair Example','Welcome'),lambda p:['Old student page'] if p.tick<1 else ['Welcome','Task 3'])
assert listed(p)==['Welcome','Task 3'] and p.tick>=1.5
# Navigation itself catches up later, even though both students have identically titled pages.
p=Page(lambda p:url('Alex Example' if p.tick<1 else 'Blair Example'),lambda p:['Task 3'])
assert listed(p)==['Task 3'] and p.tick>=1.5
# Navigation changing during a list read invalidates that snapshot.
def changing_titles(p):
    p.tick+=.1
    return ['Task 3']
p=Page(lambda p:url('Blair Example' if p.tick<.05 else 'Alex Example'),changing_titles)
assert listed(p) is None
# Clicking a listed page must not read content before the requested page resolves.
p=Page(lambda p:url('Blair Example','Task 3' if p.clicked and p.tick>=1 else 'Welcome'),lambda p:['Welcome','Task 3'])
reads=[]
with patch.object(C,'_frame',lambda _:p),patch.object(C.time,'monotonic',lambda:p.tick),patch.object(C.O,'read_loaded',lambda page,address,who,*args:reads.append((page.tick,who)) or {'synthetic':True}):
    assert C.open_listed_page(p,'Task 3',10,'Blair Example','Homework')=={'synthetic':True}
assert reads[0][0]>=1 and reads[0][1]['student_hint']=='Blair Example'
# A click that falls back to a different student never reads their content.
p=Page(lambda p:url('Alex Example' if p.clicked else 'Blair Example'),lambda p:['Task 3'])
with patch.object(C,'_frame',lambda _:p),patch.object(C.time,'monotonic',lambda:p.tick),patch.object(C.O,'read_loaded',side_effect=AssertionError('wrong content read')):
    assert C.open_listed_page(p,'Task 3',2,'Blair Example','Homework') is None
print('PASS 6 navigation checks: stale identity/list, delayed list/address, mid-read navigation, and exact-page wait')
