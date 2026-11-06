"""One reviewed batch import: all identities validated first, one session save, unreviewed rows untouched."""
from pathlib import Path
from _common import APPDIR,LAUNCH
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(**LAUNCH);page=browser.new_page(viewport={'width':1100,'height':950})
    page.set_content('<main><select id="asg-pick"><option value="synthetic">Synthetic</option></select><select id="course"><option>Course</option></select><select id="quarter"><option>Q1</option></select><section id="step-collect"></section><div id="students"></div></main>')
    source=Path(APPDIR,'app.py').read_text();page.add_style_tag(content=source.split('<style>',1)[1].split('</style>',1)[0]);page.add_style_tag(content=Path(APPDIR,'ui/workspace.css').read_text())
    page.evaluate("""() => {
      window.ROSTER=['A','B','C','D'].map(id=>({id,first:id,last:'Example'}));window.originalRoster=[...ROSTER];window.saves=0;window.reads=0;window.imports=[];window.dest={class_id:'class',assignment_id:'assignment'};
      for(const s of ROSTER){const c=document.createElement('div');c.className='student';c.dataset.rid=s.id;c.innerHTML='<input class="name"><textarea class="work"></textarea><input class="nosub" value="Old absence">';c.querySelector('.name').value=s.first+' '+s.last;c.querySelector('.work').value='Existing '+s.id;document.querySelector('#students').append(c);}
      window.feedbackWorkspace={cards:()=>[...document.querySelectorAll('.student')],payload:c=>({student_id:c.dataset.rid,name:c.querySelector('.name').value}),refresh:()=>{}};
      window.feedbackAssignment={saveForPosting:async()=>{saves++;return true;}};
      window.fetch=async(url,options)=>{let data;
        if(url.startsWith('/api/assignments/')){reads++;data={assignment:{teams:{source:dest}}};}
        else if(options){const body=JSON.parse(options.body);if(url.endsWith('/attachment-imported')){imports.push(body);data={};}else data={job:{id:'batch-job'}};}
        else if(url.includes('?assignment='))data={jobs:[]};
        else data={job:{id:'batch-job',state:'completed',items:originalRoster.map(s=>({key:s.id,state:'done'})),drafts:originalRoster.map(s=>({key:s.id,attachments:{name:s.first+' '+s.last,target_name:s.last+', '+s.first,source:dest,attachments:[{name:s.id+'.docx',url:'https://example.org/'+s.id,state:s.id==='D'?'blocked':'text',text:s.id==='D'?'':'Evidence '+s.id,note:s.id==='D'?'Needs manual access check':'Check extracted evidence'}]}}))}};
        return {json:async()=>data};
      };
    }""")
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_script_tag(content=Path(APPDIR,'ui/attachments.js').read_text())
    page.get_by_role('button',name='Collect Teams attachments…').click();dlg=page.get_by_role('dialog')
    dlg.get_by_role('button',name='Select all students',exact=True).click();dlg.get_by_role('button',name='Collect selected students',exact=True).click()
    expect(dlg).to_contain_text('Evidence C')
    bulk=dlg.get_by_role('button',name='Add reviewed selections to Work',exact=False)
    expect(bulk).to_be_disabled()
    for name in ['A Example','B Example']:
        dlg.locator('.attachment-results section').filter(has=page.get_by_role('heading',name=name,exact=True)).get_by_role('checkbox').check()
    expect(bulk).to_contain_text('2 students')
    page.evaluate("ROSTER=ROSTER.filter(s=>s.id!=='B');saves=0;reads=0")
    bulk.click();expect(dlg).to_contain_text('no longer confirms B Example')
    assert page.locator('.work').nth(0).input_value()=='Existing A'
    assert page.locator('.work').nth(1).input_value()=='Existing B'
    assert page.evaluate('saves')==0
    page.evaluate('ROSTER=[...originalRoster];reads=0')
    bulk.click();page.wait_for_function('imports.length===2')
    assert page.evaluate('reads')==1 and page.evaluate('saves')==1
    assert page.evaluate('imports.map(x=>x.key)')==['A','B']
    for i,name in enumerate(['A','B']):
        assert page.locator('.work').nth(i).input_value().startswith('Existing '+name+'\n\n[Teams attachment:')
        assert 'Evidence '+name in page.locator('.work').nth(i).input_value()
        assert page.locator('.nosub').nth(i).input_value()==''
    assert page.locator('.work').nth(2).input_value()=='Existing C'
    assert page.locator('.work').nth(3).input_value()=='Existing D'
    assert page.locator('.nosub').nth(2).input_value()=='Old absence'
    expect(dlg).to_contain_text('Saved reviewed evidence for 2 students')
    dlg.locator('details').evaluate_all('(nodes)=>nodes.forEach(n=>n.open=true)');page.screenshot(path='/tmp/student-feedback-reviewed-batch.png')
    assert not errors,errors
    browser.close()
print('PASS batch prevalidation prevents partial imports; one source read and session save imports only reviewed students, preserving existing evidence and unchecked/blocked rows')
