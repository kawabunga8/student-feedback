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
  const title=field('Exact MySchool assignment title',el('input'));
  const course=field('Exact MySchool course name',el('input'));course.placeholder='e.g. D Concert Band 12';
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
  const localCurrent = id => { const ws=window.feedbackWorkspace;return !!ws && ws.cards().some(c=>ws.payload(c).student_id===id && ws.valid(c)); };
  function invalidate() {preview=null;previewBox.replaceChildren();confirm.checked=false;save.disabled=true;}
  form.addEventListener('input',invalidate);form.addEventListener('change',invalidate);
  student.addEventListener('change',()=>{name.value='';});
  confirm.onchange=()=>{save.disabled=busy||!preview||!confirm.checked||!localCurrent(preview.student_id);};
  async function flush() {
    if(!window.feedbackAssignment?.saveForPosting || !await window.feedbackAssignment.saveForPosting()) throw Error('Save the assignment and session first. Resolve any save conflict before posting.');
  }
  async function load() {
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
    const owner=aid(),token=++generation;busy=true;inspect.disabled=true;save.disabled=true;
    try {
      await flush();if(!localCurrent(student.value))throw Error('This student is no longer reviewed. Review and save again.');
      if(owner!==aid()||token!==generation)return;
      const body=op==='inspect'?{type:'myschool',op,assignment:owner,student_id:student.value,url:url.value.trim(),title:title.value.trim(),course:course.value.trim(),target_name:name.value.trim(),codes:codes.value.trim(),mark_graded:graded.checked}
        :{type:'myschool',op,assignment:owner,preview_id:preview.jobId,confirm:confirm.checked};
      const d=await post(body);if(d.error)throw Error(d.error);
      const out=await follow(d.job,owner,token);if(!out||owner!==aid()||token!==generation)return;
      if(op==='inspect') {
        preview={...out,jobId:d.job.id};previewBox.replaceChildren();
        previewBox.append(el('h4','Review the exact change'),el('p',out.course+' → '+out.title+' → '+out.target_name),el('p',(out.criteria||[]).length>1?'Levels to save, by criterion (check each against MySchool):':'Level to save:'),...(out.criteria||[]).map((c,i)=>el('p',(i+1)+'. '+(c.label||'(no label found)')+': '+(c.existing||'ungraded')+' → '+c.chosen)),el('p','Approved comment: '+out.comment),el('p','Existing comment: '+(out.existing.comment||'(empty)')),el('p',out.mark_graded?'Status will be set to Graded.':'Status will be preserved.'),el('p',out.publication==='0'?'Assignment is unpublished. It will stay unpublished.':'Assignment is published: saved values may be visible immediately under its existing settings. Publication will not be changed.'));
        message.textContent='Preview only: nothing changed in MySchool. This preview expires after 10 minutes.';
      } else {
        invalidate();message.textContent=out.verified?'Verified by reopening MySchool: the approved level and comment match. Publication setting preserved. Record the MySchool completion tick after checking.':'Save outcome is uncertain. Check MySchool before trying again.';
      }
    } catch(e) {if(owner===aid()&&token===generation)message.textContent=e.message;}
    finally {if(owner===aid()&&token===generation){busy=false;inspect.disabled=false;save.disabled=!preview||!confirm.checked||!localCurrent(preview.student_id);}}
  }
  inspect.onclick=()=>{invalidate();run('inspect');};save.onclick=()=>{if(preview&&confirm.checked)run('save');};refresh.onclick=load;
  launch.onclick=()=>{dlg.showModal();load();};
  $('#asg-pick')?.addEventListener('change',()=>{generation++;busy=false;inspect.disabled=false;invalidate();message.textContent='Assignment changed. Reopen the pilot to load its reviewed students.';student.replaceChildren();});
})();
