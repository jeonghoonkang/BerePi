/* Run with node test_nominatim_ui.js. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
  return {hidden: true, textContent: '', children: [], scrollTop: 0, scrollHeight: 0, clientHeight: 0,
    addEventListener(name, listener) { this[name] = listener; },
    replaceChildren() { this.children = []; }, append(...items) { this.children.push(...items); }};
}

async function main() {
  const ids = Object.fromEntries(['panel', 'state', 'refresh', 'fetch-error', 'info', 'progress', 'error', 'logs']
    .map(id => [`nominatim-${id}`, element()]));
  let interval, changed, requests = 0, failure = false;
  const data = {phase: 'map_download', ready: false, message: '지도 다운로드 중', progress: '50% · 남은 시간 0:00:50',
    events: [{time: '2026-11-08', message: '<img src=x onerror=alert(1)>'}]};
  const document = {hidden: false, getElementById: id => ids[id], createElement: element};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/nominatim.js'), 'utf8'), {
    document, MutationObserver: class { constructor(callback) { changed = callback; } observe() {} },
    setInterval(callback) { interval = callback; },
    fetch: async () => { requests++; return {ok: !failure, status: 503, json: async () => data}; },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  interval(); await settle();
  assert.equal(requests, 0, 'Hidden tabs should not poll');
  ids['nominatim-panel'].hidden = false;
  changed(); await settle();
  assert.match(ids['nominatim-state'].textContent, /다운로드 중/);
  assert.match(ids['nominatim-progress'].textContent, /50%/);
  assert.match(ids['nominatim-logs'].textContent, /<img/); // Log is inert text, never HTML.

  data.phase = 'error'; data.error = 'Docker permission denied';
  await ids['nominatim-refresh'].click();
  assert.equal(ids['nominatim-error'].hidden, false);
  assert.equal(ids['nominatim-error'].textContent, data.error);
  failure = true;
  await ids['nominatim-refresh'].click();
  assert.match(ids['nominatim-fetch-error'].textContent, /이전 결과/);
  assert.equal(ids['nominatim-fetch-error'].hidden, false);
  failure = false; data.phase = 'ready'; data.ready = true; data.error = null;
  interval(); await settle();
  assert.match(ids['nominatim-state'].textContent, /준비 완료/);
  assert.equal(ids['nominatim-error'].hidden, true);
  assert.equal(ids['nominatim-fetch-error'].hidden, true);
  const before = requests;
  document.hidden = true;
  interval(); await settle();
  assert.equal(requests, before);
  console.log('Nominatim UI: polling, progress, errors, recovery and safe logs passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
