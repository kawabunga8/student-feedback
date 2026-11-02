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
  const name=field('Exact student name in the Teams roster',el('input'));name.placeholder='Last, First — check against Teams';
  const inspect=el('button','Read Teams destination and preview');inspect.type='button';form.append(inspect);
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
  student.onchange=()=>{name.value='';};confirm.onchange=()=>{save.disabled=busy||!preview||!confirm.checked||!current(preview.student_id);};
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
      (d.students||[]).forEach(s=>student.add(new Option(s.name,s.student_id)));message.textContent='Choose one reviewed student and confirm their exact Teams roster name.';
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
    }catch(e){if(owner===aid()&&token===generation){invalidate();message.textContent=e.message;}}
    finally{if(owner===aid()&&token===generation){busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;save.disabled=!preview||!confirm.checked||!current(preview.student_id);}}
  }
  inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked)run('save');};launch.onclick=()=>{dlg.showModal();load();};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;student.disabled=false;name.disabled=false;inspect.disabled=false;invalidate();student.replaceChildren();message.textContent='Assignment changed. Reopen this pilot.';});
})();
