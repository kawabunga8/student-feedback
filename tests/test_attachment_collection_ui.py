"""Synthetic UI: selection, evidence preview, exact identity, additive import, subset retry and assignment isolation."""
import re
from pathlib import Path
from _common import APPDIR,LAUNCH
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(**LAUNCH);page=browser.new_page(viewport={'width':1100,'height':950})
    page.set_content('<main><select id="asg-pick"><option value="asg-synthetic">Synthetic</option></select><select id="course"><option value="0">Synthetic</option></select><select id="quarter"><option>Q1</option></select><section id="step-collect"></section><div id="students"><div class="student" data-rid="s1"><input class="name" value="Alex Example"><textarea class="work">Existing work</textarea><input class="nosub" value="Old no-submission finding"></div></div></main>')
    app_source=Path(APPDIR,'app.py').read_text()
    page.add_style_tag(content=app_source.split('<style>',1)[1].split('</style>',1)[0])
    page.add_style_tag(content=Path(APPDIR,'ui/workspace.css').read_text())
    page.evaluate("""() => {
      window.ROSTER=[{id:'s1',first:'Alex',last:'Example'},{id:'s2',first:'Blair',last:'Example'}];window.requests=[];window.delivered=[];window.source={class_id:'class-1',assignment_id:'assignment-1'};window.edits=0;
      document.querySelector('.work').addEventListener('input',()=>edits++);
      window.feedbackWorkspace={cards:()=>[...document.querySelectorAll('.student')],payload:c=>({student_id:c.dataset.rid,name:c.querySelector('.name').value}),refresh:()=>{}};
      window.feedbackAssignment={saveForPosting:async()=>true};
      window.fetch=async(url,options)=>{
        let data;
        if(url.startsWith('/api/assignments/'))data={assignment:{teams:{source}}};
        else if(options){let body=JSON.parse(options.body);if(url.endsWith('/delivered')){delivered.push(body);data={};}else {requests.push(body);data={job:{id:'collection-1'}};}}
        else if(url.includes('?assignment='))data={jobs:[]};
        else data={job:{id:'collection-1',type:'attachment_collect',state:'completed',items:[{key:'s1',state:'done'},{key:'s2',state:'done'}],drafts:[
          {key:'s1',attachments:{student_id:'s1',name:'Alex Example',target_name:'Example, Alex',source,attachments:[{name:'Work.docx',url:'https://example.org/work',state:'text',text:'EXTRACTED SYNTHETIC WORK',note:'Pictures not read.'}]}},
          {key:'s2',attachments:{student_id:'s2',name:'Blair Example',target_name:'Example, Blair',source,attachments:[{name:'Project',url:'https://example.org/blocked',state:'blocked',note:'Human check; not bypassed.'}]}}
        ]}};
        if(data.job?.drafts){const selected=new Set((requests.at(-1)?.students||[]).map(s=>s.student_id));data.job.items=data.job.items.filter(i=>selected.has(i.key));data.job.drafts=data.job.drafts.filter(i=>selected.has(i.key));}
        return {json:async()=>data};
      };
    }""")
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_script_tag(content=Path(APPDIR,'ui/attachments.js').read_text())
    page.get_by_role('button',name='Collect Teams attachments…').click();dlg=page.get_by_role('dialog')
    expect(dlg.get_by_role('button',name='Collect selected students',exact=True)).to_be_disabled()
    dlg.get_by_label('Alex Example',exact=True).check()
    dlg.get_by_role('button',name='Collect selected students',exact=True).click()
    expect(dlg).to_contain_text('EXTRACTED SYNTHETIC WORK')
    assert page.evaluate('requests[0].students')==[{'student_id':'s1'}]
    assert page.locator('.work').input_value()=='Existing work'
    assert 'Blair Example' in dlg.inner_text() # selection list, not imported evidence
    add=dlg.get_by_role('button',name='Add extracted text to Work',exact=True)
    expect(add).to_be_disabled()
    dlg.get_by_label('I checked the student match and extracted text against the sources.',exact=True).check()
    add.click()
    expect(page.locator('.work')).to_have_value(re.compile('EXTRACTED SYNTHETIC WORK'))
    assert page.locator('.work').input_value().startswith('Existing work\n\n[Teams attachment: Work.docx]')
    assert page.locator('.nosub').input_value()==''
    assert page.evaluate('edits')==1
    page.wait_for_function('delivered.length===1')
    dlg.get_by_role('button',name='Select all students',exact=True).click()
    dlg.get_by_role('button',name='Collect selected students',exact=True).click()
    page.wait_for_function('requests.length===2')
    expect(dlg).to_contain_text('Human check; not bypassed.')
    dlg.locator('details').evaluate_all('(nodes)=>nodes.forEach(n=>n.open=true)')
    page.screenshot(path='/tmp/student-feedback-attachments-preview.png')
    # A saved destination change blocks importing an already-rendered collection.
    page.evaluate("window.source={class_id:'changed-class',assignment_id:'changed-assignment'}")
    dlg.get_by_label('I checked the student match and extracted text against the sources.',exact=True).check()
    dlg.get_by_role('button',name='Add extracted text to Work',exact=True).click()
    expect(dlg).to_contain_text('The Teams destination changed')
    page.evaluate("window.source={class_id:'class-1',assignment_id:'assignment-1'}")
    # Exact same evidence is not duplicated after reopening/retrying.
    expect(dlg.get_by_role('button',name='Add extracted text to Work',exact=True)).to_be_visible()
    dlg.get_by_label('I checked the student match and extracted text against the sources.',exact=True).check()
    dlg.get_by_role('button',name='Add extracted text to Work',exact=True).click()
    expect(dlg).to_contain_text('This exact evidence is already in Work')
    assert page.locator('.work').input_value().count('EXTRACTED SYNTHETIC WORK')==1
    # Retry contains only the incomplete student and refers to the old job for reuse.
    dlg.get_by_role('button',name='Retry incomplete students',exact=True).click()
    page.wait_for_function('requests.length===3')
    assert page.evaluate('requests[2].students')==[{'student_id':'s2'}]
    assert page.evaluate('requests[2].reuse_job')=='collection-1'
    expect(dlg.get_by_role('button',name='Add extracted text to Work',exact=True)).to_have_count(0)
    page.screenshot(path='/tmp/student-feedback-attachments-ui.png')
    page.locator('#course').dispatch_event('change')
    expect(dlg).to_contain_text('Assignment or course changed')
    assert not errors,errors
    browser.close()
print('PASS selection, read-only preview, confirmation, additive evidence, absence clearing, subset retry, deduplication and assignment isolation')
