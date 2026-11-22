const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
  return {value: '', textContent: '', disabled: false, hidden: false, children: [],
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
    add(child) { this.children.push(child); }, reportValidity() { return true; },
    set innerHTML(_) { throw new Error('Unsafe HTML'); }};
}

async function main() {
  const ids = ['source-folder-root', 'source-folder-category', 'source-folder-owner', 'source-folder-items',
    'source-folder-saved', 'source-folder-status', 'source-folder-register', 'source-folder-sync',
    'source-folder-stop', 'source-folders-form'];
  const nodes = Object.fromEntries(ids.map(id => [id, element()]));
  nodes['source-folder-root'].value = '/inbox';
  nodes['source-folder-category'].value = 'family'; nodes['source-folder-owner'].value = 'alice';
  const source = {source_id: '가족', root: '/inbox/가족', category: 'family', owner_id: 'alice'};
  const requests = [], refreshed = [];
  let fail = false;
  const registration = {root: '/inbox', added: 1, items: [{source, added: true}], skipped: []};
  const syncResult = {root: '/inbox', registration, status: 'completed', error_count: 0, items: [{source_id: '가족'}]};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/source_folders.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], createElement: () => element()},
    Option: function(text, value) { return {textContent: text, value}; },
    window: {photoBrowserSourceUpdated: async source => refreshed.push(source)},
    setTimeout(callback) { setImmediate(callback); },
    fetch: async (url, options) => {
      requests.push({url, options});
      if (fail) return {ok: false, json: async () => ({error: '작업 중'})};
      const result = url.startsWith('api/jobs/') ? {status: 'completed', result: syncResult} :
        url.endsWith('/sync') ? {job_id: 'batch'} : options.method === 'POST' ? registration :
        {items: [{root: '/inbox', category: 'family', owner_id: 'alice', sources: [source]}]};
      return {ok: true, json: async () => result};
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.method, 'GET'); // no automatic scan on page load
  assert.match(nodes['source-folder-items'].children[0].textContent, /가족/);
  await nodes['source-folders-form'].onsubmit({preventDefault() {}});
  const registrationRequest = requests.find(request => request.options.method === 'POST');
  assert.equal(JSON.parse(registrationRequest.options.body).root, '/inbox');
  assert.equal(registrationRequest.options.headers['X-Photo-Browser'], '1');
  assert.match(nodes['source-folder-status'].textContent, /기존 ID/);
  await nodes['source-folder-sync'].onclick();
  assert.match(nodes['source-folder-status'].textContent, /스캔·병합 완료/);
  assert.equal(nodes['source-folder-sync'].disabled, false);
  assert.equal(nodes['source-folder-stop'].hidden, true);
  assert.equal(refreshed.length, 2);
  fail = true;
  await nodes['source-folders-form'].onsubmit({preventDefault() {}});
  assert.equal(nodes['source-folder-register'].disabled, false);
  assert.match(nodes['source-folder-status'].textContent, /작업 중/);
  console.log('Source folder UI: explicit registration, manual batch, stable source refresh and failure recovery passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
