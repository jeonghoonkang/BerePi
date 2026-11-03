/* node test_library_summary_ui.js — no browser or external packages required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  return {children: [], textContent: '', value: '', dataset: {}, attributes: {}, listeners: {}, open: false,
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    addEventListener(key, callback) { this.listeners[key] = callback; },
    setAttribute(key, value) { this.attributes[key] = value; },
    removeAttribute(key) { delete this.attributes[key]; if (key === 'data-stale') delete this.dataset.stale; },
    scrollIntoView() { this.scrolled = true; },
    set innerHTML(value) { throw new Error('Untrusted metadata must be rendered as text.'); }};
}

async function main() {
  const names = ['library-summary', 'summary-toggle', 'summary-filter', 'summary-refresh', 'summary-badge',
    'summary-metrics', 'summary-sources', 'summary-groups', 'summary-status', 'summary-note', 'summary-group-count', 'summary-more'];
  const elements = Object.fromEntries(names.map(name => [name, element()]));
  const counts = {media_count: 1, media_bytes: 100, source_file_count: 1, source_directory_count: 1,
    managed_file_count: 1, managed_directory_count: 1, missing_source_file_count: 0};
  const data = {totals: counts, source_count: 1, configured_source_count: 1, catalog_source_count: 1,
    category_ids: ['family', 'work'], owner_ids: ['alice', 'bob'], current_chunk_count: 2, inactive_media_count: 0,
    observed_at: '2026-11-03T00:00:00Z', note: 'DB 기록 기준',
    sources: [{...counts, source_id: '<script>test</script>', registered: true, root: '/source',
      category_ids: ['family', 'work'], owner_ids: ['alice', 'bob'], configured_category_ids: ['family'], configured_owner_ids: ['alice']}],
    groups: Array.from({length: 102}, (_, i) => ({...counts, source_id: 'photos', category_id: `category${i}`, owner_id: i ? 'alice' : 'bob'}))};
  let requests = [], failing = false;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/library_summary.js'), 'utf8'), {
    document: {getElementById: id => elements[id], createElement: element, hidden: false, addEventListener() {}},
    window: {addEventListener() {}}, setTimeout() { return 1; }, clearTimeout() {},
    fetch: async url => { requests.push(url); return {ok: !failing, status: failing ? 409 : 200,
      json: async () => failing ? {error: '청크 읽기 실패'} : data}; },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 0); // no full-DB load while collapsed
  elements['summary-toggle'].onclick();
  elements['library-summary'].listeners.toggle();
  await settle();
  assert.equal(elements['summary-toggle'].attributes['aria-expanded'], 'true');
  assert.equal(elements['summary-metrics'].children.length, 8);
  assert.equal(elements['summary-sources'].children[0].children[0].children[0].textContent, '<script>test</script>');
  assert.equal(elements['summary-groups'].children.length, 100);
  assert.equal(elements['summary-more'].hidden, false);
  elements['summary-more'].onclick();
  assert.equal(elements['summary-groups'].children.length, 102);
  elements['summary-filter'].value = 'BOB';
  elements['summary-filter'].oninput();
  assert.equal(elements['summary-groups'].children.length, 1);
  assert.equal(elements['summary-groups'].children[0].children[2].textContent, 'bob');
  failing = true;
  await elements['summary-refresh'].onclick();
  assert.equal(elements['library-summary'].dataset.stale, 'true');
  assert.match(elements['summary-status'].textContent, /집계 실패/);
  assert.equal(elements['summary-groups'].children.length, 1);
  failing = false;
  await elements['summary-refresh'].onclick();
  assert.equal(elements['library-summary'].dataset.stale, undefined);
  assert.equal(requests[requests.length - 1], 'api/library-summary?refresh=1');
  elements['summary-toggle'].onclick();
  const before = requests.length;
  elements['library-summary'].listeners.toggle();
  await elements['summary-refresh'].onclick();
  assert.equal(requests.length, before);
  assert.equal(elements['summary-toggle'].attributes['aria-expanded'], 'false');
  console.log('Summary UI: lazy loading, expand/collapse, grouping/filtering, paging and error recovery passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
