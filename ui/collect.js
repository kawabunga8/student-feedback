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
  dlg.append(make('p', 'status', 'Reads typed OneNote pages, read-only. Open each student’s page in OneNote, copy its address from the browser, and paste it here: one address per line, up to 40 pages for a class. The app only opens and scrolls the page: it never types, clicks buttons or changes anything.'));
  const urlIn = make('textarea', 'collect-url'); urlIn.rows = 3; urlIn.placeholder = 'Page address (https://….sharepoint.com/…/Doc.aspx?…), one per line'; urlIn.setAttribute('aria-label', 'OneNote page address');
  const bar = make('div', 'teams-actions');
  const readBtn = make('button', 'primary collect-read', 'Read page(s)'); readBtn.type = 'button';
  const msg = make('div', 'status collect-msg'); msg.setAttribute('role', 'status');
  const act = make('div', 'teams-actions collect-actions');
  bar.append(readBtn, msg);
  const prev = make('div', 'collect-preview'); prev.hidden = true;
  const foot = make('div', 'teams-actions');
  const close = make('button', 'collect-close', 'Close'); close.type = 'button'; close.onclick = () => dlg.close();
  foot.append(close);
  // ---- whole class: tries likely page titles for every student of the loaded class (read-only, one Chrome session)
  const clsBox = make('div', 'collect-class');
  clsBox.append(make('p', 'status', 'Or collect the whole class: paste any one address from the class notebook and the app opens each student\u2019s page of this assignment by its likely title. Students whose page isn\u2019t found are listed, not guessed. This takes a few minutes (about 6 s per title tried).'));
  const nbIn = make('input', 'collect-notebook'); nbIn.placeholder = 'Any page address from the class notebook (https://\u2026.sharepoint.com/\u2026/Doc.aspx?sourcedoc=\u2026)'; nbIn.setAttribute('aria-label', 'Class notebook address');
  try { nbIn.value = localStorage.getItem('collect-notebook') || ''; } catch(e) { /* not remembered */ }
  const ttIn = make('textarea', 'collect-titles'); ttIn.rows = 3; ttIn.placeholder = 'Page titles to try, one per line (leave empty: made from the assignment title, e.g. \u201cStage 3 - Prototype & Test\u201d)'; ttIn.setAttribute('aria-label', 'Page titles to try');
  const clsBtn = make('button', 'primary collect-class-read', 'Collect whole class'); clsBtn.type = 'button';
  clsBox.append(nbIn, ttIn, clsBtn);
  dlg.append(urlIn, bar, clsBox, act, prev, foot);
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
      if(typeof applyTeams === 'function' && typeof TEAMS !== 'undefined' && TEAMS) applyTeams();
      try { await postJSON('/api/jobs/' + jobId + '/delivered', {keys: ['collect']}); } catch(e) { /* the card is made either way */ }
      if(token !== generation || asgId() !== assignment) return;
      prev.hidden = true; current = null; act.replaceChildren();
      msg.textContent = how + ' Read it against the page before you rely on it, then save the session.';
    };
    act.replaceChildren(add);
  }


  // ---- several pages: one row per page read, matched to the class list, added only when you tick and confirm
  const rosterLoaded = () => typeof ROSTER !== 'undefined' && ROSTER.length > 0 && typeof window.findStudent === 'function';
  function matchNote(name) {
    if(!rosterLoaded()) return {ok: false, text: 'Load the Course Hub class list before adding these pages.'};
    if(!name.trim()) return {ok: false, text: 'Type the student\u2019s name.'};
    const r = window.findStudent(name.trim());
    if(r.status === 'match') return {ok: true, text: '\u2713 Matches the class list: ' + r.s.last + ', ' + r.s.first};
    return {ok: false, text: r.status === 'ambiguous' ? '? Could be: ' + (r.options || []).join(' or ') + '. Type the full name.' : '? Not on this class list: check the name.'};
  }
  async function showBatch(id, j, assignment) {
    if(asgId() !== assignment) return;
    const got = (j.drafts || []).filter(d => d.collect), failed = (j.items || []).filter(i => i.state === 'failed');
    const pageNo = key => (/^p(\d+)$/.exec(key) || [])[1] || key;
    current = {jobId: id, batch: true, assignment}; prev.replaceChildren(); prev.hidden = false; act.replaceChildren();
    const doneBefore = (j.items || []).filter(i => i.state === 'done' && i.delivered).length;
    prev.append(make('p', 'status', `${got.length} page${got.length === 1 ? '' : 's'} read and waiting` + (doneBefore ? `, ${doneBefore} already added` : '') + (failed.length ? `, ${failed.length} ${failed.every(f => /^s\d+$/.test(f.key)) ? 'with no matching page (not submitted, or titled differently)' : 'could not be read'}` : '') + '. Tick the pages to add; each name must match the class list.'));
    failed.forEach(f => prev.append(make('p', 'status collect-failed', /^s\d+$/.test(f.key) ? f.error : 'Page ' + pageNo(f.key) + ' was not collected: ' + f.error)));
    const rows = got.map(d => {
      const res = d.collect, src = res.source || {}, pg = res.page || {};
      const r = make('div', 'teams-row collect-row');
      const cb = make('input'); cb.type = 'checkbox'; cb.setAttribute('aria-label', 'Add page ' + pageNo(d.key));
      const name = make('input', 'collect-bname'); name.value = src.student_hint || ''; name.setAttribute('aria-label', 'Student name for page ' + pageNo(d.key));
      const note = make('div', 'teams-now'); const meta = make('div', 'teams-now');
      const counts = res.non_text_counts || {}, kinds = Object.keys(counts);
      meta.textContent = `${/^s\d+$/.test(d.key) ? 'OneNote page \u201c' + (res.title || src.page || 'untitled') + '\u201d' : 'Page ' + pageNo(d.key)}: ${(pg.chars || 0).toLocaleString()} characters. UNVERIFIED completeness.` + (kinds.length ? ' Not read: ' + kinds.map(k => counts[k] + ' ' + k).join(', ') + '.' : ' Handwriting may be missing.');
      const full = make('div', 'teams-full'); full.textContent = pg.text || ''; full.style.display = 'none'; full.style.whiteSpace = 'pre-wrap';
      const tog = make('button', 'linkish', 'Show text'); tog.type = 'button';
      tog.onclick = () => { const shut = full.style.display === 'none'; full.style.display = shut ? 'block' : 'none'; tog.textContent = shut ? 'Hide text' : 'Show text'; };
      const upd = () => { const m = matchNote(name.value); note.textContent = m.text; note.className = 'teams-now' + (m.ok ? '' : ' warn'); return m; };
      cb.checked = upd().ok; name.addEventListener('input', () => { cb.checked = upd().ok && cb.checked; upd(); });
      const mid = make('div'); mid.append(name, note, meta, tog, full);
      r.append(cb, mid); prev.append(r);
      return {d, cb, name, pg};
    });
    if(!rows.length) { msg.textContent = failed.length ? 'No page could be read. Nothing was collected.' : 'Nothing left to add.'; return; }
    const add = make('button', 'primary collect-add', 'Add ticked pages as student cards'); add.type = 'button';
    add.onclick = async () => {
      if(asgId() !== assignment) { resetPreview(); return; }
      const chosen = rows.filter(x => x.cb.checked);
      if(!chosen.length) { msg.textContent = 'Tick at least one page.'; return; }
      const names = chosen.map(x => x.name.value.trim().toLowerCase());
      if(names.some(n => !n)) { msg.textContent = 'Every ticked page needs a student name.'; return; }
      if(new Set(names).size !== names.length) { msg.textContent = 'Two ticked pages have the same student name. Fix one before adding.'; return; }
      if(chosen.some(x => !matchNote(x.name.value).ok)) { msg.textContent = 'Every ticked page must match the current Course Hub class list. Check the names before adding.'; return; }
      const matches = chosen.map(x => window.findStudent(x.name.value.trim()).s);
      const ids = matches.map(s => s.id || (s.last + ', ' + s.first).toLowerCase());
      if(new Set(ids).size !== ids.length) { msg.textContent = 'Two ticked pages match the same student. Add one page for that student at a time.'; return; }
      const token = generation, done = [];
      for(const x of chosen) {
        const nm = x.name.value.trim();
        let c = [...document.querySelectorAll('.student')].find(k => k.querySelector('.name').value.trim().toLowerCase() === nm.toLowerCase() && !k.querySelector('.work').value.trim());
        if(!c) c = window.addStudent(nm, x.pg.text || ''); else c.querySelector('.work').value = x.pg.text || '';
        c.querySelector('.work').dispatchEvent(new Event('input', {bubbles: true}));
        if(typeof applyTeams === 'function' && typeof TEAMS !== 'undefined' && TEAMS) applyTeams();
        if(rosterLoaded() && typeof window.matchCard === 'function') window.matchCard(c);
        done.push(x.d.key);
      }
      try { await postJSON('/api/jobs/' + id + '/delivered', {keys: done}); } catch(e) { /* the cards are made either way */ }
      msg.textContent = `Added ${done.length} card${done.length === 1 ? '' : 's'}. Read each against its page before you rely on it, then save the session.`;
      if(token !== generation || asgId() !== assignment) return;
      try { const fresh = (await (await fetch('/api/jobs/' + id)).json()).job; if(fresh) return showBatch(id, fresh, assignment); } catch(e) { /* leave it */ }
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
      if((j.items || []).length > 1) return showBatch(id, j, assignment);
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
    const lines = [...new Set(urlIn.value.split(/\n+/).map(x => x.trim()).filter(Boolean))];
    if(!lines.length) { msg.textContent = 'Paste the page address first.'; urlIn.focus(); return; }
    if(lines.length > 40) { msg.textContent = 'At most 40 pages at a time.'; return; }
    const token = ++generation;
    msg.textContent = 'Starting…'; prev.hidden = true; busy = true; readBtn.disabled = true;
    let d; try { d = await postJSON('/api/jobs', {type: 'onenote_read', assignment: aid, ...(lines.length > 1 ? {urls: lines} : {url: lines[0]})}); } catch(e) { d = {error: 'Couldn’t reach the app.'}; }
    if(token !== generation || asgId() !== aid) return;
    if(d.error) { msg.textContent = d.error; return stop(); }
    urlIn.value = '';                          // the address isn't kept in the dialog once the job has it
    follow(d.job.id, aid);
  };

  clsBtn.onclick = async () => {
    if(busy) return;
    const aid = asgId();
    if(!aid) { msg.textContent = 'Open or save an assignment first: collected work is kept with the assignment.'; return; }
    if(!rosterLoaded()) { msg.textContent = 'Load the Course Hub class list first: it gives the student names.'; return; }
    const base = nbIn.value.trim();
    if(!base) { msg.textContent = 'Paste an address from the class notebook first.'; nbIn.focus(); return; }
    const students = ROSTER.map(r => ({name: (r.first + ' ' + r.last).trim()})).filter(x => x.name);
    const titles = ttIn.value.split(/\n+/).map(x => x.trim()).filter(Boolean);
    try { localStorage.setItem('collect-notebook', base); } catch(e) { /* not remembered */ }
    const token = ++generation;
    msg.textContent = 'Starting\u2026'; prev.hidden = true; busy = true; readBtn.disabled = true; clsBtn.disabled = true;
    const asg = ($('#asg-pick').selectedOptions[0] || {}).textContent || '';
    let d; try { d = await postJSON('/api/jobs', {type: 'onenote_class', assignment: aid, base, titles, students, assignment_title: (typeof window.assignmentTitle === 'function' ? window.assignmentTitle() : asg)}); } catch(e) { d = {error: 'Couldn\u2019t reach the app.'}; }
    clsBtn.disabled = false;
    if(token !== generation || asgId() !== aid) return;
    if(d.error) { msg.textContent = d.error; return stop(); }
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
      const j = list.find(x => ['onenote_read', 'onenote_class'].includes(x.type) && (['queued', 'running', 'waiting_for_sign_in'].includes(x.state) || (x.items || []).some(i => i.state === 'done' && !i.delivered)));
      if(asgId() === aid && j && !current) follow(j.id, aid);
    } catch(e) { /* nothing to pick up */ }
  };

  // ---- per-student Teams statuses (read-only): fills the same per-card "Teams: …" line a status export does
  const stBtn = make('button', '', 'Read Teams statuses'); stBtn.type = 'button'; stBtn.id = 'teams-status-read';
  stBtn.title = 'Read each student\u2019s turned-in / viewed status for this assignment from Teams (read-only).';
  const stMsg = make('div', 'status teams-status-msg'); stMsg.setAttribute('role', 'status');
  host.append(stBtn, stMsg);
  let stGen = 0;
  async function followStatuses(id, aid, token) {
    for(;;) {
      if(token !== stGen || asgId() !== aid) return;
      let j; try { j = (await (await fetch('/api/jobs/' + id)).json()).job; } catch(e) { await sleep(2000); continue; }
      if(token !== stGen || asgId() !== aid) return;
      if(!j) { stMsg.textContent = 'The app lost track of that job.'; return; }
      if(['queued', 'running'].includes(j.state)) { stMsg.textContent = 'Reading Teams\u2026 a Chrome window opens for this. If it asks you to sign in, do that there.'; await sleep(1500); continue; }
      if(['waiting_for_sign_in', 'failed', 'interrupted'].includes(j.state)) {
        stMsg.textContent = (j.state === 'waiting_for_sign_in' ? 'Waiting for you to sign in. ' : 'Couldn\u2019t read Teams: ') + (j.error || '') + ' Click \u201cRead Teams statuses\u201d to try again.';
        if(j.state !== 'waiting_for_sign_in') await postJSON('/api/jobs/' + id + '/cancel', {});
        return;
      }
      const bad = (j.items || []).find(i => i.state === 'failed');
      if(bad) { stMsg.textContent = bad.error; return; }
      const res = ((j.drafts || [])[0] || {}).teams_students;
      if(!res) { stMsg.textContent = 'Teams gave no statuses.'; return; }
      TEAMS = {assignment_id: aid, title: res.title, assignment: res.title, due: res.due || '', students: res.students};
      if(typeof applyTeams === 'function') applyTeams();
      await postJSON('/api/jobs/' + id + '/delivered', {keys: ['students']});
      if(token !== stGen || asgId() !== aid) return;
      const counts = {}; res.students.forEach(s => counts[s.status] = (counts[s.status] || 0) + 1);
      stMsg.textContent = `Read ${res.students.length} students' statuses at ${when(res.read_at)}: ` + Object.entries(counts).map(([k, v]) => v + ' ' + k.toLowerCase()).join(', ') + '. Shown on each student card; nothing was changed in Teams.';
      return;
    }
  }
  stBtn.onclick = async () => {
    const aid = asgId();
    if(!aid) { stMsg.textContent = 'Open or save an assignment first.'; return; }
    const token = ++stGen; stMsg.textContent = 'Starting\u2026';
    let rec; try { rec = (await (await fetch('/api/assignments/' + aid)).json()).assignment; } catch(e) { rec = null; }
    if(token !== stGen || asgId() !== aid) return;
    const t = (rec && rec.teams) || {};
    if(!t.className || !t.title) { stMsg.textContent = 'This assignment has no saved Teams class and title yet. Read it from Teams first (Design assignment \u2192 Choose from Teams\u2026) and save.'; return; }
    let d; try { d = await postJSON('/api/jobs', {type: 'teams_students', assignment: aid, class: t.className, title: t.title}); } catch(e) { d = {error: 'Couldn\u2019t reach the app.'}; }
    if(token !== stGen || asgId() !== aid) return;
    if(d.error) { stMsg.textContent = d.error; return; }
    followStatuses(d.job.id, aid, token);
  };
  if(pick) pick.addEventListener('change', () => { stGen++; stMsg.textContent = ''; TEAMS = null; applyTeams(); });
  window.feedbackCollect = {open: () => open.click()};
})();
