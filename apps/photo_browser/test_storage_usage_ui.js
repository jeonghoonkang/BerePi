const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function element() {
  return {children: [], dataset: {}, textContent: '', hidden: false, disabled: false,
    append(...children) { this.children.push(...children); }, replaceChildren(...children) { this.children = children; },
    set innerHTML(_) { throw new Error('Unsafe HTML'); }};
}
async function main() {
  const ids = ['storage-refresh', 'storage-library-free', 'storage-library-total', 'storage-volumes',
    'storage-status', 'storage-errors', 'storage-overview', 'storage-error'];
  for (const kind of ['db', 'sources', 'managed']) ids.push(`storage-${kind}-size`, `storage-${kind}-allocation`);
  const nodes = Object.fromEntries(ids.map(id => [id, element()]));
  let interval, fail = false;
  const requests = [];
  const volume = {device_id: 'one', path: '/data', labels: ['DB', '<script>source</script>'],
    roles: ['db', 'managed', 'sources'], total_bytes: 1024, used_bytes: 512, free_bytes: 512, used_percent: 50};
  let data = {state: 'pending', running: true, categories: {}, volumes: [volume], errors: []};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/storage_usage.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], createElement: () => element(), hidden: false},
    setInterval(callback) { interval = callback; },
    fetch: async url => { requests.push(url); return {ok: !fail, status: fail ? 503 : 200, json: async () => fail ? {error: 'not available'} : data}; },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await settle();
  assert.equal(nodes['storage-db-size'].textContent, '미집계');
  assert.match(nodes['storage-status'].textContent, /백그라운드 집계 중/);
  assert.equal(nodes['storage-library-free'].textContent, '512 B');
  assert.equal(nodes['storage-volumes'].children.length, 1);
  data = {...data, state: 'ready', running: false, checked_at: '2026-11-22T00:00:00Z',
    categories: Object.fromEntries(['db', 'sources', 'managed'].map(kind => [kind, {state: 'ready', logical_bytes: 2048, allocated_bytes: 4096, file_count: 2}]))};
  interval(); await settle();
  assert.equal(nodes['storage-db-size'].textContent, '2 KiB');
  assert.match(nodes['storage-managed-allocation'].textContent, /4 KiB/);
  assert.match(nodes['storage-status'].textContent, /KST/);
  assert.match(nodes['storage-volumes'].children[0].children[0].textContent, /<script>/);
  await nodes['storage-refresh'].onclick();
  assert.equal(requests.at(-1), 'api/storage-usage?refresh=1');
  data = {...data, volumes: [volume, {...volume, device_id: 'two', path: '/other'}]};
  interval(); await settle();
  assert.equal(nodes['storage-library-free'].textContent, '2개 파일시스템'); // no pooled/free sum
  data = {...data, state: 'partial', categories: {...data.categories, sources: {state: 'error', logical_bytes: null, allocated_bytes: null, errors: ['source offline']}}};
  interval(); await settle();
  assert.equal(nodes['storage-sources-size'].textContent, '미집계');
  assert.equal(nodes['storage-errors'].children.length, 1);
  fail = true; interval(); await settle();
  assert.equal(nodes['storage-error'].hidden, false);
  assert.equal(nodes['storage-overview'].dataset.state, 'error');
  assert.equal(nodes['storage-db-size'].textContent, '2 KiB');
  console.log('Storage UI: pending vs zero, capacity, partial totals, safe labels, refresh and stale-error recovery passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
