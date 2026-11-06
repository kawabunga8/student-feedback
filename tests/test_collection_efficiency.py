"""Synthetic checks: one notebook navigation across students; wait for actual attachment readiness."""
import os,sys,tempfile
from unittest.mock import patch
from urllib.parse import quote
from _common import APPDIR,guard
os.environ['HOME']=tempfile.mkdtemp(prefix='sf-efficient-collection-');guard(os.environ['HOME']);sys.path.insert(0,APPDIR)
import onenote_class as C,attachment_collect as A
BASE='https://example.sharepoint.com/Doc.aspx?sourcedoc={test}'
def resolved(name):return BASE+'&wd=target('+quote(name+'/Homework.one|s1/Task 3|p1/',safe='')+')'
class Tree:
    labels=['Alex Example, Section Group','Homework, Section','Blair Example, Section Group','Homework, Section']
    def __init__(self,page):self.page=page
    def get_by_role(self,*a,**kw):return self
    def count(self):return 4
    def locator(self,*a):return self
    def evaluate(self,*a):return self.labels
    def nth(self,index):self.index=index;return self
    def click(self):self.page.url=resolved('Alex Example' if self.index==1 else 'Blair Example')
class Notebook:
    def __init__(self):self.url='about:blank';self.navigations=[];self.tree=Tree(self)
    def goto(self,url,**kw):self.navigations.append(url);self.url=url
    def wait_for_timeout(self,ms):raise AssertionError('ready notebook waited unnecessarily')
p=Notebook();signins=[]
with patch.object(C,'_frame',lambda _:p.tree):
    assert C.open_section(p,BASE,'Alex Example','Homework',lambda *_:signins.append(1)) is p.tree
    assert C.open_section(p,BASE,'Blair Example','Homework',lambda *_:signins.append(1)) is p.tree
assert len(p.navigations)==1 and len(signins)==1
assert not C.same_notebook(p.url,BASE.replace('{test}','{other}'))
assert not C.same_notebook(p.url,BASE.replace('example.sharepoint.com','different.sharepoint.com'))
class Frame:
    def __init__(self,url):self.url=url
class ViewerPage:
    def __init__(self,kind,delay):self.kind=kind;self.delay=delay;self.clock=0;self.clicked=False;self.listener=None;self.emitted=False
    @property
    def frames(self):return [Frame('https://teams.microsoft.com/panel')]+([Frame('https://example.sharepoint.com/doc.aspx?sourcedoc=synthetic')] if self.clicked and self.kind=='inline' and self.clock>=self.delay else [])
    def on(self,event,callback):self.listener=callback
    def remove_listener(self,event,callback):assert self.listener==callback;self.listener=None
    def wait_for_timeout(self,ms):
        self.clock+=ms/1000
        if self.kind=='popup' and not self.emitted and self.clock>=self.delay:self.emitted=True;self.listener('synthetic-popup')
class Item:
    def __init__(self,page):self.page=page;self.clicks=0
    def click(self,**kw):self.clicks+=1;self.page.clicked=True
for kind in ['inline','popup','unsupported']:
    p=ViewerPage(kind,.4);item=Item(p)
    with patch.object(A.time,'monotonic',lambda:p.clock):popup,inline=A.open_attachment(p,item,wait=1)
    assert item.clicks==1 and p.listener is None
    if kind=='inline':assert inline and popup is None and p.clock<1
    elif kind=='popup':assert popup=='synthetic-popup' and inline is None and p.clock<1
    else:assert popup is None and inline is None and p.clock>=1
print('PASS notebook tree reused across students with identity checks; inline/popup readiness returns immediately, unsupported views time out, and every attachment is clicked once')
