const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function node() {
  return {hidden: true, disabled: false, textContent: '', value: 0, handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; }, dispatchEvent(event) { this.handlers[event.type]?.(event); }};
}
async function main() {
  const ids = Object.fromEntries(['start', 'stop', 'state', 'progress', 'detail', 'error'].map(id => [`nominatim-scan-${id}`, node()]));
  const panel = ids['nominatim-panel'] = node();
  const requests = []; let interval, open, ready = false, complete = false, stopped = false, completedEvents = 0, serial = 0;
  panel.addEventListener('nominatim-scan-complete', () => completedEvents++);
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/nominatim_scan.js'), 'utf8'), {
    document: {hidden: false, getElementById: id => ids[id]},
    CustomEvent: class { constructor(type) { this.type = type; } },
    MutationObserver: class { constructor(callback) { open = callback; } observe() {} },
    setInterval(callback) { interval = callback; },
    fetch: async (url, options) => {
      requests.push({url, options});
      let data = {}, ok = true;
      if (url.includes('scan-missing')) { ok = ready; data = ready ? {job_id: `fill-tags-${++serial}`} : {error: 'Nominatim이 준비되지 않았습니다.'}; }
      else if (url.includes('/stop')) stopped = true;
      else if (url.includes('api/jobs?')) data = {items: []};
      else data = {status: complete ? 'completed' : stopped ? 'stopped' : 'running',
        progress: {total: 10, processed: 2, updated: 1, no_gps: 1, percent: 20, current_file: '<photo.jpg>'}};
      return {ok, json: async () => data};
    },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  panel.hidden = false; open(); await settle();
  await ids['nominatim-scan-start'].handlers.click();
  assert.match(ids['nominatim-scan-error'].textContent, /준비되지/);
  assert.equal(ids['nominatim-scan-start'].disabled, false);
  ready = true;
  await ids['nominatim-scan-start'].handlers.click();
  assert.equal(requests.find(request => request.url.includes('scan-missing')).options.headers['X-Photo-Browser'], '1');
  assert.equal(ids['nominatim-scan-start'].disabled, true);
  assert.equal(ids['nominatim-scan-stop'].hidden, false);
  assert.equal(ids['nominatim-scan-progress'].value, 20);
  assert.match(ids['nominatim-scan-detail'].textContent, /<photo.jpg>/);
  await ids['nominatim-scan-stop'].handlers.click();
  assert.match(ids['nominatim-scan-state'].textContent, /중지됨/);
  assert.equal(completedEvents, 1);
  stopped = false;
  await ids['nominatim-scan-start'].handlers.click();
  complete = true; interval(); await settle();
  assert.match(ids['nominatim-scan-state'].textContent, /완료/);
  assert.equal(completedEvents, 2);
  interval(); await settle(); assert.equal(completedEvents, 2);
  panel.dispatchEvent({type: 'nominatim-statistics-updated', detail: {location_scan_candidate_count: 0}});
  assert.equal(ids['nominatim-scan-start'].disabled, false); // Still allow no_gps classification.
  assert.match(ids['nominatim-scan-start'].title, /위치 조회 대상 0개/);
  console.log('Nominatim missing-tag UI: readiness, progress, stop, completion and empty selection passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
