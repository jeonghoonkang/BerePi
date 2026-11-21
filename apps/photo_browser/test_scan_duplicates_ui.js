const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function element(tag) {
  return {tag, children: [], hidden: false, textContent: '', open: false,
    append(...nodes) { this.children.push(...nodes); }, replaceChildren(...nodes) { this.children = nodes; },
    setAttribute() {}, addEventListener(name, callback) { this[name] = callback; }};
}
async function main() {
  const scope = {window: {}, document: {createElement: element}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/scan_duplicates.js'), 'utf8'), scope);
  let fail = false;
  const data = {total: 1, items: [{source_file: '<new-photo.jpg>', matches: [{media_id: 'existing', category_id: 'family', owner_id: 'alice', source_ids: ['old-source'], managed_files: [{path: '/library/existing.jpg', exists: false}]}]}]};
  const control = scope.window.photoBrowserScanDuplicates.createControls(async () => {
    if (fail) throw new Error('network');
    return data;
  });
  control.update({kind: 'scan', status: 'running', progress: {scan_id: 'scan', cross_group_duplicate_count: 0}});
  assert.equal(control.root.hidden, true);
  control.update({kind: 'scan', status: 'running', progress: {scan_id: 'scan', cross_group_duplicate_count: 0,
    source_inventory: {current: {directory_count: 2, file_count: 10, total_bytes: 200},
      comparisons: [{source_id: 'old', status: 'different_source', directory_count: 1, file_count: 5, total_bytes: 100}]}}});
  assert.equal(control.root.hidden, false);
  assert.match(control.root.children[2].textContent, /1차 구성 확인: 디렉토리 2개 · 파일 10개/);
  assert.match(control.root.children[2].textContent, /별도 소스 추정/);
  control.update({kind: 'scan', status: 'completed', result: {scan_id: 'scan', cross_group_duplicate_count: 1}});
  assert.equal(control.root.hidden, false);
  control.root.open = true; control.root.toggle();
  await new Promise(resolve => setImmediate(resolve));
  const body = control.root.children[4].children[0].children[1];
  assert.equal(body.children[0].children[0].textContent, '<new-photo.jpg>');
  assert.match(body.children[0].children[2].textContent, /family \/ alice/);
  assert.match(body.children[0].children[4].textContent, /현재 파일 없음/);
  fail = true; control.root.children.at(-1).onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(control.root.children[3].textContent, /조회 실패/);
  console.log('Scan duplicate UI: match details, safe text, missing copies and failures passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
