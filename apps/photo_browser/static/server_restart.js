/* Restart the saved server command; never accept a command from the browser. */
(() => {
  const button = document.getElementById('server-restart');
  const status = document.getElementById('server-restart-status');
  let instance;
  async function state() {
    const response = await fetch('api/server-lifecycle', {cache: 'no-store', signal: AbortSignal.timeout(4000)});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
    return value;
  }
  async function initialize() {
    try {
      const value = await state(); instance = value.instance_id;
      button.disabled = !value.supported || value.pending;
      status.textContent = value.pending ? '서버 재시작 중…' : value.supported ? '실행 당시 명령·옵션으로 다시 시작합니다.' : value.reason;
      if (value.pending) await reconnect(value.instance_id);
    } catch (error) { status.textContent = `재시작 상태 확인 실패: ${error.message}`; }
  }
  async function reconnect(oldInstance) {
    const deadline = Date.now() + 300000;
    for (let attempt = 0; Date.now() < deadline; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      let value;
      try {
        value = await state();
        if (value.instance_id !== oldInstance && !value.pending) { window.location.reload(); return; }
      } catch (_) { /* The port is briefly unavailable while the server restarts. */ }
      if (value?.error) { status.textContent = `재시작 실패: ${value.error}`; button.disabled = false; return; }
      status.textContent = `서버 재시작·재연결을 기다리는 중… ${attempt + 1}회 확인`;
    }
    status.textContent = '재연결 대기 시간이 지났습니다. 서버 로그를 확인하고 페이지를 새로고침하세요.';
  }
  button.onclick = async () => {
    if (!confirm('웹서버를 실행 당시 명령과 옵션으로 재시작하시겠습니까?\n모든 접속자의 연결이 잠시 끊깁니다. 진행 중인 작업이 있으면 먼저 중지하고 저장해야 합니다.')) return;
    button.disabled = true; status.textContent = '서버 재시작 요청 중…';
    try {
      const response = await fetch('api/server-restart', {method: 'POST', headers: {'X-Photo-Browser': '1', 'Content-Type': 'application/json'}, body: '{}'});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      await reconnect(value.instance_id || instance);
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  };
  initialize();
})();
