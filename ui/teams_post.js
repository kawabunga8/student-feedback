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
      }else{invalidate();message.textContent=out.verified?'Verified: feedback matches and the student appears in Returned. Check Teams, then record the Teams completion tick.':'Outcome uncertain. Check Teams before retrying.';}
    }catch(e){if(owner===aid()&&token===generation){invalidate();message.textContent=e.message;
      if(/student was not found|roster name/i.test(e.message)){nameRow.style.display='';nameNote.textContent='Couldn’t find “'+name.value+'” in Teams. Type the name exactly as the Teams roster shows it (usually Last, First), then preview again.';}}}
    finally{if(owner===aid()&&token===generation){busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;save.disabled=!preview||!confirm.checked||!current(preview.student_id);}}
  }
  inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked)run('save');};launch.onclick=()=>{dlg.showModal();load();};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;invalidate();student.replaceChildren();message.textContent='Assignment changed. Reopen this pilot.';});
})();

/* Every reviewed student in one run. No new posting path: it drives the one-student pilot above (same /api/jobs preview and
   Post, same approval, preview-claim and read-back checks) one student at a time. Read Teams for everyone first (nothing is
   changed), confirm once, then post and Return in order; the first problem stops the run. Return may notify each student. */
(() => {
  const $=s=>document.querySelector(s), el=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
  const aid=()=>$('#asg-pick')?.value||'';
  const post=async b=>(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  const pause=()=>new Promise(r=>setTimeout(r,1200));
  const FRESH_MS=8*60*1000;                          // the server refuses previews older than 10 minutes
  const card=el('div');card.className='card teams-bulk';
  card.append(el('h3','Teams — all reviewed students'),el('p','Reads Teams for every saved, reviewed student first (nothing is changed), then, after you confirm once, posts each one’s feedback and Returns it, one at a time. It stops at the first problem and tells you who was done. Each student gets the same checks as the one-student pilot. Return may notify students. Live posting has not yet been verified: try one student in the pilot above first.'));
  const launch=el('button','Post all reviewed feedback to Teams…');launch.type='button';card.append(launch);$('#step-delivery').append(card);
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','Teams bulk posting');dlg.append(el('h3','Teams — all reviewed students'));
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const table=el('div');table.className='teams-bulk-rows';dlg.append(table);
  const refresh=el('button','Reload reviewed students');refresh.type='button';dlg.append(refresh);
  const previewAll=el('button','Read Teams for all');previewAll.type='button';previewAll.disabled=true;dlg.append(previewAll);
  const confirm=el('input');confirm.type='checkbox';const confirmText=el('span');const confirmLabel=el('label');confirmLabel.append(confirm,confirmText);dlg.append(confirmLabel);
  const save=el('button','Post feedback and Return for all previewed students');save.type='button';save.disabled=true;dlg.append(save);
  const stop=el('button','Stop after current student');stop.type='button';stop.disabled=true;dlg.append(stop);
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();dlg.append(close);document.body.append(dlg);
  let rows=[],generation=0,busy=false,halt=false;
  const current=sid=>window.feedbackWorkspace?.cards().some(c=>window.feedbackWorkspace.payload(c).student_id===sid&&window.feedbackWorkspace.valid(c));
  const defaultName=sid=>{const r=(typeof ROSTER!=='undefined'?ROSTER:[]).find(x=>x.id===sid);return r?r.last+', '+r.first:'';};
  const ready=()=>rows.filter(r=>r.state==='previewed'&&r.preview);
  function draw(){
    table.replaceChildren();
    rows.forEach(r=>{
      const line=el('div');line.style.margin='6px 0';
      r.nameInput.disabled=busy||r.state==='posted';
      const status=el('span',r.state==='posted'?'✓ posted and Returned (verified)':r.state==='previewed'?'ready: Teams found “'+r.preview.target_name+'”'+(r.preview.existing?' · existing feedback will be replaced':''):r.error?'⚠ '+r.error:r.state==='working'?'working…':'not read yet');
      line.append(el('strong',r.name+'  '),r.nameInput,el('br'),status);table.append(line);
    });
    const n=ready().length;
    confirmText.textContent=' I checked the '+n+' previews (class, assignment, each student and exact feedback). Post and Return these '+n+' students, one after another; they may be notified.';
    previewAll.disabled=busy||!rows.length;save.disabled=busy||!n||!confirm.checked;stop.disabled=!busy;
  }
  confirm.onchange=draw;
  async function flush(){if(!await window.feedbackAssignment?.saveForPosting?.())throw Error('Save the assignment and session, and resolve any conflict first.');}
  async function follow(job,owner,token){
    for(let i=0;i<300;i++){
      if(token!==generation||owner!==aid())throw Error('The assignment changed. Stopped.');
      const j=(await(await fetch('/api/jobs/'+job.id)).json()).job;if(!j)throw Error('Job not found. Check Teams.');
      if(['queued','running','waiting_for_sign_in'].includes(j.state)){message.textContent='Chrome is working in Teams. Sign in there if asked. Keep this dialog open.';await pause();continue;}
      const fail=j.items?.find(x=>x.state==='failed');if(j.state!=='completed'||fail)throw Error(fail?.error||j.error||'The job stopped. Check Teams.');
      const out=j.drafts?.find(d=>d.teams_post)?.teams_post;if(!out)throw Error('No verified result. Check Teams before retrying.');return out;
    }
    throw Error('Timed out waiting for Teams. Check Teams before retrying.');
  }
  const inspectBody=(owner,r)=>({type:'teams_post',op:'inspect',assignment:owner,student_id:r.id,target_name:r.nameInput.value.trim()});
  async function load(){
    const owner=aid(),token=++generation;rows=[];draw();
    if(!owner){message.textContent='Open a saved assignment first.';return;}
    try{await flush();const d=await(await fetch('/api/teams-post/approved?assignment='+encodeURIComponent(owner))).json();if(d.error)throw Error(d.error);
      if(owner!==aid()||token!==generation)return;
      rows=(d.students||[]).map(s=>{const nameInput=el('input');nameInput.value=defaultName(s.student_id);nameInput.placeholder='Last, First — as the Teams roster shows it';nameInput.setAttribute('aria-label','Teams roster name for '+s.name);
        nameInput.onchange=()=>{const r=rows.find(x=>x.nameInput===nameInput);if(r&&r.state!=='posted'){r.state='';r.preview=null;r.error='';confirm.checked=false;draw();}};
        return {id:s.student_id,name:s.name,nameInput,state:'',preview:null,error:''};});
      message.textContent=rows.length?rows.length+' reviewed students. Names are filled from Course Hub; correct one only if Teams spells it differently.':'No current saved approvals. Review each student first.';
      draw();
    }catch(e){if(owner===aid()&&token===generation)message.textContent=e.message;}
  }
  async function readAll(){
    if(busy)return;const owner=aid(),token=++generation;busy=true;halt=false;confirm.checked=false;draw();
    try{await flush();
      for(const r of rows){
        if(halt||owner!==aid()||token!==generation)break;if(r.state==='posted')continue;
        if(!r.nameInput.value.trim()){r.error='Type the name exactly as Teams shows it.';draw();continue;}
        r.state='working';r.error='';r.preview=null;draw();
        try{if(!current(r.id))throw Error('No longer reviewed. Review and save again.');
          const d=await post(inspectBody(owner,r));if(d.error)throw Error(d.error);
          r.preview={...await follow(d.job,owner,token),jobId:d.job.id,at:Date.now()};r.state='previewed';
        }catch(e){r.state='';r.error=e.message;}
        draw();
      }
      message.textContent=ready().length+' of '+rows.length+' read (nothing changed in Teams). Students with a ⚠ will not be posted. Previews expire after 10 minutes.';
    }catch(e){message.textContent=e.message;}
    finally{busy=false;draw();}
  }
  async function postAll(){
    if(busy||!confirm.checked)return;const owner=aid(),token=++generation;busy=true;halt=false;const todo=ready();draw();
    const done=[];let problem='';
    try{await flush();
      for(const r of todo){
        if(halt){problem='Stopped by you.';break;}
        if(owner!==aid()||token!==generation){problem='The assignment changed.';break;}
        r.state='working';draw();
        try{if(!current(r.id))throw Error('No longer reviewed.');
          let p=r.preview;
          if(Date.now()-p.at>FRESH_MS){          // too old for the server: read Teams again and require the same values
            const d=await post(inspectBody(owner,r));if(d.error)throw Error(d.error);
            const again={...await follow(d.job,owner,token),jobId:d.job.id,at:Date.now()};
            if(again.feedback!==p.feedback||again.existing!==p.existing||again.target_name!==p.target_name||again.title!==p.title||again.class!==p.class)throw Error('Teams or the approved feedback changed since you confirmed. Not posted.');
            p=r.preview=again;
          }
          const d=await post({type:'teams_post',op:'save',assignment:owner,preview_id:p.jobId,confirm:true});if(d.error)throw Error(d.error);
          const out=await follow(d.job,owner,token);
          if(!out.verified)throw Error('The outcome is uncertain. Check Teams before trying again.');
          r.state='posted';done.push(r.name);
        }catch(e){r.state='';r.preview=null;r.error=e.message;problem=r.name+': '+e.message;draw();break;}   // a Return may have run: read Teams again
        draw();
      }
    }catch(e){problem=e.message;}
    finally{busy=false;confirm.checked=false;draw();}
    const left=todo.filter(r=>r.state!=='posted').map(r=>r.name);
    message.textContent=(done.length?'Posted and Returned (verified): '+done.join(', ')+'. ':'Nothing was posted. ')+(problem?'Stopped — '+problem+' ':'')+(left.length?'Not posted: '+left.join(', ')+'. Check Teams for any student that shows a problem, then read Teams again.':'All done. Record each student’s Teams completion tick after checking.');
  }
  refresh.onclick=load;previewAll.onclick=readAll;save.onclick=postAll;stop.onclick=()=>{halt=true;message.textContent='Stopping after the current student…';};
  launch.onclick=()=>{dlg.showModal();load();};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;halt=true;rows=[];draw();message.textContent='Assignment changed. Reopen this dialog.';});
  draw();
})();
