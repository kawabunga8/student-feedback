/* One unpublished MySchool assignment; explicit preview then Save. No grades or publishing. */
(() => {
  const $=s=>document.querySelector(s), el=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n;};
  const aid=()=>$('#asg-pick')?.value||'';
  const post=async b=>(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  const get=async url=>(await fetch(url)).json();
  const launch=el('button','Create assignment in MySchool');launch.type='button';$('.preview-student .design-actions').append(launch);
  const dlg=el('dialog');dlg.className='teams-dialog';dlg.setAttribute('aria-label','Create MySchool assignment');
  dlg.append(el('h3','Create an unpublished MySchool assignment'));
  const text=el('pre');text.className='teams-text-full';dlg.append(text);
  const form=el('div');dlg.append(form);
  function field(label,node){const l=el('label',label);node.setAttribute('aria-label',label);l.append(node);form.append(l);return node;}
  const list=el('button','Load MySchool courses');list.type='button';form.append(list);
  const course=field('MySchool course',el('select'));course.add(new Option('Load courses first…',''));
  const kind=field('Assignment type',el('select'));kind.add(new Option('Choose Formative or Summative…',''));['Formative','Summative'].forEach(x=>kind.add(new Option(x,x)));
  const due=field('MySchool due date',el('input'));due.type='date';
  const inspect=el('button','Read MySchool form and preview');inspect.type='button';form.append(inspect);
  const verify=el('button','Verify previous Save without saving again');verify.type='button';form.append(verify);
  const choices=el('fieldset');choices.append(el('legend','Learning outcomes — select what this assignment assesses'));dlg.append(choices);
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const confirm=el('input');confirm.type='checkbox';const label=el('label','I checked the course, type, due date, instructions and outcomes. Save with Publish: No and email off.');label.prepend(confirm);dlg.append(label);
  const save=el('button','Save unpublished assignment to MySchool');save.type='button';save.disabled=true;dlg.append(save);
  const close=el('button','Close');close.type='button';close.onclick=()=>dlg.close();dlg.append(close);document.body.append(dlg);
  let record=null, preview=null, generation=0, busy=false, lastSaveId='';
  function invalidate(){preview=null;confirm.checked=false;save.disabled=true;choices.querySelectorAll('label').forEach(n=>n.remove());}
  form.oninput=invalidate;form.onchange=invalidate;
  const selected=()=>[...choices.querySelectorAll('input:checked')].map(n=>n.value);
  const enable=()=>{save.disabled=busy||!preview||!confirm.checked||!selected().length;};confirm.onchange=enable;
  choices.onchange=()=>{confirm.checked=false;enable();};
  async function follow(job,owner,token){
    for(;;){const j=(await get('/api/jobs/'+job.id)).job;if(!j)throw Error('Job unavailable. Check MySchool before retrying.');
      if(owner!==aid()||token!==generation)return null;
      if(['queued','running'].includes(j.state)){message.textContent='Chrome is checking MySchool. Sign in there if asked.';await new Promise(r=>setTimeout(r,1200));continue;}
      const fail=j.items?.find(i=>i.state==='failed');if(j.state!=='completed'||fail)throw Error(fail?.error||j.error||'MySchool job stopped.');
      const out=j.drafts?.find(d=>d.myschool_create)?.myschool_create;if(!out)throw Error('No verified result. Check MySchool.');return out;
    }
  }
  async function run(op){
    if(busy||!record)return;const owner=record.id,token=++generation;busy=true;form.querySelectorAll('input,select,button').forEach(n=>n.disabled=true);choices.disabled=true;confirm.disabled=true;save.disabled=true;
    try{
      const b={type:'myschool_create',op,assignment:owner,version:record.version};
      if(op==='verify'){if(!lastSaveId)throw Error('No previous Save attempt.');b.previous_id=lastSaveId;}
      if(op==='inspect')Object.assign(b,{course:course.value,kind:kind.value,due:due.value});
      if(op==='save')Object.assign(b,{preview_id:preview.jobId,outcomes:selected(),confirm:confirm.checked});
      const d=await post(b);if(d.error)throw Error(d.error);if(op==='save')lastSaveId=d.job.id;const out=await follow(d.job,owner,token);if(!out)return;
      if(op==='list'){course.replaceChildren(new Option('Choose the exact MySchool course…',''));out.courses.forEach(c=>course.add(new Option(c,c)));message.textContent='Choose the course, assignment type and due date, then read the form.';}
      if(op==='inspect'){preview={...out,jobId:d.job.id};out.available_outcomes.forEach(name=>{const l=el('label',name),c=el('input');c.type='checkbox';c.value=name;l.prepend(c);choices.append(l);});message.textContent='Preview: '+course.value+' · '+kind.value+' · due '+due.value+'. Scale: '+out.scale+'; weight: '+out.weight+'; submissions: '+out.submissions+'. Choose learning outcomes. Nothing saved. Publish will be No, scheduled publication blank, email off. No attachments or grades are added.';}
      if(op==='save'||op==='verify'){invalidate();message.textContent='Verified unpublished in MySchool: '+out.title+' · '+out.course+' · due '+out.due+'. Title, instructions, outcomes and settings match. Email off. '+out.url;}
    }catch(e){if(owner===aid()&&token===generation){invalidate();message.textContent=e.message;}}
    finally{if(owner===aid()&&token===generation){busy=false;form.querySelectorAll('input,select,button').forEach(n=>n.disabled=false);choices.disabled=false;confirm.disabled=false;enable();}}
  }
  launch.onclick=async()=>{
    if(busy)return;invalidate();generation++;
    try{record=await window.feedbackAssignment.prepareDesign();text.textContent=record.title+'\n\n'+record.instructions;message.textContent='Load courses from MySchool, then choose the destination. This creates one unpublished assignment; it does not post student assessments.';dlg.showModal();
      const previous=(await get('/api/jobs?assignment='+encodeURIComponent(record.id))).jobs||[];
      lastSaveId=previous.find(j=>j.type==='myschool_create_save')?.id||'';
      for(const j of previous.filter(j=>['myschool_create_save','myschool_create_verify'].includes(j.type)&&j.state==='completed')){const full=(await get('/api/jobs/'+j.id)).job;const receipt=full?.drafts?.find(d=>d.myschool_create?.verified)?.myschool_create;if(receipt){message.textContent='Previously verified unpublished assignment: '+receipt.course+' → '+receipt.title+'. Local edits are not sent again. '+receipt.url;break;}}
    }catch(e){alert(e.message);}
  };
  verify.onclick=()=>run('verify');
  list.onclick=()=>{invalidate();run('list');};inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked&&selected().length)run('save');};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;record=null;invalidate();dlg.close();});
})();
