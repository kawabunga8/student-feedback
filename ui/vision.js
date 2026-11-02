/* Handwriting and pictures (prototype): the teacher chooses a photo or scan; a local vision model reads it; the teacher
   compares the transcription with the image, fixes it, matches the name, and only then adds a student card.
   The image stays in this page and goes only to the app on this computer (and from there to Ollama). Nothing is saved
   or posted, and the transcription is never treated as checked. Each image is bound to the assignment that was open when it was
   chosen: if another assignment is opened before Add, the preview is discarded rather than added to the wrong class. */
(() => {
  const host = document.querySelector('.onenote-card'), collect = document.getElementById('step-collect');
  if(!collect) return;
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const card = make('div', 'card vision-card'); card.append(make('h3', '', 'Handwriting and pictures'), make('span', 'badge', 'Prototype: a local model reads one image at a time'));
  card.append(make('p', 'hint', 'Choose a photo or scan (PNG or JPEG) of one student’s work. A vision model on this computer copies out the text. It can misread, so check every line against the picture, correct it, and match the student before adding.'));
  const pick = make('input'); pick.type = 'file'; pick.accept = 'image/png,image/jpeg'; pick.multiple = true; pick.setAttribute('aria-label', 'Choose images of student work');
  const msg = make('div', 'status vision-msg'); msg.setAttribute('role', 'status');
  const rowsBox = make('div', 'vision-rows'); card.append(pick, msg, rowsBox);
  (host || collect.lastElementChild).after(card);
  const asgSel = () => document.getElementById('asg-pick');
  const asgId = () => { const v = (asgSel() || {}).value || ''; return /^asg-\d{8}-[0-9a-f]{8}$/.test(v) ? v : ''; };
  const asgName = () => { const o = asgSel() && asgSel().selectedOptions[0]; return o ? o.textContent : ''; };
  const rows = [];
  // Drop a preview that no longer belongs to the open assignment: release the image, clear the text, keep only a note.
  function discard(r, why) {
    if(r.dead) return; r.dead = true;
    try { URL.revokeObjectURL(r.url); } catch(e) { /* nothing to release */ }
    r.row.replaceChildren(make('strong', '', r.file.name), make('div', 'status warn', why));
  }
  const WHY = 'Discarded: the assignment changed after this image was chosen. Choose the image again under the assignment it belongs to.';
  const sweep = () => rows.forEach(r => { if(!r.dead && r.assignment !== asgId()) discard(r, WHY); });
  if(asgSel()) asgSel().addEventListener('change', sweep);
  const rosterLoaded = () => typeof ROSTER !== 'undefined' && ROSTER.length > 0 && typeof window.findStudent === 'function';
  const matchNote = name => {
    if(!rosterLoaded()) return {ok: false, text: 'Load the Course Hub class list before adding this.'};
    if(!name.trim()) return {ok: false, text: 'Type the student’s name.'};
    const r = window.findStudent(name.trim());
    if(r.status === 'match') return {ok: true, text: '✓ Matches the class list: ' + r.s.last + ', ' + r.s.first};
    return {ok: false, text: r.status === 'ambiguous' ? '? Could be: ' + (r.options || []).join(' or ') + '. Type the full name.' : '? Not on this class list: check the name.'};
  };
  const b64 = f => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = rej; r.readAsDataURL(f); });

  function addRow(file, assignment) {
    const row = make('div', 'vision-row'), url = URL.createObjectURL(file);
    const img = make('img', 'vision-img'); img.src = url; img.alt = 'The image being read: ' + file.name; img.style.maxWidth = '100%'; img.style.maxHeight = '320px';
    const name = make('input', 'vision-name'); name.placeholder = 'Student name'; name.setAttribute('aria-label', 'Student name for ' + file.name);
    const note = make('div', 'teams-now'), state = make('div', 'status');
    const text = make('textarea', 'vision-text'); text.setAttribute('aria-label', 'Transcription of ' + file.name); text.hidden = true; text.rows = 10;
    const add = make('button', 'primary vision-add', 'Add as a student card'); add.type = 'button'; add.hidden = true;
    const upd = () => { const m = matchNote(name.value); note.textContent = m.text; note.className = 'teams-now' + (m.ok ? '' : ' warn'); return m; };
    name.addEventListener('input', upd); upd();
    row.append(make('strong', '', file.name), make('div', 'hint vision-bound', 'For assignment: ' + asgName()), img, state, name, note, text, add); rowsBox.append(row);
    let result = null;
    const rec = {row, url, file, assignment, dead: false}; rows.push(rec);
    add.onclick = () => {
      if(rec.dead) return;
      if(asgId() !== assignment) { discard(rec, WHY); return; }
      if(!upd().ok) { state.textContent = 'Not added: the name must match the class list.'; return; }
      if(!text.value.trim()) { state.textContent = 'The transcription is empty.'; return; }
      const c = window.addStudent(name.value.trim(), text.value);
      const n = make('div', 'status transcribed-note', 'Transcribed from ' + file.name + ' by a local model: ' + result.notes.join(' '));
      c.querySelector('.work').after(n); c.dataset.transcribed = '1';
      c.querySelector('.work').dispatchEvent(new Event('input', {bubbles: true}));
      if(typeof applyTeams === 'function' && typeof TEAMS !== 'undefined' && TEAMS) applyTeams();
      if(typeof window.matchCard === 'function') window.matchCard(c);
      add.disabled = true; state.textContent = 'Added a card. Read it against the image, then save the session.';
    };
    return {state, text, add, name, row, rec, set: r => { result = r; }};
  }

  pick.onchange = async () => {
    const files = [...pick.files].slice(0, 10); pick.value = '';
    msg.textContent = '';
    const aid = asgId();
    if(files.length && !aid) { msg.textContent = 'Open or save an assignment first: each image is kept with the assignment it was chosen under.'; return; }
    for(const f of files) {
      if(asgId() !== aid) { msg.textContent = 'The assignment changed, so the remaining images were not read. Choose them again.'; break; }
      const r = addRow(f, aid); r.state.textContent = 'Reading with a local model… this can take a minute.';
      try {
        const d = await (await fetch('/api/transcribe', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({data: await b64(f)})})).json();
        if(r.rec.dead) continue;
        if(asgId() !== aid) { discard(r.rec, WHY); continue; }
        if(d.error) { r.state.textContent = d.error; continue; }
        r.set(d); r.text.value = d.text; r.text.hidden = false; r.add.hidden = false;
        r.state.textContent = d.notes.join(' ') + ' (model: ' + d.model + ')';
      } catch(e) { r.state.textContent = 'Couldn’t reach the app.'; }
    }
  };
})();
