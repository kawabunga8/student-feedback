/* Class overview (read-only): one row per student card showing where each one is in the workflow and what to do next.
   It reads the page's own cards. It sends nothing anywhere, changes nothing, and does not repeat any student's work or
   feedback text: only names, counts and states. */
(() => {
  const ws = window.feedbackWorkspace, review = document.getElementById('step-review'), list = document.getElementById('students');
  if(!ws || !review || !list) return;
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };

  // The first thing still to do for a student. Order matters: earlier problems hide later ones.
  const NEXT = {
    work: ['Add the student’s work', 'attention'], match: ['Match to the class list', 'attention'], duplicate: ['Resolve the duplicate card', 'attention'],
    failed: ['Draft failed: try again or write it yourself', 'attention'], regen: ['Instructions changed: regenerate the draft', 'attention'],
    draft: ['Draft the feedback', 'todo'], level: ['Choose a level yourself', 'todo'], review: ['Read it and mark reviewed', 'todo'],
    rereview: ['Changed since review: review again', 'todo'], post: ['Reviewed: ready to post', 'ready'], done: ['Done in Teams and MySchool', 'done']};

  function classify(i) {
    if(!i.hasWork) return 'work';
    if(!i.matched) return 'match';
    if(i.duplicate) return 'duplicate';
    if(i.draftError) return 'failed';
    if(!i.hasDraft) return 'draft';
    if(i.outdated) return 'regen';
    if(!i.level) return 'level';
    if(i.changed) return 'rereview';
    if(!i.reviewed) return 'review';
    return i.postedTeams && i.postedMyschool ? 'done' : 'post';
  }

  function read(c, cards) {
    const out = c.querySelector('.out'), a = ws.approvals.get(c), ok = ws.valid(c), p = ws.posted.get(c) || {};
    const fresh = k => !!p[k] && p[k].bound === JSON.stringify(ws.payload(c));
    const rid = c.dataset.rid || '';
    return {name: c.querySelector('.name').value.trim(), hasWork: !!c.querySelector('.work').value.trim(), matched: !!rid,
      duplicate: !!rid && cards.some(o => o !== c && o.dataset.rid === rid),
      hasDraft: !!out && !out.classList.contains('err'), draftError: !!out && out.classList.contains('err'),
      outdated: c.classList.contains('outdated'), level: c.querySelector('.level').value, reviewed: ok, changed: !!a && !ok,
      teamsStatus: c.dataset.tstatus || '', postedTeams: ok && fresh('teams'), postedMyschool: ok && fresh('myschool')};
  }

  const box = make('div', 'card overview'); box.hidden = false;
  const head = make('div', 'overview-head'); head.append(make('h3', '', 'Class overview'));
  const filter = make('select'); filter.setAttribute('aria-label', 'Show students');
  [['all', 'All students'], ['attention', 'Needs attention'], ['todo', 'Still to do'], ['ready', 'Ready to post'], ['done', 'Done']].forEach(([v, t]) => { const o = make('option', '', t); o.value = v; filter.append(o); });
  head.append(filter); box.append(head);
  const counts = make('p', 'hint overview-counts'); counts.setAttribute('role', 'status'); box.append(counts);
  const table = make('table', 'overview-table'); table.append(make('caption', '', 'Where each student is, and the next thing to do. Read-only; click a name to go to that student.'));
  const thead = make('thead'), hr = make('tr'); ['Student', 'Teams', 'Level', 'Next'].forEach(h => { const th = make('th', '', h); th.scope = 'col'; hr.append(th); });
  thead.append(hr); const tbody = make('tbody'); table.append(thead, tbody); box.append(table);
  review.insertBefore(box, list);

  let sig = '';
  function render() {
    const cards = ws.cards(), infos = cards.map(c => ({c, i: read(c, cards)}));
    infos.forEach(x => { x.stage = classify(x.i); x.group = NEXT[x.stage][1]; });
    const tally = {attention: 0, todo: 0, ready: 0, done: 0}; infos.forEach(x => tally[x.group]++);
    const want = filter.value, shown = infos.filter(x => want === 'all' || x.group === want);
    const nextSig = JSON.stringify([want, shown.map(x => [x.i.name, x.i.teamsStatus, x.i.level, x.stage])]);
    counts.textContent = infos.length ? `${tally.attention} need attention · ${tally.todo} still to do · ${tally.ready} ready to post · ${tally.done} done` : 'No students yet.';
    if(nextSig === sig) return;
    sig = nextSig; tbody.replaceChildren();
    if(!shown.length) { const r = make('tr'), td = make('td', 'hint', infos.length ? 'No students in this group.' : 'Add or load students to see them here.'); td.colSpan = 4; r.append(td); tbody.append(r); return; }
    shown.forEach(x => {
      const r = make('tr', 'overview-' + x.group), who = make('td'), b = make('button', 'linkish', x.i.name || 'Unnamed student'); b.type = 'button';
      b.onclick = () => { x.c.hidden = false; x.c.scrollIntoView({block: 'start'}); const f = x.c.querySelector('.name'); if(f) f.focus({preventScroll: true}); };
      who.append(b);
      r.append(who, make('td', '', x.i.teamsStatus || '–'), make('td', '', x.i.level || '–'), make('td', '', NEXT[x.stage][0]));
      r.dataset.stage = x.stage; tbody.append(r);
    });
  }
  filter.onchange = render;
  document.querySelector('main').addEventListener('input', () => setTimeout(render, 0));
  document.querySelector('main').addEventListener('change', () => setTimeout(render, 0));
  setInterval(render, 1000); render();
  window.feedbackOverview = {classify, render};
})();
