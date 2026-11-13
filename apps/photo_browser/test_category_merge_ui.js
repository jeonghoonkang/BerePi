const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const nodes = [];
  class Node {
    constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.value = ''; this.listeners = {}; nodes.push(this); }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    add(option) { this.append(option); }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    querySelectorAll(selector) {
      return this.children.flatMap(child => child instanceof Node
        ? [...((selector === 'input:checked' && child.tag === 'input' && child.checked)
          || (selector === 'button' && child.tag === 'button') ? [child] : []), ...child.querySelectorAll(selector)] : []);
    }
  }
  const roots = new Map();
  const get = id => nodes.findLast(node => node.id === id) || (() => {
    const node = new Node('div'); node.id = id; roots.set(id, node); return node;
  })();
  const tab = new Node('button');
  const groups = [
    {source_id: 'nasA', category: 'family', owner_id: 'alice', count: 2},
    {source_id: 'nasA', category: 'family', owner_id: 'bob', count: 1},
    {source_id: 'nasB', category: 'travel', owner_id: 'alice', count: 3}
  ];
  const requests = [];
  const document = {getElementById: get, createElement: tag => new Node(tag), createTextNode: text => text, querySelector: () => tab};
  const scope = {document, Option: function(text, value) { const node = new Node('option'); node.textContent = text; node.value = value; return node; },
    confirm: () => true, setTimeout, fetch: async (url, options) => {
      requests.push({url, options});
      let data;
      if (url.endsWith('/categories')) data = {groups};
      else if (url === 'api/category-merges') data = {items: []};
      else if (url.endsWith('/preview')) data = {job_id: 'preview-job'};
      else if (url === 'api/jobs/preview-job') data = {status: 'preview', result: {
        operation_id: 'plan', rows: [], copy_files: 0, copy_bytes: 0, warning: ''}};
      else throw new Error(`Unexpected request: ${url}`);
      return {ok: true, json: async () => data};
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/category_merges.js'), 'utf8'), scope);
  await tab.listeners.click();
  const change = (key, value) => { const filter = get(`category-filter-${key}`); filter.value = value; filter.onchange(); };
  change('source_id', 'nasA');
  change('owner_id', 'bob');
  const choices = get('category-choices');
  const inputs = () => choices.children.filter(node => node.tag === 'label').map(label => label.children[0]);
  assert.equal(inputs().length, 1);
  inputs()[0].checked = true;
  inputs()[0].onchange();
  get('category-target').value = 'memories';
  await get('category-merge-form').onsubmit({preventDefault() {}});
  const payload = JSON.parse(requests.find(request => request.url.endsWith('/preview')).options.body);
  assert.deepEqual(payload, {selections: [{source_id: 'nasA', category: 'family', owner_id: 'bob'}], target_category: 'memories'});
  assert.equal(get('category-run').disabled, false);
  change('source_id', 'nasB');
  assert.equal(inputs().length, 0);
  assert.equal(choices.querySelectorAll('input:checked').length, 0);
  assert.equal(get('category-run').disabled, true);
  change('owner_id', '*');
  assert.equal(inputs().length, 1);
  change('category', 'family');
  assert.equal(inputs().length, 0);
  console.log('Category merge UI: filters, exact preview scope and selection reset passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
