"""MySchool posting choices and batch safeguards; synthetic DOM/jobs only, no school access."""
import json
import os
import sys
import tempfile
from pathlib import Path
from _common import APPDIR, LAUNCH, guard
HOME = tempfile.mkdtemp()
os.environ['HOME'] = HOME
guard(HOME)
from playwright.sync_api import sync_playwright, expect

checks = []
def check(label, value):
    checks.append(bool(value))
    print(('PASS ' if value else 'FAIL ') + label, flush=True)

SCRIPT = (Path(APPDIR) / 'ui/myschool.js').read_text()
SETUP = r'''() => {
 const cards = [{id:'A',name:'Alex Example'},{id:'B',name:'Blair Sample'}];
 const posted = new WeakMap(); window.marked=[]; window.requests=[];window.jobs={};window.mode='ok';
 window.publication='0';window.targetId='101';window.hold=false;
 const payload=c=>({student_id:c.id,name:c.name,feedback:'Reviewed feedback',myschool_comment:'Full approved comment for '+c.id});
 window.feedbackAssignment={saveForPosting:async()=>true};
 window.feedbackWorkspace={cards:()=>cards,payload,valid:()=>true,posted,
   markPosted:(id,kind,bound)=>{const c=cards.find(c=>c.id===id);if(bound!==JSON.stringify(payload(c)))return false;
     posted.set(c,{[kind]:{bound}});marked.push(id);return true;}};
 window.fetch=async(url,options)=>({json:async()=>{
   if(url.includes('/approved?'))return {students:cards.map(c=>({student_id:c.id,name:c.name,level:'Proficient'}))};
   if(options){const req=JSON.parse(options.body);requests.push(req);const id='job-'+requests.length;jobs[id]=req;return {job:{id}};}
   const req=jobs[url.split('/').pop()];
   if(req.op==='inspect'){
     const codes=req.codes?req.codes.split(/[,\s]+/).filter(Boolean):['PRF'];
     return {job:{state:'completed',drafts:[{myschool:{...req,url:req.url,student_id:req.student_id,
       target_id:targetId,publication,codes,approval_sha:'approval-'+req.student_id,read_at:Date.now()/1000,
       criteria:codes.map((chosen,i)=>({label:'Criterion '+(i+1),existing:'DEV',chosen})),
       comment:'Full approved comment for '+req.student_id,
       existing:{levels:codes.map(()=>'DEV'),comment:'Previous comment',status:'1'},
       desired:{levels:codes,comment:'Full approved comment for '+req.student_id,status:'1'}}}]}};
   }
   if(hold)await new Promise(resolve=>window.releaseSave=resolve);
   if(mode==='uncertain')return {job:{state:'completed',items:[{state:'failed',error:'Save may have run. Check MySchool.'}]}};
   return {job:{state:'completed',drafts:[{myschool:{verified:true}}]}};
 }});
}'''

def open_page(browser, already=False):
    pg = browser.new_page()
    pg.set_content('<select id="asg-pick"><option value="asg-synthetic">Synthetic task</option></select><div id="step-delivery"></div>')
    pg.evaluate(SETUP)
    if already:
        pg.evaluate("feedbackWorkspace.posted.set(feedbackWorkspace.cards()[0],{myschool:{bound:JSON.stringify(feedbackWorkspace.payload(feedbackWorkspace.cards()[0]))}})")
    pg.add_script_tag(content=SCRIPT)
    return pg

def batch(pg, one=False):
    pg.get_by_role('button', name='Post a batch to MySchool…', exact=True).click()
    dlg = pg.get_by_role('dialog', name='MySchool bulk posting', exact=True)
    expect(dlg.get_by_label('Include Alex Example in batch')).to_be_attached()
    dlg.get_by_label('MySchool assignment address', exact=True).fill('https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=123')
    dlg.get_by_label('Exact MySchool assignment title', exact=True).fill('Synthetic task')
    dlg.get_by_label('Exact MySchool course name', exact=True).fill('Synthetic course')
    if one:
        dlg.get_by_label('Include Blair Sample in batch').uncheck()
    return dlg

def preview(dlg):
    dlg.get_by_role('button', name='Read MySchool and preview all', exact=True).click()
    expect(dlg.locator('.myschool-bulk-rows')).to_contain_text('ready to save')

def save(dlg):
    dlg.get_by_role('checkbox', name='I checked all', exact=False).check()
    dlg.get_by_role('button', name='Save all previewed students to MySchool', exact=True).click()

def receipt(dlg, text):
    expect(dlg.locator('[role=status]').first).to_contain_text(text)

def expire(pg):
    pg.evaluate('const realNow=Date.now.bind(Date);Date.now=()=>realNow()+9*60*1000')

with sync_playwright() as p:
    browser = p.chromium.launch(**LAUNCH)
    pg = open_page(browser)
    check('both one-student and batch entry points remain available', pg.get_by_role('button',name='Post reviewed assessment to MySchool…',exact=True).count()==1 and pg.get_by_role('button',name='Post a batch to MySchool…',exact=True).count()==1)
    dlg = batch(pg, one=True)
    dlg.get_by_label('MySchool levels for Alex Example').fill('PRF, EXT+')
    preview(dlg)
    check('previewing writes nothing and excludes deselected students', pg.evaluate("requests.length===1&&requests[0].student_id==='A'&&requests[0].codes==='PRF, EXT+'"))
    check('full preview names destination, every criterion and full comment', all(t in dlg.locator('.myschool-bulk-rows').text_content() for t in ['Synthetic course → Synthetic task → Alex Example','Criterion 1','Criterion 2','EXT+','Previous comment','Full approved comment for A']))
    check('Save requires an explicit confirmation', dlg.get_by_role('button',name='Save all previewed students to MySchool',exact=True).is_disabled())
    save(dlg);receipt(dlg,'Batch complete')
    check('only the selected student is saved and marked', pg.evaluate("JSON.stringify(marked)==='[\"A\"]'&&requests.filter(r=>r.op==='save').length===1"))
    pg.close()

    pg=open_page(browser);dlg=batch(pg);preview(dlg);expire(pg);save(dlg);receipt(dlg,'Batch complete')
    check('unchanged expired previews refresh and save the whole selected batch in order',pg.evaluate("JSON.stringify(marked)==='[\"A\",\"B\"]'&&requests.filter(r=>r.op==='save').length===2&&requests.filter(r=>r.op==='inspect').length===4"))
    pg.close()

    for field,value in [('publication','1'),('targetId','999')]:
        pg=open_page(browser);dlg=batch(pg,one=True);preview(dlg);expire(pg)
        pg.evaluate('(x)=>window[x.field]=x.value',{'field':field,'value':value})
        save(dlg);receipt(dlg,'Preview and confirm the batch again')
        check('changed '+field+' on preview refresh prevents any Save',pg.evaluate("requests.every(r=>r.op!=='save')&&marked.length===0"))
        pg.close()

    pg=open_page(browser);dlg=batch(pg);preview(dlg);pg.evaluate("mode='uncertain'");save(dlg);receipt(dlg,'Outcome unknown: Alex Example')
    check('uncertain Save stops the batch and never marks completion',pg.evaluate("requests.filter(r=>r.op==='save').length===1&&marked.length===0"))
    check('summary distinguishes unknown from not attempted', 'Not attempted: Blair Sample' in dlg.locator('[role=status]').first.inner_text() and 'Nothing was saved' not in dlg.inner_text())
    check('uncertain student is locked against accidental retry',dlg.get_by_label('Include Alex Example in batch').is_disabled())
    pg.close()

    pg=open_page(browser);dlg=batch(pg);preview(dlg);pg.evaluate('hold=true');save(dlg);pg.wait_for_function('!!window.releaseSave')
    check('destination and reload controls are locked during Save',dlg.get_by_label('MySchool assignment address',exact=True).is_disabled() and dlg.get_by_role('button',name='Load reviewed students',exact=True).is_disabled())
    dlg.get_by_role('button',name='Stop after current student',exact=True).click();pg.evaluate('releaseSave()');receipt(dlg,'Stopped by you')
    check('Stop finishes the current student and leaves the next unattempted',pg.evaluate("JSON.stringify(marked)==='[\"A\"]'&&requests.filter(r=>r.op==='save').length===1"))
    pg.close()

    pg=open_page(browser,already=True);dlg=batch(pg)
    check('unchanged assessments already marked saved are excluded by default',not dlg.get_by_label('Include Alex Example in batch').is_checked() and dlg.get_by_label('Include Blair Sample in batch').is_checked())
    pg.close()

    pg=open_page(browser)
    pg.get_by_role('button',name='Post reviewed assessment to MySchool…',exact=True).click()
    dlg=pg.get_by_role('dialog',name='MySchool posting pilot',exact=True)
    expect(dlg.get_by_label('Reviewed student',exact=True).locator('option')).to_have_count(3)
    dlg.get_by_label('Reviewed student',exact=True).select_option('A')
    for label,value in [('MySchool assignment address','https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=123'),('Exact MySchool assignment title','Synthetic task'),('Exact MySchool course name','Synthetic course'),('Exact student name shown in MySchool','Alex Example')]:
        dlg.get_by_label(label,exact=True).fill(value)
    dlg.get_by_role('button',name='Read destination and preview',exact=True).click();expect(dlg.locator('.myschool-preview')).to_contain_text('Full approved comment for A')
    pg.evaluate('hold=true');dlg.get_by_role('checkbox',name='I checked the assignment',exact=False).check();dlg.get_by_role('button',name='Save this approved assessment to MySchool',exact=True).click();pg.wait_for_function('!!window.releaseSave')
    check('one-student selection is locked during Save',dlg.get_by_label('Reviewed student',exact=True).is_disabled())
    # Even a programmatic selection change must not move the receipt to another student.
    pg.evaluate("document.querySelector('dialog[aria-label=\"MySchool posting pilot\"] select').value='B';releaseSave()")
    receipt(dlg,'Marked as saved')
    check('one-student completion stays bound to the job student',pg.evaluate("JSON.stringify(marked)==='[\"A\"]'"))
    pg.close();browser.close()
print(f'{sum(checks)}/{len(checks)} checks passed')
sys.exit(0 if all(checks) else 1)
