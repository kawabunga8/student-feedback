/* Collect student work (prototype, version 1): read ONE typed OneNote page, read-only, and offer it as a student card.
   The page text is student work. It is shown here, put in a card only when you click "Add as a student card", and is
   kept (as a job result) in this assignment's own Assessment folder. Nothing here writes into OneNote. */
(() => {
  const $ = s => document.querySelector(s);
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text !== undefined && text !== '') e.textContent = text; return e; };
  const host = $('.onenote-card');
  if(!host) return;
  const asgId = () => { const v = ($('#asg-pick') || {}).value || ''; return /^asg-\d{8}-[0-9a-f]{8}$/.test(v) ? v : ''; };
  const postJSON = (path, body) => fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})}).then(r => r.json());
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const when = iso => { try { return new Date(iso).toLocaleString(); } catch(e) { return iso || ''; } };

  const open = make('button', '', 'Collect from OneNote…');
  open.id = 'collect-open'; open.type = 'button';
  open.title = 'Read one typed OneNote page (read-only) and add it as a student card.';
  host.append(open);

  const dlg = make('dialog', 'teams-dialog collect-dialog'); dlg.setAttribute('aria-label', 'Collect from OneNote');
  dlg.append(make('h3', '', 'Collect from OneNote'));
  dlg.append(make('p', 'status', 'Version 1 reads one typed page at a time. Open the student’s page in OneNote, copy its address from the browser, and paste it here. The app only opens and scrolls the page: it never types, clicks buttons or changes anything.'));
  const urlIn = make('input', 'collect-url'); urlIn.placeholder = 'Page address (https://….sharepoint.com/…/Doc.aspx?…)'; urlIn.setAttribute('aria-label', 'OneNote page address');
  const bar = make('div', 'teams-actions');
  const readBtn = make('button', 'primary collect-read', 'Read this page'); readBtn.type = 'button';
  const msg = make('div', 'status collect-msg'); msg.setAttribute('role', 'status');
  const act = make('div', 'teams-actions collect-actions');
  bar.append(readBtn, msg);
  const prev = make('div', 'collect-preview'); prev.hidden = true;
  const foot = make('div', 'teams-actions');
  const close = make('button', 'collect-close', 'Close'); close.type = 'button'; close.onclick = () => dlg.close();
  foot.append(close);
  dlg.append(urlIn, bar, act, prev, foot);
  document.body.append(dlg);

  let generation = 0;
  let busy = false, current = null;          // current: {jobId, res}
  const stop = () => { busy = false; readBtn.disabled = false; };

  function row(label, value) {
    const r = make('div', 'teams-row'); r.append(make('div', 'teams-label', label));
    const v = make('div', 'teams-val'); if(value instanceof Node) v.append(value); else v.textContent = value; r.append(v); return r;
  }
  function showResult(jobId, res, assignment) {
    if(asgId() !== assignment) return;
    current = {jobId, res, assignment}; prev.replaceChildren(); prev.hidden = false;
    const src = res.source || {}, pg = res.page || {};
    const name = make('input', 'collect-name'); name.value = src.student_hint || ''; name.placeholder = 'Student name (not found in the address: type it)';
    name.setAttribute('aria-label', 'Student name for the card');
    prev.append(row('Student', name));
    prev.append(row('Page', [src.section, src.page].filter(Boolean).join(' › ') || '(title not in the address)'));
    prev.append(row('Read', `${(pg.chars || 0).toLocaleString()} characters of typed text, read ${when(res.read_at)}.`));
    const note = row('Completeness', 'UNVERIFIED. ' + (res.completeness_note || '')); prev.append(note);
    const counts = res.non_text_counts || {};
    const kinds = Object.keys(counts);
    prev.append(row('Not read', kinds.length ? kinds.map(k => `${counts[k]} ${k}`).join(', ') + ' (not read: check these on the page)' : 'No pictures, drawings or files were listed. Handwriting may still be missing: compare with the page.'));
    const full = make('div', 'teams-full'); full.textContent = pg.text || ''; full.style.display = 'none'; full.style.whiteSpace = 'pre-wrap';
    const tog = make('button', 'linkish collect-toggle', 'Show full text'); tog.type = 'button';
    tog.onclick = () => { const shut = full.style.display === 'none'; full.style.display = shut ? 'block' : 'none'; tog.textContent = shut ? 'Hide full text' : 'Show full text'; };
    const wrap = make('div'); wrap.append(tog, full);
    prev.append(row('Text', wrap));
    const add = make('button', 'primary collect-add', 'Add as a student card'); add.type = 'button';
    add.onclick = async () => {
      if(asgId() !== assignment) { resetPreview(); return; }
      const token = generation;
      const nm = name.value.trim();
      if(!nm) { msg.textContent = 'Type the student’s name first.'; name.focus(); return; }
      const cards = [...document.querySelectorAll('.student')];
      let c = cards.find(x => x.querySelector('.name').value.trim().toLowerCase() === nm.toLowerCase() && !x.querySelector('.work').value.trim());
      let how = 'Filled the empty card for ' + nm + '.';
      if(!c) { c = window.addStudent(nm, pg.text || ''); how = 'Added a new card for ' + nm + '.'; }
      else { c.querySelector('.work').value = pg.text || ''; }
      c.querySelector('.work').dispatchEvent(new Event('input', {bubbles: true}));
      try { await postJSON('/api/jobs/' + jobId + '/delivered', {keys: ['collect']}); } catch(e) { /* the card is made either way */ }
      if(token !== generation || asgId() !== assignment) return;
      prev.hidden = true; current = null; act.replaceChildren();
      msg.textContent = how + ' Read it against the page before you rely on it, then save the session.';
    };
    act.replaceChildren(add);
  }

  async function follow(id, assignment = asgId()) {
    const token = ++generation;
    busy = true; readBtn.disabled = true; act.replaceChildren();
    for(;;) {
      if(token !== generation || asgId() !== assignment) return;
      let j; try { j = (await (await fetch('/api/jobs/' + id)).json()).job; } catch(e) { await sleep(2000); continue; }
      if(token !== generation || asgId() !== assignment) return;
      if(!j) { msg.textContent = 'The app lost track of that job.'; return stop(); }
      if(j.state === 'queued' || j.state === 'running') { msg.textContent = 'Reading the page… a Chrome window opens for this. If it asks you to sign in, do that there.'; await sleep(1500); continue; }
      if(['waiting_for_sign_in', 'failed', 'interrupted'].includes(j.state)) {
        msg.textContent = (j.state === 'waiting_for_sign_in' ? 'Waiting for you to sign in. ' : j.state === 'failed' ? 'Couldn’t read the page: ' : 'Interrupted. ') + (j.error || '');
        const again = make('button', '', j.state === 'waiting_for_sign_in' ? 'I’ve signed in: resume' : 'Try again'); again.type = 'button';
        again.onclick = async () => { const r = await postJSON('/api/jobs/' + id + '/resume', {}); if(r.error) { msg.textContent = r.error; return; } follow(id, assignment); };
        const cancel = make('button', '', 'Cancel'); cancel.type = 'button';
        cancel.onclick = async () => { await postJSON('/api/jobs/' + id + '/cancel', {}); act.replaceChildren(); msg.textContent = 'Cancelled.'; };
        act.append(again, cancel); return stop();
      }
      if(j.state === 'cancelled') { msg.textContent = 'Cancelled.'; return stop(); }
      stop();
      const bad = (j.items || []).find(i => i.state === 'failed');
      if(bad) { msg.textContent = 'The page wasn’t what the reader expected, so nothing was collected: ' + bad.error; return; }
      const res = ((j.drafts || [])[0] || {}).collect;
      if(!res) { msg.textContent = 'The reader gave no result.'; return; }
      msg.textContent = 'Read the page.'; return showResult(id, res, assignment);
    }
  }

  readBtn.onclick = async () => {
    if(busy) return;
    const aid = asgId();
    if(!aid) { msg.textContent = 'Open or save an assignment first: collected work is kept with the assignment.'; return; }
    if(!urlIn.value.trim()) { msg.textContent = 'Paste the page address first.'; urlIn.focus(); return; }
    const token = ++generation;
    msg.textContent = 'Starting…'; prev.hidden = true; busy = true; readBtn.disabled = true;
    let d; try { d = await postJSON('/api/jobs', {type: 'onenote_read', assignment: aid, url: urlIn.value.trim()}); } catch(e) { d = {error: 'Couldn’t reach the app.'}; }
    if(token !== generation || asgId() !== aid) return;
    if(d.error) { msg.textContent = d.error; return stop(); }
    urlIn.value = '';                          // the address isn't kept in the dialog once the job has it
    follow(d.job.id, aid);
  };

  function resetPreview() {
    generation++; current = null; stop();
    prev.replaceChildren(); prev.hidden = true; act.replaceChildren();
    urlIn.value = ''; msg.textContent = '';
  }
  const pick = $('#asg-pick'); if(pick) pick.addEventListener('change', resetPreview);

  open.onclick = async () => {
    dlg.showModal();
    const aid = asgId(); if(!aid || busy) return;
    try {                                       // pick up a read that finished (or is still running) while this was closed
      const list = (await (await fetch('/api/jobs?assignment=' + aid)).json()).jobs || [];
      const j = list.find(x => x.type === 'onenote_read' && (['queued', 'running', 'waiting_for_sign_in'].includes(x.state) || (x.items || []).some(i => i.state === 'done' && !i.delivered)));
      if(asgId() === aid && j && !current) follow(j.id, aid);
    } catch(e) { /* nothing to pick up */ }
  };
  window.feedbackCollect = {open: () => open.click()};
})();
