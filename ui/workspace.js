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
  const notebook = make('div', 'card onenote-card');
  notebook.innerHTML = '<h3>OneNote collection</h3><span class="badge">Typed pages, read-only</span><p>Click <strong>Collect from OneNote\u2026</strong>, paste any page address from the class notebook, then choose <strong>Collect whole class</strong>: the app opens each student\u2019s Homework section, finds this assignment\u2019s page and reads it. You can also paste one student\u2019s page address. Handwriting and pictures are not read.</p><p>You can also use saved Assessment files or upload collected work above. \u201c+ Add whole class\u201d only adds the class list.</p>';
  collect.append(notebook);
  const review = panels[3];
  const toolbar = make('div', 'review-toolbar'); review.append(toolbar);
  ['add','go'].forEach(id => toolbar.append(document.getElementById(id)));
  const pause = make('button', '', 'Stop after current student'); pause.disabled = true; toolbar.append(pause);
  const markAll = make('button', '', 'Mark all reviewed'); markAll.type = 'button'; toolbar.append(markAll);
  const unmarkAll = make('button', '', 'Unreview all'); unmarkAll.type = 'button'; toolbar.append(unmarkAll);
  const noWork = make('button', '', 'Record no submission…'); noWork.type = 'button'; noWork.title = 'Select students with no submission, record the sources you checked, and review a shared comment.'; toolbar.append(noWork);
  const postAll = make('button', 'primary', 'Preview Teams posting…'); postAll.type = 'button'; postAll.title = 'Preview reviewed feedback for Teams; posting requires a separate confirmation.'; toolbar.append(postAll);
  const search = make('input', 'student-search'); search.placeholder = 'Find a student…'; search.setAttribute('aria-label','Find a student'); toolbar.append(search);
  const actionGroup=(label,controls)=>{const group=make('div','review-action-group');group.setAttribute('role','group');group.setAttribute('aria-label',label);group.append(make('span','review-action-label',label),...controls);toolbar.append(group);};
  actionGroup('Draft feedback',[document.getElementById('add'),document.getElementById('go'),pause]);
  actionGroup('Review assessments',[markAll,unmarkAll,noWork]);
  actionGroup('Teams posting',[postAll]);
  toolbar.append(search);
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
    const isTeams=name==='Teams Assignments';
    const card = make('div','card'); card.append(make('h3','',name),make('span','badge',isTeams?'Feedback + Return':'Levels + comment'),make('p','',isTeams?'Preview reviewed feedback, confirm Post and Return, then check the saved feedback in Teams. Return may notify students.':'Preview reviewed levels and comments, confirm Save, then check the result in MySchool. Publication settings are preserved.')); targets.append(card);
  }
  delivery.append(targets);

  // Posting controls launch destination-specific previews. Manual ticks remain available as a fallback.
  const LEVEL_CODE = {Emerging:'EMG', Developing:'DEV', Proficient:'PRF', Extending:'EXT'};
  const levelCode = l => { const m = /^(Emerging|Developing|Proficient|Extending)(\+?)$/.exec(l || ''); return m ? LEVEL_CODE[m[1]] + m[2] : ''; };
  const HOSTS = {teams:['teams.microsoft.com','teams.cloud.microsoft'], myschool:['rcs.myschoolmanagement.com']};
  const DEFAULT = {teams:'https://teams.microsoft.com/v2/', myschool:'https://rcs.myschoolmanagement.com/content/common/dashboard.php'};
  const NAMES = {teams:'Teams', myschool:'MySchool'};
  const safeUrl = (kind, v) => { try { const u = new URL(v); return u.protocol === 'https:' && HOSTS[kind].includes(u.hostname) ? u.href : ''; } catch(e) { return ''; } };
  const keep = {get:k=>{try{return localStorage.getItem(k)||''}catch(e){return ''}}, set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
  const linkKey = kind => 'posting-link:' + kind + ':' + (document.getElementById('atitle').value.trim() || 'default');
  const posting = make('div','card posting'); delivery.append(posting);
  posting.append(make('h3','','Post reviewed assessments'), make('p','hint','Choose Teams or MySchool below. Each action opens a preview and requires confirmation before writing. Completion is recorded separately for each destination; exports do not post anything.'));
  const postSummary = make('p','posting-summary'); postSummary.setAttribute('role','status'); posting.append(postSummary);
  const postActions = make('div','posting-actions'); posting.append(postActions);
  const bPostTeams = make('button','primary','Preview Teams batch…'); bPostTeams.type = 'button'; bPostTeams.onclick = () => { if(window.postToAll) window.postToAll(); };
  const bCheck = make('button','','Refresh Teams statuses'); bCheck.type = 'button'; bCheck.title = 'Read who is already Returned in Teams (read-only); this does not verify saved feedback.';
  bCheck.onclick = () => { const b = document.getElementById('teams-status-read'); if(b) b.click(); else postSummary.textContent = 'Open or save an assignment first.'; };
  const bPostMs = make('button','','Preview MySchool batch…'); bPostMs.type = 'button'; bPostMs.onclick = () => window.postToMySchool?.(null);
  postActions.append(bPostTeams, bCheck, bPostMs);
  const postTable = make('table','posting-table'); posting.append(postTable);
  const manual = make('details','posting-manual'); manual.append(make('summary','','Do it by hand (copy and tick)')); posting.append(manual);
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
  const postList = make('div','posting-list'); manual.append(links, postTools, postList);   // the copy-and-tick list is the fallback, kept out of the way
  const posted = new WeakMap();   // card -> {teams:{bound, at}, myschool:{bound, at}}
  const rows = new WeakMap();
  const surname = n => { n = (n || '').trim(); return (n.includes(',') ? n.split(',')[0] : n.split(/\s+/).pop() || '').toLowerCase(); };
  const copy = async (text, btn) => { try { await navigator.clipboard.writeText(text); const was = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => btn.textContent = was, 1200); }
                                      catch(e) { const was = btn.textContent; btn.textContent = 'Copy failed'; setTimeout(() => btn.textContent = was, 2000); } };
  // A "done" mark records what was posted. Teams gets the feedback, so a later change to the MySchool comment or the level must not
  // make a Teams post look out of date (and the other way round for MySchool).
  const TICK_IGNORES = {teams:['myschool_comment','level'], myschool:[]};
  function tickMatches(c, kind, bound) {
    try { const a = JSON.parse(bound), b = payload(c); (TICK_IGNORES[kind] || []).forEach(k => { delete a[k]; delete b[k]; }); return JSON.stringify(a) === JSON.stringify(b); }
    catch(e) { return false; }
  }
  function postState(c, kind) {
    const d = (posted.get(c) || {})[kind];
    if(!d) return {done:false, text:'', stale:false};
    const stale = !tickMatches(c, kind, d.bound);
    return {done:true, stale, at:d.at, text: stale ? 'Changed after posting: update it in ' + NAMES[kind] + ', then tick again'
                                                    : 'Completion recorded ' + new Date(d.at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})};
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
    renderPostTable();
  }
  // The at-a-glance view: one line per student with where their feedback stands in Teams (and MySchool when there is a comment).
  const hhmm = at => new Date(at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  function teamsChip(c) {
    const s = postState(c, 'teams');
    if(!valid(c)) return ['Not reviewed', 'muted'];
    if(s.done && !s.stale) return ['Posted · recorded ' + hhmm(s.at), 'good'];
    if(s.stale) return ['Changed after posting', 'warn'];
    if(c.dataset.tstatus === 'Returned') return ['Returned · feedback not verified here', 'soft'];
    return ['Reviewed · preview Teams posting', 'ready'];
  }
  function msChip(c) {
    const s = postState(c, 'myschool'), p = payload(c);
    if(!valid(c)) return ['Not reviewed', 'muted'];
    if(s.done && !s.stale) return ['Saved · recorded ' + hhmm(s.at), 'good'];
    if(s.stale) return ['Changed after saving', 'warn'];
    if(!p.myschool_comment.trim()) return ['No comment yet', 'muted'];
    return [p.level ? 'Ready to save' : 'Needs a level', p.level ? 'ready' : 'warn'];
  }
  let tableSig = '';
  function renderPostTable() {
    const all = cards().filter(c => c.querySelector('.work').value.trim() || c.querySelector('.nosub')?.value.trim()).sort((a,b) => surname(payload(a).name).localeCompare(surname(payload(b).name)));
    const showMs = all.some(c => valid(c) && payload(c).myschool_comment.trim());
    const data = all.map(c => ({id:payload(c).student_id, name:payload(c).name || 'Unnamed student', level:payload(c).level, t:teamsChip(c), m:msChip(c), ts:c.dataset.tstatus || ''}));
    const sig = JSON.stringify([showMs, data]);
    if(sig === tableSig) return; tableSig = sig;
    const n = data.length, count = (arr, f) => arr.filter(f).length;
    const done = count(data, d => d.t[1] === 'good'), returned = count(data, d => d.t[1] === 'soft'), ready = count(data, d => d.t[1] === 'ready'), waiting = count(data, d => d.t[1] === 'muted'), changed = count(data, d => d.t[1] === 'warn');
    postSummary.textContent = n ? 'Teams: ' + done + ' of ' + n + ' posts recorded · ' + ready + ' ready for preview' + (returned ? ' · '+returned+' Returned (feedback not verified here)' : '') + (waiting ? ' · ' + waiting + ' not reviewed' : '') + (changed ? ' · ' + changed + ' changed since posting' : '') +
      (showMs ? ' · MySchool: ' + count(data, d => d.m[1] === 'good') + ' of ' + n + ' saves recorded' : '') : 'No students yet. Load work or add the class list first.';
    bPostTeams.disabled = !ready && !changed; bPostMs.disabled = !showMs;
    const th = (t) => { const e = make('th','',t); e.scope = 'col'; return e; };
    const head = make('tr'); head.append(th('Student'), th('Level'), th('Teams')); if(showMs) head.append(th('MySchool')); head.append(th(''));
    const chip = ([t, k]) => { const td = make('td'); td.append(make('span','chip ' + k, t)); return td; };
    const body = data.map(d => { const tr = make('tr'); tr.append(make('td','', d.name), make('td','posting-lvl', d.level ? d.level + (levelCode(d.level) ? ' (' + levelCode(d.level) + ')' : '') : '—'), chip(d.t)); if(showMs) tr.append(chip(d.m));
      const act = make('td','posting-act');   // post just this student (the same engine as Post to all)
      if(d.id && (d.t[1] === 'ready' || d.t[1] === 'warn')) { const b = make('button','','Post'); b.type = 'button'; b.title = 'Post only this student to Teams'; b.onclick = () => { if(window.postToTeams) window.postToTeams([d.id]); }; act.append(b); }
      if(d.id && showMs && (d.m[1] === 'ready' || d.m[1] === 'warn') && d.m[0] !== 'Needs a level') { const b2 = make('button','','MySchool'); b2.type = 'button'; b2.title = 'Save only this student to MySchool'; b2.onclick = () => { if(window.postToMySchool) window.postToMySchool([d.id]); }; act.append(b2); }
      tr.append(act); return tr; });
    postTable.replaceChildren(make('thead','')); postTable.firstChild.append(head); const tb = make('tbody',''); tb.append(...body); postTable.append(tb);
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
      work:c.querySelector('.work').value, nosub:c.querySelector('.nosub')?.value || '', notes:c.querySelector('.notes').value,
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
    const stale = draftBasis.get(out) !== 'imported' && draftBasis.get(out) !== basisNow();   // 'imported': written outside the app, so no basis to compare
    c.classList.toggle('outdated', stale);
    if(stale && !note) {
      note = make('p', 'draft-note', 'The instructions, criteria or Teams rubric setting changed after this draft was written. Regenerate it, or check it still fits, before reviewing. ');
      const fits = make('button', '', 'It still fits'); fits.type = 'button';       // the teacher's own check: keeps this draft, stops the warning
      fits.onclick = () => { draftBasis.set(out, basisNow()); refresh(); };
      note.append(fits); out.before(note);
    }
    if(!stale && note) note.remove();
  }
  // The MySchool comment defaults to the student's feedback (it can be edited on its own). While it still equals what the
  // app put there, it follows later edits to the feedback; once the teacher types in it, it stays theirs.
  function syncMsComment(c) {
    const box = c.querySelector('.myschool-comment'), out = c.querySelector('.out:not(.err)');
    if(!box || !out) return;
    const fb = out.innerText.trim();
    if(box.value === '' && fb) { box.value = fb; c.dataset.msAuto = '1'; c.dataset.msLast = fb; return; }   // a comment is required: an empty one is filled
    if(c.dataset.msAuto === undefined) { c.dataset.msAuto = (box.value === '' || box.value === fb) ? '1' : '0'; c.dataset.msLast = box.value; }
    if(c.dataset.msAuto !== '1' || !fb) return;
    if(box.value !== c.dataset.msLast) { c.dataset.msAuto = '0'; return; }          // edited since the app last set it
    if(box.value !== fb) { box.value = fb; c.dataset.msLast = fb; }
  }
  function refresh() {
    cards().forEach(c => {
      flagOutdated(c);
      if(!c.querySelector('.review-controls')) {
        const box = make('div','review-controls'); const label = make('label','','MySchool comment (review separately)');
        const nosub = make('input','nosub'); nosub.placeholder = 'No submission confirmed: sources checked and date (leave empty when there is work)'; nosub.setAttribute('aria-label','No submission confirmed'); nosub.style.width = '100%'; box.append(nosub);
        const comment = make('textarea','myschool-comment'); label.append(comment);
        // Typing here ends the default: from then on the MySchool comment is the teacher's own text.
        comment.addEventListener('input', () => { if(comment.value !== c.dataset.msLast) c.dataset.msAuto = '0'; });
        const approve = make('button','review-toggle','Mark reviewed'); approve.type = 'button';
        const note = make('span','review-state');
        approve.onclick = () => {
          if(valid(c)) { approvals.delete(c); note.textContent = ''; refresh(); return; }   // already reviewed: this click un-reviews
          const p = payload(c);
          if(!p.student_id || !p.feedback.trim() || !(p.work.trim() || p.nosub.trim())) { note.textContent = 'Match a Course Hub student and draft feedback first.'; return; }   // a level is optional (feedback only); MySchool posting asks for one
          if(cards().some(other => other !== c && other.dataset.rid === c.dataset.rid)) { note.textContent = 'Resolve duplicate student cards before review.'; return; }
          approvals.set(c,{bound:JSON.stringify(p),reviewed_at:new Date().toISOString()}); refresh();
        };
        box.append(label,approve,note); c.append(box);
      }
      syncMsComment(c);
      const a = approvals.get(c), ok = valid(c);
      c.querySelector('.review-toggle').textContent = ok ? 'Unreview' : 'Mark reviewed';
      if(a) c.querySelector('.review-state').textContent = ok ? 'Reviewed · edits require review again' : 'Changed · review again';
      c.classList.toggle('reviewed',ok);
      c.hidden = !c.querySelector('.name').value.toLowerCase().includes(search.value.toLowerCase());
    });
    const all = cards(), loaded = all.filter(c=>c.querySelector('.work').value.trim()).length;
    const drafted = all.filter(c=>c.querySelector('.out:not(.err)')).length, reviewed = all.filter(valid).length;
    const text = `${loaded} submissions loaded   /   ${drafted} drafts   /   ${reviewed} reviewed`;
    if(summary.textContent !== text) summary.textContent = text;
    save.disabled = !reviewed;
    const toReview = all.filter(reviewable).length; markAll.textContent = toReview ? 'Mark all ' + toReview + ' reviewed' : 'Mark all reviewed'; markAll.disabled = !toReview; unmarkAll.disabled = !reviewed; postAll.disabled = !reviewed;
    pause.disabled = !document.getElementById('go').disabled;
    renderPosting();
  }
  const reviewable = c => { const p = payload(c); return !!p.student_id && !!p.feedback.trim() && !!(p.work.trim() || p.nosub.trim()) && !valid(c) &&
    !cards().some(o => o !== c && o.dataset.rid === c.dataset.rid); };
  markAll.onclick = () => {
    const todo = cards().filter(reviewable);
    if(!todo.length) { markAll.title = 'Nothing left to review'; return; }
    if(!confirm('Mark ' + todo.length + ' draft' + (todo.length === 1 ? '' : 's') + ' as reviewed? Only do this once you have read them.')) return;
    const at = new Date().toISOString(); todo.forEach(c => approvals.set(c, {bound:JSON.stringify(payload(c)), reviewed_at:at})); refresh();
  };
  // One step for students who handed in nothing: a recorded 'no submission' note (sources checked, date), the level and comment you choose, then marked reviewed. Work stays empty: it is evidence, not feedback.
  // Nothing is posted here; posting still asks for its own confirmation. Only matched students with empty Work are offered.
  const NO_WORK_TEXT = 'No submission was found for this task. Please message me on Teams so we can find a time to catch up.';
  const reviewableIdentity = c => !!c.dataset.rid && !cards().some(o => o !== c && o.dataset.rid === c.dataset.rid);
  noWork.onclick = () => {
    refresh(); // New cards need their evidence and review fields before bulk editing.
    const empties = cards().filter(c => !c.querySelector('.work').value.trim() && !c.querySelector('.out:not(.err)') && reviewableIdentity(c));
    const dlg = make('dialog', 'no-work-dialog'); const h = make('h3', '', 'No work found');
    const list = make('div'); const picks = empties.map(c => { const l = make('label'); l.style.display = 'block'; const cb = make('input'); cb.type = 'checkbox'; cb.checked = false; l.append(cb, ' ' + c.querySelector('.name').value); list.append(l); return {c, cb}; });
    if(!empties.length) list.textContent = 'Every matched student already has work or feedback.';
    const lvl = make('select'); const src = cards()[0]; [...(src ? src.querySelectorAll('.level option') : [])].forEach(o => { const x = make('option', '', o.textContent); x.value = o.value || o.textContent; if(!o.value && o.textContent.startsWith('No level')) x.value = ''; lvl.append(x); });   // any level, none chosen for you
    const checked = make('div'); const sourceBoxes = ['ClassNotebook', 'Teams attachments and links', 'Code.org'].map(n => { const l = make('label'); l.style.display = 'block'; const cb = make('input'); cb.type = 'checkbox'; cb.checked = false; l.append(cb, ' I checked ' + n); checked.append(l); return {n, cb}; });
    const txt = make('textarea'); txt.value = NO_WORK_TEXT; txt.rows = 4; txt.style.width = '100%';
    const notice = make('p'); notice.setAttribute('role', 'status');
    const apply = make('button', 'primary', 'Apply and mark reviewed'); apply.type = 'button'; apply.disabled = !empties.length;
    const close = make('button', '', 'Close'); close.type = 'button'; close.onclick = () => { dlg.close(); dlg.remove(); };
    apply.onclick = () => {
      const chosen = picks.filter(x => x.cb.checked).map(x => x.c); if(!chosen.length) { notice.textContent = 'Select at least one student.'; return; }
      if(!txt.value.trim()) { notice.textContent = 'Enter the comment you have reviewed.'; return; }
      if(chosen.some(c => c.querySelector('.work').value.trim() || c.querySelector('.out:not(.err)') || !reviewableIdentity(c))) { notice.textContent = 'A selected student changed. Close this window and check the selection again.'; return; }
      const stamp = new Date().toISOString().slice(0, 10), used = sourceBoxes.filter(x => x.cb.checked).map(x => x.n);
      if(!used.length) { notice.textContent = 'Tick at least one source you checked.'; return; }
      chosen.forEach(c => {
        const l = c.querySelector('.level'); l.value = lvl.value; l.dispatchEvent(new Event('change', {bubbles: true}));
        if(window.insertDraft) window.insertDraft(c, txt.value.trim(), null);
        const m = c.querySelector('.myschool-comment'); if(m) { m.value = txt.value.trim(); m.dispatchEvent(new Event('input', {bubbles: true})); }
        const n = c.querySelector('.nosub'); if(n) { n.value = 'No submission found ' + stamp + ' in: ' + used.join(', '); n.dispatchEvent(new Event('input', {bubbles: true})); }
      });
      refresh();
      const at = new Date().toISOString(); chosen.filter(reviewable).forEach(c => approvals.set(c, {bound: JSON.stringify(payload(c)), reviewed_at: at})); refresh();
      dlg.close(); dlg.remove();
    };
    dlg.append(h, make('p', '', 'Records that no submission was found (what you checked and when), sets the level and comment you choose for the students ticked, and marks them reviewed. Read the shared comment before applying it. Posting is a separate step with its own preview and confirmation.'), list, checked, make('label', '', 'Level (optional; none is chosen for you)'), lvl, make('label', '', 'Comment (Teams and MySchool)'), txt, notice, apply, close);
    document.body.append(dlg); dlg.showModal();
  };
  unmarkAll.onclick = () => { cards().forEach(c => approvals.delete(c)); refresh(); };
  postAll.onclick = () => { if(window.postToAll) window.postToAll(); };
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
  // A verified post records the same "done" tick the teacher would tick by hand: bound to the exact reviewed values.
  const markPosted = (sid, kind, expectedBound) => { const c = cards().find(x => payload(x).student_id === sid); if(!c || !valid(c) || (expectedBound && expectedBound !== JSON.stringify(payload(c)))) return false;
    const t = posted.get(c) || {}; t[kind] = {bound:JSON.stringify(payload(c)), at:new Date().toISOString()}; posted.set(c, t); refresh(); return true; };
  window.feedbackWorkspace = {cards, payload, valid, approvals, posted, draftBasis, basisNow, refresh, markPosted, tickMatches};
  setInterval(refresh,1000); select(1); refresh();
})();
