"""Posting dialogs with synthetic cards and intercepted jobs only; no server or school access."""
import json
from pathlib import Path
from _common import APPDIR, LAUNCH
from playwright.sync_api import sync_playwright, expect
checks = 0
with sync_playwright() as p:
    browser=p.chromium.launch(**LAUNCH)
    for destination in ('teams','myschool'):
        page=browser.new_page()
        page.set_content('<select id="asg-pick"><option value="synthetic">Synthetic</option></select><input id="atitle" value="Design"><div id="step-delivery"></div>')
        page.evaluate("""() => {
          window.cards = ['A','B','C','D'].map(id=>({id})); window.marked=[];window.requests=[];
          window.feedbackWorkspace={cards:()=>cards,payload:c=>({student_id:c.id,name:c.id,feedback:'Exact feedback '+c.id,assignment:'Design',course:'Synthetic class'}),valid:()=>true,posted:new Map(),tickMatches:()=>false,markPosted:id=>marked.push(id)};
          window.feedbackAssignment={saveForPosting:async()=>true};
          window.fetch=async(url,options)=>{ let data;
            if(url.includes('/approved?')) data={students:cards.filter(c=>c.id!=='D').map(c=>({student_id:c.id,name:c.id,level:'Proficient'}))};
            else if(options){const body=JSON.parse(options.body);requests.push(body);window.mode=body.op;data={job:{id:'job-'+body.op}};}
            else { const kind=window.kind;const inspect=mode==='inspect';
              const drafts=inspect?cards.map(c=>({key:c.id,[kind+'_batch']:{existing:'Previous '+c.id,target_name:c.id,criteria:[],desired:{comment:'Exact comment '+c.id},existingComment:'old'}})):[{key:'A',[kind+'_batch']:{verified:true}}];
              if(inspect&&kind==='myschool') drafts.push({key:'@assignment',myschool_batch:{course:'Synthetic class',title:'Design',publication:'0'}});
              const items=cards.map((c,i)=>({key:c.id,state:inspect||i===0?'done':'failed',error:i===1?'Connection lost after write':'Not attempted: earlier student failed'}));
              if(inspect&&kind==='myschool')items.push({key:'@assignment',state:'done'});
              data={job:{state:'completed',items,drafts}};
            } return {json:async()=>data};
          };
        }""")
        page.evaluate('(kind)=>window.kind=kind',destination)
        source=Path(APPDIR,'ui', 'teams_post.js' if destination=='teams' else 'myschool.js').read_text()
        if destination=='teams': source=source[source.index('/* Post to Teams:'):]
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_script_tag(content=source)
        if destination=='myschool':
            page.evaluate('postToAllMySchool()')
            page.get_by_label('MySchool assignment address').fill('https://example.invalid/assessment')
            page.get_by_label('MySchool assignment address').dispatch_event('change')
            page.get_by_role('button',name='Read MySchool',exact=True).click()
        else: page.evaluate('postToAll()')
        dlg=page.get_by_role('dialog')
        expect(dlg.get_by_role('status')).to_contain_text('3 ready')
        expect(dlg).to_contain_text('Exact feedback A' if destination=='teams' else 'Exact comment A')
        expect(dlg.locator('.posting-exclusions')).to_contain_text('D: not eligible')
        checks+=1
        if destination=='myschool':
            page.get_by_label('MySchool assignment address').fill('https://example.invalid/other')
            page.get_by_label('MySchool assignment address').dispatch_event('change')
            expect(dlg.get_by_role('button',name='Save to MySchool',exact=True)).to_be_hidden()
            page.get_by_role('button',name='Read MySchool',exact=True).click()
            expect(dlg.get_by_role('status')).to_contain_text('3 ready')
            checks+=1
        # The only checkbox in Teams; MySchool also has the Graded option.
        dlg.locator('input[type=checkbox]').last.check()
        dlg.get_by_role('button',name='Post feedback and Return' if destination=='teams' else 'Save to MySchool',exact=True).click()
        expect(dlg.get_by_role('status')).to_contain_text('Outcome uncertain: B')
        expect(dlg.get_by_role('status')).to_contain_text('Not attempted: C')
        expect(dlg.get_by_role('status')).to_contain_text('Verified posts: 1' if destination=='teams' else 'Verified saves: 1')
        assert page.evaluate('marked')==['A']
        assert page.evaluate("requests.filter(r=>r.op==='save').length")==1
        assert not errors,errors
        checks+=1
        page.close()
    browser.close()
print(f'PASS {checks} batch preview and mixed-outcome checks; no automatic retry')
