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
  dlg.append(picks,all,start,retry,stop,results,close);document.body.append(dlg);
  let generation=0,busy=false,owner='',currentJob='',choices=[],failed=[],last=null,course='';
  const courseNow=()=>JSON.stringify([$('#course')?.value,$('#quarter')?.value]);
  const same=token=>token===generation&&owner===aid()&&course===courseNow();
  const roster=()=>typeof ROSTER!=='undefined'?ROSTER:[];
  const safeUrl=u=>{try{const v=new URL(u);return v.protocol==='https:'&&!v.username&&!v.password?v.href:'';}catch(e){return '';}};
  function controls(){start.disabled=busy||!choices.some(x=>x.cb.checked);all.disabled=busy;retry.disabled=busy;history.disabled=busy;stop.disabled=!busy;choices.forEach(x=>x.cb.disabled=busy);}
  function evidence(a){return '[Teams attachment: '+a.name+']\nSource: '+a.url+'\n'+a.text;}
  function target(sid){const cards=ws()?.cards().filter(c=>String(ws().payload(c).student_id)===String(sid))||[];return cards.length===1?cards[0]:null;}
  function render(job,token){
    results.replaceChildren();failed=[];
    const data=new Map((job.drafts||[]).map(d=>[String(d.key),d.attachments]));
    for(const item of job.items||[]){
      const id=String(item.key),r=data.get(id),name=choices.find(c=>c.id===id)?.name||id;
      const box=el('section');box.append(el('h4',name));results.append(box);
      if(!r){box.append(el('p',item.state==='failed'?item.error:item.delivered?'Evidence already added to Work.':item.state==='cancelled'?'Not collected: stopped.':item.state==='done'?'No unread result available.':'Waiting for collection…'));if(['failed','cancelled'].includes(item.state))failed.push(id);continue;}
      box.append(el('p','Teams roster: '+r.target_name+' · '+(r.read_at?new Date(r.read_at*1000).toLocaleString():'')),el('p',r.note||''));
      const attachments=r.attachments||[];
      if(attachments.some(a=>['blocked','unreadable'].includes(a.state))||/not present/.test(r.note||''))failed.push(id);
      attachments.forEach(a=>{
        const detail=el('details');detail.append(el('summary',a.name+' — '+({text:'text extracted; review required',screenshot:'screenshot only; manual check required',blocked:'blocked',unreadable:'unreadable'}[a.state]||'needs checking')+(a.reused?' (reused from earlier collection)':'')));
        detail.append(el('p',a.note||''));const url=safeUrl(a.url);
        if(url){const link=el('a','Open source');link.href=url;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);}
        if(a.text){const text=el('pre',a.text);text.style.whiteSpace='pre-wrap';detail.append(text);}
        if(a.screenshot&&/^[A-Za-z0-9+/=]+$/.test(a.screenshot)){const image=el('img');image.src='data:image/jpeg;base64,'+a.screenshot;image.alt='Viewport screenshot of '+a.name;image.style.maxWidth='100%';detail.append(image);}
        box.append(detail);
      });
      const text=attachments.filter(a=>a.state==='text'&&a.text&&safeUrl(a.url));
      if(text.length){
        const label=el('label'),checked=el('input');label.className='attachment-confirm';checked.type='checkbox';label.append(checked,' I checked the student match and extracted text against the sources.');
        const add=el('button','Add extracted text to Work');add.type='button';add.disabled=true;
        const note=el('p');
        checked.onchange=()=>add.disabled=!checked.checked;
        add.onclick=async()=>{
          if(!same(token)){note.textContent='Assignment or course changed. Reopen collection.';return;}
          let saved;try{saved=(await(await fetch('/api/assignments/'+owner)).json()).assignment;}catch(e){note.textContent='Could not verify the saved Teams destination. No evidence added.';return;}
          if(!same(token))return;
          const source=saved?.teams?.source;
          if(!source||source.class_id!==r.source?.class_id||source.assignment_id!==r.source?.assignment_id){note.textContent='The Teams destination changed. Collect again for the saved assignment before adding evidence.';return;}
          const current=roster().filter(s=>String(s.id)===id);
          const expected=current.length===1?(current[0].first+' '+current[0].last).trim():'';
          if(!expected||expected!==r.name){note.textContent='The current class list no longer confirms this student. Reload the correct course.';return;}
          let c=target(id);
          if(!c){const dup=ws().cards().filter(c=>String(ws().payload(c).student_id)===id);if(dup.length){note.textContent='Resolve duplicate student cards first.';return;}
            c=window.addStudent(r.name,'');window.matchCard?.(c);ws()?.refresh?.();
            if(String(c.dataset.rid)!==id){c.remove();note.textContent='Student identity could not be matched. No evidence was added.';return;}}
          const work=c.querySelector('.work'),chunks=text.map(evidence).filter(chunk=>!work.value.includes(chunk));
          if(!same(token))return;
          work.value=[work.value.trim(),...chunks].filter(Boolean).join('\n\n');
          const no=c.querySelector('.nosub');if(no){no.value='';no.dispatchEvent(new Event('input',{bubbles:true}));}
          work.dispatchEvent(new Event('input',{bubbles:true}));add.disabled=true;checked.disabled=true;
          note.textContent=chunks.length?'Text appended to Work. Existing work was preserved; review the assessment again.':'This exact evidence is already in Work; nothing duplicated.';
          if(!await window.feedbackAssignment?.saveForPosting?.()){note.textContent+=' Session save failed; keep this page open and resolve the conflict. Collection results are retained.';return;}
          if(!same(token))return;
          try{await post('/api/jobs/'+job.id+'/delivered',{keys:[id]});}catch(e){note.textContent+=' Could not record delivery; the evidence remains in Work.';}
        };
        box.append(label,add,note);
      }
    }
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
    if(busy||!ids.length)return;const token=++generation;busy=true;controls();message.textContent='Saving the assignment and starting read-only collection…';
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
  history.onchange=()=>{if(busy||!history.value)return;const token=++generation;currentJob=history.value;results.replaceChildren();follow(currentJob,token);};
  launch.onclick=async()=>{
    const token=++generation;owner=aid();course=courseNow();busy=false;last=null;results.replaceChildren();picks.replaceChildren();choices=[];retry.hidden=true;currentJob='';history.replaceChildren();history.hidden=true;dlg.showModal();
    if(!owner){message.textContent='Open a saved assignment first.';controls();return;}
    choices=roster().map(s=>{const name=(s.first+' '+s.last).trim(),label=el('label'),cb=el('input');cb.type='checkbox';label.className='attachment-student';label.append(cb,' '+name);picks.append(label);cb.onchange=controls;return {id:String(s.id),name,cb};});
    message.textContent=choices.length?'Choose one student or select the whole class. This reads attachments without posting or returning work.':'Load the current Course Hub class list first.';controls();
    try{const jobs=(await(await fetch('/api/jobs?assignment='+encodeURIComponent(owner))).json()).jobs||[];if(!same(token))return;const saved=jobs.filter(j=>j.type==='attachment_collect');saved.forEach(j=>{const option=el('option',new Date(j.created).toLocaleString()+' · '+j.total+' students · '+j.state);option.value=j.id;history.append(option);});history.hidden=!saved.length;const job=saved[0];if(job){currentJob=job.id;history.value=job.id;busy=['queued','running'].includes(job.state);controls();follow(job.id,token);}}catch(e){if(same(token))message.textContent+=' Previous results could not be loaded.';}
  };
  for(const selector of ['#asg-pick','#course','#quarter'])$(selector)?.addEventListener('change',()=>{generation++;busy=false;results.replaceChildren();choices=[];picks.replaceChildren();retry.hidden=true;message.textContent='Assignment or course changed. Reopen collection for the current class.';controls();});
})();
