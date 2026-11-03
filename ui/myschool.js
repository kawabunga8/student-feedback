/* One reviewed student at a time (one or several criteria), explicit preview then Save. No publishing. */
(() => {
  const $ = s => document.querySelector(s);
  const el = (tag, text='') => { const e=document.createElement(tag); e.textContent=text; return e; };
  const aid = () => $('#asg-pick')?.value || '';
  const post = async b => (await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  const pause = () => new Promise(r=>setTimeout(r,1200));
  const card=el('div');card.className='card myschool-pilot';
  card.append(el('h3','MySchool pilot — one student'),el('p','Preview one saved, reviewed assessment, then explicitly save its level(s) and MySchool comment. With several criteria you type one level per criterion, in the order MySchool shows them, and check the preview. Publishing is never changed. Live saving has not yet been verified.'));
  const launch=el('button','Post reviewed assessment to MySchool…');launch.type='button';card.append(launch);$('#step-delivery').append(card);
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','MySchool posting pilot');
  dlg.append(el('h3','MySchool posting pilot'));
  const form=el('div');dlg.append(form);
  function field(label,control) {const l=el('label',label);l.style.display='block';control.setAttribute('aria-label',label);l.append(control);form.append(l);return control;}
  const student=field('Reviewed student',el('select'));
  const refresh=el('button','Refresh reviewed students');refresh.type='button';form.append(refresh);
  const url=field('MySchool assignment address',el('input'));url.placeholder='https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=…';
  const title=field('Exact MySchool assignment title',el('input'));title.placeholder='Leave empty: it is read from MySchool';
  const course=field('Exact MySchool course name',el('input'));course.placeholder='Leave empty: it is read from MySchool';
  const readNote=el('p');readNote.className='hint';form.append(readNote);
  // The address is remembered with the assignment; title and course are read from MySchool itself unless typed.
  const urlKey=()=>'myschool-address:'+(aid()||'none');
  const keepGet=k=>{try{return localStorage.getItem(k)||'';}catch(e){return '';}},keepSet=(k,v)=>{try{localStorage.setItem(k,v);}catch(e){}};
  const rememberedUrl=()=>keepGet(urlKey())||keepGet('posting-link:myschool:'+(document.getElementById('atitle')?.value.trim()||'default'));
  url.addEventListener('change',()=>{if(url.value.trim())keepSet(urlKey(),url.value.trim());});
  let autoFilled=false;url.addEventListener('input',()=>{if(autoFilled){title.value='';course.value='';readNote.textContent='';autoFilled=false;}});
  const name=field('Exact student name shown in MySchool',el('input'));name.placeholder='Confirm the MySchool spelling; it may differ from Course Hub';
  const codes=field('Level for each MySchool criterion, in page order (leave empty only if the student has one criterion)',el('input'));codes.placeholder='e.g. PRF, EXT+ (EMG, DEV, PRF, EXT, optional +)';
  const graded=field('Also set this student’s status to Graded',el('input'));graded.type='checkbox';
  const inspect=el('button','Read destination and preview');inspect.type='button';form.append(inspect);
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const previewBox=el('div');previewBox.className='myschool-preview';dlg.append(previewBox);
  const confirm=el('input');confirm.type='checkbox';const confirmLabel=el('label','I checked the assignment, course, student, level and exact comment. Save these values to MySchool.');confirmLabel.prepend(confirm);dlg.append(confirmLabel);
  const save=el('button','Save this approved assessment to MySchool');save.type='button';save.disabled=true;dlg.append(save);
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();dlg.append(close);document.body.append(dlg);
  let generation=0, preview=null, busy=false;
  dlg.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
  const localCurrent = id => { const ws=window.feedbackWorkspace;return !!ws && ws.cards().some(c=>ws.payload(c).student_id===id && ws.valid(c)); };
  function invalidate() {preview=null;previewBox.replaceChildren();confirm.checked=false;save.disabled=true;}
  form.addEventListener('input',invalidate);form.addEventListener('change',invalidate);
  student.addEventListener('change',()=>{name.value='';});
  confirm.onchange=()=>{save.disabled=busy||!preview||!confirm.checked||!localCurrent(preview.student_id);};
  async function flush() {
    if(!window.feedbackAssignment?.saveForPosting || !await window.feedbackAssignment.saveForPosting()) throw Error('Save the assignment and session first. Resolve any save conflict before posting.');
  }
  async function load() {
    if(busy)return;
    const owner=aid(), token=++generation;
    invalidate();student.replaceChildren(new Option('Choose a saved, reviewed student…',''));
    if(!aid()) {message.textContent='Open a saved assignment first.';return;}
    try {await flush(); const d=await(await fetch('/api/myschool/approved?assignment='+encodeURIComponent(aid()))).json();if(d.error)throw Error(d.error);
      if(owner!==aid()||token!==generation)return;
      (d.students||[]).forEach(s=>student.add(new Option(s.name+' — '+s.level,s.student_id)));
      message.textContent=d.students?.length?'Choose the student and confirm the exact MySchool destination.':'No current saved approvals. Review a student and their MySchool comment first.';
    } catch(e) {if(owner===aid()&&token===generation)message.textContent=e.message;}
  }
  async function follow(job,owner,token) {
    while(token===generation && owner===aid()) {
      const d=await(await fetch('/api/jobs/'+job.id)).json();const j=d.job;if(!j)throw Error(d.error||'Job not found.');
      if(token!==generation||owner!==aid())throw Error('The assignment changed. Check MySchool for the current job.');
      if(['queued','running'].includes(j.state)) {message.textContent='Chrome is checking MySchool. Sign in there if asked. Keep this dialog open.';await pause();continue;}
      if(token!==generation||owner!==aid())return;
      const failed=(j.items||[]).find(x=>x.state==='failed');
      if(j.state!=='completed'||failed)throw Error(failed?.error||j.error||'The job stopped. Check MySchool and create a fresh preview.');
      const out=j.drafts?.find(x=>x.myschool)?.myschool;if(!out)throw Error('No verified result was returned.');
      return out;
    }
  }
  async function run(op) {
    if(busy)return;
    const owner=aid(),token=++generation, sid=student.value;
    const selected=window.feedbackWorkspace.cards().find(c=>window.feedbackWorkspace.payload(c).student_id===sid);
    const bound=selected?JSON.stringify(window.feedbackWorkspace.payload(selected)):'';
    busy=true;form.querySelectorAll('input,select,button').forEach(e=>e.disabled=true);save.disabled=true;close.disabled=true;
    try {
      await flush();if(!localCurrent(student.value))throw Error('This student is no longer reviewed. Review and save again.');
      if(owner!==aid()||token!==generation)return;
      if(op==='inspect'&&(!title.value.trim()||!course.value.trim())){   // only the address was given: ask MySchool what this assignment is called
        message.textContent='Reading the assignment from MySchool… Chrome opens for this; sign in there if asked.';
        const d0=await post({type:'myschool',op:'read',assignment:owner,url:url.value.trim()});if(d0.error)throw Error(d0.error);
        const got=await follow(d0.job,owner,token);if(!got||!got.title||!got.course)throw Error('MySchool did not show this assignment’s title and course. Check the address.');
        if(!title.value.trim())title.value=got.title;if(!course.value.trim())course.value=got.course;autoFilled=true;
        readNote.textContent='From MySchool: '+got.course+' → '+got.title+(got.publication&&got.publication!=='0'?' (published)':' (unpublished)')+'. Check this is the right assignment before you confirm.';
      }
      const body=op==='inspect'?{type:'myschool',op,assignment:owner,student_id:student.value,url:url.value.trim(),title:title.value.trim(),course:course.value.trim(),target_name:name.value.trim(),codes:codes.value.trim(),mark_graded:graded.checked}
        :{type:'myschool',op,assignment:owner,preview_id:preview.jobId,confirm:confirm.checked};
      const d=await post(body);if(d.error)throw Error(d.error);
      const out=await follow(d.job,owner,token);if(!out||owner!==aid()||token!==generation)return;
      if(op==='inspect') {
        preview={...out,jobId:d.job.id};previewBox.replaceChildren();
        previewBox.append(el('h4','Review the exact change'),el('p',out.course+' → '+out.title+' → '+out.target_name),el('p',(out.criteria||[]).length>1?'Levels to save, by criterion (check each against MySchool):':'Level to save:'),...(out.criteria||[]).map((c,i)=>el('p',(i+1)+'. '+(c.label||'(no label found)')+': '+(c.existing||'ungraded')+' → '+c.chosen)),el('p','Approved comment: '+out.comment),el('p','Existing comment: '+(out.existing.comment||'(empty)')),el('p',out.mark_graded?'Status will be set to Graded.':'Status will be preserved.'),el('p',out.publication==='0'?'Assignment is unpublished. It will stay unpublished.':'Assignment is published: saved values may be visible immediately under its existing settings. Publication will not be changed.'));
        message.textContent='Preview only: nothing changed in MySchool. This preview expires after 10 minutes.';
      } else {
        const marked=out.verified&&window.feedbackWorkspace?.markPosted?.(sid,'myschool',bound);invalidate();message.textContent=out.verified?'Verified by reopening MySchool: the approved level and comment match. Publication setting preserved. '+(marked?'Marked as saved.':'Local assessment changed; completion was not marked.'):'Save outcome is uncertain. Check MySchool before trying again.';
      }
    } catch(e) {if(owner===aid()&&token===generation)message.textContent=e.message;}
    finally {if(owner===aid()&&token===generation){busy=false;form.querySelectorAll('input,select,button').forEach(e=>e.disabled=false);close.disabled=false;save.disabled=!preview||!confirm.checked||!localCurrent(preview.student_id);}}
  }
  inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked)run('save');};refresh.onclick=load;
  launch.onclick=()=>{if(!url.value.trim())url.value=rememberedUrl();readNote.textContent='';dlg.showModal();load();};window.postOneMySchool=launch.onclick;
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;form.querySelectorAll('input,select,button').forEach(e=>e.disabled=false);close.disabled=false;invalidate();message.textContent='Assignment changed. Reopen the pilot to load its reviewed students.';student.replaceChildren();});
})();

/* Several reviewed students in one run. This adds no new posting path: it drives the one-student pilot above
   (same /api/jobs preview and Save, same approval, preview-claim and read-back checks) one student at a time.
   Preview all first (read-only), confirm once, then Save in order; the first failure stops the run. Publishing is never changed. */
(() => {
  const $ = s => document.querySelector(s);
  const el = (tag, text='') => { const e=document.createElement(tag); e.textContent=text; return e; };
  const aid = () => $('#asg-pick')?.value || '';
  const post = async b => (await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  const pause = () => new Promise(r=>setTimeout(r,1200));
  const FRESH_MS = 8*60*1000;                       // the server refuses previews older than 10 minutes
  const card=el('div');card.className='card myschool-bulk';
  card.append(el('h3','MySchool — batch posting'),el('p','Choose reviewed students, preview every change, then confirm the batch. Saves run one student at a time. The run stops at the first problem and tells you who was saved. Each student uses the same checks as the one-student pilot. Live saving has not yet been verified: try one student in the pilot above first.'));
  const launch=el('button','Post a batch to MySchool…');launch.type='button';card.append(launch);$('#step-delivery').append(card);
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','MySchool bulk posting');
  dlg.append(el('h3','MySchool — batch posting'));
  const form=el('div');dlg.append(form);
  function field(label,control){const l=el('label',label);l.style.display='block';control.setAttribute('aria-label',label);l.append(control);form.append(l);return control;}
  const url=field('MySchool assignment address',el('input'));url.placeholder='https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=…';
  const title=field('Exact MySchool assignment title',el('input'));title.placeholder='Leave empty: it is read from MySchool';
  const course=field('Exact MySchool course name',el('input'));course.placeholder='Leave empty: it is read from MySchool';
  const readNote=el('p');readNote.className='hint';form.append(readNote);
  // The address is remembered with the assignment, so it is pasted once. Title and course are read from MySchool itself unless typed.
  const urlKey=()=>'myschool-address:'+(aid()||'none');
  const keepGet=k=>{try{return localStorage.getItem(k)||'';}catch(e){return '';}},keepSet=(k,v)=>{try{localStorage.setItem(k,v);}catch(e){}};
  const rememberedUrl=()=>keepGet(urlKey())||keepGet('posting-link:myschool:'+(document.getElementById('atitle')?.value.trim()||'default'));
  url.addEventListener('change',()=>{if(url.value.trim())keepSet(urlKey(),url.value.trim());});
  let autoFilled=false;url.addEventListener('input',()=>{if(autoFilled){title.value='';course.value='';readNote.textContent='';autoFilled=false;}});   // a different address: forget what was read for the old one
  const graded=field('Also set each student’s status to Graded',el('input'));graded.type='checkbox';
  const refresh=el('button','Load reviewed students');refresh.type='button';form.append(refresh);
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const pubNote=el('p');pubNote.setAttribute('role','status');pubNote.style.fontWeight='600';dlg.append(pubNote);
  const table=el('div');table.className='myschool-bulk-rows';dlg.append(table);
  const previewAll=el('button','Read MySchool and preview all');previewAll.type='button';previewAll.disabled=true;dlg.append(previewAll);
  const confirm=el('input');confirm.type='checkbox';const confirmText=el('span');const confirmLabel=el('label');confirmLabel.append(confirm,confirmText);dlg.append(confirmLabel);
  const save=el('button','Save all previewed students to MySchool');save.type='button';save.disabled=true;dlg.append(save);
  const stop=el('button','Stop after current student');stop.type='button';stop.disabled=true;dlg.append(stop);
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();dlg.append(close);document.body.append(dlg);
  let rows=[], generation=0, busy=false, halt=false;
  dlg.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
  const localCurrent = id => { const ws=window.feedbackWorkspace; return !!ws && ws.cards().some(c=>ws.payload(c).student_id===id && ws.valid(c)); };
  const ready = () => rows.filter(r=>r.include.checked && r.preview && r.state==='previewed');
  const boundFor=id=>{const ws=window.feedbackWorkspace,c=ws.cards().find(c=>ws.payload(c).student_id===id);return c?JSON.stringify(ws.payload(c)):'';};
  // Progress and timestamps may change; destination, publication and assessment values require fresh confirmation.
  const confirmedValues=p=>JSON.stringify(Object.fromEntries(['url','title','course','target_id','target_name','student_id','publication','criteria','desired','existing','comment','codes','mark_graded','approval_sha'].map(k=>[k,p[k]])));
  function draw() {
    form.querySelectorAll('input,button').forEach(e=>e.disabled=busy);close.disabled=busy;confirm.disabled=busy;
    // Keep input nodes attached while focus/change/click events run.
    [...table.children].filter(e=>!rows.some(r=>r.line===e)).forEach(e=>e.remove());
    rows.forEach(r => {
      if(!r.line){
        r.line=el('div');r.line.style.margin='8px 0';r.status=el('span');r.previewBox=el('div');
        r.line.append(r.include,el('strong',r.name+' — '+(r.level||'no level')+'  '),r.nameInput,r.levelsInput,el('br'),r.status,r.previewBox);
      }
      const line=r.line;
      const locked=busy||r.state==='saved'||r.state==='unknown';
      r.include.disabled=locked;r.nameInput.disabled=locked;r.levelsInput.disabled=locked;
      r.status.textContent=r.state==='saved'?'✓ saved and verified':r.state==='unknown'?'⚠ Outcome unknown — check MySchool before retrying':r.state==='previewed'?'ready to save':r.error?'⚠ '+r.error:r.state==='working'?'working…':r.already?'Previously marked saved; excluded by default':'not previewed';
      r.previewBox.replaceChildren();
      if(r.state==='previewed'&&r.preview){   // the full change, as the one-student pilot shows it: each criterion, the whole comment, the status
        const p=r.preview,det=el('details'),sum=el('summary','Full preview: '+(p.criteria||[]).map(c=>(c.existing||'ungraded')+' → '+c.chosen).join(', '));det.append(sum,el('div',p.course+' → '+p.title+' → '+p.target_name));
        (p.criteria||[]).forEach((c,i)=>det.append(el('div',(i+1)+'. '+(c.label||'(no label found)')+': '+(c.existing||'ungraded')+' → '+c.chosen)));
        det.append(el('div','Comment — existing: '+((p.existing&&p.existing.comment)||'(empty)')),el('div','Comment — will save: '+p.comment),el('div',p.mark_graded?'Status will be set to Graded.':'Status will be preserved.'));
        r.previewBox.append(det);
      }
      if(line.parentElement!==table)table.append(line);
    });
    const pub=ready().filter(r=>r.preview.publication!=='0').length;
    pubNote.textContent=pub?'This assignment is published: saved results may be visible to students immediately under its existing settings. Publication is not changed.':ready().length?'This assignment is unpublished and will stay unpublished.':'';
    const n=ready().length;
    confirmText.textContent=' I checked all '+n+' previews (assignment, course, each student, level and comment). Save these '+n+' students to MySchool, one after another.';
    previewAll.disabled=busy||!rows.length||!url.value.trim();
    save.disabled=busy||!n||!confirm.checked;
    stop.disabled=!busy;
  }
  function invalidate(){rows.forEach(r=>{if(!['saved','unknown'].includes(r.state)){r.state='';r.preview=null;r.error='';}});confirm.checked=false;draw();}
  form.addEventListener('input',()=>{if(!busy)invalidate();});form.addEventListener('change',()=>{if(!busy)invalidate();});
  confirm.onchange=draw;
  async function flush(){
    if(!window.feedbackAssignment?.saveForPosting || !await window.feedbackAssignment.saveForPosting()) throw Error('Save the assignment and session first. Resolve any save conflict before posting.');
  }
  async function follow(job,owner,token){
    for(let i=0;i<300;i++){
      if(token!==generation||owner!==aid())throw Error('The assignment changed. Stopped.');
      const d=await(await fetch('/api/jobs/'+job.id)).json();const j=d.job;if(!j)throw Error(d.error||'Job not found.');
      if(token!==generation||owner!==aid())throw Error('The assignment changed. Check MySchool for the current job.');
      if(['queued','running','waiting_for_sign_in'].includes(j.state)){message.textContent='Chrome is working in MySchool. Sign in there if asked. Keep this dialog open.';await pause();continue;}
      const failed=(j.items||[]).find(x=>x.state==='failed');
      if(j.state!=='completed'||failed)throw Error(failed?.error||j.error||'The job stopped. Check MySchool.');
      const out=j.drafts?.find(x=>x.myschool)?.myschool;if(!out)throw Error('No verified result was returned.');
      return out;
    }
    throw Error('Timed out waiting for MySchool. Check MySchool before retrying.');
  }
  const inspectBody=(owner,r)=>({type:'myschool',op:'inspect',assignment:owner,student_id:r.id,url:url.value.trim(),title:title.value.trim(),course:course.value.trim(),target_name:r.nameInput.value.trim(),mark_graded:graded.checked,
    ...(r.levelsInput.value.trim()?{codes:r.levelsInput.value.trim()}:{})});   // empty: the student's own level (single-criterion assignments); several criteria need one level each, typed here
  async function load(){
    if(busy)return;
    const owner=aid(),token=++generation;rows=[];draw();
    if(!owner){message.textContent='Open a saved assignment first.';return;}
    try{
      await flush();const d=await(await fetch('/api/myschool/approved?assignment='+encodeURIComponent(owner))).json();if(d.error)throw Error(d.error);
      if(owner!==aid()||token!==generation)return;
      rows=(d.students||[]).map(s=>{const nameInput=el('input');nameInput.value=s.name;nameInput.setAttribute('aria-label','MySchool name for '+s.name);
        const ws=window.feedbackWorkspace,c=ws.cards().find(c=>ws.payload(c).student_id===s.student_id),tick=c&&(ws.posted?.get(c)||{}).myschool;
        const already=!!(tick&&tick.bound===boundFor(s.student_id));
        const include=el('input');include.type='checkbox';include.style.width='auto';include.checked=!already;include.setAttribute('aria-label','Include '+s.name+' in batch');include.onchange=()=>{confirm.checked=false;draw();};
        const levelsInput=el('input');levelsInput.placeholder='Levels, one per criterion in page order (e.g. PRF, EXT+). Empty = '+(s.level||'no level')+' for a single criterion';levelsInput.setAttribute('aria-label','MySchool levels for '+s.name);
        const reset=()=>{const r=rows.find(x=>x.nameInput===nameInput);if(r&&r.state!=='saved'){r.state='';r.preview=null;r.error='';confirm.checked=false;draw();}};nameInput.onchange=reset;levelsInput.onchange=reset;
        return {id:s.student_id,name:s.name,level:s.level,include,already,nameInput,levelsInput,state:'',preview:null,error:''};});
      message.textContent=rows.length?rows.length+' reviewed students. Check each name matches MySchool exactly, fill in the assignment details, then preview all.':'No current saved approvals. Review each student and their MySchool comment first.';
      draw();
    }catch(e){if(owner===aid()&&token===generation)message.textContent=e.message;}
  }
  async function previewEveryone(){
    const names=rows.filter(r=>r.include.checked&&!['saved','unknown'].includes(r.state)).map(r=>r.nameInput.value.trim().toLowerCase());
    if(new Set(names).size!==names.length){message.textContent='Two selected students have the same MySchool name. Correct the names before previewing.';return;}
    if(busy)return;const owner=aid(),token=++generation;busy=true;halt=false;confirm.checked=false;draw();
    try{
      await flush();
      if(!title.value.trim()||!course.value.trim()){   // only the address was given: ask MySchool what this assignment is called
        message.textContent='Reading the assignment from MySchool… Chrome opens for this; sign in there if asked.';
        const d0=await post({type:'myschool',op:'read',assignment:owner,url:url.value.trim()});if(d0.error)throw Error(d0.error);
        const got=await follow(d0.job,owner,token);if(!got||!got.title||!got.course)throw Error('MySchool did not show this assignment’s title and course. Check the address.');
        if(!title.value.trim())title.value=got.title;if(!course.value.trim())course.value=got.course;autoFilled=true;
        readNote.textContent='From MySchool: '+got.course+' → '+got.title+(got.publication&&got.publication!=='0'?' (published)':' (unpublished)')+'. Check this is the right assignment before you confirm.';
      }
      for(const r of rows){
        if(halt||owner!==aid()||token!==generation)break;
        if(!r.include.checked||r.state==='saved'||r.state==='unknown')continue;
        r.state='working';r.error='';r.preview=null;draw();
        try{
          if(!localCurrent(r.id))throw Error('No longer reviewed. Review and save again.');
          const d=await post(inspectBody(owner,r));if(d.error)throw Error(d.error);
          r.preview={...await follow(d.job,owner,token),jobId:d.job.id,at:Date.now()};r.state='previewed';
        }catch(e){r.state='';r.error=e.message;}
        draw();
      }
      message.textContent=ready().length+' of '+rows.length+' previewed (nothing changed in MySchool). Students with a ⚠ will not be saved. Previews expire after 10 minutes.';
    }catch(e){message.textContent=e.message;}
    finally{busy=false;draw();}
  }
  async function saveEveryone(){
    if(busy||!confirm.checked)return;const owner=aid(),token=++generation;busy=true;halt=false;const todo=ready();draw();
    const done=[];let problem='';
    try{
      await flush();
      for(const r of todo){
        if(halt){problem='Stopped by you.';break;}
        if(owner!==aid()||token!==generation){problem='The assignment changed.';break;}
        r.state='working';draw();let dispatched=false;const bound=boundFor(r.id);
        try{
          if(!localCurrent(r.id))throw Error('No longer reviewed.');
          let p=r.preview;
          if(Date.now()-p.at>FRESH_MS){        // preview too old for the server: read again and require the same values
            const d=await post(inspectBody(owner,r));if(d.error)throw Error(d.error);
            const again={...await follow(d.job,owner,token),jobId:d.job.id,at:Date.now()};
            if(confirmedValues(again)!==confirmedValues(p))throw Error('The destination, publication setting or assessment changed. Preview and confirm the batch again.');
            p=r.preview=again;
          }
          if(halt||owner!==aid()||token!==generation)throw Error('Stopped before Save.');
          dispatched=true;
          const d=await post({type:'myschool',op:'save',assignment:owner,preview_id:p.jobId,confirm:true});if(d.error)throw Error(d.error);
          const out=await follow(d.job,owner,token);
          if(!out.verified)throw Error('Save outcome is uncertain. Check MySchool before trying again.');
          r.state='saved';done.push(r.name);window.feedbackWorkspace?.markPosted?.(r.id,'myschool',bound);
        }catch(e){r.state=dispatched?'unknown':'';r.preview=null;r.error=e.message;problem=r.name+': '+e.message;draw();break;}   // a Save may have used this preview: read MySchool again
        draw();
      }
    }catch(e){problem=e.message;}
    finally{busy=false;confirm.checked=false;draw();}
    const unknown=todo.filter(r=>r.state==='unknown').map(r=>r.name);
    const left=todo.filter(r=>!['saved','unknown'].includes(r.state)).map(r=>r.name);
    message.textContent=(done.length?'Saved and verified: '+done.join(', ')+'. ':'No saves verified. ')+(problem?'Stopped — '+problem+' ':'')+(unknown.length?'Outcome unknown: '+unknown.join(', ')+'. Check MySchool before reloading or retrying. ':'')+(left.length?'Not attempted: '+left.join(', ')+'.':'')+(!problem&&!unknown.length&&!left.length?' Batch complete.':'');
  }
  refresh.onclick=load;previewAll.onclick=previewEveryone;save.onclick=saveEveryone;stop.onclick=()=>{halt=true;message.textContent='Stopping after the current student…';};
  launch.onclick=()=>{if(!url.value.trim())url.value=rememberedUrl();readNote.textContent='';dlg.showModal();load();};window.postToAllMySchool=launch.onclick;
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;halt=true;rows=[];draw();message.textContent='Assignment changed. Reopen this dialog.';});
  draw();
})();
