const assert = require('node:assert/strict');
const {harness} = require('./browser_races.cjs');
function flatten(el) {return [el, ...el.children.flatMap(flatten)];}
const trace = {
  mode: 'multiagent', coordinator_version: '1', stages: [
    {role:'activity', identity:'activity-model', state:'SUCCEEDED', response_id:'activity-id',
      findings:{activity_type:'<img src=x onerror=alert(1)>', quantity:150}, failure_code:null},
    {role:'evidence', identity:'vision-model', state:'SKIPPED', response_id:null, findings:null, failure_code:null},
    {role:'rules', identity:'regen v11', state:'FAILED', response_id:null, findings:null, failure_code:'RETRIEVAL_MISSING'}
  ]
};

const h = harness();
h.run(`var originalCreateElement=document.createElement;
  document.createElement=(tag)=>{const el=originalCreateElement(tag);
    el.classList={add(name){el.className=(el.className || '')+' '+name;}}; return el;};`);
const rendered = h.run(`renderOrchestrationTrace(${JSON.stringify(trace)})`);
const nodes = flatten(rendered);
const text = nodes.map(n=>n.textContent || '').join(' ');
assert.equal(rendered.tag, 'details');
for (const expected of ['Multiagent analysis', 'activity-model', 'activity-id', 'RETRIEVAL_MISSING',
  'No images supplied', '<img src=x onerror=alert(1)>']) assert.ok(text.includes(expected), expected);
assert.ok(nodes.every(n=>!n.innerHTML));
assert.ok(nodes.every(n=>n.tag !== 'img'));
assert.equal(h.run('renderOrchestrationTrace(null)'), null);

const record = {id:'A', version:2, current_revision:1, description:'Test reported source',
  review_status:'PENDING_REVIEW', updated_at:'2026-10-08T09:00:00Z', images:[], device_location:null,
  revisions:[], reviews:[], attempts:[{id:'attempt-1', state:'FAILED', revision:1,
    agent_name:'regen', agent_version:'11', started_at:'2026-10-08T09:00:00Z',
    image_ids:[], analysis:null, failure_message:'Safe failure', orchestration_trace:trace}],
  latest_attempt:{id:'attempt-1', state:'FAILED', agent_name:'regen', agent_version:'11',
    analysis:null, failure_message:'Safe failure', orchestration_trace:trace}};
const history = h.run(`historyCard(${JSON.stringify(record)})`);
assert.ok(flatten(history).some(n=>n.textContent === 'Multiagent analysis · coordinator v1'));
h.run(`current=${JSON.stringify(record)}; renderDetail();`);
const detail = flatten(h.element('#detail-content'));
assert.equal(detail.filter(n=>n.textContent === 'Multiagent analysis · coordinator v1').length, 2);
assert.ok(detail.some(n=>n.textContent === 'Retry analysis ↻'));
assert.ok(!detail.some(n=>n.tag==='button' && n.textContent === 'Approve →'));
console.log('PASS orchestration current/history rendering, failed/skipped stages, legacy null, and escaping');
