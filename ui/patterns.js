/* Class patterns (optional, teacher-started). Runs the "Looking for" criteria against each student's work on the local
   model, one student at a time, then asks the app to count how many students met each criterion. Only the work text
   goes to the local app (the same place drafting sends it); only criteria and counts come back. Names are never sent,
   the report never contains names or work text, and nothing is saved: results are lost when the page reloads.
   Counts are hidden for any criterion checked for fewer than 5 students. The teacher reviews the report before using it. */
(() => {
  const ws = window.feedbackWorkspace, review = document.getElementById('step-review'), list = document.getElementById('students');
  if(!ws || !review || !list) return;
  const make = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const post = async (path, body) => {
    const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const d = await r.json();
    if(d.error) throw new Error(d.error);
    return d;
  };

  const box = make('div', 'card patterns');
  box.append(make('h3', '', 'Class patterns (optional)'));
  box.append(make('p', 'hint', 'Checks each student’s work against your “Looking for” criteria on your own computer, then counts how many students met each one. ' +
    'The report lists criteria and counts only: no names and no work. A criterion checked for fewer than 5 students is hidden. ' +
    'It is a prompt for your own review, not an assessment, and it is not saved: it is lost if you reload the page.'));
  const run = make('button', '', 'Check criteria for the class'); run.type = 'button';
  const stop = make('button', '', 'Stop'); stop.type = 'button'; stop.disabled = true;
  const status = make('p', 'hint'); status.setAttribute('role', 'status');
  const report = make('pre'); report.hidden = true; report.style.whiteSpace = 'pre-wrap';
  const copy = make('button', '', 'Copy report'); copy.type = 'button'; copy.hidden = true;
  const bar = make('div'); bar.append(run, ' ', stop, ' ', copy);
  box.append(bar, status, report);
  review.insertBefore(box, list);

  let stopping = false;
  stop.onclick = () => { stopping = true; stop.disabled = true; };
  copy.onclick = () => { navigator.clipboard.writeText(report.textContent); copy.textContent = 'Copied'; setTimeout(() => copy.textContent = 'Copy report', 1500); };

  run.onclick = async () => {
    const rubric = (document.getElementById('rubric') || {}).value || '', model = (document.getElementById('model') || {}).value || '';
    const cards = ws.cards().filter(c => c.querySelector('.work') && c.querySelector('.work').value.trim());
    if(!cards.length) { status.textContent = 'Add or load some student work first.'; return; }
    if(!rubric.trim()) { status.textContent = 'Add an assignment description with a “Looking for:” line first.'; return; }
    run.disabled = true; stop.disabled = false; stopping = false; report.hidden = true; copy.hidden = true;
    const rows = []; let criteria = [], unchecked = 0, i = 0;
    try {
      for(const c of cards) {
        if(stopping) break;
        i++; status.textContent = `Checking ${i} of ${cards.length} …`;
        const d = await post('/api/criteria-check', {model, rubric, work: c.querySelector('.work').value});
        criteria = d.criteria;
        if(!d.checked) unchecked++;
        rows.push({done: d.done, missing: d.missing});          // criteria only: no name, no work text
      }
      if(!rows.length) { status.textContent = 'Stopped before any student was checked.'; return; }
      if(unchecked === rows.length) { status.textContent = 'The checker returned nothing for any student. Make sure the model is running (as for drafting), then try again.'; return; }
      const d = await post('/api/class-patterns', {criteria, rows});
      report.textContent = d.markdown; report.hidden = false; copy.hidden = false;
      status.textContent = (stopping ? `Stopped after ${rows.length} of ${cards.length} students. ` : '') +
        (unchecked ? `${unchecked} of ${rows.length} could not be checked and are left out of the counts. ` : '') + 'Review the report before using or sharing it.';
    } catch(err) {
      status.textContent = err.message;
    } finally {
      run.disabled = false; stop.disabled = true;
    }
  };
})();
