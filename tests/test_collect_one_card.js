// A repeat collection must update a student's card, never add a second one. The page's own helper is cut out of
// ui/collect.js and run against a stand-in for the cards, so no browser is needed. (It checks the decision, not the clicks.)
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../ui/collect.js', 'utf8');
const body = src.slice(src.indexOf('  function cardsFor'), src.indexOf('  // ---- several pages'));
const card = (name, work, rid) => ({dataset: rid ? {rid} : {}, querySelector: q => q === '.name' ? {value: name} : {value: work}});
function run(cards, roster) {
  const document = {querySelectorAll: () => cards}; const ROSTER = roster; const window = {findStudent: n => {
    const s = roster.find(r => (r.first + ' ' + r.last).toLowerCase() === n.toLowerCase()); return s ? {status: 'match', s} : {status: 'none'}; }};
  return new Function('document', 'ROSTER', 'window', body + '; return plan;')(document, ROSTER, window);
}
const roster = [{id: 'a', first: 'Ada', last: 'Test'}, {id: 'b', first: 'Bo', last: 'Test'}];
let r = 0; const t = (label, fn) => { fn(); r++; console.log('PASS ' + label); };
t('no card yet: add', () => assert.equal(run([], roster)('Ada Test', 'x').kind, 'add'));
t('an empty card is filled', () => assert.equal(run([card('Ada Test', '', 'a')], roster)('Ada Test', 'x').kind, 'fill'));
t('a card that already has different work is replaced, not duplicated', () => assert.equal(run([card('Ada Test', 'old', 'a')], roster)('Ada Test', 'new').kind, 'replace'));
t('a card that already holds this page is left alone', () => assert.equal(run([card('Ada Test', ' same ', 'a')], roster)('Ada Test', 'same').kind, 'same'));
t('the class-list identity finds the card even if the typed name differs', () => assert.equal(run([card('A. Test', 'old', 'a')], roster)('Ada Test', 'new').kind, 'replace'));
t('another student’s card is not touched', () => assert.equal(run([card('Bo Test', 'old', 'b')], roster)('Ada Test', 'new').kind, 'add'));
t('duplicate cards are refused, not guessed', () => assert.deepEqual(run([card('Ada Test', 'a1', 'a'), card('Ada Test', 'a2', 'a')], roster)('Ada Test', 'new'), {kind: 'many', n: 2}));
t('a name with no class list still matches by typed name', () => assert.equal(run([card('Zed Q', 'old')], [])('zed q', 'new').kind, 'replace'));
console.log(`\n${r}/${r} passed`);
