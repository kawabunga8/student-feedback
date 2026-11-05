/* Save to MySchool: one student or the whole class, on one engine (myschool_batch.py).
   Only the assignment's MySchool address is needed (remembered). MySchool is read in ONE Chrome session: the assignment's own
   title and course, the students on it (matched automatically by name), and each student's existing levels and comment. Saving
   needs your one confirmation, re-checks each student's approval at the moment of writing, never retries a Save, verifies by
   reopening MySchool, and stops at the first problem. Publishing is never changed. */
(() => {
  const $ = s => document.querySelector(s), el = (tag, text='') => { const e = document.createElement(tag); e.textContent = text; return e; };
  const aid = () => $('#asg-pick')?.value || '';
  const post = async b => (await fetch('/api/jobs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)})).json();
  const pause = () => new Promise(r => setTimeout(r, 1200));
  const keepGet = k => { try { return localStorage.getItem(k) || ''; } catch(e) { return ''; } };
  const keepSet = (k, v) => { try { localStorage.setItem(k, v); } catch(e) {} };
  const dlg = el('dialog'); dlg.className = 'teams-dialog'; dlg.setAttribute('aria-label', 'MySchool posting');
  const title = el('h3'); dlg.append(title);
  const urlLabel = el('label', 'MySchool assignment address'); urlLabel.style.display = 'block';
  const url = el('input'); url.setAttribute('aria-label', 'MySchool assignment address');
  url.placeholder = 'https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=…'; urlLabel.append(url); dlg.append(urlLabel);
  const gradedLabel = el('label'); gradedLabel.style.display = 'block';
  const graded = el('input'); graded.type = 'checkbox'; graded.checked = true; gradedLabel.append(graded, document.createTextNode(' Set each student’s status to Graded (MySchool does this itself whenever a level is chosen; untick only if a save is refused for another reason)')); dlg.append(gradedLabel);
  const where = el('p'); where.style.fontWeight = '600'; dlg.append(where);              // "From MySchool: course → title (published/unpublished)"
  const message = el('p'); message.setAttribute('role', 'status'); dlg.append(message);
  const excluded = el('p'); excluded.className = 'posting-exclusions'; dlg.append(excluded);
  const table = el('div'); table.className = 'myschool-bulk-rows'; dlg.append(table);
  const confirm = el('input'); confirm.type = 'checkbox'; const confirmText = el('span'); const confirmLabel = el('label'); confirmLabel.append(confirm, confirmText);
  const save = el('button', 'Save to MySchool'); save.type = 'button'; save.disabled = true;
  const stop = el('button', 'Stop'); stop.type = 'button'; stop.disabled = true;
  const again = el('button', 'Read MySchool'); again.type = 'button';
  const close = el('button', 'Close'); close.type = 'button'; close.onclick = () => dlg.close();
  dlg.append(confirmLabel, save, stop, again, close); document.body.append(dlg);
  dlg.addEventListener('cancel', e => { if(busy) e.preventDefault(); });
  let rows = [], generation = 0, busy = false, previewJob = '', curJob = '', header = null;
  const ws = () => window.feedbackWorkspace;
  const urlKey = () => 'myschool-address:' + (aid() || 'none');
  const remembered = () => keepGet(urlKey()) || keepGet('posting-link:myschool:' + (document.getElementById('atitle')?.value.trim() || 'default'));
  const cardOf = id => ws()?.cards().find(c => ws().payload(c).student_id === id);
  const current = id => { const c = cardOf(id); return !!c && ws().valid(c); };
  const alreadySaved = id => { const w = ws(), c = cardOf(id), t = c && (w.posted.get(c) || {}).myschool; return !!t && w.tickMatches(c, 'myschool', t.bound); };
  const ready = () => rows.filter(r => r.state === 'ready');
  function draw() {
    table.replaceChildren();
    rows.forEach(r => {
      const line = el('div'); line.style.margin = '8px 0';
      r.levelsInput.hidden = !r.needsLevels; r.levelsInput.disabled = busy;
      const status = r.state === 'saved' ? '✓ saved and verified in MySchool' : r.state === 'ready' ? 'ready: ' + r.preview.target_name + ' · ' + (r.preview.criteria || []).map(c => (c.existing || 'ungraded') + ' → ' + c.chosen).join(', ')
        : r.state === 'working' ? 'working…' : r.state === 'unattempted' ? 'Not attempted — ' + r.error : r.state === 'uncertain' ? 'Outcome uncertain — check MySchool before trying again. ' + r.error : r.state === 'error' ? 'Preview blocked — ' + r.error : 'waiting';
      line.append(el('strong', r.name + ' — ' + (r.level || 'no level') + '  '), r.levelsInput, el('br'), el('span', status));
      if(r.state === 'ready' && r.preview) {        // the whole change, as the one-student pilot always showed it
        const p = r.preview, det = el('details'); det.append(el('summary', 'Full preview'));
        (p.criteria || []).forEach((c, i) => det.append(el('div', (i + 1) + '. ' + (c.label || '(no label found)') + ': ' + (c.existing || 'ungraded') + ' → ' + c.chosen)));
        det.append(el('div', 'Comment — existing: ' + ((p.existing && p.existing.comment) || '(empty)')), el('div', 'Comment — will save: ' + (p.desired && p.desired.comment)),
          el('div', graded.checked ? 'Status will be set to Graded.' : 'Status will be preserved.'));
        line.append(det);
      }
      table.append(line);
    });
    const n = ready().length;
    confirmText.textContent = ' I checked the assignment, course and ' + (n === 1 ? 'this student' : 'these ' + n + ' students') + ' (levels and exact comments). Save ' + (n === 1 ? 'it' : 'them') + ' to MySchool' + (n > 1 ? ', one after another' : '') + '.';
    confirmLabel.hidden = !n; save.hidden = !n; save.disabled = busy || !n || !confirm.checked; stop.disabled = !busy; again.disabled = busy || !url.value.trim();
    gradedLabel.querySelector('input').disabled = busy; url.disabled = busy;
    where.textContent = header ? 'From MySchool: ' + header.course + ' → ' + header.title + (header.publication && header.publication !== '0' ? ' (published: saved results may be visible to students immediately; publication is not changed)' : ' (unpublished; it will stay unpublished)') + '. Check this is the right assignment.' : '';
  }
  confirm.onchange = draw;
  url.addEventListener('change', () => { if(url.value.trim()) keepSet(urlKey(), url.value.trim()); header = null; previewJob = ''; confirm.checked = false; rows.forEach(r => { if(r.state !== 'saved') { r.state = ''; r.preview = null; } }); draw(); });
  graded.addEventListener('change', () => { if(!busy) { rows.forEach(r => { if(r.state !== 'saved') { r.state = ''; r.preview = null; } }); confirm.checked = false; previewJob = ''; draw(); } });
  async function flush() { if(!await window.feedbackAssignment?.saveForPosting?.()) throw Error('Save the assignment and session, and resolve any conflict first.'); }
  async function follow(jobId, owner, token, onItem) {
    for(let i = 0; i < 900; i++) {
      if(token !== generation || owner !== aid()) throw Error('The assignment changed. Stopped.');
      const j = (await (await fetch('/api/jobs/' + jobId)).json()).job; if(!j) throw Error('Job not found. Check MySchool.');
      const drafts = new Map((j.drafts || []).map(d => [d.key, d.myschool_batch]));
      (j.items || []).forEach(it => onItem(it, drafts.get(it.key)));
      draw();
      if(['queued', 'running'].includes(j.state)) { message.textContent = 'Working in MySchool… Chrome is open for this one session; sign in there if asked.'; await pause(); continue; }
      if(j.state === 'waiting_for_sign_in') throw Error('MySchool needs you to sign in, in the Chrome window. Then try again.');
      return j;
    }
    throw Error('Timed out waiting for MySchool. Check MySchool before retrying.');
  }
  async function readMySchool() {
    if(busy) return; const owner = aid(), token = ++generation; busy = true; confirm.checked = false; previewJob = ''; header = null;
    rows.forEach(r => { if(r.state !== 'saved') { r.state = 'working'; r.error = ''; r.preview = null; } }); draw();
    try {
      await flush();
      const asked = rows.filter(r => r.state !== 'saved'); if(!asked.length) return;
      asked.forEach(r => { r.bound = JSON.stringify(ws().payload(cardOf(r.id))); });
      const d = await post({type:'myschool_batch', op:'inspect', assignment:owner, url:url.value.trim(), mark_graded:graded.checked,
        students: asked.map(r => ({student_id:r.id, ...(r.levelsInput.value.trim() ? {levels:r.levelsInput.value.trim()} : {})}))});
      if(d.error) throw Error(d.error); curJob = d.job.id;
      await follow(d.job.id, owner, token, (it, res) => {
        if(it.key === '@assignment') { if(it.state === 'done' && res) header = res; return; }
        const r = rows.find(x => x.id === it.key); if(!r || r.state === 'saved') return;
        if(it.state === 'done' && res) { r.state = 'ready'; r.preview = res; r.needsLevels = (res.criteria || []).length > 1; }
        else if(it.state === 'failed') { r.state = 'error'; r.error = it.error || 'MySchool did not return a result.'; r.needsLevels = /criteria on the MySchool page|level control/i.test(r.error); }
      });
      previewJob = curJob; keepSet(urlKey(), url.value.trim());
      const bad = rows.filter(r => r.state === 'error').length;
      message.textContent = ready().length + ' ready to save' + (bad ? ' · ' + bad + ' need attention (⚠, not saved)' : '') + '. Nothing was changed in MySchool.';
    } catch(e) { message.textContent = e.message; rows.forEach(r => { if(r.state === 'working') { r.state = 'error'; r.error = e.message; } }); }
    finally { busy = false; draw(); }
  }
  async function saveAll() {
    if(busy || !confirm.checked || !previewJob) return; const owner = aid(), token = ++generation; busy = true; const todo = ready();
    todo.forEach(r => { r.state = 'working'; }); draw();
    const done = []; let problem = '';
    try {
      await flush();
      if(todo.some(r => !current(r.id) || JSON.stringify(ws().payload(cardOf(r.id))) !== r.bound)) throw Error('A student is no longer reviewed. Read MySchool again.');
      const d = await post({type:'myschool_batch', op:'save', assignment:owner, url:url.value.trim(), preview_id:previewJob, confirm:true, students: todo.map(r => ({student_id:r.id}))});
      if(d.error) throw Error(d.error); curJob = d.job.id;
      await follow(d.job.id, owner, token, (it, res) => {
        const r = todo.find(x => x.id === it.key); if(!r || r.state === 'saved') return;
        if(it.state === 'done' && res && res.verified) { r.state = 'saved'; done.push(r.name); ws()?.markPosted?.(r.id, 'myschool', r.bound); }
        else if(it.state === 'failed') { r.error = it.error || 'No verified result.'; r.state = /^Not attempted/.test(r.error) ? 'unattempted' : 'uncertain'; if(!problem && !/Not attempted/.test(r.error)) problem = r.name + ': ' + r.error; }
      });
    } catch(e) { problem = problem || e.message; todo.forEach(r => { if(r.state === 'working') { r.state = 'uncertain'; r.error = e.message; } }); }
    finally { todo.forEach(r => { if(r.state === 'working') { r.state = 'uncertain'; r.error = 'The job ended without a verified result.'; } }); busy = false; confirm.checked = false; previewJob = ''; draw(); }
    const uncertain = todo.filter(r => r.state === 'uncertain').map(r => r.name), unattempted = todo.filter(r => r.state === 'unattempted').map(r => r.name);
    message.textContent = 'Verified saves: ' + done.length + '. ' + (problem ? 'Stopped — ' + problem + ' ' : '') +
      (uncertain.length ? 'Outcome uncertain: ' + uncertain.join(', ') + '. Check the saved levels and comment in MySchool before making a new preview. ' : '') +
      (unattempted.length ? 'Not attempted: ' + unattempted.join(', ') + '. These need a fresh preview before saving. ' : '') +
      (!uncertain.length && !unattempted.length ? 'All selected saves were verified.' : 'No automatic retries.');
    draw();
  }
  again.onclick = readMySchool; save.onclick = saveAll;
  stop.onclick = async () => { if(curJob) { try { await fetch('/api/jobs/' + curJob + '/cancel', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}); } catch(e) {} } message.textContent = 'Stopping after the current student…'; };
  // ids: the students to save (one or several); null = every reviewed student not already saved. Reads MySchool by itself when the address is known.
  async function postToMySchool(ids) {
    const owner = aid(); generation++; busy = false; rows = []; previewJob = ''; header = null; draw();
    excluded.textContent = ''; dlg.showModal(); title.textContent = 'Save to MySchool'; message.textContent = 'Loading reviewed students…';
    if(!url.value.trim()) url.value = remembered();
    if(!owner) { message.textContent = 'Open a saved assignment first.'; return; }
    try {
      await flush(); const d = await (await fetch('/api/myschool/approved?assignment=' + encodeURIComponent(owner))).json(); if(d.error) throw Error(d.error);
      const list = (d.students || []).filter(s => ids ? ids.includes(s.student_id) : !alreadySaved(s.student_id));
      const eligible = new Set((d.students || []).map(s => s.student_id));
      const omitted = ws().cards().map(c => ws().payload(c)).filter(p => !ids || ids.includes(p.student_id)).filter(p => !eligible.has(p.student_id) || (!ids && alreadySaved(p.student_id))).map(p => p.name + ': ' + (!eligible.has(p.student_id) ? 'not eligible — check student match, saved review, level and comment' : 'a current MySchool save is already recorded'));
      excluded.textContent = omitted.length ? 'Excluded from this preview: ' + omitted.join('; ') + '.' : 'All eligible students in this selection are included.';
      rows = list.map(s => { const levelsInput = el('input'); levelsInput.hidden = true; levelsInput.setAttribute('aria-label', 'MySchool levels for ' + s.name);
        levelsInput.placeholder = 'One level per criterion, in order (e.g. PRF, EXT+)'; levelsInput.onchange = () => { const r = rows.find(x => x.levelsInput === levelsInput); if(r && r.state !== 'saved') { r.state = ''; r.error = ''; confirm.checked = false; draw(); } };
        return {id:s.student_id, name:s.name, level:s.level, levelsInput, state:'', error:'', preview:null, needsLevels:false, bound:''}; });
      title.textContent = rows.length === 1 ? 'Save to MySchool — ' + rows[0].name : 'Save to MySchool — ' + rows.length + ' students';
      if(!rows.length) { message.textContent = 'No reviewed student to save. Review and save first.'; draw(); return; }
      draw();
      if(url.value.trim()) readMySchool(); else message.textContent = 'Paste the MySchool assignment’s Assessment address, then click Read MySchool. It is remembered for this assignment.';
    } catch(e) { message.textContent = e.message; }
  }
  window.postToMySchool = postToMySchool; window.postToAllMySchool = () => postToMySchool(null); window.postOneMySchool = () => postToMySchool(null);
  $('#asg-pick')?.addEventListener('change', () => { generation++; busy = false; rows = []; header = null; draw(); message.textContent = 'Assignment changed. Reopen this dialog.'; });
  draw();
})();
