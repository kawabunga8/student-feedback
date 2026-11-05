/* Exercise the actual discovery cache and job orchestration, with a synthetic clock and reader. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../ui/assignment.js'), 'utf8');
const block = source.slice(source.indexOf('  // BEGIN TEAMS DISCOVERY CACHE'), source.indexOf('  tb.textContent ='));
let clock = 0, reads = 0, fail = false, release;
const context = vm.createContext({Date:{now:()=>clock}, Map, JSON, console,
  tmsg:{}, tb:{}, stopWait:()=>{},
  postJSON:async (_url, body)=> { reads++; return {job:{id:JSON.stringify(body)}}; },
  follow:async (id, done)=> { if(release) await new Promise(resolve=>release.push(resolve)); if(!fail) done({ok:true, marker:id, read_at:'synthetic',student_view:{title:'Synthetic'}}); }
});
vm.runInContext(block+';globalThis.read = startTeams;', context);
(async()=>{
  const request={op:'read',class:'Synthetic A',title:'Design'};
  let result;
  const read=(b=request,refresh=false)=>context.read(b,r=>{result=r},refresh);
  await read(); assert.equal(reads,1); assert.equal(result.reused,undefined);
  result.student_view.title='local edit';
  await read(); assert.equal(reads,1); assert.equal(result.reused,true); assert.equal(result.student_view.title,'Synthetic');
  await read({...request,class:'Synthetic B'});assert.equal(reads,2);
  await read({...request,title:'Different assignment'});assert.equal(reads,3);
  await read({op:'list'});await read({op:'list'});assert.equal(reads,4);
  await read(request,true);assert.equal(reads,5);assert.equal(result.reused,undefined);
  clock=10*60*1000;await read();assert.equal(reads,6);
  fail=true;await read(request,true);await read();assert.equal(reads,8);fail=false;
  release=[];
  const first=read(request,true), second=read(request);
  await new Promise(resolve=>setImmediate(resolve));assert.equal(reads,9);
  release.forEach(resolve=>resolve());await Promise.all([first,second]);release=null;
  assert.equal(reads,9);
  console.log('PASS discovery reuse, copy isolation, class/title keys, list reuse, refresh, expiry, failed reads and concurrent deduplication');
})().catch(error=>{console.error(error);process.exitCode=1});
