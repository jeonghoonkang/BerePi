/* Run with node test_directory_update_ui.js; no third-party packages needed. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const ids = Object.fromEntries(['directory-update', 'directory-update-button', 'directory-update-status',
    'directory-path', 'path', 'date', 'type', 'recursive'].map(id => [id, {value: '', textContent: '', disabled: false}]));
  let added = true, failure = false, refreshFailure = false, browseFailure = false, calls = 0;
  const previews = [], selected = [];
  const source = {source_id: 'directory_new', root: '/photos/new', recursive: true};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/directory_update.js'), 'utf8'), {
    document: {getElementById: id => ids[id]},
    window: {photoBrowserSourceUpdated: async value => {
      if (refreshFailure) throw new Error('refresh failed');
      selected.push(value);
    }},
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, 'api/sources/register-directory');
      assert.equal(options.method, 'POST');
      assert.equal(options.headers['X-Photo-Browser'], '1');
      assert.equal(JSON.parse(options.body).path, '/photos/new');
      return {ok: !failure, json: async () => failure ? {error: '작업 중'} : {added, source}};
    },
    browse: async folder => { previews.push(folder); return browseFailure ? undefined : {path: folder}; },
  });
  const submit = () => ids['directory-update'].onsubmit({preventDefault() {}});
  ids['directory-path'].value = ' /photos/new ';
  await submit();
  assert.match(ids['directory-update-status'].textContent, /신규 소스 추가.*directory_new/);
  assert.equal(ids['path'].value, '/photos/new');
  assert.equal(ids.recursive.checked, true);
  assert.equal(selected.length, 1);
  assert.deepEqual(previews, ['/photos/new']);
  assert.equal(ids['directory-update-button'].disabled, false);

  added = false; source.recursive = false;
  await submit();
  assert.match(ids['directory-update-status'].textContent, /기존 소스 선택/);
  assert.equal(ids.recursive.checked, false);

  failure = true;
  const previousPreviews = previews.length;
  await submit();
  assert.match(ids['directory-update-status'].textContent, /적용하지 못했습니다.*작업 중/);
  assert.equal(previews.length, previousPreviews);
  assert.equal(ids['directory-update-button'].disabled, false);

  failure = false; refreshFailure = true;
  await submit();
  assert.match(ids['directory-update-status'].textContent, /등록됐지만 화면 갱신에 실패/);

  refreshFailure = false; browseFailure = true;
  await submit();
  assert.match(ids['directory-update-status'].textContent, /기존 소스 선택.*폴더 미리보기 실패/);

  const previousCalls = calls;
  ids['directory-path'].value = '';
  await submit();
  assert.equal(calls, previousCalls);
  ids['directory-path'].value = '/photos/new';
  ids['directory-update-button'].disabled = true;
  await submit();
  assert.equal(calls, previousCalls);
  console.log('Directory Update UI: new/existing sources, failures and repeat prevention passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
