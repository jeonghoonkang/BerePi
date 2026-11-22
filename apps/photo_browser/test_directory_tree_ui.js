const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element(tag = 'div') {
  return {tag, children: [], listeners: {}, value: '', hidden: false, textContent: '',
    append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); },
    replaceChildren(...children) { this.children = []; this.append(...children); },
    addEventListener(name, callback) { this.listeners[name] = callback; },
    querySelector(tag) { return this.children.find(child => child.tag === tag || child.querySelector(tag)); },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    showModal() { this.open = true; }, close() { this.open = false; this.onclose?.(); },
    scrollIntoView() {},
    set innerHTML(_) { throw new Error('Unsafe HTML'); }};
}

async function main() {
  const ids = ['tree-scope', 'tree-refresh', 'tree-gallery', 'tree-selected-path', 'tree-media-status',
    'tree-more-files', 'directory-tree-roots', 'directory-tree-panel', 'tree-viewer', 'tree-viewer-close',
    'tree-viewer-title', 'tree-viewer-media', 'tree-viewer-download'];
  const nodes = Object.fromEntries(ids.map(id => [id, element()]));
  nodes['tree-scope'].value = 'source'; nodes['directory-tree-panel'].hidden = true;
  const requests = [];
  const window = {};
  let observe;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/directory_tree.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], createElement: tag => element(tag), querySelector: () => ({click() {}})}, window, URLSearchParams,
    MutationObserver: class { constructor(callback) { observe = callback; } observe() {} },
    fetch: async url => {
      requests.push(url);
      const query = new URL(url, 'http://localhost/').searchParams;
      const result = url.endsWith('/roots') ? {sources: [{name: '<script>source</script>', source_id: 'photos', path: '/inbox', scope: 'source'}],
        managed: [{name: '라이브러리', path: '/managed', scope: 'managed'}]} :
        query.get('kind') === 'media' ? {items: [{name: '<img>.jpg', path: query.get('path') + '/a.jpg', video: false}],
          total: 101, next_offset: query.get('offset') === '100' ? null : 100} :
        {items: [{name: 'nested', path: '/inbox/nested'}], next_offset: null};
      return {ok: true, json: async () => result};
    },
  });
  assert.equal(requests.length, 0); // closed tab does not traverse the filesystem
  nodes['directory-tree-panel'].hidden = false; observe();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 1); // roots only, no recursive enumeration
  const details = nodes['directory-tree-roots'].children[0].children[0];
  assert.equal(details.children[0].textContent, '📁 <script>source</script>');
  details.open = true; details.listeners.toggle();
  await details.children[0].listeners.click();
  assert.equal(nodes['tree-gallery'].children.length, 1);
  assert.equal(nodes['tree-more-files'].hidden, false);
  assert.equal(details.children[1].children[0].children[0].tag, 'details');
  await nodes['tree-more-files'].onclick();
  assert.equal(nodes['tree-gallery'].children.length, 2);
  assert.equal(nodes['tree-more-files'].hidden, true);
  nodes['tree-gallery'].children[0].onclick();
  assert.equal(nodes['tree-viewer'].open, true);
  assert.match(nodes['tree-viewer-download'].href, /download=1/);
  nodes['tree-viewer-close'].onclick();
  assert.equal(nodes['tree-viewer-media'].children.length, 0);
  nodes['tree-scope'].value = 'managed'; await nodes['tree-scope'].onchange();
  assert.equal(nodes['tree-gallery'].children.length, 0);
  const managed = nodes['directory-tree-roots'].children[0].children[0];
  await managed.children[0].listeners.click();
  assert.equal(nodes['tree-selected-path'].textContent, '/managed');
  assert.ok(requests.some(url => url.includes('scope=managed')));
  await window.photoBrowserOpenDirectory({source_id: 'photos', path: '/inbox/nested'});
  assert.equal(nodes['tree-selected-path'].textContent, '/inbox/nested');
  console.log('Directory tree UI: lazy expansion, safe labels, media pagination, viewer and scope switching passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
