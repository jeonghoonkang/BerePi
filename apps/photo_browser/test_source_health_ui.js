const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
  return {children: [], dataset: {}, value: '', textContent: '', hidden: false, disabled: false,
    append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } },
    replaceChildren(...children) { this.children = []; this.append(...children); },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    setAttribute() {}, close() { this.open = false; },
    set innerHTML(_) { throw new Error('Unsafe HTML'); }};
}

async function main() {
  const names = ['source-health-banner', 'source-health-banner-text', 'health-summary', 'health-message',
    'source-health-panel', 'health-view', 'health-issues', 'health-empty', 'health-page', 'health-prev',
    'health-next', 'health-check', 'detail-original-check', 'library-detail', 'detail-original-locations'];
  const nodes = Object.fromEntries(names.map(name => [name, element()]));
  nodes['health-view'].value = 'open'; nodes['library-detail'].dataset.mediaId = 'photo';
  const issue = {issue_id: 'incident', media_id: 'photo', name: '<photo.jpg>', source_id: 'photos', path: '/photos/old.jpg',
    status: 'open', problem: '原本 missing', first_seen_at: '2026-11-22T00:00:00Z', last_seen_at: '2026-11-22T00:00:05Z', observations: 1};
  let interval, action, allow = false, repaired = false, failing = false;
  const requests = [], navigated = [];
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/source_health.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], createElement: () => element(), hidden: false}, URLSearchParams,
    window: {photoBrowserOpenDirectory: async value => navigated.push(value)},
    confirm: () => allow,
    MutationObserver: class { observe() {} },
    setInterval(callback) { interval = callback; }, setTimeout(callback) { setImmediate(callback); },
    fetch: async (url, options) => {
      requests.push({url, options});
      if (failing) return {ok: false, status: 503, json: async () => ({error: 'unavailable'})};
      let data;
      if (url.includes('/api/library/') || url.startsWith('api/library/')) data = {items: [{source_id: 'photos', path: '/photos/old.jpg', folder: '/photos', health: 'missing', problem: 'file missing'}]};
      else if (url.includes('/issues?')) data = {items: url.includes('view=resolved') ?
        [{...issue, status: 'resolved', resolved_at: '2026-11-22T00:01:00Z', resolution: 'verified_db_path_updated', new_path: '/photos/new.jpg'}] : repaired ? [] : [issue], total: repaired && !url.includes('resolved') ? 0 : 1};
      else if (url.startsWith('api/jobs/')) {
        if (action === 'repair') repaired = true;
        data = {status: 'completed', result: action === 'find' ? {candidates: ['/photos/new.jpg'], checked_files: 10, limited: true, warning: 'Confirm candidate'} : {status: 'completed', new_path: '/photos/new.jpg'}};
      } else if (options.method === 'POST') { action = url.split('/').pop(); data = {job_id: 'operation'}; }
      else data = {active_count: repaired ? 0 : 1, resolved_count: repaired ? 1 : 0, checked_at: '2026-11-22T00:00:05Z', monitoring: true, interval: 5};
      return {ok: true, json: async () => data};
    },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await settle();
  assert.match(nodes['source-health-banner-text'].textContent, /미해결 1건/);
  assert.equal(nodes['source-health-banner'].dataset.state, 'warning');
  const row = nodes['health-issues'].children[0];
  const input = row.children[4]; input.value = 'typed path';
  interval(); await settle();
  assert.equal(nodes['health-issues'].children[0], row);
  assert.equal(input.value, 'typed path'); // polling must not replace an editing input
  await row.children[3].onclick();
  assert.match(row.children[6].children[0].textContent, /전체 검색은 아닙니다/);
  await row.children[6].children[1].onclick();
  assert.equal(input.value, '/photos/new.jpg');
  await row.children[5].onclick();
  assert.equal(requests.some(request => request.url.endsWith('/repair')), false);
  allow = true; await row.children[5].onclick();
  assert.ok(requests.some(request => request.url.endsWith('/repair') && request.options.headers['X-Photo-Browser'] === '1'));
  assert.equal(nodes['source-health-banner'].dataset.state, 'ok');
  nodes['health-view'].value = 'resolved'; nodes['health-view'].onchange(); await settle();
  assert.match(nodes['health-issues'].children[0].children[2].textContent, /검증한 새 원본 경로/);
  await nodes['detail-original-check'].onclick();
  const original = nodes['detail-original-locations'].children[0];
  assert.match(original.textContent, /old.jpg/);
  await original.children[0].onclick();
  assert.equal(navigated[0].source_id, 'photos');
  failing = true; interval(); await settle();
  assert.equal(nodes['source-health-banner'].dataset.state, 'error');
  console.log('Source health UI: alerts, preserved input, bounded candidate search, explicit repair, history and original navigation passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
