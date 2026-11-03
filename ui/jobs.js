/* Background drafting: queue the drafts as a job the local worker runs, watch progress, and bring finished drafts
   into the cards. The worker keeps going if this page is closed; reopen the assignment to collect what it wrote. */
(() => {
  const $ = s => document.querySelector(s);
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text) e.textContent = text; return e; };
  const sha = async text => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(b => b.toString(16).padStart(2, '0')).join('');
  const go = $('#go'), toolbar = $('.review-toolbar'), students = $('#students');
  if(!go || !toolbar || !students || !window.crypto || !crypto.subtle) return;
  const ws = () => window.feedbackWorkspace;
  const asgId = () => { const v = ($('#asg-pick') || {}).value || ''; return /^asg-\d{8}-[0-9a-f]{8}$/.test(v) ? v : ''; };
  const post = (path, body) => fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})}).then(r => r.json());

  const btn = make('button', 'primary', 'Draft in the background');
  btn.title = 'The app writes the drafts one after another and keeps going if you close this page.';
  go.after(btn);
  const redo = make('label', 'bg-redo'); const redoBox = make('input'); redoBox.type = 'checkbox'; redo.append(redoBox, ' Redraft students who already have feedback');
  btn.after(redo);
  const useBox = make('input'); useBox.type = 'checkbox'; useBox.id = 'use-rubric';
  const useLabel = make('label', 'bg-redo'); useLabel.append(useBox, ' Use the Teams rubric as assessment criteria');
  const useHint = make('span', 'hint-inline');
  redo.after(useLabel, useHint);
  // The checkbox is only available when this assignment has a rubric that was read from Teams. The drafts then name each criterion,
  // describe evidence and give a next step; they never name or imply a level (that stays with you).
  const fa = () => window.feedbackAssignment;
  const syncUse = () => {
    const r = fa() && fa().rubric();
    useBox.disabled = !r;
    useBox.checked = !!(r && fa().useRubric());        // the saved record decides, so switching assignments switches this too
    useHint.textContent = r ? ' (' + r.criteria.map(c => c.name).join(', ') + '. Save the assignment so the app uses the saved rubric.)' : ' (no rubric has been read from Teams for this assignment)';
  };
  useBox.onchange = () => { if(fa()) fa().setUseRubric(useBox.checked); syncUse(); if(ws()) ws().refresh(); };
  syncUse(); setInterval(syncUse, 1500);
  const pickEl = $('#asg-pick'); if(pickEl) pickEl.addEventListener('change', () => setTimeout(syncUse, 400));
  const panel = make('div', 'card jobs-panel'); panel.hidden = true; students.before(panel);
  const note = make('div', 'bg-note'); note.setAttribute('role', 'status'); panel.before(note);
  const say = t => { note.textContent = t || ''; };

  const key = async c => c.dataset.rid || ('name-' + (await sha(c.querySelector('.name').value.trim().toLowerCase())).slice(0, 24));
  const cardsByKey = async () => { const m = new Map(); for(const c of document.querySelectorAll('.student')) m.set(await key(c), c); return m; };

  function insertDraft(c, text, basis) {
    const res = c.querySelector('.result');
    res.innerHTML = '';
    const out = make('div', 'out'); out.contentEditable = 'true'; out.textContent = text.replace(/\*\*/g, '');
    const copy = make('button', '', 'Copy'); copy.style.marginTop = '8px';
    copy.onclick = () => { navigator.clipboard.writeText(out.innerText); copy.textContent = 'Copied'; setTimeout(() => copy.textContent = 'Copy', 1500); };
    res.append(out, copy);
    if(ws() && ws().draftBasis) ws().draftBasis.set(out, basis || ws().basisNow());
  }

  window.insertDraft = insertDraft;                    // the Assessment-folder loader puts saved drafts on cards with this

  async function queue() {
    const aid = asgId();
    if(!aid) { say('Save the assignment first (Save in the assignment bar) so the app can keep the job with it.'); return; }
    const rubric = $('#rubric').value.trim(), stds = [...document.querySelectorAll('.std:checked')].map(c => c.value);
    if(!rubric && !stds.length) { say('Add an assignment description or tick a learning standard.'); return; }
    const items = []; let skipped = 0;
    for(const c of document.querySelectorAll('.student')) {
      const work = c.querySelector('.work').value;
      if(!work.trim()) continue;
      if(!redoBox.checked && c.querySelector('.out:not(.err)')) { skipped++; continue; }
      if($('#skipret') && $('#skipret').checked && c.dataset.tstatus === 'Returned') { skipped++; continue; }
      const name = c.querySelector('.name').value.trim();
      items.push({key: await key(c), work, notes: c.querySelector('.notes').value, level: c.querySelector('.level').value,
                  grade: c.querySelector('.sgrade').value || $('#grade').value, label: name || 'Student'});
    }
    if(!items.length) { say(skipped ? 'Everyone with work already has feedback (tick "Redraft" to write them again).' : 'Paste some student work first.'); return; }
    btn.disabled = true;
    const r = await post('/api/jobs', {assignment: aid, basis: ws() ? ws().basisNow() : '', overwrite: redoBox.checked,
      settings: {use_rubric: useBox.checked, model: $('#model').value, rubric, doc: $('#doc').value, standards: stds, grade: $('#grade').value,
                 term: $('#quarter').value ? (window.SCHOOL_YEAR || '') + ' ' + $('#quarter').value : '', length: $('#length').value, title: $('#atitle').value},
      items}).catch(e => ({error: e.message}));
    btn.disabled = false;
    if(r.error) { say(r.error); return; }
    say(`Queued ${items.length} draft${items.length === 1 ? '' : 's'}${skipped ? ` (${skipped} skipped)` : ''}. You can keep working or close this page.`);
    poll();
  }
  btn.onclick = () => queue();

  const STATE = {queued: 'Waiting to start', running: 'Writing…', completed: 'Finished', failed: 'Stopped', cancelled: 'Cancelled',
                 interrupted: 'Interrupted (the app was closed)', waiting_for_sign_in: 'Waiting for sign-in', needs_teacher_input: 'Needs you'};
  function render(jobs) {
    panel.replaceChildren();
    const shown = jobs.filter(j => j.type === 'draft' && (['queued', 'running', 'interrupted', 'failed'].includes(j.state) || (j.drafts || []).length));
    panel.hidden = !shown.length;
    shown.forEach(j => {
      const row = make('div', 'job-row'), c = j.counts || {};
      row.append(make('strong', '', 'Background drafting: ' + (STATE[j.state] || j.state)));
      row.append(make('span', 'job-count', ` ${c.done || 0} of ${j.total} drafted` + (c.failed ? `, ${c.failed} failed` : '')));
      const bar = make('progress'); bar.max = j.total; bar.value = c.done || 0; row.append(bar);
      if(j.error) row.append(make('div', 'job-error', j.error));
      const failed = (j.items || []).filter(i => i.state === 'failed');
      if(failed.length) row.append(make('div', 'job-error', failed.length + ' student(s) failed; open them and use Generate feedback to retry.'));
      const acts = make('div', 'job-actions');
      if(['queued', 'running'].includes(j.state)) { const b = make('button', '', 'Cancel'); b.onclick = () => post('/api/jobs/' + j.id + '/cancel').then(poll); acts.append(b); }
      if(['interrupted', 'failed'].includes(j.state)) {
        const b = make('button', 'primary', 'Resume'); b.onclick = () => post('/api/jobs/' + j.id + '/resume').then(poll);
        const x = make('button', '', 'Cancel'); x.onclick = () => post('/api/jobs/' + j.id + '/cancel').then(poll); acts.append(b, x);
      }
      row.append(acts); panel.append(row);
    });
  }

  let busy = false, timer = null;
  async function deliver(j) {
    const m = await cardsByKey(), done = [], notes = {put: 0, kept: 0, changed: 0, missing: 0};
    for(const d of j.drafts || []) {
      const c = m.get(d.key);
      if(!c) { notes.missing++; continue; }                           // that student isn't on this page; draft stays on offer
      if(await sha(c.querySelector('.work').value) !== d.work_sha) { notes.changed++; done.push(d.key); continue; }
      if(!j.overwrite && c.querySelector('.out:not(.err)')) { notes.kept++; done.push(d.key); continue; }
      insertDraft(c, d.feedback, j.basis); notes.put++; done.push(d.key);
    }
    if(done.length) await post('/api/jobs/' + j.id + '/delivered', {keys: done});
    if(notes.put || notes.kept || notes.changed) {
      say(`Added ${notes.put} draft${notes.put === 1 ? '' : 's'} from the background job.` + (notes.changed ? ` ${notes.changed} not added because the student's work changed afterwards.` : '') + (notes.kept ? ` ${notes.kept} not added because feedback already existed.` : '') + ' Review each one before approving.');
      $('#dl').disabled = false; $('#dlteams').disabled = false;
      if(ws()) ws().refresh();
    }
  }
  async function poll() {
    if(busy) return; busy = true; clearTimeout(timer);
    let active = false;
    try {
      const aid = asgId();
      if(aid) {
        const list = (await (await fetch('/api/jobs?assignment=' + aid)).json()).jobs || [];
        for(const j of list) {
          if(j.type !== 'draft') continue;
          const full = (j.items || []).some(i => i.state === 'done' && !i.delivered) ? (await (await fetch('/api/jobs/' + j.id)).json()).job : j;
          if(full && (full.drafts || []).length) { await deliver(full); }
        }
        render((await (await fetch('/api/jobs?assignment=' + aid)).json()).jobs || []);
        active = list.some(j => ['queued', 'running'].includes(j.state));
      } else render([]);
    } catch(e) { /* the app is restarting; try again */ }
    busy = false; timer = setTimeout(poll, active ? 2000 : 6000);
  }
  document.addEventListener('visibilitychange', () => { if(document.visibilityState === 'visible') poll(); });
  setTimeout(poll, 1500);
  window.feedbackJobs = {poll};
})();
