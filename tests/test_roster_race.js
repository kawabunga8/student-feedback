/* Exercise the actual page's roster loader against deliberately reordered responses. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app.py'),'utf8');
const block=source.slice(source.indexOf('let rosterGeneration = 0;'),source.indexOf('function quarterForToday(){'));
const elements={'#course':{value:'0'},'#quarter':{value:'Q1'},'#addall':{},'#rosternote':{}};
const cards=[{dataset:{rid:'old-student'}}],pending=[],matched=[];
const context=vm.createContext({Array,encodeURIComponent,ROSTER:[],COURSES:[{name:'A',sections:[{}]},{name:'B',sections:[{}]}],
  $:s=>elements[s],document:{querySelectorAll:s=>s==='.student'?cards:[]},
  wirePicker:c=>{c.options=context.ROSTER.map(s=>s.id)},setNote:(c,n)=>{c.note=n},matchAll:()=>matched.push(context.ROSTER.map(s=>s.id)),
  fetch:url=>new Promise((resolve,reject)=>pending.push({url,resolve:students=>resolve({json:async()=>({students})}),reject}))
});
vm.runInContext(block+';globalThis.load=loadRoster;',context);
(async()=>{
  const first=context.load();assert.equal(cards[0].dataset.rid,undefined);assert.equal(elements['#addall'].disabled,true);
  elements['#course'].value='1';const second=context.load();pending[1].resolve([{id:'B-student'}]);await second;
  pending[0].resolve([{id:'A-student'}]);await first;
  assert.equal(context.ROSTER[0].id,'B-student');assert.match(elements['#rosternote'].textContent,/in B/);assert.equal(matched.length,1);
  // A stale error must not overwrite a newer success either.
  const third=context.load();elements['#quarter'].value='Q2';const fourth=context.load();
  pending[3].resolve([{id:'B-Q2'}]);await fourth;pending[2].reject(Error('stale failure'));await third;
  assert.equal(context.ROSTER[0].id,'B-Q2');assert.doesNotMatch(elements['#rosternote'].textContent,/Couldn't/);
  // A current failure leaves neither old students nor old matching ids available.
  cards[0].dataset.rid='B-Q2';const fifth=context.load();pending[4].reject(Error('offline'));await fifth;
  assert.equal(context.ROSTER.length,0);assert.equal(cards[0].dataset.rid,undefined);assert.equal(elements['#addall'].disabled,true);
  // Clearing the course while a response is pending cannot repopulate its roster.
  elements['#course'].value='0';const sixth=context.load();elements['#course'].value='';await context.load();pending[5].resolve([{id:'A-late'}]);await sixth;
  assert.equal(context.ROSTER.length,0);assert.equal(elements['#addall'].disabled,true);
  console.log('PASS 5 roster checks: immediate identity clearing, reversed responses, stale failure, current failure and cleared course');
})().catch(e=>{console.error(e);process.exitCode=1});
