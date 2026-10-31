/* Saved assignments, the Design step and "Choose from Teams…".
   The saved assignment record is the centre: Setup, Design and (later) collection and approval all use the same
   record. Records are saved on this laptop (~/Library/Application Support/student-feedback/assignments) and hold no
   student data. Nothing here sends anything to Teams or MySchool. Student-facing text and teacher-only guidance are
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
    record = d.assignment; savedCore = core(); keep.set('last-assignment', record.id);
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
  }
  function newAssignment() {
    record = null; design = emptyDesign(); sources = {}; teams = null; savedCore = null;
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
    <p class="hint">Until the app can list your Teams assignments itself, copy the assignment from Teams and paste it here.
      Nothing is changed in Teams.</p>
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
  function noteTeams() {
    teams = {...(teams || {}), className:clsIn.value.trim() || (teams && teams.className) || '', importedAt:nowIso()};
    if(parsed) Object.assign(teams, {title:parsed.title, due:parsed.due, referenceMaterials:parsed.referenceMaterials,
                                     imported:{title:parsed.title, instructions:parsed.instructions}});
    if(!design.teamsClass && teams.className) { design.teamsClass = teams.className; refreshers.forEach(f => f()); }
    updateBar();
  }
  function useTitle() { setField('#atitle', parsed.title); mark('title', 'Teams (Student view, pasted)'); noteTeams(); }
  function useInstructions(ask) {
    const cur = splitRubric($('#rubric').value);
    if(ask && cur.instructions && cur.instructions !== parsed.instructions &&
       !confirm('Replace the instructions in Setup with the ones from Teams?' + (cur.focus.length ? ' Your teacher-only feedback focus is kept.' : ''))) return false;
    setField('#rubric', composeRubric(parsed.instructions, cur.focus)); mark('instructions', 'Teams (Student view, pasted)'); noteTeams(); return true;
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
      applyCourseValue(sel.value, 'Course Hub (match you confirmed)'); noteTeams();
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
  function render() {
    const rows = [];
    if(parsed) {
      const curTitle = $('#atitle').value.trim(), cur = splitRubric($('#rubric').value).instructions;
      rows.push(row('title', 'Assignment name', parsed.title, [hintEl(compare(curTitle, parsed.title))],
        parsed.title && curTitle !== parsed.title ? button('Use', '', () => { useTitle(); render(); }) : null));
      if(parsed.due) rows.push(row('due', 'Due', parsed.due, [hintEl('For reference: the due date stays in Teams.')]));
      const refs = parsed.referenceMaterials.length
        ? hintEl('Reference materials (kept separate, not added to the instructions): ' + parsed.referenceMaterials.join('; ')) : null;
      rows.push(row('instructions', 'Instructions', parsed.instructions ? clip(parsed.instructions, 240) + '  (' + parsed.instructions.length + ' characters)' : '',
        [hintEl(compare(cur, parsed.instructions)), refs],
        parsed.instructions && cur !== parsed.instructions ? button('Use', '', () => { if(useInstructions(true)) render(); }) : null));
    }
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
  panel.append(make('p', 'hint', 'Plan a new assignment here, then copy its title and instructions into Teams. Feedback later uses the same ' +
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
  const dClass = bind(field(ctxGrid, 'Intended Teams class', input('RCS - … [2026-27]')), () => design.teamsClass, v => design.teamsClass = v);
  dClass.setAttribute('list', 'teams-classes');
  const dCourse = field(ctxGrid, 'Course (Course Hub)', make('select')), dGrade = field(ctxGrid, 'Grade', make('select'));
  const dTerm = field(ctxGrid, 'Term', make('select'));
  function syncMirrors() {
    const clone = (to, from) => { to.replaceChildren(...[...$(from).children].map(n => n.cloneNode(true))); to.value = $(from).value; };
    dTitle.value = $('#atitle').value; clone(dCourse, '#course'); clone(dGrade, '#grade'); clone(dTerm, '#quarter'); clone(dLength, '#length');
  }
  const mirror = (el, sel, after) => el.addEventListener('change', () => { $(sel).value = el.value; fire($(sel), 'change'); syncMirrors(); if(after) after(); changed(); });
  dTitle.addEventListener('input', () => { $('#atitle').value = dTitle.value; fire($('#atitle'), 'input', 'change'); changed(); });
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
  const dType = bind(field(subGrid, 'Students submit', select([['notebook', 'On a Class Notebook page'], ['teams', 'A file or link in Teams'], ['both', 'Both']])),
    () => design.submission.type, v => design.submission.type = v);
  const dSection = bind(field(subGrid, 'Notebook section', input('Homework')), () => design.submission.section, v => design.submission.section = v);
  const dPage = bind(field(subGrid, 'Notebook page title', input('Same as the assignment name'), '(distribute the page so every copy has this title)'),
    () => design.submission.page, v => design.submission.page = v);
  const dFiles = bind(field(subGrid, 'Required files', input('e.g. one PDF, or a link to your project')), () => design.submission.files, v => design.submission.files = v);
  bind(field(sub, 'How students show they’re done', input("When you're finished, click Turn in in Teams.")), () => design.submission.completion, v => design.submission.completion = v);

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
  const later = button('Create draft in Teams', '', null); later.disabled = true; later.title = 'Coming later: creates an unpublished draft in Teams. Publishing stays a separate step you do.';
  stuActs.append(later, make('span', 'hint-inline', 'coming later'));
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
    if(s.type !== 'teams') where.push('Class Notebook → ' + (s.section.trim() || 'Homework') + ' → "' + (page || 'the page your teacher sent') + '". Use the page your teacher sent you and keep its title.');
    if(s.type !== 'notebook') where.push('attach your work to this assignment in Teams' + (s.files.trim() ? ' (' + s.files.trim() + ')' : '') + '.');
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
    dSection.closest('.d-field').hidden = dPage.closest('.d-field').hidden = d.submission.type === 'teams';
    dFiles.closest('.d-field').hidden = d.submission.type === 'notebook';
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
