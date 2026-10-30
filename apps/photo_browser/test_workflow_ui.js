/* Run with node test_workflow_ui.js; no browser or third-party packages needed. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
  return {dataset: {}, attributes: {}, textContent: '', hidden: false, value: 0,
    setAttribute(key, value) { this.attributes[key] = value; },
    removeAttribute(key) { delete this.attributes[key]; }};
}

async function main() {
  const keys = ['settings', 'scan', 'database', 'merge'];
  const nodes = Object.fromEntries(keys.map(key => {
    const node = element();
    const children = Object.fromEntries(['.workflow-number', '.workflow-state', '.workflow-detail', 'progress', 'button'].map(k => [k, element()]));
    node.querySelector = selector => children[selector];
    return [key, node];
  }));
  const root = element();
  root.querySelector = selector => nodes[selector.match(/="(.+)"/)[1]];
  root.querySelectorAll = () => [];
  const ids = {'merge-workflow': root};
  for (const id of ['workflow-summary', 'workflow-total', 'workflow-error', 'workflow-refresh', 'workflow-note']) ids[id] = element();
  let data = {steps: keys.map((id, index) => ({id, status: index ? 'pending' : 'completed', percent: index ? 0 : 100, detail: '저장된 상태'})),
    percent: 25, completed_steps: 1, total_steps: 4, note: '단계 기준'};
  let failing = false;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/workflow.js'), 'utf8'), {
    document: {getElementById: id => ids[id], hidden: false, addEventListener() {}},
    window: {addEventListener() {}},
    setTimeout() { return 1; }, clearTimeout() {},
    fetch: async () => ({ok: !failing, status: failing ? 503 : 200, json: async () => data}),
  });
  const settled = () => new Promise(resolve => setImmediate(resolve));
  await settled();
  assert.equal(nodes.settings.dataset.state, 'completed');
  assert.equal(nodes.settings.querySelector('.workflow-number').textContent, '✓');
  assert.equal(nodes.scan.querySelector('button').attributes['aria-current'], 'step');
  assert.equal(ids['workflow-total'].value, 25);

  data = {...data, steps: data.steps.map(s => s.id === 'scan' ? {...s, status: 'running', percent: null} : s)};
  await ids['workflow-refresh'].onclick();
  assert.equal(nodes.scan.dataset.state, 'running');
  assert.equal(nodes.scan.querySelector('.workflow-state').textContent, '진행 중');
  assert.equal(nodes.scan.querySelector('progress').attributes.value, undefined);

  failing = true;
  await ids['workflow-refresh'].onclick();
  assert.equal(ids['workflow-error'].hidden, false);
  assert.equal(root.dataset.stale, 'true');
  assert.equal(nodes.scan.dataset.state, 'running'); // retain, but explicitly flag old data

  failing = false;
  data = {...data, percent: 100, completed_steps: 4,
    steps: data.steps.map(s => ({...s, status: 'completed', percent: 100}))};
  await ids['workflow-refresh'].onclick();
  assert.equal(ids['workflow-error'].hidden, true);
  assert.equal(ids['workflow-total'].value, 100);
  assert.match(ids['workflow-summary'].textContent, /4\/4/);
  for (const node of Object.values(nodes)) {
    assert.equal(node.dataset.state, 'completed');
    assert.equal(node.querySelector('progress').value, 100);
    assert.equal(node.querySelector('button').attributes['aria-current'], undefined);
  }
  console.log('Workflow UI: completion, live progress, failure and recovery passed.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
