/* Real session lifecycle functions with reordered synthetic responses. No app or browser. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../ui/assignment.js'),'utf8');
const functions=source.slice(source.indexOf('  async function saveSession()'),source.indexOf('  // Loading an Assessment folder'))+'\n'+source.slice(source.indexOf('  async function attachSession('),source.indexOf('  function trustNote()'));
function setup(){
 const reads=[],writes=[];
 const c=vm.createContext({record:{id:'A'},sess:{},sessionGeneration:0,cards:[],sessNote:{replaceChildren(){}},
  getJSON:url=>new Promise(resolve=>reads.push({url,resolve})),postJSON:(url,body)=>new Promise(resolve=>writes.push({body,resolve})),
  collect:()=>c.cards,restoreStudents:list=>c.cards=list,clearCards:()=>c.cards=[],renderSess(){},showSessionConflict(){throw Error('stale conflict shown')},ws:{refresh(){}},sleep:async()=>{}});
 vm.runInContext(source.split('\n').find(l=>l.includes('const ownsSession ='))+'\n'+functions,c);
 return {c,reads,writes};
}
const result=(name,version=1)=>({path:name,status:{marker:name},session:{version,updated:'synthetic',students:[{name}]}});
(async()=>{
 let {c,reads}=setup();let a=c.attachSession(false);c.record={id:'B'};let b=c.attachSession(false);reads[1].resolve(result('B'));await b;reads[0].resolve(result('A'));await a;
 assert.equal(c.cards[0].name,'B');assert.equal(c.sess.path,'B');assert.equal(c.sess.aid,'B');
 // A late save cannot contaminate B's version/signature, even when it returns an error or conflict.
 for(const response of [{session:{version:99},path:'A'}, {error:'stale error'}, {conflict:true,current:{}}]){
  const env=setup();c=env.c;reads=env.reads;let load=c.attachSession(false);reads[0].resolve(result('A'));await load;c.cards=[{name:'A edited'}];let save=c.saveSession();
  c.record={id:'B'};load=c.attachSession(false);reads[1].resolve(result('B',2));await load;
  env.writes[0].resolve(response);await save;assert.equal(c.sess.version,2);assert.equal(c.sess.err,'');assert.equal(c.cards[0].name,'B');assert.equal(c.sess.busy,false);
 }
 // Same assignment reopened still needs a generation check: earlier loads are stale too.
 ({c,reads}=setup());a=c.attachSession(false);b=c.attachSession(false);reads[1].resolve(result('A newest',2));await b;reads[0].resolve(result('A old'));await a;assert.equal(c.cards[0].name,'A newest');assert.equal(c.sess.version,2);
 // Status reads cannot replace another assignment's server approval status.
 let status=c.refreshStatus();c.record={id:'B'};b=c.attachSession(false);reads[3].resolve(result('B'));await b;reads[2].resolve({status:{marker:'A late'}});await status;assert.equal(c.sess.status.marker,'B');
 console.log('PASS 6 ownership cases: reversed loads, late save/success/error/conflict, same-assignment reopen and late status');
})().catch(e=>{console.error(e);process.exitCode=1});
