const assert = require('node:assert/strict');
const {harness} = require('./browser_races.cjs');
function submit(h) {return h.element('#question-form').events.submit({preventDefault(){}});}
function flatten(el) {return [el, ...el.children.flatMap(flatten)];}
function configure(h) {
  h.run(`var asks=[];api=async(url,body)=>(asks.push({url,body}),
    {answer:'<script>general answer</script>',citations:[
      {title:'Source',url:'https://example.org/rule'},
      {title:'Unsafe',url:'javascript:alert(1)'}],knowledge_searched:true});`);
}

async function success() {
  const h=harness();configure(h);
  h.element('#question-input').value='What is the capital of Kenya?';
  await submit(h);
  assert.equal(h.run('asks[0].url'),'/api/questions');
  assert.equal(h.run('asks[0].body.question'),'What is the capital of Kenya?');
  assert.equal(h.run('asks[0].body.history.length'),0);
  assert.equal(h.run('busy'),false);
  assert.equal(h.element('#question-input').value,'');
  const nodes=flatten(h.element('#question-log'));
  assert.equal(nodes.some(n=>n.textContent==='<script>general answer</script>'),true);
  assert.equal(nodes.some(n=>n.innerHTML),false);
  const links=nodes.filter(n=>n.tag==='a');
  assert.equal(links.length,1);assert.equal(links[0].href,'https://example.org/rule');
  assert.equal(links[0].rel,'noopener noreferrer');
}
async function followup() {
  const h=harness();configure(h);
  h.element('#question-input').value='What is Re-gen?';await submit(h);
  h.element('#question-input').value='And how do I submit?';await submit(h);
  const body=JSON.parse(h.run('JSON.stringify(asks[1].body)'));
  assert.deepEqual(body.history,[{role:'user',content:'What is Re-gen?'},
    {role:'assistant',content:'<script>general answer</script>'}]);
}
async function duplicate() {
  const h=harness();h.run(`var asks=[];var resolveAnswer;
    api=(url,body)=>(asks.push({url,body}),new Promise(r=>resolveAnswer=r));`);
  h.element('#question-input').value='Hello';const first=submit(h);await submit(h);
  assert.equal(h.run('asks.length'),1);
  h.element('#question-reset').events.click();
  h.run(`resolveAnswer({answer:'Hello!',citations:[]});`);await first;
  assert.equal(h.run('questionChat.turns.length'),1);
  assert.equal(h.element('#question-reset').disabled,false);
}
async function failure() {
  const h=harness();h.run(`api=async()=>{throw new Error('Question service unavailable');};`);
  h.element('#question-input').value='Keep this question';await submit(h);
  assert.equal(h.element('#question-input').value,'Keep this question');
  assert.equal(h.run('questionChat.turns.length'),0);
  assert.equal(h.element('#question-progress').textContent,'Question service unavailable');
  assert.equal(h.element('#question-send').disabled,false);
  assert.equal(h.run('busy'),false);
}
async function navigation() {
  const h=harness();h.run(`var asks=[];var resolveAnswer;
    location.hash='#ask';renderRoute();
    $('#description').value='Activity draft';
    submissionPicker.add([new File([new Uint8Array([1])],'draft.png',{type:'image/png'})]);
    api=(url,body)=>(asks.push({url,body}),new Promise(r=>resolveAnswer=r));`);
  assert.equal(h.element('#ask-view').hidden,false);
  h.element('#question-input').value='A question';const request=submit(h);
  h.run(`location.hash='#submit';renderRoute();resolveAnswer({answer:'An answer',citations:[]});`);
  await request;
  assert.equal(h.run('location.hash'),'#submit');
  assert.equal(h.element('#description').value,'Activity draft');
  assert.equal(h.run('submissionPicker.files.length'),1);
  assert.equal(h.run('questionChat.turns.length'),1);
  assert.equal(h.run('asks.length'),1);
}
async function reset() {
  const h=harness();configure(h);
  h.element('#question-input').value='Old question';await submit(h);
  h.element('#question-reset').events.click();
  assert.equal(h.run('questionChat.turns.length'),0);
  h.element('#question-input').value='New question';await submit(h);
  assert.equal(h.run('asks[1].body.history.length'),0);
}
async function limits() {
  const h=harness();configure(h);
  h.run(`questionChat.turns=Array.from({length:10},(_,n)=>({question:'Q'+n,answer:'A'+n}));`);
  h.element('#question-input').value='Follow up';await submit(h);
  assert.equal(h.run('asks[0].body.history.length'),12);
  assert.equal(h.run('asks[0].body.history[0].content'),'Q4');
  h.run(`questionChat.turns=Array.from({length:5},(_,n)=>({question:String(n).repeat(4000),answer:'a'.repeat(8000)}));`);
  h.element('#question-input').value='Follow up';await submit(h);
  assert.equal(h.run('asks[1].body.history.length'),4);
  assert.equal(h.run('asks[1].body.history[0].content[0]'),'3');
  assert.equal(h.run('asks[1].body.history.reduce((n,m)=>n+m.content.length,0)'),24000);
  h.element('#question-input').value='x'.repeat(4001);await submit(h);
  assert.equal(h.run('asks.length'),2);
}
async function examples() {
  const h=harness();configure(h);
  const buttons=h.element('#question-examples').children;
  assert.equal(buttons.length,3);
  buttons[0].events.click();
  assert.equal(h.element('#question-input').value,'How does Re-gen work?');
  assert.equal(h.run('asks.length'),0);
}
async function transport() {
  const h=harness();
  h.run(`fetch=async()=>{throw new Error('private network details');};`);
  h.element('#question-input').value='Keep the question';await submit(h);
  assert.equal(h.element('#question-input').value,'Keep the question');
  assert.equal(h.element('#question-progress').textContent.includes('saved'),false);
  h.run(`fetch=async()=>({json:async()=>{throw new Error('private parse details');}});`);
  await submit(h);
  assert.equal(h.element('#question-progress').textContent.includes('saved'),false);
  assert.equal(h.element('#question-progress').textContent.includes('private'),false);
}
const cases={success,followup,duplicate,failure,navigation,reset,limits,examples,transport};
cases[process.argv[2]]().then(()=>console.log('PASS '+process.argv[2])).catch(e=>{console.error(e);process.exitCode=1;});
