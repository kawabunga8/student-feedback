/* Teams attachment collection: explicit student selection, read-only jobs, reviewed import into Work. */
(() => {
  const $=s=>document.querySelector(s),el=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
  const host=$('#step-collect');if(!host)return;
  const ws=()=>window.feedbackWorkspace,aid=()=>$('#asg-pick')?.value||'';
  const post=(path,body)=>fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
  const card=el('div');card.className='card attachment-collection';card.append(el('h3','Teams attachments'),el('p','Collect attachments for selected students in one browser session. Word text can be extracted; other supported views get a screenshot for manual checking. A missing attachment is not proof of no submission.'));
  const launch=el('button','Collect Teams attachments…');launch.type='button';card.append(launch);host.append(card);
  const dlg=el('dialog');dlg.className='teams-dialog attachment-dialog';dlg.setAttribute('aria-label','Collect Teams attachments');dlg.append(el('h3','Collect Teams attachments'));
  const message=el('p');message.setAttribute('role','status');dlg.append(message);
  const history=el('select');history.setAttribute('aria-label','Saved attachment collections');history.hidden=true;dlg.append(history);
  const picks=el('div'),results=el('div');results.className='attachment-results';
  const all=el('button','Select all students'),start=el('button','Collect selected students'),retry=el('button','Retry incomplete students'),stop=el('button','Stop after current student'),close=el('button','Close');
  [all,start,retry,stop,close].forEach(b=>b.type='button');retry.hidden=true;stop.disabled=true;
  const bulk=el('button','Add reviewed selections to Work');bulk.type='button';bulk.className='primary attachment-bulk-import';bulk.hidden=true;
  dlg.append(picks,all,start,retry,stop,bulk,results,close);document.body.append(dlg);
  let generation=0,busy=false,importing=false,importEntries=[],owner='',currentJob='',choices=[],failed=[],last=null,course='';
  const courseNow=()=>JSON.stringify([$('#course')?.value,$('#quarter')?.value]);
  const same=token=>token===generation&&owner===aid()&&course===courseNow();
  const roster=()=>typeof ROSTER!=='undefined'?ROSTER:[];
  const safeUrl=u=>{try{const v=new URL(u);return v.protocol==='https:'&&!v.username&&!v.password?v.href:'';}catch(e){return '';}};
  function controls(){
    const locked=busy||importing;
    start.disabled=locked||!choices.some(x=>x.cb.checked);all.disabled=locked;retry.disabled=locked;history.disabled=locked;stop.disabled=!busy;choices.forEach(x=>x.cb.disabled=locked);
    const selected=importEntries.filter(e=>e.checked.checked&&!e.text.every(a=>a.imported_at));
    bulk.hidden=!importEntries.length;bulk.textContent='Add reviewed selections to Work'+(selected.length?' ('+selected.length+' students)':'');bulk.disabled=locked||!selected.length;
    importEntries.forEach(e=>{e.checked.disabled=locked||e.text.every(a=>a.imported_at);e.add.disabled=locked||!e.checked.checked||e.checked.disabled;});
  }
  function evidence(a){return '[Teams attachment: '+a.name+']\nSource: '+a.url+'\n'+a.text;}
  async function importReviewed(entries,job,token){
    const chosen=entries.filter(e=>e.checked.checked&&!e.checked.disabled);
    if(importing||busy||!chosen.length||!same(token))return;
    importing=true;controls();
    try{
      const saved=(await(await fetch('/api/assignments/'+owner)).json()).assignment;
      if(!same(token))return;
      const source=saved?.teams?.source;
      const planned=[];
      for(const e of chosen){
        if(!source||source.class_id!==e.r.source?.class_id||source.assignment_id!==e.r.source?.assignment_id)throw Error('The Teams destination changed. Collect again for the saved assignment before adding evidence.');
        const current=roster().filter(s=>String(s.id)===e.id);
        if(current.length!==1||(current[0].first+' '+current[0].last).trim()!==e.r.name)throw Error('The current class list no longer confirms '+e.r.name+'. Reload the correct course.');
        const cards=ws().cards().filter(c=>String(ws().payload(c).student_id)===e.id);
        if(cards.length>1)throw Error('Resolve duplicate student cards for '+e.r.name+' first.');
        if(!cards.length&&typeof window.findStudent==='function'&&String(window.findStudent(e.r.name).s?.id)!==e.id)throw Error('Student identity could not be matched for '+e.r.name+'. No evidence was added.');
        planned.push({e,c:cards[0]});
      }
      const created=[];
      try{
        for(const plan of planned)if(!plan.c){plan.c=window.addStudent(plan.e.r.name,'');created.push(plan.c);window.matchCard?.(plan.c);ws()?.refresh?.();if(String(plan.c.dataset.rid)!==plan.e.id)throw Error('Student identity could not be matched. No evidence was added.');}
      }catch(error){created.forEach(c=>c.remove());throw error;}
      for(const {e,c} of planned){
        const work=c.querySelector('.work'),chunks=e.text.map(evidence).filter(chunk=>!work.value.includes(chunk));
        work.value=[work.value.trim(),...chunks].filter(Boolean).join('\n\n');
        const no=c.querySelector('.nosub');if(no){no.value='';no.dispatchEvent(new Event('input',{bubbles:true}));}
        work.dispatchEvent(new Event('input',{bubbles:true}));
        e.note.textContent=chunks.length?'Text appended to Work. Existing work was preserved; review the assessment again.':'This exact evidence is already in Work; nothing duplicated.';
      }
      if(!await window.feedbackAssignment?.saveForPosting?.())throw Error('Session save failed; keep this page open and resolve the conflict. Collection results are retained.');
      if(!same(token))return;
      for(const e of chosen){
        const d=await post('/api/jobs/'+job.id+'/attachment-imported',{key:e.id,indexes:e.attachments.map((a,i)=>e.text.includes(a)?i:-1).filter(i=>i>=0)});
        if(!same(token))return;if(d.error)throw Error(d.error);
        e.text.forEach(a=>a.imported_at=new Date().toISOString());e.checked.disabled=true;
      }
      message.textContent='Saved reviewed evidence for '+chosen.length+' student'+(chosen.length===1?'':'s')+'. Existing work was preserved. Review the assessments again before posting.';
    }catch(error){if(same(token)){message.textContent=error.message;chosen.forEach(e=>e.note.textContent=error.message);}}
    finally{if(same(token)){importing=false;controls();}}
  }
  function render(job,token){
    results.replaceChildren();failed=[];importEntries=[];
    const data=new Map((job.drafts||[]).map(d=>[String(d.key),d.attachments]));
    for(const item of job.items||[]){
      const id=String(item.key),r=data.get(id),name=choices.find(c=>c.id===id)?.name||id;
      const box=el('section');box.append(el('h4',name));results.append(box);
      if(!r){box.append(el('p',item.state==='failed'?item.error:item.delivered?'Evidence already added to Work.':item.state==='cancelled'?'Not collected: stopped.':item.state==='done'?'No unread result available.':'Waiting for collection…'));if(['failed','cancelled'].includes(item.state))failed.push(id);continue;}
      box.append(el('p','Teams roster: '+r.target_name+' · '+(r.read_at?new Date(r.read_at*1000).toLocaleString():'')),el('p',r.note||''));
      const attachments=r.attachments||[];
      if(attachments.some(a=>['blocked','unreadable'].includes(a.state))||/not present/.test(r.note||''))failed.push(id);
      attachments.forEach(a=>{
        const detail=el('details');detail.append(el('summary',a.name+' — '+({text:'text extracted; review required',screenshot:'screenshot only; manual check required',blocked:'blocked',unreadable:'unreadable'}[a.state]||'needs checking')+(a.imported_at?' (text already imported)':'')+(a.reused?' (reused from earlier collection)':'')));
        detail.append(el('p',a.note||''));const url=safeUrl(a.url);
        if(url){const link=el('a','Open source');link.href=url;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);}
        if(a.text){const text=el('pre',a.text);text.style.whiteSpace='pre-wrap';detail.append(text);}
        if(a.screenshot&&/^[A-Za-z0-9+/=]+$/.test(a.screenshot)){const image=el('img');image.src='data:image/jpeg;base64,'+a.screenshot;image.alt='Viewport screenshot of '+a.name;image.style.maxWidth='100%';detail.append(image);}
        box.append(detail);
      });
      const text=attachments.filter(a=>a.state==='text'&&!a.imported_at&&a.text&&safeUrl(a.url));
      if(text.length){
        const label=el('label'),checked=el('input');label.className='attachment-confirm';checked.type='checkbox';label.append(checked,' I checked the student match and extracted text against the sources.');
        const add=el('button','Add extracted text to Work');add.type='button';add.disabled=true;
        const note=el('p');
        const entry={id,r,attachments,text,checked,add,note};importEntries.push(entry);
        checked.onchange=controls;
        add.onclick=()=>importReviewed([entry],job,token);
        box.append(label,add,note);
      }
    }
    bulk.onclick=()=>importReviewed(importEntries,job,token);
    retry.hidden=!failed.length;controls();
  }
  async function follow(id,token){
    for(let n=0;n<1200&&same(token);n++){
      let job;try{job=(await(await fetch('/api/jobs/'+id)).json()).job;}catch(e){message.textContent='Connection lost. Reopen collection to recover saved results; no evidence was added automatically.';break;}
      if(!same(token))return;
      if(!job){message.textContent='Collection job was not found.';break;}
      last=job;
      // Avoid rebuilding checkboxes/previews while a read is active; saved results appear when it stops.
      if(['queued','running'].includes(job.state)){message.textContent='Collecting attachments… '+(job.counts?.done||0)+' students finished. Sign in in Chrome if prompted.';await new Promise(r=>setTimeout(r,1200));continue;}
      busy=false;render(job,token);
      message.textContent=job.state==='waiting_for_sign_in'?'Microsoft sign-in is needed in Chrome. Sign in, then use Resume collection.':job.error||'Collection finished. Expand each source, check the student and text, then add evidence to Work. Screenshots and unreadable sources require manual checking.';
      if(['waiting_for_sign_in','interrupted','failed'].includes(job.state)){
        const resume=el('button','Resume collection');resume.type='button';resume.onclick=async()=>{if(!same(token)||busy)return;const d=await post('/api/jobs/'+id+'/resume',{});if(d.error){message.textContent=d.error;return;}busy=true;controls();follow(id,token);};results.prepend(resume);
      }
      controls();return;
    }
    if(same(token)){busy=false;controls();}
  }
  async function collect(ids,reuse=''){
    if(busy||importing||!ids.length)return;const token=++generation;busy=true;controls();message.textContent='Saving the assignment and starting read-only collection…';
    try{
      if(!await window.feedbackAssignment?.saveForPosting?.())throw Error('Save the assignment and resolve any conflict first.');
      if(!same(token))return;
      const d=await post('/api/jobs',{type:'attachment_collect',assignment:owner,students:ids.map(id=>({student_id:id})),reuse_job:reuse});
      if(!same(token))return;if(d.error)throw Error(d.error);currentJob=d.job.id;if(![...history.options].some(o=>o.value===currentJob)){const option=el('option','New collection');option.value=currentJob;history.prepend(option);history.hidden=false;}history.value=currentJob;follow(currentJob,token);
    }catch(e){if(same(token)){message.textContent=e.message;busy=false;controls();}}
  }
  start.onclick=()=>collect(choices.filter(c=>c.cb.checked).map(c=>c.id));
  all.onclick=()=>{choices.forEach(c=>c.cb.checked=true);controls();};
  retry.onclick=()=>collect([...new Set(failed)],currentJob);
  stop.onclick=async()=>{if(currentJob&&busy){const d=await post('/api/jobs/'+currentJob+'/cancel',{});message.textContent=d.error||'Stopping collection; finished results will remain available.';}};
  close.onclick=()=>dlg.close();
  history.onchange=()=>{if(busy||importing||!history.value)return;const token=++generation;currentJob=history.value;results.replaceChildren();follow(currentJob,token);};
  launch.onclick=async()=>{
    const token=++generation;owner=aid();course=courseNow();busy=false;importing=false;importEntries=[];last=null;results.replaceChildren();picks.replaceChildren();choices=[];retry.hidden=true;currentJob='';history.replaceChildren();history.hidden=true;dlg.showModal();
    if(!owner){message.textContent='Open a saved assignment first.';controls();return;}
    choices=roster().map(s=>{const name=(s.first+' '+s.last).trim(),label=el('label'),cb=el('input');cb.type='checkbox';label.className='attachment-student';label.append(cb,' '+name);picks.append(label);cb.onchange=controls;return {id:String(s.id),name,cb};});
    message.textContent=choices.length?'Choose one student or select the whole class. This reads attachments without posting or returning work.':'Load the current Course Hub class list first.';controls();
    try{const jobs=(await(await fetch('/api/jobs?assignment='+encodeURIComponent(owner))).json()).jobs||[];if(!same(token))return;const saved=jobs.filter(j=>j.type==='attachment_collect');saved.forEach(j=>{const option=el('option',new Date(j.created).toLocaleString()+' · '+j.total+' students · '+j.state);option.value=j.id;history.append(option);});history.hidden=!saved.length;const job=saved[0];if(job){currentJob=job.id;history.value=job.id;busy=['queued','running'].includes(job.state);controls();follow(job.id,token);}}catch(e){if(same(token))message.textContent+=' Previous results could not be loaded.';}
  };
  for(const selector of ['#asg-pick','#course','#quarter'])$(selector)?.addEventListener('change',()=>{generation++;busy=false;importing=false;importEntries=[];results.replaceChildren();choices=[];picks.replaceChildren();retry.hidden=true;message.textContent='Assignment or course changed. Reopen collection for the current class.';controls();});
})();
