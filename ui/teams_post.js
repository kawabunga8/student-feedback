/* One approved student, explicit preview then Return. No automatic posting or retries. */
(() => {
  const $=s=>document.querySelector(s), el=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
  const aid=()=>$('#asg-pick')?.value||'';
  const post=async body=>(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  const card=el('div');card.className='card teams-post-pilot';
  card.append(el('h3','Teams posting pilot — one student'),el('p','Preview approved feedback, then post it and Return to one student. Return may notify the student. Live posting has not yet been verified.'));
  const launch=el('button','Post reviewed feedback to Teams…');launch.type='button';card.append(launch);$('#step-delivery').append(card);
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','Teams posting pilot');dlg.append(el('h3','Teams posting pilot'));
  const form=el('div');dlg.append(form);
  function field(label,control){const l=el('label',label);control.setAttribute('aria-label',label);l.append(control);form.append(l);return control;}
  const student=field('Reviewed student',el('select'));
  const name=field('Exact student name in the Teams roster',el('input'));name.placeholder='Last, First — exactly as the Teams roster shows it';
  const nameRow=name.parentElement;nameRow.style.display='none';                 // shown only when the app can't find the student in Teams
  const nameNote=el('p');nameNote.className='hint';form.append(nameNote);
  // Course Hub's class list gives "Last, First". Without it (Course Hub off) the teacher has to type the name.
  const defaultName=sid=>{const r=(typeof ROSTER!=='undefined'?ROSTER:[]).find(x=>x.id===sid);return r?r.last+', '+r.first:'';};
  function setName(){name.value=defaultName(student.value);nameRow.style.display=(name.value||!student.value)?'none':'';
    nameNote.textContent=!student.value?'':name.value?'Looking for “'+name.value+'” in the Teams roster (from Course Hub).':'Course Hub’s class list isn’t available, so type the name exactly as the Teams roster shows it.';}
  const inspect=el('button','Read Teams again and refresh the preview');inspect.type='button';form.append(inspect);
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const box=el('div');box.className='teams-post-preview';dlg.append(box);
  const confirm=el('input');confirm.type='checkbox';
  const label=el('label','I checked the student, assignment and exact feedback. Post this feedback and Return; the student may be notified.');label.prepend(confirm);dlg.append(label);
  const save=el('button','Post feedback and Return');save.type='button';save.disabled=true;dlg.append(save);
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();dlg.append(close);document.body.append(dlg);
  let generation=0,preview=null,busy=false;
  const current=sid=>window.feedbackWorkspace?.cards().some(c=>window.feedbackWorkspace.payload(c).student_id===sid&&window.feedbackWorkspace.valid(c));
  function invalidate(){preview=null;box.replaceChildren();confirm.checked=false;save.disabled=true;}
  form.addEventListener('input',invalidate);form.addEventListener('change',invalidate);
  student.onchange=()=>{setName();autoPreview();};
  name.onchange=()=>{autoPreview();};                                     // typed a corrected name: look again
  // The preview only reads Teams (nothing is changed), so it starts by itself once the app has a student and a name.
  function autoPreview(){if(student.value&&name.value.trim()&&!busy)setTimeout(()=>{invalidate();run('inspect');},0);}confirm.onchange=()=>{save.disabled=busy||!preview||!confirm.checked||!current(preview.student_id);};
  async function flush(){if(!await window.feedbackAssignment?.saveForPosting())throw Error('Save the assignment and session, and resolve any conflict first.');}
  async function follow(job,owner,token){
    while(owner===aid()&&token===generation){
      const j=(await(await fetch('/api/jobs/'+job.id)).json()).job;if(!j)throw Error('Job not found. Check Teams.');
      if(['queued','running'].includes(j.state)){message.textContent='Chrome is checking Teams. Keep this dialog open.';await new Promise(r=>setTimeout(r,1200));continue;}
      if(owner!==aid()||token!==generation)return;
      const fail=j.items?.find(i=>i.state==='failed');if(j.state!=='completed'||fail)throw Error(fail?.error||j.error||'Check Teams before creating a fresh preview.');
      const out=j.drafts?.find(d=>d.teams_post)?.teams_post;if(!out)throw Error('No verified result. Check Teams before retrying.');return out;
    }
  }
  async function load(){
    if(busy){message.textContent='A Teams check is still running. Keep this dialog open until it finishes.';return;}
    const owner=aid(),token=++generation;invalidate();student.replaceChildren(new Option('Choose a saved, reviewed student…',''));
    try{await flush();const d=await(await fetch('/api/teams-post/approved?assignment='+encodeURIComponent(owner))).json();if(owner!==aid()||token!==generation)return;if(d.error)throw Error(d.error);
      (d.students||[]).forEach(s=>student.add(new Option(s.name,s.student_id)));message.textContent=(d.students||[]).length===1?'Reading Teams for the one reviewed student…':'Choose one reviewed student. The app reads Teams for them automatically and finds them by name; you only need to type the name if it can’t.';
      if((d.students||[]).length===1){student.value=d.students[0].student_id;setName();autoPreview();}
    }catch(e){if(owner===aid()&&token===generation)message.textContent=e.message;}
  }
  async function run(op){
    if(busy)return;const owner=aid(),token=++generation;busy=true;student.disabled=true;name.disabled=true;inspect.disabled=true;save.disabled=true;
    try{await flush();if(owner!==aid()||token!==generation)return;if(!current(student.value))throw Error('Review this student and save before posting.');
      const body=op==='inspect'?{type:'teams_post',op,assignment:owner,student_id:student.value,target_name:name.value.trim()}:{type:'teams_post',op,assignment:owner,preview_id:preview.jobId,confirm:confirm.checked};
      const d=await post(body);if(d.error)throw Error(d.error);const out=await follow(d.job,owner,token);if(!out||owner!==aid()||token!==generation)return;
      if(op==='inspect'){preview={...out,jobId:d.job.id};box.replaceChildren(el('h4','Review the exact change'),el('p',out.class+' → '+out.title+' → '+out.target_name),el('p','Existing feedback: '+(out.existing||'(empty)')),el('p','Approved feedback:'));
        const full=el('div',out.feedback);full.style.whiteSpace='pre-wrap';box.append(full);message.textContent='Preview only. Posting replaces the existing feedback and Returns this student’s work. This preview expires in 10 minutes.';
      }else{if(out.verified)window.feedbackWorkspace?.markPosted?.(student.value,'teams');invalidate();message.textContent=out.verified?'Verified: feedback matches and the student appears in Returned. Marked as posted.':'Outcome uncertain. Check Teams before retrying.';}
    }catch(e){if(owner===aid()&&token===generation){invalidate();message.textContent=e.message;
      if(/student was not found|roster name/i.test(e.message)){nameRow.style.display='';nameNote.textContent='Couldn’t find “'+name.value+'” in Teams. Type the name exactly as the Teams roster shows it (usually Last, First), then preview again.';}}}
    finally{if(owner===aid()&&token===generation){busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;save.disabled=!preview||!confirm.checked||!current(preview.student_id);}}
  }
  inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked)run('save');};launch.onclick=()=>{dlg.showModal();load();};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;invalidate();student.replaceChildren();message.textContent='Assignment changed. Reopen this pilot.';});
})();

/* Post to Teams: one student or the whole class, on the same engine. Reading and posting each run in ONE Chrome session
   (teams_batch.py): Teams is opened once and the roster is walked. Reading changes nothing and starts by itself; posting needs
   your one confirmation, re-checks each student's approval at the moment of writing, and stops at the first problem.
   Return may notify each student. */
(() => {
  const $=s=>document.querySelector(s), el=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
  const aid=()=>$('#asg-pick')?.value||'';
  const post=async b=>(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  const pause=()=>new Promise(r=>setTimeout(r,1200));
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','Teams bulk posting');
  const title=el('h3');dlg.append(title);
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const excluded = el('p'); excluded.className = 'posting-exclusions'; dlg.append(excluded);
  const table=el('div');table.className='teams-bulk-rows';dlg.append(table);
  const again=el('button','Read Teams again');again.type='button';
  const confirm=el('input');confirm.type='checkbox';const confirmText=el('span');const confirmLabel=el('label');confirmLabel.append(confirm,confirmText);
  const save=el('button','Post feedback and Return');save.type='button';save.disabled=true;
  const stop=el('button','Stop');stop.type='button';stop.disabled=true;
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();
  dlg.append(confirmLabel,save,stop,again,close);document.body.append(dlg);
  let rows=[],generation=0,busy=false,previewJob='',curJob='';
  const ws=()=>window.feedbackWorkspace;
  const current=sid=>ws()?.cards().some(c=>ws().payload(c).student_id===sid&&ws().valid(c));
  const defaultName=sid=>{const r=(typeof ROSTER!=='undefined'?ROSTER:[]).find(x=>x.id===sid);return r?r.last+', '+r.first:'';};
  const ready=()=>rows.filter(r=>r.state==='ready');
  function draw(){
    table.replaceChildren();
    rows.forEach(r=>{
      const line=el('div');line.style.margin='6px 0';
      r.nameInput.disabled=busy||r.state==='posted';
      const status=r.state==='posted'?'✓ posted, Returned, and the saved feedback matches':r.state==='ready'?'ready'+(r.existing?' · replaces the feedback already there':''):r.state==='skipped'?'already Returned in Teams: skipped':r.state==='working'?'working…':r.state==='unattempted'?'Not attempted — '+r.error:r.state==='uncertain'?'Outcome uncertain — check Teams before trying again. '+r.error:r.state==='error'?'Preview blocked — '+r.error:'waiting';
      line.append(el('strong',r.name+'  '),r.nameInput,el('br'),el('span',status));if(r.state==='ready'&&r.bound){const p=JSON.parse(r.bound),details=el('details');details.append(el('summary','Full preview: recipient and exact feedback'),el('p',(p.course||'(course unavailable)')+' → '+p.assignment+' → '+r.nameInput.value.trim()),el('p','Existing feedback: '+(r.existing||'(empty)')),el('p','Approved feedback:'));const text=el('div',p.feedback);text.style.whiteSpace='pre-wrap';details.append(text,el('p','Replaces existing feedback and Returns the work. The student may be notified.'));line.append(details);}table.append(line);
    });
    const n=ready().length;
    confirmText.textContent=' I checked the '+n+' student'+(n===1?'':'s')+' (class, assignment and exact feedback). Post and Return '+(n===1?'this student':'these '+n+', one after another')+'; they may be notified.';
    confirmLabel.hidden=!n;save.hidden=!n;save.disabled=busy||!n||!confirm.checked;stop.disabled=!busy;again.disabled=busy;
  }
  confirm.onchange=draw;
  async function flush(){if(!await window.feedbackAssignment?.saveForPosting?.())throw Error('Save the assignment and session, and resolve any conflict first.');}
  // Follow one job, updating the rows as each student's result arrives.
  async function follow(jobId,owner,token,onItem){
    for(let i=0;i<900;i++){
      if(token!==generation||owner!==aid())throw Error('The assignment changed. Stopped.');
      const j=(await(await fetch('/api/jobs/'+jobId)).json()).job;if(!j)throw Error('Job not found. Check Teams.');
      const drafts=new Map((j.drafts||[]).map(d=>[d.key,d.teams_batch]));
      (j.items||[]).forEach(it=>onItem(it,drafts.get(it.key),j));draw();
      if(['queued','running'].includes(j.state)){message.textContent=(previewJob?'Posting: each student is re-checked, written, then verified (Returned, and the feedback Teams kept is read back)… ':'Identifying eligible students and reading Teams… ')+'Chrome is open for this one session; sign in there if asked.';await pause();continue;}
      if(j.state==='waiting_for_sign_in')throw Error('Teams needs you to sign in, in the Chrome window. Then try again.');
      return j;
    }
    throw Error('Timed out waiting for Teams. Check Teams before retrying.');
  }
  const names=()=>rows.map(r=>({student_id:r.id,target_name:r.nameInput.value.trim()}));
  async function readTeams(){
    if(busy)return;const owner=aid(),token=++generation;busy=true;confirm.checked=false;previewJob='';
    rows.forEach(r=>{if(r.state!=='posted'){r.state='working';r.error='';r.existing='';}});draw();
    try{await flush();
      const asked=rows.filter(r=>r.state!=='posted');if(!asked.length)return;
      asked.forEach(r=>{const c=ws().cards().find(c=>ws().payload(c).student_id===r.id);r.bound=JSON.stringify(ws().payload(c));});
      const d=await post({type:'teams_batch',op:'inspect',assignment:owner,students:asked.map(r=>({student_id:r.id,target_name:r.nameInput.value.trim()}))});if(d.error)throw Error(d.error);
      curJob=d.job.id;
      const j=await follow(d.job.id,owner,token,(it,res)=>{const r=rows.find(x=>x.id===it.key);if(!r||r.state==='posted')return;
        if(it.state==='done'&&res){if(res.skipped){r.state='skipped';}else{r.state='ready';r.existing=(res.existing||'').trim();}}
        else if(it.state==='failed'){r.state='error';r.error=it.error||'Teams did not return a result.';}});
      previewJob=d.job.id;
      const skipped=rows.filter(r=>r.state==='skipped').length,bad=rows.filter(r=>r.state==='error').length;
      message.textContent=ready().length+' ready to post'+(skipped?' · '+skipped+' already Returned (skipped)':'')+(bad?' · '+bad+' need attention (⚠, not posted)':'')+'. Nothing was changed in Teams.';
    }catch(e){message.textContent=e.message;rows.forEach(r=>{if(r.state==='working'){r.state='error';r.error=e.message;}});}
    finally{busy=false;draw();}
  }
  async function postAll(){
    if(busy||!confirm.checked||!previewJob)return;const owner=aid(),token=++generation;busy=true;const todo=ready();
    todo.forEach(r=>{r.state='working';});draw();
    const done=[];let problem='';
    try{await flush();
      if(todo.some(r=>!current(r.id)||!ws().cards().some(c=>JSON.stringify(ws().payload(c))===r.bound)))throw Error('A student is no longer reviewed. Read Teams again.');
      const d=await post({type:'teams_batch',op:'save',assignment:owner,preview_id:previewJob,confirm:true,students:todo.map(r=>({student_id:r.id}))});if(d.error)throw Error(d.error);
      curJob=d.job.id;
      await follow(d.job.id,owner,token,(it,res)=>{const r=todo.find(x=>x.id===it.key);if(!r||r.state==='posted')return;
        if(it.state==='done'&&res&&res.verified){r.state='posted';done.push(r.name);ws()?.markPosted?.(r.id,'teams',r.bound);}
        else if(it.state==='failed'){r.error=it.error||'No verified result.';r.state=/^Not attempted/.test(r.error)?'unattempted':'uncertain';if(!problem&&!/Not attempted/.test(r.error))problem=r.name+': '+r.error;}});
    }catch(e){problem=problem||e.message;todo.forEach(r=>{if(r.state==='working'){r.state='uncertain';r.error=e.message;}});}
    finally{todo.forEach(r=>{if(r.state==='working'){r.state='uncertain';r.error='The job ended without a verified result.';}});busy=false;confirm.checked=false;previewJob='';draw();}
    const uncertain=todo.filter(r=>r.state==='uncertain').map(r=>r.name),unattempted=todo.filter(r=>r.state==='unattempted').map(r=>r.name);
    message.textContent='Verified posts: '+done.length+'. '+(problem?'Stopped — '+problem+' ':'')+(uncertain.length?'Outcome uncertain: '+uncertain.join(', ')+'. Check the saved feedback and Returned status in Teams before making a new preview. ':'')+(unattempted.length?'Not attempted: '+unattempted.join(', ')+'. These need a fresh preview before posting. ':'')+(!uncertain.length&&!unattempted.length?'All selected posts were verified.':'No automatic retries.');
    draw();
  }
  again.onclick=readTeams;save.onclick=postAll;
  stop.onclick=async()=>{if(curJob){try{await fetch('/api/jobs/'+curJob+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}}message.textContent='Stopping after the current student…';};
  // ids: the students to post (one or several); null = every reviewed student. Opens, reads Teams by itself, and waits for the one confirmation.
  async function postToTeams(ids){
    const owner=aid();generation++;busy=false;rows=[];previewJob='';draw();
    excluded.textContent='';dlg.showModal();title.textContent='Post to Teams';message.textContent='Loading reviewed students…';
    if(!owner){message.textContent='Open a saved assignment first.';return;}
    try{await flush();const d=await(await fetch('/api/teams-post/approved?assignment='+encodeURIComponent(owner))).json();if(d.error)throw Error(d.error);
      const posted=sid=>{const w=ws();const c=w?.cards().find(x=>w.payload(x).student_id===sid);const t=c&&(w.posted.get(c)||{}).teams;return !!t&&t.bound===JSON.stringify(w.payload(c));};
      const list=(d.students||[]).filter(s=>ids?ids.includes(s.student_id):!posted(s.student_id));   // the whole class skips students this app already posted
      const eligible=new Set((d.students||[]).map(s=>s.student_id));
      const omitted=ws().cards().map(c=>ws().payload(c)).filter(p=>!ids||ids.includes(p.student_id)).filter(p=>!eligible.has(p.student_id)||(!ids&&posted(p.student_id))).map(p=>p.name+': '+(!eligible.has(p.student_id)?'not eligible — check student match, saved review and required feedback':'a current Teams post is already recorded'));
      excluded.textContent=omitted.length?'Excluded from this preview: '+omitted.join('; ')+'.':'All eligible students in this selection are included.';
      rows=list.map(s=>{const nameInput=el('input');nameInput.value=defaultName(s.student_id);nameInput.placeholder='Last, First — as the Teams roster shows it';nameInput.setAttribute('aria-label','Teams roster name for '+s.name);
        nameInput.onchange=()=>{const r=rows.find(x=>x.nameInput===nameInput);if(r&&r.state!=='posted'){r.state='';r.error='';confirm.checked=false;draw();}};
        return {id:s.student_id,name:s.name,nameInput,state:'',error:'',existing:''};});
      title.textContent=rows.length===1?'Post to Teams — '+rows[0].name:'Post to Teams — '+rows.length+' students';
      if(!rows.length){message.textContent='No reviewed student to post. Review and save first.';draw();return;}
      draw();readTeams();
    }catch(e){message.textContent=e.message;}
  }
  window.postToTeams=postToTeams;window.postToAll=()=>postToTeams(null);
  document.querySelector('.teams-post-pilot')?.remove();   // the old one-student card: a row's Post button now does the same on this engine
  const launch=el('button','Post all reviewed feedback to Teams…');launch.type='button';launch.onclick=()=>postToTeams(null);
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;rows=[];draw();message.textContent='Assignment changed. Reopen this dialog.';});
  draw();
})();
