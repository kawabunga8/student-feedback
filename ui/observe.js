/* Performance observations (optional). For work the teacher watches or listens to (video, audio), the teacher records,
   per rubric criterion, a level and a short note. Nothing is ever pre-filled: a level exists only if the teacher picks it.
   Nothing here reads, plays or uploads media: evidence links open in the teacher's own browser tab on SharePoint.
   "Use my notes" copies the typed notes (never levels) into the student's Notes box, which the local drafting model
   already reads. Editing a Notes box voids that student's review like any other edit. Saved beside the session. */
(() => {
  const ws = window.feedbackWorkspace, review = document.getElementById('step-review'), list = document.getElementById('students');
  if(!ws || !review || !list) return;
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const getJSON = async p => (await fetch(p)).json();
  const postJSON = async (p, b) => { const r = await fetch(p, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}); const d = await r.json(); d.__status = r.status; return d; };
  const HEAD = "Teacher's observations (what the teacher saw and heard; the only source for what the student did):";
  const keyOf = c => c.dataset.rid || c.querySelector('.name').value.trim();
  const nameOf = c => c.querySelector('.name').value.trim() || 'Unnamed student';

  const box = make('div', 'card observe');
  box.append(make('h3', '', 'Performance observations (optional)'));
  box.append(make('p', 'hint', 'For video or audio work you watch or listen to yourself: choose a level and write a short note for each criterion. ' +
    'Nothing is pre-filled and no recording is opened, played or uploaded by this app. “Use my notes” copies your typed notes (not the levels) into the student’s Notes box for drafting.'));
  const siteIn = make('input'); siteIn.size = 60; siteIn.placeholder = 'https://rcschool.sharepoint.com/sites/<class team site>'; siteIn.setAttribute('aria-label', 'Class team SharePoint site address');
  const listBtn = make('button', '', 'Load evidence list from SharePoint'); listBtn.type = 'button';
  const listStatus = make('p', 'hint'); listStatus.setAttribute('role', 'status');
  const listBox = make('div'); listBox.append(make('p', 'hint', 'Optional: lists each student’s submitted files (names, sizes and links only; nothing is opened or downloaded) using this app’s own Chrome window. You may be asked to sign in there.'), siteIn, ' ', listBtn, listStatus);
  const who = make('select'); who.setAttribute('aria-label', 'Student to observe');
  const prev = make('button', '', '‹ Previous'), next = make('button', '', 'Next ›'), status = make('p', 'hint'); status.setAttribute('role', 'status');
  [prev, next].forEach(b => b.type = 'button');
  const bar = make('div'); bar.append(prev, ' ', who, ' ', next);
  const state = make('select'); state.setAttribute('aria-label', 'Observation status');
  [['unobserved', 'Not watched yet'], ['observed', 'Observed'], ['revisit', 'Needs another look']].forEach(([v, t]) => { const o = make('option', '', t); o.value = v; state.append(o); });
  const evidence = make('div', 'observe-evidence'), rows = make('div', 'observe-criteria');
  const strengths = make('textarea'); strengths.rows = 2; strengths.placeholder = 'Strengths you noticed'; strengths.setAttribute('aria-label', 'Strengths');
  const nextStep = make('textarea'); nextStep.rows = 2; nextStep.placeholder = 'One next step'; nextStep.setAttribute('aria-label', 'Next step');
  const useNotes = make('button', '', 'Use my notes in this student’s Notes box'), check = make('button', '', 'Check draft against my notes');
  [useNotes, check].forEach(b => b.type = 'button');
  const flags = make('ul'); flags.hidden = true;
  const actions = make('div'); actions.append(useNotes, ' ', check);
  box.append(listBox, bar, status, state, evidence, rows, strengths, nextStep, actions, flags);
  review.insertBefore(box, list);

  let aid = '', data = null, version = 0, store = {}, saveTimer = 0, dirty = false, busy = false, failedAt = 0;

  const current = () => ws.cards().find(c => keyOf(c) === who.value) || null;
  const blank = () => ({status: 'unobserved', criteria: [], strengths: '', next_step: ''});
  const obsFor = k => store[k] || (store[k] = blank());
  const critOf = (o, id) => o.criteria.find(c => c.id === id) || (o.criteria.push({id, level: '', note: '', ts: ''}), o.criteria[o.criteria.length - 1]);
  const touch = () => { dirty = true; clearTimeout(saveTimer); saveTimer = setTimeout(save, 1500); status.textContent = 'Unsaved changes …'; };

  function renderEvidence(c) {
    evidence.replaceChildren();
    const items = (data && data.evidence && c && data.evidence[c.dataset.rid || '']) || [];
    if(!items.length) { evidence.append(make('p', 'hint', 'No evidence list loaded for this student. You can still record observations.')); return; }
    evidence.append(make('p', 'hint', 'Submitted files (metadata only; links open in your own browser tab):'));
    const ul = make('ul');
    items.forEach(i => {
      const li = make('li'), kb = Math.max(1, Math.round((i.bytes || 0) / 1024));
      const safe = /^https:\/\/[a-z0-9.-]+\.sharepoint\.com\//i.test(i.url || '');
      if(safe) { const a = make('a', '', i.name); a.href = i.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; li.append(a); } else li.append(document.createTextNode(i.name));
      li.append(document.createTextNode(` (${i.kind}, ${kb} KB)`)); ul.append(li);
    });
    evidence.append(ul);
  }

  function render() {
    const c = current(), o = c ? obsFor(keyOf(c)) : null;
    rows.replaceChildren(); flags.hidden = true;
    [state, strengths, nextStep, useNotes, check].forEach(e => e.disabled = !c);
    if(!c || !data) { renderEvidence(null); return; }
    state.value = o.status; strengths.value = o.strengths; nextStep.value = o.next_step;
    renderEvidence(c);
    if(!data.criteria.length) rows.append(make('p', 'hint', 'This assignment has no success criteria yet. Add them in Design assignment to record a level and note for each.'));
    data.criteria.forEach(k => {
      const cr = o.criteria.find(x => x.id === k.id) || {level: '', note: '', ts: ''};
      const row = make('div', 'observe-row'), lab = make('strong', '', k.text || 'Criterion ' + (+k.id + 1));
      const lv = make('select'); lv.setAttribute('aria-label', 'Level for ' + (k.text || k.id));
      const none = make('option', '', '— not chosen —'); none.value = ''; lv.append(none);
      data.levels.forEach(l => ['', '+'].forEach(p => { if(l === 'Extending' && p) return; const o2 = make('option', '', l + p); o2.value = l + p; lv.append(o2); }));
      lv.value = cr.level || '';
      const note = make('textarea'); note.rows = 2; note.maxLength = 2000; note.value = cr.note || ''; note.placeholder = 'What you saw or heard'; note.setAttribute('aria-label', 'Note for ' + (k.text || k.id));
      const ts = make('input'); ts.maxLength = 20; ts.value = cr.ts || ''; ts.placeholder = 'e.g. 1:24'; ts.size = 8; ts.setAttribute('aria-label', 'Timestamp for ' + (k.text || k.id));
      lv.onchange = () => { critOf(obsFor(keyOf(c)), k.id).level = lv.value; touch(); };
      note.oninput = () => { critOf(obsFor(keyOf(c)), k.id).note = note.value; touch(); };
      ts.oninput = () => { critOf(obsFor(keyOf(c)), k.id).ts = ts.value; touch(); };
      row.append(lab, ' ', lv, ' ', ts, note); rows.append(row);
    });
  }
  state.onchange = () => { const c = current(); if(c) { obsFor(keyOf(c)).status = state.value; touch(); } };
  strengths.oninput = () => { const c = current(); if(c) { obsFor(keyOf(c)).strengths = strengths.value; touch(); } };
  nextStep.oninput = () => { const c = current(); if(c) { obsFor(keyOf(c)).next_step = nextStep.value; touch(); } };

  async function save() {
    if(!aid || !dirty || busy) return;
    busy = true; clearTimeout(saveTimer);
    try {
      const d = await postJSON('/api/observations', {assignment: aid, baseVersion: version, students: store});
      if(d.__status === 409) { status.textContent = 'These observations were saved somewhere else. Reloaded the saved copy; your last edit was not saved.'; apply(d.current ? {...data, version: d.current.version, students: d.current.students} : data); dirty = false; render(); return; }
      if(d.error) { status.textContent = d.error; return; }
      version = d.version; data = d; dirty = false; status.textContent = 'Saved.';
    } catch(e) { status.textContent = 'Couldn’t reach the app, so these observations are not saved yet.'; }
    finally { busy = false; }
  }
  const apply = d => { data = d; version = d.version; store = JSON.parse(JSON.stringify(d.students || {})); };
  const siteKey = () => 'observe-site-' + aid;
  const remember = () => { try { siteIn.value = (aid && localStorage.getItem(siteKey())) || siteIn.value; } catch(e) {} };

  let polling = false;
  async function pollListing() {
    if(polling || !aid) return;
    polling = true; const mine = aid;
    try {
      for(;;) {
        const d = await getJSON('/api/evidence-listing?assignment=' + encodeURIComponent(mine));
        if(mine !== aid) return;
        if(d.state === 'running') { listStatus.textContent = d.message || 'Working …'; listBtn.disabled = true; await new Promise(r => setTimeout(r, 2000)); continue; }
        listBtn.disabled = false;
        if(d.state === 'done') {
          const c = d.counts || {}, kinds = Object.entries(c.files_by_kind || {}).map(([k, n]) => `${n} ${k}`).join(', ') || 'no files';
          listStatus.textContent = `Evidence list saved: ${c.students_with_evidence || 0} students with files (${kinds}), ${c.flagged || 0} folders not matched to the class list, ${c.no_evidence || 0} students with nothing found for this assignment.`;
          if(dirty) await save();
          data = null; failedAt = 0; await load();
        } else if(d.state === 'error') listStatus.textContent = d.message || 'The listing didn’t finish.';
        else if(d.error) listStatus.textContent = d.error;
        return;
      }
    } catch(e) { listStatus.textContent = 'Couldn’t reach the app.'; listBtn.disabled = false; }
    finally { polling = false; }
  }
  listBtn.onclick = async () => {
    if(!aid || !data) { listStatus.textContent = 'Open a saved assignment with its students first (observations need a saved session).'; return; }
    const site = siteIn.value.trim();
    if(!site) { listStatus.textContent = 'Paste the class team’s SharePoint site address first.'; return; }
    try { localStorage.setItem(siteKey(), site); } catch(e) {}
    listBtn.disabled = true; listStatus.textContent = 'Starting …';
    let d; try { d = await postJSON('/api/evidence-listing', {assignment: aid, site}); } catch(e) { d = {error: 'Couldn’t reach the app.'}; }
    if(d.error) { listStatus.textContent = d.error; listBtn.disabled = false; return; }
    if(d.state === 'error') { listStatus.textContent = d.message; listBtn.disabled = false; return; }
    listStatus.textContent = d.message || 'Working …'; pollListing();
  };

  async function load() {
    const owner = (window.feedbackAssignment && window.feedbackAssignment.cardsOwner()) || '';
    if(owner === aid && (data || Date.now() - failedAt < 15000)) return;   // after an error, try again at most every 15 s
    if(dirty) await save();
    aid = owner; data = null; store = {}; dirty = false;
    if(!aid) { status.textContent = 'Open a saved assignment with its students to record observations.'; fill(); render(); return; }
    let d; try { d = await getJSON('/api/observations?assignment=' + encodeURIComponent(aid)); } catch(e) { d = {error: 'Couldn’t reach the app.'}; }
    if(((window.feedbackAssignment && window.feedbackAssignment.cardsOwner()) || '') !== aid) return;
    if(d.error) { status.textContent = d.error; data = null; aid = owner; failedAt = Date.now(); fill(); render(); return; }
    failedAt = 0; apply(d); status.textContent = ''; remember(); fill(); render(); pollListing();
  }

  function fill() {
    const keep = who.value, cards = ws.cards();
    who.replaceChildren(...cards.map(c => { const o = make('option', '', nameOf(c)); o.value = keyOf(c); return o; }));
    if(cards.some(c => keyOf(c) === keep)) who.value = keep;
  }
  const move = d => { if(!who.options.length) return; who.selectedIndex = (who.selectedIndex + d + who.options.length) % who.options.length; render(); };
  prev.onclick = () => move(-1); next.onclick = () => move(1); who.onchange = render;

  useNotes.onclick = async () => {
    const c = current(); if(!c) return;
    await save();
    let d; try { d = await getJSON('/api/observations?assignment=' + encodeURIComponent(aid)); } catch(e) { status.textContent = 'Couldn’t reach the app.'; return; }
    const text = (d.notes || {})[keyOf(c)] || '';
    if(!text) { status.textContent = 'Write at least one note, strength or next step first.'; return; }
    const box_ = c.querySelector('.notes'), old = box_.value, at = old.indexOf(HEAD);
    const kept = (at >= 0 ? old.slice(0, at) : old).replace(/\s+$/, '');
    box_.value = (kept ? kept + '\n\n' : '') + text; box_.dispatchEvent(new Event('input', {bubbles: true}));
    status.textContent = 'Copied your notes into this student’s Notes box. Review that student again after drafting.';
  };

  check.onclick = async () => {
    const c = current(); if(!c) return;
    const draft = c.querySelector('.out:not(.err)')?.innerText || '';
    flags.replaceChildren(); flags.hidden = true;
    if(!draft.trim()) { status.textContent = 'Draft feedback for this student first.'; return; }
    await save();
    const d = await postJSON('/api/observation-claims', {assignment: aid, key: keyOf(c), draft});
    if(d.error) { status.textContent = d.error; return; }
    if(!d.unsupported.length) { status.textContent = 'Every substantive sentence shares wording with your notes. Still read the draft yourself.'; return; }
    status.textContent = 'These sentences do not match anything in your notes. Check each against what you saw, or remove it:';
    d.unsupported.forEach(s => flags.append(make('li', '', s))); flags.hidden = false;
  };

  window.addEventListener('beforeunload', e => { if(dirty) { e.preventDefault(); e.returnValue = ''; } });
  setInterval(() => { if(!busy) { load().then(() => { if(ws.cards().length !== who.options.length) { fill(); render(); } }); } }, 1000);
  fill(); render(); load();
})();
