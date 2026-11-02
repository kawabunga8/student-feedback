/* Local workflow shell. Reviewed snapshots are exports, not posting authorization. */
(() => {
  const main = document.querySelector('main');
  const make = (tag, cls, text) => { const e = document.createElement(tag); e.className = cls; if(text) e.textContent = text; return e; };
  const header = make('header', 'workspace-header');
  header.innerHTML = '<div><span class="eyebrow">TEACHER WORKSPACE</span><h1>Student Feedback</h1><p>From student work to feedback you have reviewed.</p></div><span class="local-badge">● Local processing</span>';
  main.querySelector('h1').remove(); main.querySelector('.sub').remove();
  main.prepend(header);
  const nav = make('nav', 'steps'); nav.setAttribute('aria-label', 'Assessment workflow'); header.after(nav);
  const STEPS = [['design','Design assignment'], ['setup','Setup'], ['collect','Collect'], ['review','Draft & review'], ['delivery','Export & posting']];
  const panels = STEPS.map(([key, label], i) => {
    const section = make('section', 'workflow-panel'); section.id = 'step-' + key; section.dataset.panel = key;
    const h = make('h2', '', label); section.append(h); main.append(section);
    const b = make('button', 'step', (i + 1) + '  ' + label); b.type = 'button'; b.onclick = () => select(i); nav.append(b);
    return section;
  });
  const setupCards = [...main.children].filter(e => e.classList.contains('card'));
  setupCards.forEach(e => panels[1].append(e));
  const collect = panels[2];
  collect.append(make('p', 'hint', 'Load saved work or upload files, then check each student match in Draft & review.'));
  const imports = make('div', 'card import-tools'); collect.append(imports);
  ['addall','files','filepick','split','assess'].forEach(id => imports.append(document.getElementById(id)));
  const notebook = make('div', 'card');
  notebook.innerHTML = '<h3>OneNote collection</h3><span class="badge">Manual test available</span><p>The local browser test can read a notebook page. Automatic class collection and vision transcription are not connected yet.</p><p>Continue using saved Assessment files or upload collected work above.</p>';
  collect.append(notebook);
  const review = panels[3];
  const toolbar = make('div', 'review-toolbar'); review.append(toolbar);
  ['add','go'].forEach(id => toolbar.append(document.getElementById(id)));
  const pause = make('button', '', 'Stop after current student'); pause.disabled = true; toolbar.append(pause);
  const search = make('input', 'student-search'); search.placeholder = 'Find a student…'; search.setAttribute('aria-label','Find a student'); toolbar.append(search);
  review.append(document.getElementById('students'));
  const skip = document.getElementById('skipret').closest('label'); review.insertBefore(skip, document.getElementById('students'));
  review.insertBefore(document.getElementById('teamsnote'), document.getElementById('students'));
  const summary = make('div', 'summary'); header.after(summary);
  const delivery = panels[4];
  delivery.append(make('p','hint','Review every draft and select each level yourself. CSV exports support manual entry; they do not post to either system.'));
  const exports = make('div','card export-tools'); delivery.append(exports);
  ['dl','dlteams'].forEach(id => exports.append(document.getElementById(id)));
  const save = make('button', '', 'Save reviewed snapshot (.json)'); exports.append(save);
  const deliveryStatus = make('p','status'); exports.append(deliveryStatus);
  const targets = make('div','destination-grid');
  for(const name of ['Teams Assignments','MySchool']) {
    const card = make('div','card'); card.append(make('h3','',name),make('span','badge','Assisted'),make('p','','Open it, copy each approved text, paste, then submit there yourself. Automated posting and read-back verification are not built yet.')); targets.append(card);
  }
  delivery.append(targets);

  // ---- Assisted posting: open each system, copy the approved text, Shingo pastes and submits. Nothing here
  // ---- posts automatically. Ticks record what he has done and checked; any later edit flags it as out of date.
  const LEVEL_CODE = {Emerging:'EMG', Developing:'DEV', Proficient:'PRF', Extending:'EXT'};
  const levelCode = l => { const m = /^(Emerging|Developing|Proficient|Extending)(\+?)$/.exec(l || ''); return m ? LEVEL_CODE[m[1]] + m[2] : ''; };
  const HOSTS = {teams:['teams.microsoft.com','teams.cloud.microsoft'], myschool:['rcs.myschoolmanagement.com']};
  const DEFAULT = {teams:'https://teams.microsoft.com/v2/', myschool:'https://rcs.myschoolmanagement.com/content/common/dashboard.php'};
  const NAMES = {teams:'Teams', myschool:'MySchool'};
  const safeUrl = (kind, v) => { try { const u = new URL(v); return u.protocol === 'https:' && HOSTS[kind].includes(u.hostname) ? u.href : ''; } catch(e) { return ''; } };
  const keep = {get:k=>{try{return localStorage.getItem(k)||''}catch(e){return ''}}, set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
  const linkKey = kind => 'posting-link:' + kind + ':' + (document.getElementById('atitle').value.trim() || 'default');
  const posting = make('div','card posting'); delivery.append(posting);
  posting.append(make('h3','','Assisted posting'), make('p','hint','Only reviewed students appear here. For each one: copy, switch to Teams or MySchool, paste, and click Return or save there yourself. Tick a box only after you have checked it in that system.'));
  const links = make('div','posting-links'); posting.append(links);
  const linkInputs = {};
  for(const [kind, label, help] of [
    ['teams','Teams link (optional)','Leave empty to open Teams, then go to Assignments → this assignment → the first student, and use the arrows to move between students.'],
    ['myschool','MySchool link (optional)','Paste the address of this assignment\u2019s Assessment tab in MySchool, or leave empty to open the MySchool dashboard.']]) {
    const l = make('label','',label), i = make('input',''), h = make('span','hint',help);
    i.placeholder = DEFAULT[kind]; l.append(i,h); links.append(l); linkInputs[kind] = i;
    i.addEventListener('change',() => { const v = i.value.trim();
      h.textContent = v && !safeUrl(kind,v) ? 'That isn\u2019t a ' + NAMES[kind] + ' address, so it won\u2019t be opened.' : help;
      keep.set(linkKey(kind), v); });
  }
  const loadLinks = () => { for(const k in linkInputs) linkInputs[k].value = keep.get(linkKey(k)); };
  document.getElementById('atitle').addEventListener('change', loadLinks); loadLinks();
  const openSystem = kind => window.open(safeUrl(kind, linkInputs[kind].value.trim()) || DEFAULT[kind], 'feedback-' + kind, 'noopener');
  const postTools = make('div','posting-tools'); posting.append(postTools);
  for(const kind of ['teams','myschool']) { const b = make('button','','Open ' + NAMES[kind]); b.type = 'button'; b.onclick = () => openSystem(kind); postTools.append(b); }
  const postProgress = make('span','posting-progress'); postTools.append(postProgress);
  const postList = make('div','posting-list'); posting.append(postList);
  const posted = new WeakMap();   // card -> {teams:{bound, at}, myschool:{bound, at}}
  const rows = new WeakMap();
  const surname = n => { n = (n || '').trim(); return (n.includes(',') ? n.split(',')[0] : n.split(/\s+/).pop() || '').toLowerCase(); };
  const copy = async (text, btn) => { try { await navigator.clipboard.writeText(text); const was = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => btn.textContent = was, 1200); }
                                      catch(e) { const was = btn.textContent; btn.textContent = 'Copy failed'; setTimeout(() => btn.textContent = was, 2000); } };
  function postState(c, kind) {
    const d = (posted.get(c) || {})[kind];
    if(!d) return {done:false, text:'', stale:false};
    const stale = d.bound !== JSON.stringify(payload(c));
    return {done:true, stale, at:d.at, text: stale ? 'Changed after posting: update it in ' + NAMES[kind] + ', then tick again'
                                                    : 'Done ' + new Date(d.at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})};
  }
  function makeRow(c) {
    const row = make('div','posting-row'), who = make('div','posting-who');
    const name = make('strong',''), lvl = make('span','posting-level'); who.append(name, lvl);
    const dest = {};
    for(const kind of ['teams','myschool']) {
      const box = make('div','posting-dest'), head = make('span','posting-dest-name', NAMES[kind]);
      const cp = make('button','', kind === 'teams' ? 'Copy feedback' : 'Copy comment'); cp.type = 'button';
      cp.onclick = () => { const p = payload(c); copy(kind === 'teams' ? p.feedback : p.myschool_comment, cp); };
      const tick = make('label','posting-tick'), cb = make('input',''); cb.type = 'checkbox';
      // Record on click: the page refreshes on the checkbox's input event, which fires before change.
      cb.addEventListener('click', () => { const all = posted.get(c) || {};
        if(cb.checked) all[kind] = {bound:JSON.stringify(payload(c)), at:new Date().toISOString()}; else delete all[kind];
        posted.set(c, all); refresh(); });
      tick.append(cb, document.createTextNode(' Done in ' + NAMES[kind]));
      const st = make('span','posting-state'); box.append(head, cp, tick, st); dest[kind] = {cp, cb, st};
    }
    const dests = make('div','posting-dests');
    dests.append(...['teams','myschool'].map(k => dest[k].cp.parentElement));
    row.append(who, dests);
    const r = {row, name, lvl, dest}; rows.set(c, r); return r;
  }
  let lastOrder = '';
  function renderPosting() {
    const shown = cards().filter(c => valid(c) || posted.get(c)).sort((a,b) => surname(payload(a).name).localeCompare(surname(payload(b).name)));
    const order = shown.map(c => (rows.get(c) ? '' : 'new') + payload(c).student_id).join('|');
    if(order !== lastOrder) { postList.replaceChildren(...shown.map(c => (rows.get(c) || makeRow(c)).row)); lastOrder = shown.map(c => payload(c).student_id).join('|'); }
    if(!shown.length) postList.replaceChildren(make('p','hint','No reviewed students yet. Mark students reviewed in Draft & review first.'));
    let doneT = 0, doneM = 0;
    for(const c of shown) {
      const r = rows.get(c), p = payload(c), ok = valid(c);
      r.name.textContent = p.name || 'Unnamed student';
      r.lvl.textContent = p.level ? 'Level: ' + p.level + (levelCode(p.level) ? ' (' + levelCode(p.level) + ')' : '') : 'No level';
      r.row.classList.toggle('not-reviewed', !ok);
      for(const kind of ['teams','myschool']) {
        const d = r.dest[kind], s = postState(c, kind);
        d.cb.checked = s.done && !s.stale;   // out-of-date ticks show unticked, so one click re-confirms
        d.cp.disabled = !ok || (kind === 'myschool' && !p.myschool_comment.trim());
        d.cp.title = !ok ? 'Review this student again first' : (kind === 'myschool' && !p.myschool_comment.trim()) ? 'No MySchool comment written' : '';
        d.st.textContent = !ok && !s.done ? 'Review again first' : s.text;
        d.st.classList.toggle('stale', s.stale);
        if(s.done && !s.stale) kind === 'teams' ? doneT++ : doneM++;
      }
    }
    const reviewed = cards().filter(valid).length;
    postProgress.textContent = reviewed ? `Teams ${doneT} of ${reviewed}   ·   MySchool ${doneM} of ${reviewed}` : '';
  }
  function postingSummary(c) {
    const out = {};
    for(const kind of ['teams','myschool']) { const s = postState(c, kind); out[kind] = s.done ? {done_at:s.at, changed_since:s.stale} : null; }
    return out;
  }
  const status = document.getElementById('status'); status.setAttribute('role','status'); main.append(status);
  // Remove the original action container after relocating its controls.
  [...main.children].filter(e => e.classList.contains('bar')).forEach(e => e.remove());
  function select(i) { panels.forEach((p,n) => p.hidden = n !== i); [...nav.children].forEach((b,n) => { b.classList.toggle('active',n===i); b.setAttribute('aria-current',n===i?'step':'false'); }); }
  const cards = () => [...document.querySelectorAll('.student')];
  const approvals = new WeakMap();
  function payload(c) {
    return {student_id:c.dataset.rid || '', name:c.querySelector('.name').value,
      work:c.querySelector('.work').value, notes:c.querySelector('.notes').value,
      level:c.querySelector('.level').value, grade:c.querySelector('.sgrade').value || document.getElementById('grade').value,
      feedback:c.querySelector('.out:not(.err)')?.innerText || '', myschool_comment:c.querySelector('.myschool-comment').value,
      assignment:document.getElementById('atitle').value, instructions:document.getElementById('rubric').value,
      course:document.getElementById('course').selectedOptions[0]?.textContent || '', school_year:SCHOOL_YEAR,
      quarter:document.getElementById('quarter').value, department:document.getElementById('doc').value,
      standards:[...document.querySelectorAll('.std:checked')].map(e=>({id:e.value,label:e.closest('label').textContent.trim()})),
      rubric:rubricSetting()};
  }
  function valid(c) { const a = approvals.get(c); return !!a && a.bound === JSON.stringify(payload(c)); }
  // Each draft remembers the instructions and standards it was written against. If those change later, the
  // draft is flagged as possibly outdated (its review mark is voided anyway, because the review binds them).
  const draftBasis = new WeakMap();
  const rubricSetting = () => (window.feedbackAssignment && window.feedbackAssignment.setting()) || {use: false, canon: ''};
  const basisNow = () => JSON.stringify([document.getElementById('rubric').value,
    [...document.querySelectorAll('.std:checked')].map(e => e.closest('label').textContent.trim()), rubricSetting()]);
  function flagOutdated(c) {
    const out = c.querySelector('.out:not(.err)');
    let note = c.querySelector('.draft-note');
    if(!out) { if(note) note.remove(); c.classList.remove('outdated'); return; }
    if(!draftBasis.has(out)) draftBasis.set(out, basisNow());
    const stale = draftBasis.get(out) !== basisNow();
    c.classList.toggle('outdated', stale);
    if(stale && !note) { note = make('p', 'draft-note', 'The instructions, criteria or Teams rubric setting changed after this draft was written. Regenerate it, or check it still fits, before reviewing.'); out.before(note); }
    if(!stale && note) note.remove();
  }
  function refresh() {
    cards().forEach(c => {
      flagOutdated(c);
      if(!c.querySelector('.review-controls')) {
        const box = make('div','review-controls'); const label = make('label','','MySchool comment (review separately)');
        const comment = make('textarea','myschool-comment'); label.append(comment);
        const approve = make('button','','Mark reviewed'); approve.type = 'button';
        const note = make('span','review-state');
        approve.onclick = () => {
          const p = payload(c);
          if(!p.student_id || !p.level || !p.feedback.trim() || !p.work.trim()) { note.textContent = 'Match a Course Hub student, choose a level, and draft feedback first.'; return; }
          if(cards().some(other => other !== c && other.dataset.rid === c.dataset.rid)) { note.textContent = 'Resolve duplicate student cards before review.'; return; }
          approvals.set(c,{bound:JSON.stringify(p),reviewed_at:new Date().toISOString()}); refresh();
        };
        box.append(label,approve,note); c.append(box);
      }
      const a = approvals.get(c), ok = valid(c);
      if(a) c.querySelector('.review-state').textContent = ok ? 'Reviewed · edits require review again' : 'Changed · review again';
      c.classList.toggle('reviewed',ok);
      c.hidden = !c.querySelector('.name').value.toLowerCase().includes(search.value.toLowerCase());
    });
    const all = cards(), loaded = all.filter(c=>c.querySelector('.work').value.trim()).length;
    const drafted = all.filter(c=>c.querySelector('.out:not(.err)')).length, reviewed = all.filter(valid).length;
    const text = `${loaded} submissions loaded   /   ${drafted} drafts   /   ${reviewed} reviewed`;
    if(summary.textContent !== text) summary.textContent = text;
    save.disabled = !reviewed;
    pause.disabled = !document.getElementById('go').disabled;
    renderPosting();
  }
  search.oninput = refresh;
  main.addEventListener('input',refresh); main.addEventListener('change',() => setTimeout(refresh,0));
  save.onclick = async () => {
    const records = [];
    for(const c of cards().filter(valid)) {
      const p = payload(c), approval = approvals.get(c);
      const digest = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(p.work));
      records.push({...p, source_sha256:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''), reviewed_at:approval.reviewed_at, posting:postingSummary(c)});
    }
    // Recheck after asynchronous hashing: edits must not slip into a reviewed export.
    if(records.some(r=>!cards().some(c=>valid(c) && JSON.stringify(payload(c)) === JSON.stringify(Object.fromEntries(Object.entries(r).filter(([k])=>!['source_sha256','reviewed_at','posting'].includes(k))))))) {
      deliveryStatus.textContent = 'Work changed during export. Review again.'; return;
    }
    const blob = new Blob([JSON.stringify({version:1, purpose:'reviewed snapshot; not posting authorization',records},null,2)],{type:'application/json'});
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = 'reviewed-feedback.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    deliveryStatus.textContent = `${records.length} reviewed records exported. Store this file with the assignment work. This workspace does not automatically save student data; keep the page open until you export.`;
  };
  pause.onclick = () => { window.feedbackStopRequested = true; pause.disabled = true; };
  document.getElementById('go').addEventListener('click',() => { window.feedbackStopRequested = false; select(3); });
  const notice = make('p','hint','Student work and review marks stay in this page until you export. Reloading loses them.'); review.prepend(notice);
  window.addEventListener('beforeunload',e=>{ if(cards().some(c=>c.querySelector('.work').value.trim())) { e.preventDefault(); e.returnValue=''; } });
  // Lets the session saver (assignment.js) read and restore this page's state.
  window.feedbackWorkspace = {cards, payload, valid, approvals, posted, draftBasis, basisNow, refresh};
  setInterval(refresh,1000); select(1); refresh();
})();
