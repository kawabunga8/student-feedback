"""Read Teams attachments for matched students in one browser session. Never types, saves or Returns.
JSON request on stdin; per-student results on stdout. Text and screenshots belong only in assignment sidecars.
"""
import base64
import io
import json
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
import teams_read as T
import teams_batch as B

MAX_BYTES = 12 * 1024 * 1024
MAX_TEXT = 120000


def docx_text(raw):
    """Bounded extraction; never runs document macros or external relationships."""
    if len(raw) > MAX_BYTES:
        raise ValueError('File is too large for text extraction.')
    with zipfile.ZipFile(io.BytesIO(raw)) as doc:
        info = doc.getinfo('word/document.xml')
        if info.file_size > MAX_BYTES:
            raise ValueError('Document expands beyond the text limit.')
        root = ET.fromstring(doc.read(info))
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    text = '\n'.join(''.join(t.text or '' for t in p.iter(ns+'t')) for p in root.iter(ns+'p')).strip()
    if len(text) > MAX_TEXT:
        raise ValueError('Document text exceeds the collection limit; open it manually.')
    return text


def web_url(url):
    p = urlsplit(url)
    return url if p.scheme == 'https' and p.hostname and not p.username and not p.password else ''


DOWNLOAD_JS = """async limit => {
 const u=new URL(location.href);u.searchParams.set('download','1');
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try {const r=await fetch(u.toString(),{credentials:'include',signal:controller.signal});
 if(!r.ok) return {error:'download unavailable'};
 const reader=r.body.getReader();let size=0,parts=[];
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();return {error:'file too large'};}parts.push(value);}
 let text='';for(const part of parts)for(let i=0;i<part.length;i+=8192)text+=String.fromCharCode(...part.subarray(i,i+8192));
 return {data:btoa(text)};} finally {clearTimeout(timer);}
}"""


def read_attachment_page(pg):
    """Extract actual Word document text when available; otherwise preserve a labelled viewport screenshot.
    Body text from an editor is not treated as student evidence: it can contain unrelated controls.
    """
    pg.wait_for_load_state('domcontentloaded', timeout=20000)
    url = web_url(pg.url)
    if not url:
        return {'state':'unreadable', 'url':'', 'note':'The attachment did not expose a supported HTTPS page.'}
    body = pg.locator('body').inner_text(timeout=10000)
    if re.search(r'verify (?:you are|that you are) human|captcha|AADSTS|sign in to (?:your|continue)|access denied|request access', body, re.I) or pg.locator('input[type=password]').count():
        return {'state':'blocked', 'url':url, 'note':'Sign-in, access restriction or human check. Open the source and check it yourself; nothing was bypassed.'}
    host = urlsplit(url).hostname or ''
    if host.endswith('.sharepoint.com'):
        try:
            downloaded = pg.evaluate(DOWNLOAD_JS, MAX_BYTES)
            raw = base64.b64decode(downloaded.get('data',''), validate=True)
            if raw.startswith(b'PK'):
                text = docx_text(raw)
                if text:
                    return {'state':'text', 'url':url, 'text':text, 'note':'Word document text extracted. Pictures, drawings and embedded files are not read.'}
        except Exception:
            pass
    try:
        image = pg.screenshot(type='jpeg', quality=55, full_page=False, timeout=10000)
        if len(image) <= 250000:
            return {'state':'screenshot', 'url':url, 'screenshot':base64.b64encode(image).decode(), 'note':'Viewport screenshot only, not extracted text or proof the whole attachment was read. Check the source.'}
    except Exception:
        pass
    return {'state':'unreadable', 'url':url, 'note':'No supported document text or screenshot was captured. Open the source manually.'}


def open_attachment(page, item, wait=8):
    """Click once and return as soon as a popup OR a new identifiable inline viewer appears."""
    before = {f.url for f in page.frames}
    popups = []
    listener = lambda pg: popups.append(pg)
    page.on('popup', listener)
    try:
        item.click(timeout=8000)
        deadline = time.monotonic() + wait
        while True:
            if popups:
                if len(popups) != 1:
                    for pg in popups:pg.close()
                    raise ValueError('Multiple attachment windows opened; manual check required.')
                return popups[0], None
            candidates = list(dict.fromkeys(f.url for f in page.frames if f.url not in before and web_url(f.url) and re.search(r'wordeditor|wopiframe|doc\.aspx|classnotebook', f.url, re.I)))
            if len(candidates) == 1:
                return None, candidates[0]
            if time.monotonic() >= deadline:
                return None, None
            page.wait_for_timeout(200)
    finally:
        page.remove_listener('popup', listener)


def collect_attachments(page, ctx, panel, previous=None):
    tabs = panel.get_by_role('tablist', name='Attachment')
    if tabs.count() != 1:
        # A missing attachment area is not evidence that the student submitted nothing.
        return [], 'The attachment area was not present uniquely in the supported panel; check Teams manually.'
    controls = tabs.first.get_by_role('tab')
    count = controls.count()
    if count > 20:
        raise ValueError('More than 20 attachments: open this student in Teams manually.')
    labels = [controls.nth(i).inner_text().strip() for i in range(count)]
    old = previous or []
    reusable = len(old) == count and [a.get('name') for a in old] == labels
    results = []
    for i, label in enumerate(labels):
        if reusable and old[i].get('state') in ('text','screenshot'):
            results.append({**old[i], 'reused':True})
            continue
        item = controls.nth(i)
        pg = None
        try:
            pg, inline = open_attachment(page, item)
            if pg is not None:
                entry = read_attachment_page(pg)
            elif inline:
                # Read an identifiable viewer separately, not the grading panel's editor controls.
                pg = ctx.new_page(); pg.goto(inline, wait_until='domcontentloaded', timeout=20000)
                entry = read_attachment_page(pg)
            else:
                entry = {'state':'unreadable', 'url':'', 'note':'No identifiable attachment viewer appeared. Open this source in Teams manually.'}
        except Exception:
            entry = {'state':'unreadable', 'url':web_url(pg.url) if pg else '', 'note':'The attachment could not be read. No text was inferred.'}
        finally:
            if pg is not None:
                pg.close()
        if not entry.get('url'):
            try:
                entry['url'] = web_url(B.s_frame(page, panel).url)
            except Exception:
                entry['url'] = web_url(page.url)
        results.append({'name':label or 'Untitled attachment', **entry})
    return results, '' if count else 'No attachments were listed. This does not check OneNote or other sources.'


def open_student(page, session, req, st, tab):
    B.show_tab(session.frame(), page, tab)
    f = session.frame()
    if tab == 'To return':
        out = B.open_panel(page, f, req, st, True)
        if out is None:
            raise ValueError('Student not found uniquely in the supported roster.')
        return out[0], out[2]
    rows = f.get_by_role('row').filter(has=f.get_by_text(st['target_name'], exact=True))
    if rows.count() != 1:
        raise ValueError('Student not found uniquely in Returned.')
    cell = rows.first.get_by_text(st['target_name'], exact=True)
    if cell.count() != 1:
        raise ValueError('Returned student identity is ambiguous.')
    cell.click(timeout=8000)
    f.locator('#editorAnchor').wait_for(state='attached', timeout=20000)
    f = B.s_frame(page, f)
    if T.ids_from_url(f.url) != req['source'] or f.get_by_role('button', name='Currently selected student: '+B.display_name(st['target_name']), exact=True).count() != 1:
        raise ValueError('The opened panel did not match the saved assignment and student.')
    match = re.search(r'/submissions/([0-9a-f-]{36})', urlsplit(f.url).path)
    if not match:
        raise ValueError('The submission identity could not be verified.')
    panel = f.get_by_role('dialog').filter(has=f.locator('#editorAnchor'))
    if panel.count() != 1:
        panel = f.get_by_role('complementary').filter(has=f.locator('#editorAnchor'))
    if panel.count() != 1:
        raise ValueError('Unsupported Returned attachment panel.')
    return panel, match[1]


def run(req, emit):
    if os.environ.get('SF_FORBID_BROWSER'):
        raise T.ReadError('setup','Browser use is switched off for tests.')
    from playwright.sync_api import sync_playwright
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(T.TEAMS, wait_until='domcontentloaded')
            session = T.Session(page,60);session.t0=time.time()
            _,_,ids = session.open_one(req['class'],req['title'])
            if ids != req['source']:
                raise T.ReadError('differs','The Teams assignment differs from the saved link. Collection stopped.')
            known = {tab:B.tab_names(page,session,tab) for tab in ('To return','Returned')}
            if any(names is None for names in known.values()):
                raise T.ReadError('differs','Both Teams roster tabs must be read completely before collecting attachments. No missing-work conclusions were made.')
            for st in req['students']:
                key = st['target_name'].strip().lower()
                matches = [tab for tab,names in known.items() if names is not None and key in names]
                if len(matches) != 1:
                    emit({'item':{'student_id':st['student_id'],'error':'The student was not found exactly once across the Teams roster tabs. Check the roster name.'}})
                    continue
                try:
                    panel, submission = open_student(page,session,req,st,matches[0])
                    entries,note = collect_attachments(page,ctx,panel,st.get('previous') if st.get('previous_submission') == submission else None)
                    emit({'item':{'student_id':st['student_id'],'name':st['name'],'target_name':st['target_name'],'source':ids,'submission_id':submission,'attachments':entries,'note':note,'read_at':time.time()}})
                except T.ReadError:
                    raise
                except Exception:
                    emit({'item':{'student_id':st['student_id'],'error':'The student attachment panel could not be verified or read. Check Teams manually.'}})
                finally:
                    f = session.frame()
                    if f.get_by_role('button',name=re.compile(r'^close( viewer)?$',re.I)).count():
                        B.close_panel(page,f)
        finally:
            ctx.close()


class CollectionStopped(BaseException):
    """Cooperative stop must unwind panel/context cleanup without becoming an item failure."""


def main():
    try:
        req = json.loads(sys.stdin.readline())
        def emit(msg):
            print(json.dumps(msg,ensure_ascii=False),flush=True)
            if req.get('acknowledge') and sys.stdin.readline().strip() != 'continue':
                raise CollectionStopped()
        run(req,emit)
        print(json.dumps({'ok':True}),flush=True)
    except CollectionStopped:
        print(json.dumps({'ok':True,'stopped':True}),flush=True)
    except T.ReadError as e:
        print(json.dumps({'ok':False,'kind':e.kind,'error':str(e)[:200]}),flush=True)
    except Exception:
        print(json.dumps({'ok':False,'kind':'error','error':'Attachment collection stopped. Completed results remain available.'}),flush=True)

if __name__=='__main__':main()
