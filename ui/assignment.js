/* Saved assignments, the Design step and "Choose from Teams…".
   The saved assignment record is the centre: Setup, Design and (later) collection and approval all use the same
   record. Records are saved on this laptop (~/Library/Application Support/student-feedback/assignments) and hold no
   student data. Draft creation sends only reviewed student-facing title and instructions to Teams; publishing is not implemented. Student-facing text and teacher-only guidance are
   kept apart: only the student-facing part is ever offered for copying into Teams. */
(() => {
  // ------------------------------------------------------------------ helpers
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const button = (text, cls, onclick) => { const b = make('button', cls, text); b.type = 'button'; if(onclick) b.onclick = onclick; return b; };
  const keep = {get:k=>{try{return localStorage.getItem(k)||''}catch(e){return ''}}, set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
  const fire = (el, ...types) => types.forEach(t => el.dispatchEvent(new Event(t, {bubbles:true})));
  let programmatic = 0;            // > 0 while this script fills a field, so the change isn't logged as "Edited here"
  function setField(sel, value) {
    const el = $(sel); if(!el || value == null) return;
    programmatic++; try { el.value = value; fire(el, 'input', 'change'); } finally { programmatic--; }
  }
  const flash = (btn, text) => { const was = btn.textContent; btn.textContent = text; setTimeout(() => btn.textContent = was, 1400); };
  const copy = async (text, btn) => { try { await navigator.clipboard.writeText(text); flash(btn, 'Copied'); } catch(e) { flash(btn, 'Copy failed'); } };
  const nowIso = () => new Date().toISOString();
  const when = iso => { const d = new Date(iso); return iso && !isNaN(d) ? d.toLocaleString(undefined, {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'}) : ''; };
  const clip = (s, n) => s.length > n ? s.slice(0, n).trimEnd() + '…' : s;
  const getJSON = async url => (await fetch(url)).json();
  const postJSON = async (url, body) => (await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})).json();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function until(test, ms) { const end = Date.now() + ms; for(;;) { try { if(test()) return true; } catch(e) {} if(Date.now() > end) return false; await sleep(50); } }
  // The page's own data: top-level `let`s in the main script.
  const courses = () => { try { return COURSES || []; } catch(e) { return []; } };
  const schoolYear = () => { try { return SCHOOL_YEAR || ''; } catch(e) { return ''; } };
  const stdDocs = () => { try { return STD || {}; } catch(e) { return {}; } };
  const lines = text => (text || '').split('\n').map(s => s.replace(/^\s*[-*•]\s*/, '').trim()).filter(Boolean);
  const words = s => (s || '').trim().split(/\s+/).filter(Boolean).length;
  // Same patterns feedback.py uses to find command terms in the title and instructions.
  const COMMAND_TERMS = {describe:/\b(?:describ\w*|description)\b/i, explain:/\b(?:explain\w*|explanation)\b/i, justify:/\bjustif\w*/i,
    analyse:/\banaly[sz]\w*/i, 'compare and contrast':/\b(?:compar\w*|contrast\w*)\b/i, discuss:/\bdiscuss\w*/i,
    evaluate:/\bevaluat\w*/i, list:/\blist\b/i, identify:/\bidentif\w*/i};
  const termsIn = text => Object.keys(COMMAND_TERMS).filter(t => COMMAND_TERMS[t].test(text));

  // ------------------------------------------------------------------ course identity (Course Hub is authoritative)
  const optionText = v => { const o = [...$('#course').options].find(o => o.value === String(v)); return o && v !== '' ? o.textContent : ''; };
  const stripTerm = n => (n || '').replace(/\s*\([^)]*\)\s*$/, '').trim();
  function courseKey(value) {
    const c = courses()[value]; if(value === '' || !c) return null;
    return {name:c.name, label:optionText(value) || c.name, sectionIds:(c.sections || []).map(s => s.id), schoolYear:schoolYear()};
  }
  function courseValueFor(key) {                       // the same Course Hub sections first, then the same course name
    if(!key || !key.name) return '';
    const list = courses(), ids = new Set(key.sectionIds || []);
    let i = ids.size ? list.findIndex(c => (c.sections || []).some(s => ids.has(s.id))) : -1;
    if(i < 0) i = list.findIndex(c => c.name === key.name);
    return i < 0 ? '' : String(i);
  }
  const courseGrades = v => { const c = courses()[v]; return v !== '' && c && Array.isArray(c.grades) ? c.grades : []; };
  let classMap = {};                                   // {schoolYear: {Teams class name: {name, label, sectionIds, confirmed}}}
  const loadClassMap = async () => { try { classMap = (await getJSON('/api/class-map')).map || {}; } catch(e) {} };
  const yearMap = () => classMap[schoolYear()] || {};
  const mappedCourse = cls => cls ? yearMap()[cls] || null : null;
  function suggestCourse(cls) {                        // a suggestion only: Shingo confirms every match
    const tl = ' ' + cls.toLowerCase().replace(/\[[^\]]*\]/g, ' ') + ' ';
    const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    let hits = courses().map((c, i) => ({c, i, base:stripTerm(c.name).toLowerCase()}))
      .filter(x => x.base && new RegExp('[^a-z0-9]' + esc(x.base) + '[^a-z0-9]').test(tl));
    if(hits.length > 1) { const longest = Math.max(...hits.map(h => h.base.length)); hits = hits.filter(h => h.base.length === longest); }
    if(hits.length > 1) { const q = +((tl.match(/\bq([1-4])\b/) || [])[1] || 0);
      if(q) hits = hits.filter(h => (h.c.quarters || []).includes(q)); }
    return hits.length === 1 ? String(hits[0].i) : '';
  }

  // ------------------------------------------------------------------ Setup fields <-> record
  // Setup's instructions box holds the student-facing instructions, then (optionally) the teacher's feedback focus
  // as a "Must include:" list, which feedback.py checks every draft against. The focus never goes to Teams.
  const FOCUS_HEAD = "Teacher's feedback focus (not shown to students):";
  function composeRubric(instructions, focus) {
    instructions = (instructions || '').trim(); focus = (focus || []).map(s => s.trim()).filter(Boolean);
    return focus.length ? (instructions ? instructions + '\n\n' : '') + FOCUS_HEAD + '\nMust include:\n' + focus.map(f => '- ' + f).join('\n') : instructions;
  }
  function splitRubric(text) {
    text = text || ''; const i = text.indexOf(FOCUS_HEAD);
    if(i < 0) return {instructions:text.trim(), focus:[]};
    return {instructions:text.slice(0, i).trim(), focus:lines(text.slice(i + FOCUS_HEAD.length).replace(/^\s*Must include:\s*$/im, ''))};
  }
  const stdLabel = box => box.closest('label').textContent.trim();
  const stdLabels = () => $$('.std').map(stdLabel);
  const tickedStandards = () => $$('.std:checked').map(stdLabel);
  function setStandards(labels) {                      // returns saved labels not in the current list
    $$('.std').forEach(b => { const want = labels.includes(stdLabel(b)); if(b.checked !== want) { b.checked = want; fire(b, 'change'); } });
    const have = stdLabels(); return labels.filter(l => !have.includes(l));
  }
  const emptyDesign = () => ({purpose:'', directions:'', evidence:'', teamsClass:'', criteria:[],
    submission:{type:'notebook', section:'Homework', page:'', files:'', completion:"When you're finished, click Turn in in Teams."},
    feedback:{mustAddress:'', myschool:'short', myschoolGuidance:''}, teacherNotes:''});
  function normalize(d) {
    const e = emptyDesign(); d = d && typeof d === 'object' ? d : {};
    return {...e, ...d, submission:{...e.submission, ...(d.submission || {})}, feedback:{...e.feedback, ...(d.feedback || {})},
      criteria:Array.isArray(d.criteria) ? d.criteria.map(c => ({text:c.text || '', evidence:c.evidence || '', standard:c.standard || ''})) : []};
  }
  const designHasContent = d => !!(d.purpose.trim() || d.directions.trim() || d.evidence.trim() || d.criteria.some(c => c.text.trim()) ||
                                    d.feedback.mustAddress.trim() || d.teacherNotes.trim());

  let record = null, design = emptyDesign(), sources = {}, teams = null, savedCore = null;
  function currentRecord() {
    const parts = splitRubric($('#rubric').value);
    return {id:record ? record.id : undefined, title:$('#atitle').value.trim(), course:courseKey($('#course').value),
      grade:$('#grade').value, term:$('#quarter').value, instructions:parts.instructions, focus:parts.focus,
      standards:tickedStandards(), length:$('#length').value, teams, design, sources};
  }
  const core = () => { const r = currentRecord(); delete r.id; delete r.sources; return JSON.stringify(r); };
  const dirty = () => record ? core() !== savedCore : !!($('#atitle').value.trim() || $('#rubric').value.trim());

  // ------------------------------------------------------------------ the assignment bar
  const bar = make('div', 'card assignment-bar');
  const pick = make('select', 'asg-pick'); pick.id = 'asg-pick';
  const pickLabel = make('label', '', 'Assignment'); pickLabel.htmlFor = 'asg-pick';
  const saveBtn = button('Save assignment', 'primary', () => save());
  const teamsBtn = button('Choose from Teams…', '', () => openTeams(''));
  const barStatus = make('div', 'asg-status'); barStatus.setAttribute('role', 'status');
  const barNote = make('div', 'asg-note');
  bar.append(pickLabel, pick, saveBtn, teamsBtn, barStatus, barNote);
  $('nav.steps').after(bar);
  function setNote(text, warn) { barNote.textContent = text || ''; barNote.classList.toggle('warn', !!warn); }
  function updateBar() {
    const parts = [];
    if(record) parts.push((dirty() ? 'Unsaved changes · version ' + record.version + ' saved ' : 'Saved · version ' + record.version + ' · ') + when(record.updated));
    else parts.push('New assignment · not saved yet');
    if(teams && teams.className) parts.push('Teams class: ' + teams.className);
    const text = parts.join('   ·   ');
    if(barStatus.textContent !== text) barStatus.textContent = text;
    barStatus.title = record ? (record.history || []).slice(-6).map(h => 'v' + h.version + ' ' + when(h.at) + ': ' + h.kind +
      (h.kind === 'created' ? '' : ' (' + h.changed.join(', ') + ')')).join('\n') : '';
    saveBtn.disabled = !!record && !dirty();
  }
  async function refreshList() {
    let list = []; try { list = (await getJSON('/api/assignments')).assignments || []; } catch(e) {}
    pick.replaceChildren(new Option('— New assignment —', ''),
      ...list.map(a => new Option(a.title + (a.course ? ' · ' + a.course : '') + ' (v' + a.version + ')', a.id)));
    pick.value = record ? record.id : '';
  }
  pick.onchange = async () => {
    const id = pick.value;
    if(dirty() && !confirm('Discard the unsaved changes to "' + ($('#atitle').value.trim() || 'this assignment') + '"?')) { pick.value = record ? record.id : ''; return; }
    await flushSession();
    if(!id) { newAssignment(); return; }
    let d; try { d = await getJSON('/api/assignments/' + encodeURIComponent(id)); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
    if(d.error) { setNote(d.error, true); pick.value = record ? record.id : ''; return; }
    await applyRecord(d.assignment);
  };
  async function save() {
    const rec = currentRecord();
    if(!rec.title) { setNote('Add an assignment name before saving.', true); $('#atitle').focus(); return null; }
    const before = record ? record.version : 0;
    let d; try { d = await postJSON('/api/assignments', {assignment:rec, baseVersion:record ? record.version : null}); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
    if(d.conflict && d.current) { showConflict(d.current); await refreshList(); return null; }
    if(d.error) { setNote('Not saved: ' + d.error, true); return null; }
    const firstSave = !record;
    record = d.assignment; savedCore = core(); keep.set('last-assignment', record.id);
    if(sess.aid !== record.id) await attachSession(firstSave); else refreshStatus();
    const last = (record.history || []).slice(-1)[0] || {}, unsynced = designOutOfSync();
    setNote(record.version === before ? 'Nothing had changed since the last save.' :
      (last.kind === 'created' ? 'Saved on this laptop as version 1.' :
       last.kind === 'content' ? 'Saved as version ' + record.version + '. The instructions or criteria changed: drafts written against the earlier wording are marked “possibly outdated” in Draft & review, and their review marks need redoing.' :
       last.kind === 'title' ? 'Saved as version ' + record.version + '. Name change recorded.' : 'Saved as version ' + record.version + '.') +
      (unsynced ? ' The Design step differs from Setup: use “Use this design in Setup” if feedback should follow the design.' : ''),
      last.kind === 'content' || unsynced);
    await refreshList(); updateBar(); return record;
  }
  // Saved in another tab or window after this page loaded it: nothing was written. Shingo chooses what happens.
  function showConflict(cur) {
    setNote('Not saved: this assignment was saved somewhere else (another tab or window?) as version ' + cur.version + ', ' +
      when(cur.updated) + '. Your changes are still on this page.', true);
    barNote.append(' ', button('Load version ' + cur.version + ' (drops the changes here)', '', () => applyRecord(cur)), ' ',
      button('Save mine as version ' + (cur.version + 1), '', async () => { record = cur; await save(); }));
  }
  const ready = (async () => {                          // wait for the page's courses and standards before filling fields
    let std = {}; const [s] = await Promise.all([getJSON('/api/standards').catch(() => ({})), until(() => courses().length > 0, 10000)]); std = s || {};
    await until(() => Object.keys(stdDocs()).length >= Object.keys(std).length, 3000); await sleep(30);
  })();
  async function applyRecord(rec) {
    await ready;
    if(record?.id !== rec.id) { TEAMS = null; applyTeams(); }
    record = rec; design = normalize(rec.design); sources = {...(rec.sources || {})}; teams = rec.teams || null;
    const notes = [];
    setField('#atitle', rec.title || '');
    setField('#rubric', composeRubric(rec.instructions, rec.focus));
    if(rec.length) setField('#length', rec.length);
    if(rec.term && [...$('#quarter').options].some(o => o.value === rec.term)) setField('#quarter', rec.term);
    const v = courseValueFor(rec.course);
    if(rec.course && v === '') notes.push('The saved course (' + (rec.course.label || rec.course.name) + ') isn’t in Course Hub’s list now. Choose the course again.');
    else if(rec.course && rec.course.schoolYear && schoolYear() && rec.course.schoolYear !== schoolYear())
      notes.push('Saved for ' + rec.course.schoolYear + '; matched by name to this year’s ' + optionText(v) + '.');
    setField('#course', v);
    if(rec.grade) setField('#grade', rec.grade);
    const missing = setStandards(rec.standards || []);
    if(missing.length) notes.push(missing.length + (missing.length === 1 ? ' saved standard isn’t' : ' saved standards aren’t') + ' in the current standards list.');
    savedCore = core(); keep.set('last-assignment', rec.id); pick.value = rec.id;
    renderDesign(); renderSources(); setNote(notes.join(' '), notes.length > 0); updateBar();
    await attachSession(false);
  }
  function newAssignment() {
    TEAMS = null; applyTeams();
    record = null; design = emptyDesign(); sources = {}; teams = null; savedCore = null;
    Object.assign(sess, {aid:'', version:null, path:'', sig:'', hold:false, loaded:false, err:''}); sessNote.replaceChildren(); clearCards();
    setField('#atitle', ''); setField('#rubric', ''); setStandards([]);
    keep.set('last-assignment', ''); pick.value = '';
    renderDesign(); renderSources(); setNote('New assignment. Course, grade and term are kept from before: change them if needed.'); updateBar();
  }

  // ------------------------------------------------------------------ where each Setup field came from
  const SOURCE_FIELDS = {title:'#atitle', instructions:'#rubric', course:'#course', grade:'#grade'};
  const sourceEls = {};
  for(const [k, sel] of Object.entries(SOURCE_FIELDS)) { const el = make('div', 'field-source'); $(sel).after(el); sourceEls[k] = el; }
  const gradeChoice = make('div', 'grade-choice'); sourceEls.grade.after(gradeChoice);
  function renderSources() {
    for(const k in sourceEls) { const s = sources[k]; sourceEls[k].textContent = s ? 'Source: ' + s.from + (s.at ? ' · ' + when(s.at) : '') : ''; }
  }
  const mark = (k, from) => { sources[k] = {from, at:nowIso()}; renderSources(); };
  $('#atitle').addEventListener('input', () => { if(!programmatic) mark('title', 'Edited here'); });
  $('#rubric').addEventListener('input', () => { if(!programmatic) mark('instructions', 'Edited here'); });
  $('#grade').addEventListener('change', () => { if(!programmatic) { mark('grade', 'Chosen here'); gradeChoice.replaceChildren(); } });
  $('#course').addEventListener('change', () => {       // runs after the page's own handler, which sets a one-grade course's grade
    if(programmatic) return;
    mark('course', 'Chosen here'); if(courseGrades($('#course').value).length === 1) mark('grade', 'Course Hub grades');
  });
  function applyCourseValue(v, from) {
    setField('#course', v); mark('course', from);
    if(courseGrades(v).length === 1) mark('grade', 'Course Hub grades');
  }

  // ------------------------------------------------------------------ field buttons
  function fieldButtons(label, ...btns) {
    const head = make('div', 'field-head'); head.style.marginTop = label.style.marginTop; label.style.marginTop = '0';
    label.before(head); head.append(label, ...btns);
  }
  fieldButtons($('label[for="atitle"]'), button('Get from Teams', 'from-teams', () => openTeams('title')));
  fieldButtons($('label[for="rubric"]'), button('Get from Teams', 'from-teams', () => openTeams('instructions')));
  fieldButtons($$('label[for="course"]').pop(), button('Match Teams class', 'from-teams', () => openTeams('course')));
  fieldButtons($('label[for="grade"]'), button('Use course grades', 'from-teams', useCourseGrades));
  function useCourseGrades() {                         // the grade comes from Course Hub, never from the assignment's name
    gradeChoice.replaceChildren();
    const v = $('#course').value, g = courseGrades(v);
    if(v === '') { gradeChoice.textContent = 'Choose the course first: the grade comes from Course Hub.'; return; }
    if(!g.length) { gradeChoice.textContent = 'Course Hub has no grade for this course. Choose it above.'; return; }
    if(g.length === 1) { setField('#grade', 'Grade ' + g[0]); mark('grade', 'Course Hub grades'); return; }
    gradeChoice.append(make('span', '', 'This course has grades ' + g.join(', ') + '. Which is this assignment for?'),
      ...g.map(n => button('Grade ' + n, '', () => { setField('#grade', 'Grade ' + n); mark('grade', 'Course Hub grades (you chose)'); gradeChoice.replaceChildren(); })));
  }
  // ------------------------------------------------------------------ Choose from Teams (pasted Student view for now)
  // Step 3 replaces the paste with a read-only picker driven by the local Chrome worker. Same rows, same rules.
  const TEAM = /RCS\s*-\s*[A-Z0-9]+\s*-\s*[^\[\n]+?\[\d{4}-\d{2}\]/;
  const UI_LINE = /^(Back|Instructions|Reference materials|My work|Points|No points|Turn in|Hand in|Undo turn in|Add work|Close|Student view|Edit assignment|Return|Assignments|Grading|Rubric|Student work|Feedback|Open|Download|More options|\.\.\.|⋯)$/i;
  const STOP = /^(Reference materials|My work|Points|No points|Rubric|Student work|Add work|Turn in|Hand in|Feedback|Grading)$/i;
  const PREVIEW = /preview of what this assignment/i;
  function parseTeams(text) {
    const raw = (text || '').replace(/\r/g, '').split('\n'), t = raw.map(s => s.trim());
    const dueAt = t.findIndex(s => /^Due\b/i.test(s));
    const insAt = t.findIndex((s, i) => i > dueAt && /^Instructions$/i.test(s));
    const head = dueAt >= 0 ? dueAt : insAt;
    let title = '';
    for(let i = head - 1; i >= 0; i--) if(t[i] && !UI_LINE.test(t[i]) && !PREVIEW.test(t[i]) && !TEAM.test(t[i])) { title = t[i]; break; }
    let instructions = '';
    if(insAt >= 0) {
      let end = t.length; for(let i = insAt + 1; i < t.length; i++) if(STOP.test(t[i])) { end = i; break; }
      instructions = raw.slice(insAt + 1, end).join('\n').replace(/\n{3,}/g, '\n\n').trim();
    }
    const refAt = t.findIndex(s => /^Reference materials$/i.test(s)), referenceMaterials = [];
    if(refAt >= 0) for(let i = refAt + 1; i < t.length && !STOP.test(t[i]); i++) if(t[i] && !UI_LINE.test(t[i])) referenceMaterials.push(t[i]);
    const due = dueAt >= 0 ? t[dueAt].replace(/\s*[•·]\s*Multiple submissions allowed.*$/i, '') : '';
    const team = ((text.match(TEAM) || [''])[0]).replace(/\s+/g, ' ').trim();
    return {title, due, instructions, referenceMaterials:referenceMaterials.slice(0, 12), team, found:dueAt >= 0 || insAt >= 0};
  }
  const dlg = make('dialog', 'teams-dialog'); dlg.setAttribute('aria-label', 'Choose from Teams');
  dlg.innerHTML = `<h3>Choose from Teams</h3>
    <p class="hint">The app can read your assignment list from Teams in its own Chrome window, or you can paste the assignment
      yourself. Either way nothing is changed in Teams.</p>
    <div class="teams-reader">
      <div class="teams-actions"><button type="button" class="primary teams-list-btn">List my assignments</button>
        <input class="teams-filter" aria-label="Filter the list by class or title" placeholder="Filter by class or title…" hidden>
        <span class="status teams-job-msg" role="status"></span><span class="teams-job-actions"></span></div>
      <div class="teams-list" role="list"></div>
    </div>
    <p class="hint"><b>Or paste it:</b></p>
    <ol class="hint"><li>In Teams, open the assignment and choose <b>Student view</b>.</li>
      <li>Click in the assignment, press <b>⌘A</b>, then <b>⌘C</b>.</li>
      <li>Click <b>Paste from clipboard</b>, or paste into the box below.</li></ol>
    <textarea class="teams-paste" aria-label="Text copied from Teams" placeholder="Paste the Student view text here"></textarea>
    <div class="teams-actions"><button type="button" class="teams-clip">Paste from clipboard</button>
      <button type="button" class="teams-read">Read it</button><span class="status teams-msg" role="status"></span></div>
    <label for="teams-class">Teams class <span class="hint-inline">(the Student view doesn’t show it: copy it from the
      Assignments list, e.g. “RCS - H - Q1 ICT 9 [2026-27]”)</span></label>
    <input id="teams-class" class="teams-class" list="teams-classes" autocomplete="off" placeholder="RCS - … [2026-27]">
    <datalist id="teams-classes"></datalist>
    <div class="teams-results"></div>
    <div class="teams-actions"><button type="button" class="primary teams-all" disabled>Import all assignment details</button>
      <button type="button" class="teams-save">Save assignment</button><button type="button" class="teams-close">Close</button></div>`;
  document.body.append(dlg);
  const dq = s => dlg.querySelector(s);
  const paste = dq('.teams-paste'), clsIn = dq('.teams-class'), results = dq('.teams-results'), msg = dq('.teams-msg'), allBtn = dq('.teams-all');
  let parsed = null, focusField = '', changingMatch = false;
  dq('.teams-close').onclick = () => dlg.close();
  dq('.teams-save').onclick = async () => { if(await save()) msg.textContent = 'Saved: ' + record.title + ', version ' + record.version + '.'; else msg.textContent = barNote.textContent; };
  dq('.teams-clip').onclick = async () => {
    try { paste.value = await navigator.clipboard.readText(); read(); }
    catch(e) { msg.textContent = 'The browser didn’t allow reading the clipboard. Click in the box and press ⌘V instead.'; }
  };
  dq('.teams-read').onclick = () => read();
  clsIn.addEventListener('input', () => { changingMatch = false; render(); });
  function renderClassList() { dq('#teams-classes').replaceChildren(...Object.keys(yearMap()).sort().map(c => new Option(c, c))); }
  // ---- read from Teams (a background job; read-only). The result fills the same preview rows the paste does.
  const tb = dq('.teams-list-btn'), tmsg = dq('.teams-job-msg'), tlist = dq('.teams-list'), tact = dq('.teams-job-actions'), tfilter = dq('.teams-filter');
  let tItems = [];
  const stopWait = () => { tb.disabled = false; };
  async function follow(id, onDone) {
    tact.replaceChildren(); tb.disabled = true;
    for(;;) {
      let j; try { j = (await (await fetch('/api/jobs/' + id)).json()).job; } catch(e) { await sleep(2000); continue; }
      if(!j) { tmsg.textContent = 'The app lost track of that job.'; return stopWait(); }
      if(j.state === 'queued' || j.state === 'running') { tmsg.textContent = 'Reading Teams… a Chrome window opens for this. If it asks you to sign in, do that there.'; await sleep(1500); continue; }
      if(j.state === 'waiting_for_sign_in' || j.state === 'failed' || j.state === 'interrupted') {
        tmsg.textContent = (j.state === 'waiting_for_sign_in' ? 'Waiting for you to sign in. ' : j.state === 'failed' ? 'Couldn’t read Teams: ' : 'Interrupted. ') + (j.error || '');
        tact.append(button(j.state === 'waiting_for_sign_in' ? 'I’ve signed in: resume' : 'Try again', '', async () => {
          const r = await postJSON('/api/jobs/' + id + '/resume', {}); if(r.error) { tmsg.textContent = r.error; return; } follow(id, onDone); }),
          button('Cancel', '', async () => { await postJSON('/api/jobs/' + id + '/cancel', {}); tact.replaceChildren(); tmsg.textContent = 'Cancelled.'; stopWait(); }));
        return stopWait();
      }
      if(j.state === 'cancelled') { tmsg.textContent = 'Cancelled.'; return stopWait(); }
      stopWait();
      const bad = (j.items || []).find(i => i.state === 'failed');
      if(bad) { tmsg.textContent = 'Teams didn’t show what was expected: ' + bad.error; return; }
      const res = ((j.drafts || [])[0] || {}).teams;
      if(!res) { tmsg.textContent = 'Teams gave no result.'; return; }
      return onDone(res);
    }
  }
  async function startTeams(body, onDone) {
    tmsg.textContent = 'Starting…'; tb.disabled = true;
    let d; try { d = await postJSON('/api/jobs', {type:'teams_read', ...body}); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
    if(d.error) { tmsg.textContent = d.error; return stopWait(); }
    return follow(d.job.id, onDone);
  }
  tb.onclick = () => startTeams({op:'list'}, res => { tItems = res.assignments || []; tfilter.hidden = !tItems.length; renderTeamsList();
    tmsg.textContent = tItems.length ? `Read ${tItems.length} assignments at ${when(res.read_at)}. Choose one to read.` : 'Teams showed no assignments.'; });
  tfilter.addEventListener('input', renderTeamsList);
  function renderTeamsList() {
    const q = tfilter.value.trim().toLowerCase(), cls = clsIn.value.trim().toLowerCase();
    const rows = tItems.filter(x => !q || (x.title + ' ' + x.class_name).toLowerCase().includes(q))
      .sort((a, b) => (cls && b.class_name.toLowerCase() === cls) - (cls && a.class_name.toLowerCase() === cls)).slice(0, 60);
    tlist.replaceChildren(...rows.map(x => {
      const r = make('div', 'teams-item'); r.setAttribute('role', 'listitem');
      const t = make('div'); t.append(make('strong', '', x.title), make('div', 'hint-inline', `${x.class_name} · ${x.due_heading ? x.due_heading + ', ' : ''}${x.due_text.replace(/^due\s*/i, 'due ')}` +
        (x.fractions.length ? ` · Teams counts ${x.fractions.join(' and ')} (not labelled by Teams)` : '')));
      r.append(t, button('Read this assignment', '', () => readOne(x)));
      return r;
    }));
    if(!rows.length && tItems.length) tlist.append(make('div', 'hint-inline', 'Nothing matches that filter.'));
  }
  // Three different facts, never merged: no rubric button in Student view / a rubric is attached but its descriptors weren't read / read.
  const rubricStateOf = sv => !sv.rubric_present ? 'absent' : sv.rubric_read ? 'read' : 'present_unread';
  const rubricText = st => st === 'read' ? 'present and read from Teams (kept separate from the instructions).'
    : st === 'present_unread' ? 'present in Teams (View rubric), not read: its descriptors are not in the instructions and were not imported. Check it in Teams.'
    : 'no rubric button was shown in Student view; check Teams if you expected one.';
  function readOne(x) {
    return startTeams({op:'read', class:x.class_name, title:x.title}, res => {
      const sv = res.student_view, rc = res.roster_counts;
      parsed = {title:sv.title, due:sv.due, instructions:sv.instructions, referenceMaterials:sv.reference_materials || [], team:res.source.teams_class,
                found:true, how:'read', source:res.source, counts:rc, sections:sv.sections_found, refsRead:!!sv.reference_materials_read, rubricState:rubricStateOf(sv), rubricNote:sv.rubric_note || '', rubric:sv.rubric || null};
      clsIn.value = res.source.teams_class; paste.value = '';
      tmsg.textContent = 'Read “' + sv.title + '” at ' + when(res.read_at) + '. Check the preview below against Teams before using it.';
      render();
    });
  }
  const sourceLabel = () => parsed && parsed.how === 'read' ? 'Teams (read by the app ' + when(parsed.source.read_at) + ')' : 'Teams (Student view, pasted)';
  function read() {
    parsed = paste.value.trim() ? parseTeams(paste.value) : null;
    if(parsed && parsed.team && !clsIn.value.trim()) clsIn.value = parsed.team;
    msg.textContent = !parsed ? 'Paste the Student view text first.' : !parsed.found
      ? 'This doesn’t look like a Teams Student view (no “Due” or “Instructions” line). Check each row before using it.'
      : 'Check each row, then use the ones you want, or import them all.';
    render();
  }
  const compare = (now, fromTeams) => !fromTeams ? '' : !now ? 'Empty in Setup now' : now === fromTeams ? 'Same as Setup' : 'Setup now: ' + clip(now, 120);
  const hintEl = (text, cls) => make('div', cls || 'teams-now', text);
  function row(key, label, value, extras, action) {
    const r = make('div', 'teams-row' + (key === focusField ? ' focus' : '')); r.dataset.key = key;
    const v = make('div', 'teams-val');
    if(value) v.append(make('span', '', value)); else if(value === '') v.append(make('span', 'hint-inline', 'Not in the pasted text'));
    (extras || []).filter(Boolean).forEach(e => v.append(e));
    const a = make('div', 'teams-act'); if(action) a.append(action);
    r.append(make('div', 'teams-label', label), v, a); return r;
  }
  // For the drafting controls and the review: the rubric read from Teams, whether it is switched on for drafting, and the
  // setting a draft or an approval is bound to. The switch lives in the saved record (teams.useRubric), so it is per assignment.
  const rubricRead = () => teams && teams.rubricState === 'read' && teams.rubric ? teams.rubric : null;
  const rubricCanon = r => r ? [r.title, ...r.criteria.flatMap(c => c.levels.map(l => c.name + '|' + l.level + '|' + l.descriptor))].join('\n') : '';   // same text as app.py rubric_canon
  window.feedbackAssignment = {
    rubric: rubricRead,
    useRubric: () => !!(rubricRead() && teams.useRubric),
    setUseRubric: v => { if(!rubricRead()) return; teams = {...teams, useRubric: !!v}; updateBar(); },
    setting: () => { const u = !!(rubricRead() && teams.useRubric); return {use: u, canon: u ? rubricCanon(teams.rubric) : ''}; }};
  function noteTeams() {
    teams = {...(teams || {}), className:clsIn.value.trim() || (teams && teams.className) || '', importedAt:nowIso()};
    if(parsed) Object.assign(teams, {title:parsed.title, due:parsed.due, referenceMaterials:parsed.referenceMaterials,
                                     imported:{title:parsed.title, instructions:parsed.instructions}},
                             parsed.how === 'read' ? {source:parsed.source, statusCounts:parsed.counts, referenceMaterialsRead:false, rubricState:parsed.rubricState || 'absent', rubric:parsed.rubric || null} : {});
    if(!design.teamsClass && teams.className) { design.teamsClass = teams.className; refreshers.forEach(f => f()); }
    updateBar();
  }
  function useTitle() { setField('#atitle', parsed.title); mark('title', sourceLabel()); noteTeams(); }
  function useInstructions(ask) {
    const cur = splitRubric($('#rubric').value);
    if(ask && cur.instructions && cur.instructions !== parsed.instructions &&
       !confirm('Replace the instructions in Setup with the ones from Teams?' + (cur.focus.length ? ' Your teacher-only feedback focus is kept.' : ''))) return false;
    setField('#rubric', composeRubric(parsed.instructions, cur.focus)); mark('instructions', sourceLabel()); noteTeams(); return true;
  }
  function courseRow() {
    const cls = clsIn.value.trim(), extras = [];
    if(!cls) return row('course', 'Course', null, [hintEl('Add the Teams class name above to match it to a Course Hub course.')]);
    const y = (cls.match(/\[(\d{4})-\d{2}\]/) || [])[1], sy = (schoolYear().match(/\d{4}/) || [])[0];
    if(y && sy && y !== sy) extras.push(hintEl('This class is from ' + y + '; Course Hub is showing ' + schoolYear() + '.', 'teams-now warn'));
    if(!schoolYear()) return row('course', 'Course', null, [hintEl('Course Hub isn’t connected (the course list is the built-in copy), so a match can’t be saved. Choose the course in Setup.', 'teams-now warn')]);
    const m = mappedCourse(cls), mv = m ? courseValueFor(m) : '';
    if(m && mv !== '' && !changingMatch) {
      extras.push(hintEl($('#course').value === mv ? 'Same as Setup' : $('#course').value === '' ? 'Empty in Setup now' : 'Setup now: ' + optionText($('#course').value)));
      const change = button('Change match', 'linkish', () => { changingMatch = true; render(); });
      extras.push(change);
      return row('course', 'Course', optionText(mv) + ' (your saved match, ' + when(m.confirmed) + ')', extras,
        $('#course').value === mv ? null : button('Use', '', () => { applyCourseValue(mv, 'Course Hub (saved match for this Teams class)'); noteTeams(); render(); }));
    }
    if(m && mv === '') extras.push(hintEl('Your saved match (' + (m.label || m.name) + ') isn’t in Course Hub’s list now. Choose again.', 'teams-now warn'));
    const sel = make('select', 'teams-course'); sel.setAttribute('aria-label', 'Course Hub course for this Teams class');
    sel.append(...[...$('#course').children].map(n => n.cloneNode(true)));
    sel.options[0].textContent = 'Choose the Course Hub course…';
    const suggested = suggestCourse(cls); sel.value = mv || suggested || '';
    extras.push(hintEl(suggested ? 'Suggested from the class name. Check it, then confirm.' : 'No single course matches this class name. Choose one, then confirm.'), sel);
    const confirmBtn = button('Confirm match', 'primary', async () => {
      if(sel.value === '') { msg.textContent = 'Choose a course first.'; return; }
      let d; try { d = await postJSON('/api/class-map', {schoolYear:schoolYear(), className:cls, course:courseKey(sel.value)}); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
      if(d.error) { msg.textContent = 'Match not saved: ' + d.error; return; }
      classMap = d.map || classMap; changingMatch = false; renderClassList();
      applyCourseValue(sel.value, 'Course Hub (match you confirmed)'); noteTeams(); syncClassPicker();
      msg.textContent = 'Saved: ' + cls + ' → ' + optionText(sel.value) + ' for ' + schoolYear() + '.'; render();
    });
    return row('course', 'Course', null, extras, confirmBtn);
  }
  function gradeRow() {
    const v = $('#course').value, g = courseGrades(v), cur = $('#grade').value;
    if(v === '') return row('grade', 'Grade', null, [hintEl('Match the course first: the grade comes from Course Hub, never from the assignment name.')]);
    if(!g.length) return row('grade', 'Grade', null, [hintEl('Course Hub has no grade for this course. Set it in Setup.')]);
    if(g.length === 1) { const val = 'Grade ' + g[0];
      return row('grade', 'Grade', val + ' (Course Hub)', [hintEl(compare(cur, val))],
        cur === val ? null : button('Use', '', () => { setField('#grade', val); mark('grade', 'Course Hub grades'); render(); })); }
    const sel = make('select', 'teams-grade'); sel.setAttribute('aria-label', 'Grade for this assignment');
    sel.append(new Option('Choose…', ''), ...g.map(n => new Option('Grade ' + n, 'Grade ' + n)));
    if(g.map(n => 'Grade ' + n).includes(cur)) sel.value = cur;
    return row('grade', 'Grade', null, [hintEl('This course has grades ' + g.join(', ') + '. Which is this assignment for? (Setup now: ' + cur + ')'), sel],
      button('Use', '', () => { if(!sel.value) { msg.textContent = 'Choose the grade first.'; return; }
        setField('#grade', sel.value); mark('grade', 'Course Hub grades (you chose)'); render(); }));
  }
  // The rubric as Teams showed it (criteria, then four levels each). Kept apart from the instructions: not merged into them,
  // not typed into any field. The teacher compares it with Teams.
  const rubricLines = r => r.criteria.map(c => c.name + '\n' + c.levels.map(l => '  ' + l.level + ': ' + l.descriptor).join('\n')).join('\n\n');
  function rubricRow(r) {
    const total = r.criteria.reduce((n, c) => n + c.levels.length, 0);
    const row_ = row('rubric', 'Rubric', r.title + ' (' + r.criteria.length + ' criteria: ' + r.criteria.map(c => c.name).join(', ') + '; ' + total + ' descriptors)',
      [hintEl('Read from Teams’ View rubric dialog, exactly as shown. Kept separate from the instructions and not imported into any field.')]);
    const span = row_.querySelector('.teams-val > span'), short = span.textContent;
    const tog = make('button', 'linkish', 'Show full rubric'); tog.type = 'button'; tog.setAttribute('aria-expanded', 'false');
    tog.onclick = () => {
      const open = tog.getAttribute('aria-expanded') !== 'true';
      tog.setAttribute('aria-expanded', String(open)); tog.textContent = open ? 'Show less' : 'Show full rubric';
      span.textContent = open ? short + '\n\n' + rubricLines(r) : short; span.classList.toggle('teams-full', open);
    };
    span.after(make('br'), tog);
    return row_;
  }
  function render() {
    const rows = [];
    if(parsed) {
      const curTitle = $('#atitle').value.trim(), cur = splitRubric($('#rubric').value).instructions;
      rows.push(row('title', 'Assignment name', parsed.title, [hintEl(compare(curTitle, parsed.title))],
        parsed.title && curTitle !== parsed.title ? button('Use', '', () => { useTitle(); render(); }) : null));
      if(parsed.due) rows.push(row('due', 'Due', parsed.due, [hintEl('For reference: the due date stays in Teams.')]));
      const refs = parsed.referenceMaterials.length
        ? hintEl('Reference materials, listed by name only (not opened or read, and not added to the instructions): ' + parsed.referenceMaterials.join('; ')) : null;
      const insRow = row('instructions', 'Instructions', parsed.instructions ? clip(parsed.instructions, 240) + '  (' + parsed.instructions.length + ' characters)' : '',
        [hintEl(compare(cur, parsed.instructions)), refs],
        parsed.instructions && cur !== parsed.instructions ? button('Use', '', () => { if(useInstructions(true)) render(); }) : null);
      if(parsed.instructions && parsed.instructions.length > 240) {      // so the whole text can be compared with Teams
        const span = insRow.querySelector('.teams-val > span'), short = span.textContent, n = parsed.instructions.length;
        const tog = make('button', 'linkish', 'Show full instructions'); tog.type = 'button'; tog.setAttribute('aria-expanded', 'false');
        tog.onclick = () => {
          const open = tog.getAttribute('aria-expanded') !== 'true';
          tog.setAttribute('aria-expanded', String(open));
          tog.textContent = open ? 'Show less' : 'Show full instructions';
          span.textContent = open ? parsed.instructions : short;
          span.classList.toggle('teams-full', open);
        };
        span.after(make('br'), tog);
      }
      rows.push(insRow);
    }
    if(parsed && parsed.how === 'read' && parsed.rubricState === 'read' && parsed.rubric) rows.push(rubricRow(parsed.rubric));
    if(parsed && parsed.how === 'read') {
      const c = parsed.counts || {}, st = c.statuses || {}, total = (c.to_return || 0) + (c.returned || 0);
      rows.push(row('counts', 'Status counts', total ? total + ' students: ' + Object.entries(st).map(([k, v]) => v + ' ' + k.toLowerCase()).join(', ') + (c.returned ? ', ' + c.returned + ' returned' : '') : 'Not read',
        [c.consistent === false ? hintEl('The rows didn’t add up to the “results found” line Teams showed. Don’t rely on these counts.', 'teams-now warn') : hintEl('Counts only: no student names or per-student statuses are read yet.')]));
      rows.push(row('source', 'Source', 'Class ' + parsed.source.class_id.slice(0, 8) + '…, assignment ' + parsed.source.assignment_id.slice(0, 8) + '…',
        [hintEl('Read ' + when(parsed.source.read_at) + ' from Teams Assignments. Sections found: ' + (parsed.sections || []).join(', ') + '. Rubric: ' + rubricText(parsed.rubricState) + (parsed.rubricNote ? ' ' + parsed.rubricNote : ''))]));
    }
    if(!parsed && teams && teams.source && teams.rubricState)
      rows.push(row('saved', 'Last read from Teams', when(teams.source.read_at || teams.importedAt || ''), [hintEl('Rubric: ' + rubricText(teams.rubricState))]));
    rows.push(courseRow(), gradeRow());
    results.replaceChildren(...rows);
    allBtn.disabled = !(parsed && (parsed.title || parsed.instructions));
    const f = results.querySelector('.focus'); if(f && dlg.open) f.scrollIntoView({block:'nearest'});
  }
  allBtn.onclick = () => {
    if(!parsed) return;
    const curTitle = $('#atitle').value.trim(), cur = splitRubric($('#rubric').value).instructions, replacing = [];
    if(parsed.title && curTitle && curTitle !== parsed.title) replacing.push('the assignment name');
    if(parsed.instructions && cur && cur !== parsed.instructions) replacing.push('the instructions (your teacher-only feedback focus is kept)');
    if(replacing.length && !confirm('Replace ' + replacing.join(' and ') + ' with what Teams shows?')) return;
    if(parsed.title) useTitle();
    if(parsed.instructions) useInstructions(false);
    const todo = [], cls = clsIn.value.trim(), m = mappedCourse(cls), mv = m ? courseValueFor(m) : '';
    if(mv !== '') { if($('#course').value !== mv) applyCourseValue(mv, 'Course Hub (saved match for this Teams class)'); }
    else todo.push(cls ? 'confirm the course match' : 'add the Teams class name, then confirm the course');
    noteTeams();
    const g = courseGrades($('#course').value);
    if(mv !== '' && g.length === 1) { setField('#grade', 'Grade ' + g[0]); mark('grade', 'Course Hub grades'); }
    else if(mv !== '' && g.length > 1) todo.push('choose the grade (this course has grades ' + g.join(', ') + ')');
    else if(mv !== '') todo.push('set the grade in Setup (Course Hub has none for this course)');
    render();
    msg.textContent = 'Imported the ' + [parsed.title && 'name', parsed.instructions && 'instructions'].filter(Boolean).join(' and ') +
      (mv !== '' ? ' and the course' : '') + '. ' + (todo.length ? 'Still to do: ' + todo.join('; ') + '. ' : '') + 'Save the assignment when it looks right.';
  };
  function openTeams(field) {
    focusField = field || ''; changingMatch = false;
    if(!clsIn.value.trim()) clsIn.value = (teams && teams.className) || design.teamsClass || '';
    renderClassList();
    if(paste.value.trim()) read(); else { parsed = null; msg.textContent = ''; render(); }
    dlg.showModal();
    (field === 'course' && !paste.value.trim() ? clsIn : paste).focus();
  }
  // ------------------------------------------------------------------ Design assignment
  const panel = $('[data-panel="design"]');
  panel.append(make('p', 'hint', 'Plan a new assignment here, then copy it or create an unpublished Teams draft. Feedback later uses the same ' +
    'saved assignment, so the wording, criteria and standards match. Student-facing text and your teacher-only notes are kept apart: ' +
    'only the student-facing part is offered for copying.'));
  const dz = make('div', 'design'); panel.append(dz);
  const refreshers = [];
  const card = (title, sub, tag) => {
    const c = make('section', 'card' + (tag === 'teacher' ? ' teacher-only' : '')), h = make('h3', '', title);
    if(tag) h.append(make('span', tag === 'teacher' ? 'teacher-tag' : 'student-tag', tag === 'teacher' ? 'Teacher only' : 'Student-facing'));
    c.append(h); if(sub) c.append(make('p', 'hint', sub)); dz.append(c); return c;
  };
  let uid = 0;
  function field(parent, label, el, hint) {
    el.id = el.id || 'd-f' + (++uid);
    const l = make('label', 'd-label', label); l.htmlFor = el.id; if(hint) l.append(make('span', 'hint-inline', ' ' + hint));
    const w = make('div', 'd-field'); w.append(l, el); parent.append(w); return el;
  }
  const input = ph => { const i = make('input'); if(ph) i.placeholder = ph; return i; };
  const area = (ph, rows) => { const t = make('textarea'); if(ph) t.placeholder = ph; if(rows) t.style.minHeight = rows * 26 + 'px'; return t; };
  const select = opts => { const s = make('select'); s.append(...opts.map(([v, t]) => new Option(t, v))); return s; };
  function bind(el, get, set) {                         // a design field: edits go into the record's design
    const put = () => { set(el.value); changed(); };
    el.addEventListener('input', put); el.addEventListener('change', put); refreshers.push(() => { el.value = get(); });
    return el;
  }

  // Context: mirrors of Setup's fields, so there is only one value for each
  const ctx = card('Context', 'The same fields as Setup.');
  const ctxGrid = make('div', 'design-grid'); ctx.append(ctxGrid);
  const dTitle = field(ctxGrid, 'Assignment name', input('e.g. Task 3: Prototype & Test'));
  const dClass = field(ctxGrid, 'Intended Teams class', make('select'));
  dClass.id = 'design-teams-class';
  const classHint = make('p', 'hint');
  const classFind = button('Choose class from Teams…', '', () => openTeams('course'));
  dClass.after(classHint, classFind);
  function syncClassPicker() {
    const value = $('#course').value;
    const matches = Object.keys(yearMap()).filter(cls => value !== '' && courseValueFor(yearMap()[cls]) === value).sort();
    let selected = design.teamsClass || '';
    // A known class belonging to another course must not follow a course switch.
    if(selected && yearMap()[selected] && !matches.includes(selected)) selected = '';
    if(!selected && matches.length === 1) selected = matches[0];
    dClass.replaceChildren(new Option(matches.length ? 'Choose the Teams class…' : 'No confirmed Teams class for this course', ''));
    matches.forEach(cls => dClass.add(new Option(cls, cls)));
    if(selected && !matches.includes(selected)) dClass.add(new Option(selected + ' (saved; match not confirmed)', selected));
    dClass.value = selected; design.teamsClass = selected;
    classHint.textContent = matches.length === 1 ? 'Filled from your confirmed Course Hub → Teams match.'
      : matches.length > 1 ? 'Several Teams classes match this course. Choose the intended class.'
      : 'Choose the class from Teams and confirm its Course Hub match. The app will remember it.';
  }
  dClass.addEventListener('change', () => { design.teamsClass = dClass.value; changed(); });
  const dCourse = field(ctxGrid, 'Course (Course Hub)', make('select')), dGrade = field(ctxGrid, 'Grade', make('select'));
  const dTerm = field(ctxGrid, 'Term', make('select'));
  function syncMirrors() {
    const clone = (to, from) => { to.replaceChildren(...[...$(from).children].map(n => n.cloneNode(true))); to.value = $(from).value; };
    dTitle.value = $('#atitle').value; clone(dCourse, '#course'); clone(dGrade, '#grade'); clone(dTerm, '#quarter'); clone(dLength, '#length'); syncClassPicker();
  }
  const mirror = (el, sel, after) => el.addEventListener('change', () => { $(sel).value = el.value; fire($(sel), 'change'); syncMirrors(); if(after) after(); changed(); });
  dTitle.addEventListener('input', () => { $('#atitle').value = dTitle.value; fire($('#atitle'), 'input', 'change'); changed(); });
  $('#course').addEventListener('change', () => { syncClassPicker(); });
  mirror(dCourse, '#course', () => renderCriteria()); mirror(dGrade, '#grade'); mirror(dTerm, '#quarter', () => renderCriteria());

  // Student task
  const task = card('Student task', null, 'student');
  bind(field(task, 'Purpose', area('Why this task matters, or what students will learn from it.', 3)), () => design.purpose, v => design.purpose = v);
  bind(field(task, 'Directions', area('What students do, step by step. Use a command term (describe, explain, justify…) only where you want that kind of thinking.', 5)),
    () => design.directions, v => design.directions = v);
  const termsNote = make('div', 'status'); task.append(termsNote);
  bind(field(task, 'Required evidence', area('What students hand in, one item per line (e.g. five “How might we” questions).', 3), 'one per line'),
    () => design.evidence, v => design.evidence = v);

  // Success criteria, each linked to a learning standard
  const crit = card('Success criteria', 'Students see these as a checklist and every draft is checked against them. Keep each to 8 words or fewer.', 'student');
  const critList = make('div', 'd-crits'); crit.append(critList);
  const critNote = make('div', 'status'); crit.append(button('+ Add criterion', '', () => { design.criteria.push({text:'', evidence:'', standard:''}); renderCriteria(); changed(); critList.querySelector('.d-crit:last-child input')?.focus(); }), critNote);
  function renderCriteria() {
    const labels = stdLabels();
    critList.replaceChildren(...design.criteria.map((c, i) => {
      const r = make('div', 'd-crit');
      const t = input('Criterion'), e = input('How students show it'), s = make('select');
      t.setAttribute('aria-label', 'Criterion ' + (i + 1)); e.setAttribute('aria-label', 'How students show criterion ' + (i + 1));
      s.setAttribute('aria-label', 'Learning standard for criterion ' + (i + 1));
      s.append(new Option('No standard linked', ''), ...labels.map(l => new Option(l, l)));
      if(c.standard && !labels.includes(c.standard)) s.append(new Option(c.standard + ' (not in this course’s list)', c.standard));
      t.value = c.text; e.value = c.evidence; s.value = c.standard;
      const w = make('div', 'd-crit-warn warn');
      const check = () => { const p = [];
        if(words(c.text) > 8) p.push('Over 8 words, so drafts can’t be checked against it.');
        if(c.text.trim() && !c.evidence.trim()) p.push('Say how students show it.');
        if(c.text.trim() && !c.standard) p.push('Link a standard.');
        w.textContent = p.join(' '); };
      t.oninput = () => { c.text = t.value; check(); changed(); }; e.oninput = () => { c.evidence = e.value; check(); changed(); };
      s.onchange = () => { c.standard = s.value; check(); changed(); };
      const x = button('Remove', 'd-remove', () => { design.criteria.splice(i, 1); renderCriteria(); changed(); });
      x.setAttribute('aria-label', 'Remove criterion ' + (i + 1));
      check(); r.append(t, e, s, x, w); return r;
    }));
    if(!design.criteria.length) critList.append(make('p', 'status', labels.length ? 'No criteria yet.' : 'No criteria yet. Choose the course to link criteria to its standards.'));
  }

  // Submission setup
  const sub = card('Submission setup', null, 'student');
  const subGrid = make('div', 'design-grid'); sub.append(subGrid);
  const dType = bind(field(subGrid, 'Students submit', select([['notebook', 'On a Class Notebook page'], ['teams', 'A file or link in Teams'], ['both', 'Both'], ['forms', 'Microsoft Forms quiz']])),
    () => design.submission.type, v => design.submission.type = v);
  const dSection = bind(field(subGrid, 'Notebook section', input('Homework')), () => design.submission.section, v => design.submission.section = v);
  const dPage = bind(field(subGrid, 'Notebook page title', input('Same as the assignment name'), '(distribute the page so every copy has this title)'),
    () => design.submission.page, v => design.submission.page = v);
  const dFiles = bind(field(subGrid, 'Required files', input('e.g. one PDF, or a link to your project')), () => design.submission.files, v => design.submission.files = v);
  const dCompletion = bind(field(sub, 'How students show they’re done', input("When you're finished, click Turn in in Teams.")), () => design.submission.completion, v => design.submission.completion = v);

  const formsNote = make('p', 'hint', 'Teacher: export quiz responses from Microsoft Forms to Excel. Forms response import is not built yet; selecting this type only saves the submission setup.');
  sub.append(formsNote);
  dType.addEventListener('change', () => {
    const teamsDone = "When you're finished, click Turn in in Teams.", formsDone = 'Complete the quiz and click Submit in Microsoft Forms.';
    if(design.submission.type === 'forms' && design.submission.completion === teamsDone) design.submission.completion = formsDone;
    else if(design.submission.type !== 'forms' && design.submission.completion === formsDone) design.submission.completion = teamsDone;
    dCompletion.value = design.submission.completion; changed();
  });

  // Feedback setup (teacher only)
  const fb = card('Feedback setup', 'Used for drafting feedback and the MySchool comment. None of this is copied for Teams.', 'teacher');
  const fbGrid = make('div', 'design-grid'); fb.append(fbGrid);
  const dLength = field(fbGrid, 'Feedback length', make('select')); mirror(dLength, '#length');
  bind(field(fbGrid, 'MySchool comment', select([['short', 'A short comment (1–2 sentences)'], ['full', 'The same text as the Teams feedback'], ['none', 'No comment, level only']])),
    () => design.feedback.myschool, v => design.feedback.myschool = v);
  bind(field(fb, 'Feedback must address', area('One per line, 8 words or fewer each (e.g. Names a specific client need).', 3), 'drafts are checked for each'),
    () => design.feedback.mustAddress, v => design.feedback.mustAddress = v);
  const focusNote = make('div', 'status warn'); fb.append(focusNote);
  bind(field(fb, 'MySchool comment guidance', input('e.g. Name the level and one next step.')), () => design.feedback.myschoolGuidance, v => design.feedback.myschoolGuidance = v);
  bind(field(fb, 'Notes for marking', area('Anything you want in front of you while reviewing: common mistakes, what Extending looks like…', 3)),
    () => design.teacherNotes, v => design.teacherNotes = v);

  // Preview: student-facing text for Teams, and the teacher-only brief
  const pv = card('Preview');
  const grid = make('div', 'preview-grid'); pv.append(grid);
  const stuCol = make('div', 'preview-student'), teaCol = make('div', 'preview-teacher teacher-only');
  stuCol.append(make('span', 'student-tag', 'For students · goes into Teams'));
  const pTitle = make('pre', 'd-prev-title'), pIns = make('pre', 'd-prev-ins');
  stuCol.append(pTitle, pIns);
  const stuActs = make('div', 'design-actions'); stuCol.append(stuActs);
  stuActs.append(button('Copy title', '', e => copy($('#atitle').value.trim(), e.target)),
    button('Copy instructions', '', e => copy(studentInstructions(), e.target)));
  const createDraft = button('Create draft in Teams', '', async () => {
    draftMessage.textContent = '';
    if(!designHasContent(design) || !design.teamsClass || !$('#atitle').value.trim()) {
      setNote('Add a title, student task and intended Teams class first.', true); return;
    }
    if(design.submission.type === 'forms') { setNote('Forms quizzes need New quiz in Teams. This prototype creates ordinary assignments only.', true); return; }
    useInSetup();
    if(splitRubric($('#rubric').value).instructions !== studentInstructions().trim()) {
      setNote('Use this design in Setup before creating the draft.', true); return;
    }
    const saved = await save(); if(!saved) { setNote('Save the assignment and resolve any conflict first.', true); return; }
    draftExisting = false; draftOwner = saved.id; draftVersion = saved.version; draftSnapshot = JSON.stringify(currentRecord());
    draftPreview.textContent = saved.design.teamsClass + '\n\n' + saved.title + '\n\n' + saved.instructions;
    draftConfirm.checked = false; draftGo.disabled = true;
    draftMessage.textContent = 'Creates an unpublished ordinary assignment. Only title and instructions are copied. Teams defaults remain for dates, points and recipients; review those in Teams before publishing. Files, notebook links and rubric objects are not attached. Teacher-only notes stay here.';
    draftDialog.showModal();
    try {
      const previous = (await getJSON('/api/jobs?assignment=' + encodeURIComponent(saved.id))).jobs || [];
      let receipt = null;
      for(const j of previous.filter(j => j.type === 'teams_create' && j.state === 'completed')) {
        const full = (await getJSON('/api/jobs/' + j.id)).job;
        receipt = full?.drafts?.find(d => d.teams_create?.verified)?.teams_create;
        if(receipt) break;
      }
      if(record?.id === saved.id && draftDialog.open && receipt) {
        draftExisting = true; draftConfirm.checked = false; draftGo.disabled = true;
        draftMessage.textContent = 'Previously verified unpublished draft: ' + receipt.class + ' → ' + receipt.title + '. Later local changes are not sent again. Review the existing draft in Teams. ' + receipt.url;
      }
    } catch(e) { /* Server duplicate protection remains authoritative if history is unavailable. */ }
  });
  stuActs.append(createDraft);
  const draftDialog = make('dialog', 'teams-dialog'); draftDialog.setAttribute('aria-label', 'Create Teams draft');
  draftDialog.append(make('h3', '', 'Create an unpublished Teams draft'));
  const draftPreview = make('pre', 'teams-text-full'), draftMessage = make('p', 'status'); draftMessage.setAttribute('role','status');
  const draftRecovery = make('input'); draftRecovery.type = 'url'; draftRecovery.setAttribute('aria-label','Existing empty draft URL (optional recovery)');
  const draftRecoveryLabel = make('label', '', 'Recover a failed attempt: paste its existing empty Teams draft URL (optional). This reuses that draft; it will not create another.'); draftRecoveryLabel.append(draftRecovery);
  const draftConfirm = make('input'); draftConfirm.type = 'checkbox';
  const draftLabel = make('label', '', 'I checked the class, title and full student-facing instructions. Create an unpublished draft.'); draftLabel.prepend(draftConfirm);
  let draftOwner = '', draftVersion = 0, draftSnapshot = '', draftBusy = false, draftExisting = false;
  const draftGo = button('Create unpublished draft', 'primary', async () => {
    if(draftBusy || draftExisting || !draftConfirm.checked) return;
    if(record?.id !== draftOwner || JSON.stringify(currentRecord()) !== draftSnapshot || record.version !== draftVersion) {
      draftGo.disabled = true; draftMessage.textContent = 'Assignment changed. Close and review a fresh preview.'; return;
    }
    draftBusy = true; draftGo.disabled = true; draftConfirm.disabled = true; createDraft.disabled = true;
    try {
      const d = await postJSON('/api/jobs', {type:'teams_create', assignment:draftOwner, version:draftVersion, confirm:true, recovery_url:draftRecovery.value.trim()});
      if(d.error) throw Error(d.error);
      for(;;) {
        const out = await getJSON('/api/jobs/' + d.job.id), j = out.job;
        if(!j) throw Error('Job unavailable. Check Teams Drafts before trying again.');
        if(['queued','running'].includes(j.state)) { draftMessage.textContent = 'Chrome is creating the draft. Nothing will be published.'; await sleep(1200); continue; }
        const result = j.drafts?.find(x => x.teams_create)?.teams_create;
        if(j.state !== 'completed' || !result?.verified) throw Error(j.items?.find(x => x.state === 'failed')?.error || j.error || 'Creation stopped. Check Teams Drafts.');
        draftMessage.textContent = 'Verified in Teams Drafts: ' + result.class + ' → ' + result.title + '. Title and full instructions match. Unpublished; review dates, recipients, files and rubric in Teams.';
        break;
      }
    } catch(e) { draftMessage.textContent = e.message; }
    finally { draftBusy = false; createDraft.disabled = false; draftConfirm.disabled = false; draftGo.disabled = true; }
  });
  draftGo.disabled = true;
  draftConfirm.onchange = () => { draftGo.disabled = draftBusy || draftExisting || !draftConfirm.checked; };
  draftRecovery.oninput = () => { draftConfirm.checked = false; draftGo.disabled = true; };
  draftDialog.append(draftPreview, draftMessage, draftRecoveryLabel, draftLabel, draftGo, button('Close', '', () => draftDialog.close())); document.body.append(draftDialog);
  $('#asg-pick').addEventListener('change', () => { if(!draftBusy) { draftDialog.close(); draftGo.disabled = true; draftOwner = ''; } });

  teaCol.append(make('span', 'teacher-tag', 'Teacher only · stays on this laptop'));
  const pBrief = make('pre', 'd-brief'); teaCol.append(pBrief);
  grid.append(stuCol, teaCol);
  const syncNote = make('div', 'status d-sync'); pv.append(syncNote);
  const useBtn = button('Use this design in Setup', 'primary', useInSetup);
  const startBtn = button('Start from Setup’s instructions', '', () => {
    design.directions = splitRubric($('#rubric').value).instructions; renderDesign(); changed();
  });
  const pvActs = make('div', 'design-actions'); pvActs.append(useBtn, startBtn, button('Save assignment', '', () => save())); pv.append(pvActs);

  function designStandards() { return [...new Set(design.criteria.map(c => c.standard).filter(Boolean))]; }
  function studentInstructions() {
    const d = design, s = d.submission, parts = [], crits = d.criteria.filter(c => c.text.trim());
    if(d.purpose.trim()) parts.push(d.purpose.trim());
    if(d.directions.trim()) parts.push(d.directions.trim());
    if(lines(d.evidence).length) parts.push('What to hand in:\n' + lines(d.evidence).map(x => '- ' + x).join('\n'));
    const page = s.page.trim() || $('#atitle').value.trim();
    const where = [];
    if(['notebook', 'both'].includes(s.type)) where.push('Class Notebook → ' + (s.section.trim() || 'Homework') + ' → "' + (page || 'the page your teacher sent') + '". Use the page your teacher sent you and keep its title.');
    if(['teams', 'both'].includes(s.type)) where.push('attach your work to this assignment in Teams' + (s.files.trim() ? ' (' + s.files.trim() + ')' : '') + '.');
    if(s.type === 'forms') where.push('complete the Microsoft Forms quiz linked in this Teams assignment.');
    parts.push('Where to submit: ' + where.join(' Also ') + (s.completion.trim() ? '\n' + s.completion.trim() : ''));
    if(crits.length) parts.push('Success criteria:\n' + crits.map(c => '- ' + c.text.trim()).join('\n'));
    const shows = crits.filter(c => c.evidence.trim());
    if(shows.length) parts.push('What to show for each:\n' + shows.map(c => '- ' + c.text.trim() + ': ' + c.evidence.trim()).join('\n'));
    const stds = designStandards();
    if(stds.length) parts.push('Assessed against: ' + stds.join('; ') + ' (levels are recorded in MySchool).');
    return parts.join('\n\n');
  }
  function teacherBrief() {
    const d = design, out = ['ASSESSMENT BRIEF (teacher only, not for Teams)', ($('#atitle').value.trim() || '(no name yet)'),
      [optionText($('#course').value), $('#grade').value, $('#quarter').value].filter(Boolean).join(' · ')];
    const crits = d.criteria.filter(c => c.text.trim());
    if(crits.length) out.push('', 'Criteria → what to look for → standard', ...crits.map(c => '- ' + c.text.trim() + ' → ' + (c.evidence.trim() || '?') + ' → ' + (c.standard || 'no standard linked')));
    if(lines(d.feedback.mustAddress).length) out.push('', 'Feedback must address', ...lines(d.feedback.mustAddress).map(x => '- ' + x));
    const len = $('#length').selectedOptions[0]; out.push('', 'Feedback length: ' + (len ? len.textContent : ''));
    out.push('MySchool comment: ' + ({short:'short (1–2 sentences)', full:'same text as the Teams feedback', none:'none, level only'}[d.feedback.myschool] || d.feedback.myschool) +
      (d.feedback.myschoolGuidance.trim() ? ': ' + d.feedback.myschoolGuidance.trim() : ''));
    if(d.teacherNotes.trim()) out.push('', 'Notes for marking', d.teacherNotes.trim());
    return out.join('\n');
  }
  function designOutOfSync() {
    if(!designHasContent(design)) return false;
    const now = splitRubric($('#rubric').value);
    return now.instructions !== studentInstructions() || JSON.stringify(now.focus) !== JSON.stringify(lines(design.feedback.mustAddress));
  }
  function useInSetup() {
    if(!designHasContent(design)) { syncNote.textContent = 'Fill in the design first.'; return; }
    const text = composeRubric(studentInstructions(), lines(design.feedback.mustAddress)), cur = $('#rubric').value.trim();
    if(cur && cur !== text && !confirm('Replace the instructions in Setup with this design? Drafts written against the old wording will be marked “possibly outdated”.')) return;
    setField('#rubric', text); mark('instructions', 'Design step');
    const stds = designStandards(); if(stds.length) setStandards(stds);
    changed(); setNote('Setup now uses this design. Save the assignment to keep it.');
  }
  window.feedbackAssignment.prepareDesign = async () => {
    if(!designHasContent(design) || !$('#atitle').value.trim()) throw Error('Add a title and student task in Design first.');
    useInSetup();
    if(splitRubric($('#rubric').value).instructions !== studentInstructions().trim()) throw Error('Use this design in Setup before creating the assignment.');
    const saved = await save();
    if(!saved) throw Error('Save the assignment and resolve any conflict first.');
    return saved;
  };

  // Teacher-only brief at the top of Draft & review
  const reviewPanel = $('[data-panel="review"]');
  const brief = make('details', 'card brief-card teacher-only'), briefText = make('pre', '');
  brief.append(make('summary', '', 'Assessment brief (teacher only)'), briefText);
  reviewPanel.querySelector('h2').after(brief);

  function changed() {
    const d = design, ins = studentInstructions(), has = designHasContent(d);
    pTitle.textContent = $('#atitle').value.trim() || '(assignment name)';
    pIns.textContent = has ? ins : 'The student-facing instructions appear here as you fill in the design.';
    pBrief.textContent = teacherBrief(); briefText.textContent = pBrief.textContent; brief.hidden = !has;
    const terms = termsIn($('#atitle').value + '\n' + ins);
    termsNote.textContent = terms.length ? 'Command terms in this task: ' + terms.join(', ') + '. Feedback will look for that kind of thinking.'
      : 'No command terms yet. That’s fine unless you want feedback on a particular kind of thinking (explain, justify…).';
    const crits = d.criteria.filter(c => c.text.trim());
    critNote.textContent = !crits.length ? 'Add at least one criterion: feedback uses them as its checklist.'
      : crits.length + (crits.length === 1 ? ' criterion' : ' criteria') + '; ' + designStandards().length + ' linked standard' + (designStandards().length === 1 ? '' : 's') + '.';
    critNote.classList.toggle('warn', !crits.length);
    const long = lines(d.feedback.mustAddress).filter(x => words(x) > 8);
    focusNote.textContent = long.length ? 'Over 8 words, so drafts can’t be checked for: ' + long.map(x => '“' + x + '”').join(', ') : '';
    dSection.closest('.d-field').hidden = dPage.closest('.d-field').hidden = !['notebook', 'both'].includes(d.submission.type);
    dFiles.closest('.d-field').hidden = !['teams', 'both'].includes(d.submission.type);
    formsNote.hidden = d.submission.type !== 'forms';
    dPage.placeholder = $('#atitle').value.trim() || 'Same as the assignment name';
    const setupIns = splitRubric($('#rubric').value).instructions;
    syncNote.textContent = !has ? 'No design yet.' + (setupIns ? ' This assignment’s instructions are in Setup (for example, imported from Teams): start from them, or leave the design empty.' : '')
      : designOutOfSync() ? 'Setup’s instructions are different from this design. Feedback uses Setup’s version: click “Use this design in Setup” to switch.'
      : 'Setup uses this design.';
    syncNote.classList.toggle('warn', has && designOutOfSync());
    useBtn.disabled = !has; startBtn.hidden = has || !setupIns;
    updateBar();
  }
  function renderDesign() { refreshers.forEach(f => f()); syncMirrors(); renderCriteria(); changed(); }
  $$('nav.steps .step')[0].addEventListener('click', () => { syncMirrors(); renderCriteria(); changed(); });

  // ------------------------------------------------------------------ assessment session (saved automatically)
  // Student work, drafts, levels, notes, MySchool comments, review approvals and posting ticks are saved to
  // manifest.json in the assignment's folder under Assessment (outside git), a couple of seconds after each change.
  // An approval is saved with the exact values that were reviewed; whether it still holds is worked out again every
  // time the session is opened, so a change to anything reviewed (or to the assignment's instructions) voids it.
  const ws = window.feedbackWorkspace;
  const sess = {aid:'', version:null, path:'', sig:'', hold:false, loaded:false, busy:false, at:'', err:'', status:null};
  const sessLine = make('div', 'asg-session'); sessLine.setAttribute('role', 'status');
  barStatus.after(sessLine);
  const sessNote = make('div', 'sess-note'); sessLine.after(sessNote);
  function collect() {
    return ws.cards().map(c => {
      const out = c.querySelector('.out:not(.err)'), a = ws.approvals.get(c), p = ws.posted.get(c) || {};
      const tick = x => x ? {bound:x.bound, at:x.at} : null;
      return {student_id:c.dataset.rid || '', name:c.querySelector('.name').value, orig:c.dataset.orig || '',
        grade:c.querySelector('.sgrade').value, work:c.querySelector('.work').value, notes:c.querySelector('.notes').value,
        level:c.querySelector('.level').value, feedback:out ? out.innerText : '',
        myschool_comment:c.querySelector('.myschool-comment')?.value || '', basis:out ? (ws.draftBasis.get(out) || '') : '',
        approval:a ? {bound:a.bound, at:a.reviewed_at} : null, posting:{teams:tick(p.teams), myschool:tick(p.myschool)}};
    }).filter(s => s.name.trim() || s.work.trim() || s.feedback.trim());
  }
  function clearCards() { ws.cards().forEach(c => c.remove()); }
  function restoreStudents(list) {
    clearCards();
    const made = list.map(st => {
      const c = window.addStudent(st.name, st.work);
      if(st.student_id) c.dataset.rid = st.student_id; if(st.orig) c.dataset.orig = st.orig;
      if([...c.querySelector('.sgrade').options].some(o => o.value === st.grade)) c.querySelector('.sgrade').value = st.grade;
      if([...c.querySelector('.level').options].some(o => o.value === st.level)) c.querySelector('.level').value = st.level;
      c.querySelector('.notes').value = st.notes;
      if(st.student_id) window.setNote(c, '✓ Restored from the saved session');
      if(st.feedback) {
        const out = make('div', 'out', st.feedback.replace(/\*\*/g, '')); out.contentEditable = 'true';
        const cp = make('button', '', 'Copy'); cp.style.marginTop = '8px';
        cp.onclick = () => { navigator.clipboard.writeText(out.innerText); cp.textContent = 'Copied'; setTimeout(() => cp.textContent = 'Copy', 1500); };
        c.querySelector('.result').append(out, cp);
        ws.draftBasis.set(out, st.basis || ws.basisNow());
      }
      return [c, st];
    });
    ws.refresh();                                       // creates each card's review controls
    for(const [c, st] of made) {
      const box = c.querySelector('.myschool-comment'); if(box) box.value = st.myschool_comment;
      if(st.approval) ws.approvals.set(c, {bound:st.approval.bound, reviewed_at:st.approval.at});
      const p = {}; for(const k of ['teams', 'myschool']) if(st.posting && st.posting[k]) p[k] = {bound:st.posting[k].bound, at:st.posting[k].at};
      if(Object.keys(p).length) ws.posted.set(c, p);
    }
    ws.refresh();
  }
  async function saveSession() {
    if(!record || !sess.loaded || sess.busy || sess.hold || sess.aid !== record.id) return;
    const students = collect(), s = JSON.stringify(students);
    if(s === sess.sig) return;
    if(!students.length && sess.version == null) { sess.sig = s; return; }
    sess.busy = true; let d;
    try { d = await postJSON('/api/session', {assignment:record.id, baseVersion:sess.version, students}); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
    sess.busy = false;
    if(d.conflict) { sess.hold = true; showSessionConflict(d.current); return; }
    if(d.error) { sess.err = d.error; renderSess(); return; }
    Object.assign(sess, {version:d.session.version, path:d.path, sig:s, at:d.session.updated, err:'', status:d.status}); renderSess();
  }
  // The server judges approvals itself, from the saved session and the saved assignment. Ask again after the assignment is saved.
  async function refreshStatus() {
    if(!record || !sess.loaded || sess.aid !== record.id) return;
    try { const d = await getJSON('/api/session?assignment=' + encodeURIComponent(record.id)); if(!d.error) { sess.status = d.status; renderSess(); } } catch(e) {}
  }
  async function flushSession() { for(let i = 0; i < 20 && sess.busy; i++) await sleep(100); await saveSession(); }
  window.feedbackAssignment.saveForPosting = async () => {
    await flushSession();
    return !!record && !dirty() && sess.loaded && !sess.hold && !sess.err && sess.sig === JSON.stringify(collect());
  };
  function showSessionConflict(cur) {
    sessNote.classList.add('warn');
    sessNote.replaceChildren('Student work not saved: this session was saved somewhere else (another tab or window?) at ' + when(cur.updated) +
      '. Your work is still on this page. ',
      button('Load the saved session (drops the work here)', '', () => { restoreStudents(cur.students || []); Object.assign(sess, {version:cur.version, sig:JSON.stringify(collect()), hold:false}); sessNote.replaceChildren(); renderSess(); }), ' ',
      button('Save mine on top', '', () => { sess.version = cur.version; sess.hold = false; sess.sig = ''; sessNote.replaceChildren(); saveSession(); }));
    renderSess();
  }
  async function attachSession(fresh) {                 // fresh: a record just created from this page's own students
    sess.aid = record.id; sess.hold = false; sess.err = ''; sess.loaded = false; sess.version = null; sess.sig = ''; sessNote.replaceChildren();
    if(fresh) { sess.loaded = true; renderSess(); return; }
    let d; try { d = await getJSON('/api/session?assignment=' + encodeURIComponent(record.id)); } catch(e) { d = {error:'Couldn’t reach the app.'}; }
    if(d.error) { sess.err = d.error; renderSess(); return; }     // autosave stays off: it must not overwrite a session it couldn't read
    sess.path = d.path; sess.status = d.status;
    if(d.session) { restoreStudents(d.session.students || []); Object.assign(sess, {version:d.session.version, at:d.session.updated}); } else clearCards();
    sess.sig = JSON.stringify(collect()); sess.loaded = true; ws.refresh(); renderSess();
  }
  function trustNote() {                               // reviewed on this page, but not counted by the server (yet)
    if(JSON.stringify(collect()) !== sess.sig) return '';
    const local = ws.cards().filter(c => ws.valid(c)).length, server = sess.status ? sess.status.approved : 0;
    return local > server ? ' · ' + (local - server) + ' reviewed ' + (local - server === 1 ? 'student isn’t' : 'students aren’t') +
      ' approved on the server' + (dirty() ? ': save the assignment' : ': mark them reviewed again') : '';
  }
  function renderSess() {
    const n = ws.cards().length;
    const text = !record ? (n ? 'Student work is not saved between sessions until you save the assignment.' : '')
      : sess.err ? 'Session not saved: ' + sess.err
      : !sess.loaded ? 'Opening the saved session…'
      : sess.hold ? 'Session not saved: see below.'
      : sess.version == null ? (n ? 'Session: saving shortly…' : 'No student work yet.')
      : (JSON.stringify(collect()) !== sess.sig ? 'Session: saving…' : 'Session saved ' + when(sess.at)) + ' · Assessment › ' + sess.path.split('/').join(' › ') + trustNote();
    if(sessLine.textContent !== text) sessLine.textContent = text;
    sessLine.classList.toggle('warn', !!(sess.err || sess.hold));
  }
  setInterval(() => { saveSession().then(renderSess); }, 2000);
  document.addEventListener('visibilitychange', () => { if(document.visibilityState === 'hidden') saveSession(); });

  // ------------------------------------------------------------------ keep everything current, and start
  const main = $('main');
  main.addEventListener('input', () => updateBar());
  main.addEventListener('change', () => setTimeout(() => { updateBar(); if(!panel.hidden) changed(); }, 0));
  window.addEventListener('beforeunload', e => { if(record && dirty()) { e.preventDefault(); e.returnValue = ''; } });
  renderDesign(); renderSources(); updateBar();
  (async () => {
    await Promise.all([ready, loadClassMap(), refreshList()]);
    const last = keep.get('last-assignment');
    if(last) {
      let d = {}; try { d = await getJSON('/api/assignments/' + encodeURIComponent(last)); } catch(e) {}
      if(d.assignment) { await applyRecord(d.assignment); return; }
    }
    renderDesign(); updateBar();
  })();
})();
