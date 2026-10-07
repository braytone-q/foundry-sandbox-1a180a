// Run the actual browser script with a minimal DOM boundary and deferred HTTP.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const {File} = require("node:buffer");
const source = fs.readFileSync("regen_api/static/app.js", "utf8").replace(/renderRoute\(\);\s*$/, "");

function harness() {
  const elements = new Map();
  class Element {
    constructor(tag = "div") { this.tag = tag; this.value = ""; this.dataset = {}; this.children = []; this.events = {}; }
    set id(value) { this._id = value; elements.set(`#${value}`, this); }
    get id() { return this._id; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    addEventListener(type, fn) { this.events[type] = fn; }
    setAttribute(key, value) { this[key] = value; }
    reportValidity() { return true; }
    showModal() { this.open = true; }
    close() { this.open = false; }
  }
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  }
  const context = vm.createContext({document: {querySelector: element, querySelectorAll: () => [],
    createElement: (tag) => new Element(tag)}, window: {addEventListener() {}},
    location: {hash: "#submission/A"}, URLSearchParams, URL, FormData, File, console});
  const run = (code) => vm.runInContext(code, context);
  run(fs.readFileSync("regen_api/static/images.js", "utf8")); run(source);
  return {element, run};
}
function findButton(element, text) {
  if (element.tag === "button" && element.textContent === text) return element;
  for (const child of element.children) { const match = findButton(child, text); if (match) return match; }
}

async function refreshCannotRedirectReview() {
  const h = harness();
  h.run(`
    var resolveRefresh; var posts = [];
    renderDetail = () => {};
    api = (url, body) => body
      ? (posts.push({url, body}), Promise.resolve({...current, review_status:'APPROVED'}))
      : new Promise(resolve => resolveRefresh = resolve);
    current = {id:'A', version:2};
    var inflight = refresh();
    ++routeSequence; location.hash = '#submission/B';
    current = {id:'B', version:2, review_status:'PENDING_REVIEW', latest_attempt:{state:'SUCCEEDED'}};
  `);
  const form = h.run("reviewCard(current)");
  h.element("#reviewer-name").value = "Reviewer B";
  h.element("#review-notes").value = "Approve activity B";
  findButton(form, "Approve →").events.click();
  assert.equal(h.element("#review-dialog").open, true);
  await h.run("resolveRefresh({id:'A',version:2}); inflight;");
  await h.element("#confirmation-form").events.submit({preventDefault() {}});
  const observed = JSON.parse(h.run("JSON.stringify({current:current.id,posts})"));
  assert.equal(observed.current, "B", "An old refresh must not replace the viewed record");
  assert.equal(observed.posts.length, 1);
  assert.equal(observed.posts[0].url, "/api/submissions/B/reviews", "Confirmation must stay bound to B");
  assert.equal(observed.posts[0].body.notes, "Approve activity B");
  assert.deepEqual(Object.keys(observed.posts[0].body).sort(), ["action", "expected_version", "notes", "reviewer_name"]);
}

async function latestFilterWins() {
  const h = harness();
  await h.run(`
    var requests=[];
    api=(url)=>new Promise(resolve=>requests.push({url,resolve}));
    $('#status-filter').value='APPROVED'; var old=loadQueue();
    $('#status-filter').value='REJECTED'; var recent=loadQueue();
    requests[1].resolve({total:0,items:[]}); recent;
  `);
  await h.run("requests[0].resolve({total:9,items:[]}); old;");
  assert.equal(h.element("#status-filter").value, "REJECTED");
  assert.equal(h.element("#queue-total").textContent, "0", "Older filters must not overwrite the latest results");
  assert.equal(h.element("#page-label").textContent, "0 activities");
}

async function confirmationStaysBoundToRecord() {
  const h = harness();
  h.run(`
    var posts=[];
    renderDetail=()=>{};
    current={id:'B',version:2,review_status:'PENDING_REVIEW',latest_attempt:{state:'SUCCEEDED'}};
    api=(url,body)=>(posts.push({url,body}),Promise.resolve({...current,review_status:'APPROVED'}));
  `);
  const form = h.run("reviewCard(current)");
  h.element("#reviewer-name").value = "Reviewer B";
  h.element("#review-notes").value = "Approve activity B";
  findButton(form, "Approve →").events.click();
  h.run("current={id:'A',version:2};");
  await h.element("#confirmation-form").events.submit({preventDefault() {}});
  assert.equal(h.run("posts.length"), 0, "A confirmation must never act on a different current record");
}

async function navigationRetainsImageDraft() {
  const h = harness();
  await h.run(`
    $('#description').value='Draft with photograph';
    var photo=new File([new Uint8Array([1])], 'photo.png', {type:'image/png'});
    submissionPicker.add([photo]);
    api=async()=>({total:0,items:[]});
    location.hash='#queue'; renderRoute();
  `);
  assert.equal(h.run("submissionPicker.files.length"), 1, "Navigation must retain selected draft images");
  await h.run("location.hash='#submit'; renderRoute();");
  assert.equal(h.element("#description").value, "Draft with photograph");
  assert.equal(h.run("submissionBody($('#description').value, submissionPicker.files) instanceof FormData"), true);
  assert.equal(h.run("submissionBody($('#description').value, submissionPicker.files).getAll('images')[0].name"), "photo.png");
}

async function imageComparisonIsVisibleAndSafe() {
  const h = harness();
  const card = h.run(`renderImageAssessment({overall:'MISMATCH', model:'gpt-5-mini', images:[{image_number:1,filename:'photo.png',verdict:'UNRELATED',visible_content:'<script>poster</script>',explanation:'This is a poster, not an observed event.'}]},1)`);
  function flatten(el) { return [el, ...el.children.flatMap(flatten)]; }
  assert.equal(flatten(card).some(el => el.textContent === 'Image mismatch'), true);
  assert.equal(flatten(card).some(el => el.textContent === '<script>poster</script>'), true);
  assert.equal(flatten(card).some(el => el.innerHTML), false);
  const legacy = h.run('renderImageAssessment(null, 1)');
  assert.equal(flatten(legacy).some(el => el.textContent?.includes('not recorded')), true);
}
const checks = {refresh: refreshCannotRedirectReview, filters: latestFilterWins, confirmation: confirmationStaysBoundToRecord, image_draft: navigationRetainsImageDraft, image_comparison:imageComparisonIsVisibleAndSafe};
const check = checks[process.argv[2]];
if (!check) throw new Error("Choose refresh, filters or confirmation");
check().then(() => console.log(`PASS ${process.argv[2]}`)).catch((error) => { console.error(error); process.exitCode = 1; });
