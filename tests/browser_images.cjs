const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const {File} = require("node:buffer");
class Element {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.events = {}; this.dataset = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, fn) { this.events[type] = fn; }
  setAttribute(key, value) { this[key] = value; }
}
const revoked = [], urls = [], context = vm.createContext({document: {createElement: tag => new Element(tag)},
  URL: {createObjectURL: file => { const url = `blob:${urls.length}`; urls.push(url); return url; }, revokeObjectURL: url => revoked.push(url)},
  FormData, console});
vm.runInContext(fs.readFileSync("regen_api/static/images.js", "utf8"), context);
const run = code => vm.runInContext(code, context);
const file = (name = "test.png", type = "image/png", bytes = 1) => new File([new Uint8Array(bytes)], name, {type});
context.root = new Element(); context.batch = Array.from({length: 20}, (_, i) => file(`${i}.png`));
run("var picker = new ImagePicker(root); picker.add(batch);");
assert.equal(run("picker.files.length"), 20);
context.extra = file();
assert.equal(run("picker.add([extra])"), false, "21st image must reject without changing selection");
assert.equal(run("picker.files.length"), 20);
run("picker.remove(4)"); assert.deepEqual(revoked, ["blob:4"]);
assert.equal(run("picker.files.length"), 19);
run("picker.clear()"); assert.equal(revoked.length, 20); assert.equal(run("picker.files.length"), 0);
context.bad = file("script.svg", "image/svg+xml");
assert.equal(run("picker.add([batch[0], bad])"), false); assert.equal(run("picker.files.length"), 0);
context.large = file("large.jpg", "image/jpeg", 8 * 1024 * 1024 + 1);
assert.equal(run("picker.add([large])"), false);
run("var limited = new ImagePicker(document.createElement('div'), {existing: 19})");
assert.equal(run("limited.add(batch.slice(0, 2))"), false);
context.malicious = file('<script>alert(1)</script>.png');
run("picker.add([malicious])");
function all(element) { return [element, ...element.children.flatMap(all)]; }
assert.equal(all(context.root).some(el => el.textContent === '<script>alert(1)</script>.png'), true);
assert.equal(all(context.root).some(el => el.innerHTML), false);
const body = run("submissionBody('Updated activity', picker.files, 7)");
assert.equal(body.get("description"), "Updated activity"); assert.equal(body.get("expected_version"), "7");
assert.equal(body.getAll("images").length, 1);
assert.equal(body.getAll("images")[0].name, '<script>alert(1)</script>.png');
assert.equal(run("JSON.stringify(submissionBody('Words only', [], 8))"), '{"description":"Words only","expected_version":8}');
context.record = {images: [{id: "one", filename: "old.png", width: 12, height: 8, size_bytes: 100},
  {id: "two", filename: '<img src=x onerror=alert(1)>', width: 12, height: 8, size_bytes: 120}]};
const historical = run("imageGallery(record, ['one'])");
assert.equal(all(historical).filter(el => el.tag === "img").length, 1);
assert.equal(all(historical).find(el => el.tag === "img").src, "/api/images/one");
assert.equal(all(historical).some(el => el.textContent === "old.png"), true);
assert.equal(all(historical).some(el => el.textContent === '<img src=x onerror=alert(1)>'), false);
console.log("PASS image selection, receipts, multipart and history gallery");
