/* The password is only sent to the same-origin server and is never cached here. */
(() => {
  const el = id => document.getElementById(id);
  if (!el('auth-bar')) return;
  let enabled = false, authenticated = false, initialized = false, timer;
  const message = text => { el('auth-message').textContent = text; };
  async function api(path, data) {
    const response = await fetch(path, {method: data ? 'POST' : 'GET', cache: 'no-store',
      credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'},
      body: data ? JSON.stringify(data) : undefined});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  async function status() {
    const value = await api('api/auth/status');
    const previous = {enabled, authenticated};
    enabled = value.enabled; authenticated = value.authenticated;
    if (initialized && enabled && !authenticated && (previous.authenticated || !previous.enabled)) {
      window.location.reload(); return;
    }
    el('auth-state').textContent = authenticated ? '로그인됨' : enabled ? '로그인 필요' : '암호 미설정 · 현재 인증 없이 접근 가능';
    el('auth-login').hidden = !enabled || authenticated;
    el('auth-account').hidden = !authenticated;
    if (!initialized || previous.enabled !== enabled || previous.authenticated !== authenticated) el('auth-change').hidden = enabled;
    el('auth-setup-help').hidden = enabled;
    el('auth-token-label').hidden = enabled;
    el('auth-setup-token').required = !enabled;
    initialized = true;
  }
  function bind(id, handler) {
    el(id).onsubmit = async event => {
      event.preventDefault();
      const button = el(id).querySelector('button[type=submit]'); button.disabled = true;
      try { await handler(); }
      catch (error) { message(error.message); }
      finally { button.disabled = false; el(id).querySelectorAll('input[type=password]').forEach(input => { input.value = ''; }); }
    };
  }
  bind('auth-login', async () => {
    await api('api/auth/login', {password: el('auth-password').value});
    window.location.reload();
  });
  bind('auth-change', async () => {
    if (el('auth-new-password').value !== el('auth-confirm-password').value) throw new Error('새 비밀번호 확인 값이 다릅니다.');
    await api(enabled ? 'api/auth/password' : 'api/auth/setup', {
      password: el('auth-new-password').value, confirm_password: el('auth-confirm-password').value,
      ...(!enabled ? {setup_token: el('auth-setup-token').value} : {}),
    });
    await status(); message('비밀번호를 저장했습니다. 현재 로그인은 유지되고 다른 세션은 종료됩니다.');
    el('auth-change').hidden = true;
    el('auth-change-toggle').setAttribute('aria-expanded', 'false');
  });
  el('auth-change-toggle').onclick = () => {
    el('auth-change').hidden = !el('auth-change').hidden;
    el('auth-change-toggle').setAttribute('aria-expanded', String(!el('auth-change').hidden));
  };
  el('auth-logout').onclick = async () => {
    try { await api('api/auth/logout', {}); window.location.reload(); }
    catch (error) { message(error.message); }
  };
  function poll() {
    clearTimeout(timer);
    if (!document.hidden) status().catch(error => message(error.message));
    timer = setTimeout(poll, 30000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  window.addEventListener('pagehide', () => clearTimeout(timer));
  poll();
})();
