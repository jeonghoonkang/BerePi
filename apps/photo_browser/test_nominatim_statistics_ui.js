/* Run with node test_nominatim_statistics_ui.js. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
  return {hidden: true, value: '', disabled: false, textContent: '', children: [],
    addEventListener(event, callback) { this[event] = callback; },
    dispatchEvent() {}, replaceChildren() { this.children = []; }, append(...children) { this.children.push(...children); }};
}

async function main() {
  const ids = Object.fromEntries(['refresh', 'status', 'error', 'summary', 'kind', 'search', 'rows', 'previous', 'next']
    .map(name => [`nominatim-statistics-${name}`, element()]));
  ids['nominatim-panel'] = element();
  ids['nominatim-statistics-kind'].value = 'location_tags';
  let poll, open, fail = false, requests = [];
  const group = {tag_count: 101, empty_photo_count: 1, empty_percent: 33.33};
  const row = {tag: '<script>unsafe</script>', photo_count: 2, percent: 66.67, missing_photo_count: 1, missing_percent: 33.33};
  const data = {total_photos: 3, missing_gps_photo_count: 2, missing_gps_percent: 66.67,
    tag_count: 101, groups: {location_tags: group, tags: group},
    observed_at: '2026-11-08', items: [row], matched_tags: 101};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/nominatim_statistics.js'), 'utf8'), {
    document: {hidden: false, getElementById: id => ids[id], createElement: element}, URLSearchParams,
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options?.detail; } },
    MutationObserver: class { constructor(callback) { open = callback; } observe() {} },
    setInterval(callback) { poll = callback; }, setTimeout, clearTimeout,
    fetch: async url => { requests.push(url); return {ok: !fail, json: async () => fail ? {error: 'DB 읽기 실패'} : data}; },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  poll(); await settle(); assert.equal(requests.length, 0);
  ids['nominatim-panel'].hidden = false; open(); await settle();
  const summary = ids['nominatim-statistics-summary'].children;
  const gpsIndex = summary.findIndex(item => item.textContent === 'GPS 정보가 없는 사진');
  const tagIndex = summary.findIndex(item => item.textContent === '사용 중인 고유 태그 수');
  assert.ok(gpsIndex >= 0 && gpsIndex < tagIndex);
  assert.equal(summary[gpsIndex + 1].textContent, '2개 (66.67%)');
  const cells = ids['nominatim-statistics-rows'].children[0].children;
  assert.equal(cells[0].textContent, row.tag); // Tag names are inert text.
  assert.equal(cells[2].textContent, '66.67%');
  assert.equal(cells[3].textContent, '1');
  assert.equal(ids['nominatim-statistics-next'].disabled, false);
  ids['nominatim-statistics-next'].click(); await settle();
  assert.match(requests.at(-1), /offset=100/);
  ids['nominatim-statistics-kind'].value = 'tags';
  ids['nominatim-statistics-kind'].change(); await settle();
  assert.match(requests.at(-1), /kind=tags/);
  assert.match(requests.at(-1), /offset=0/);
  ids['nominatim-statistics-refresh'].click(); await settle();
  assert.match(requests.at(-1), /refresh=1/);
  fail = true; poll(); await settle();
  assert.equal(ids['nominatim-statistics-error'].hidden, false);
  assert.match(ids['nominatim-statistics-error'].textContent, /최신이 아닐 수/);
  assert.equal(ids['nominatim-statistics-rows'].children[0].children[2].textContent, '66.67%');
  fail = false; data.total_photos = 0; data.items = []; data.matched_tags = 0;
  poll(); await settle();
  assert.equal(ids['nominatim-statistics-error'].hidden, true);
  assert.equal(ids['nominatim-statistics-next'].disabled, true);
  assert.match(ids['nominatim-statistics-rows'].children[0].children[0].textContent, /태그가 없습니다/);
  console.log('Nominatim statistics UI: coverage, pagination, refresh, safe names and failures passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
