/* node test_auth_ui.js: GUI flow contract, no real credentials or browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  return {value: '', hidden: true, disabled: false, textContent: '', attributes: {},
    setAttribute(key, value) { this.attributes[key] = value; }};
}

async function environment(enabled) {
  const ids = ['auth-bar', 'auth-message', 'auth-state', 'auth-login', 'auth-account', 'auth-change',
    'auth-setup-help', 'auth-token-label', 'auth-setup-token', 'auth-password', 'auth-new-password',
    'auth-confirm-password', 'auth-change-toggle', 'auth-logout'];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  for (const [form, fields] of [['auth-login', ['auth-password']], ['auth-change', ['auth-setup-token', 'auth-new-password', 'auth-confirm-password']]]) {
    const button = element();
    elements[form].querySelector = () => button;
    elements[form].querySelectorAll = () => fields.map(id => elements[id]);
  }
  const state = {enabled, authenticated: false}, calls = [];
  let poll, reloads = 0;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/auth.js'), 'utf8'), {
    document: {getElementById: id => elements[id], hidden: false, addEventListener() {}},
    window: {location: {reload() { reloads++; }}, addEventListener() {}},
    setTimeout(callback) { poll = callback; return 1; }, clearTimeout() {},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (options.method === 'GET') return {ok: true, json: async () => ({...state})};
      state.authenticated = !url.endsWith('/logout');
      if (url.endsWith('/setup')) state.enabled = true;
      return {ok: true, json: async () => ({ok: true})};
    },
  });
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await settle();
  return {el: id => elements[id], calls, state, settle, poll: () => poll(), reloads: () => reloads};
}

async function main() {
  const app = await environment(true);
  assert.equal(app.el('auth-login').hidden, false);
  assert.equal(app.el('auth-change').hidden, true);
  app.el('auth-password').value = 'fixture-password';
  await app.el('auth-login').onsubmit({preventDefault() {}});
  assert.equal(app.calls[app.calls.length - 1].url, 'api/auth/login');
  assert.equal(app.calls[app.calls.length - 1].options.credentials, 'same-origin');
  assert.equal(app.el('auth-password').value, '');
  assert.equal(app.reloads(), 1);
  app.poll(); await app.settle();
  assert.equal(app.el('auth-account').hidden, false);
  app.el('auth-change-toggle').onclick();
  assert.equal(app.el('auth-change').hidden, false);
  app.el('auth-new-password').value = 'new-fixture-password';
  app.el('auth-confirm-password').value = 'different';
  const before = app.calls.length;
  await app.el('auth-change').onsubmit({preventDefault() {}});
  assert.equal(app.calls.length, before);
  assert.match(app.el('auth-message').textContent, /확인 값이 다릅니다/);
  app.el('auth-new-password').value = 'new-fixture-password';
  app.el('auth-confirm-password').value = 'new-fixture-password';
  await app.el('auth-change').onsubmit({preventDefault() {}});
  assert.equal(app.calls[app.calls.length - 2].url, 'api/auth/password');
  assert.equal(app.el('auth-new-password').value, '');
  assert.equal(app.el('auth-change').hidden, true);
  assert.match(app.el('auth-message').textContent, /저장했습니다/);
  await app.el('auth-logout').onclick();
  assert.equal(app.calls[app.calls.length - 1].url, 'api/auth/logout');
  assert.equal(app.reloads(), 2);

  const setup = await environment(false);
  assert.equal(setup.el('auth-login').hidden, true);
  assert.equal(setup.el('auth-change').hidden, false);
  assert.equal(setup.el('auth-token-label').hidden, false);
  setup.el('auth-setup-token').value = 'fixture-owner-token';
  setup.el('auth-new-password').value = 'initial-fixture-password';
  setup.el('auth-confirm-password').value = 'initial-fixture-password';
  await setup.el('auth-change').onsubmit({preventDefault() {}});
  const call = setup.calls.find(c => c.url === 'api/auth/setup');
  assert.equal(JSON.parse(call.options.body).setup_token, 'fixture-owner-token');
  assert.equal(setup.el('auth-setup-token').value, '');
  assert.equal(setup.el('auth-account').hidden, false);
  console.log('Auth UI: login, password save/confirmation, logout and initial setup passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
