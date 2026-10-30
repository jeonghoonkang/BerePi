/* Server-derived progress: never infer completion from a click or localStorage. */
(() => {
  const root = document.getElementById('merge-workflow');
  if (!root) return;
  const names = {pending: '대기', running: '진행 중', completed: '완료', warning: '확인 필요', failed: '실패'};
  const symbols = {pending: null, running: '↻', completed: '✓', warning: '!', failed: '×'};
  const summary = document.getElementById('workflow-summary');
  const overall = document.getElementById('workflow-total');
  const error = document.getElementById('workflow-error');
  const refresh = document.getElementById('workflow-refresh');
  let loading = false, timer, lastAnnouncement = '';

  function render(data) {
    let current = false;
    for (const [index, step] of data.steps.entries()) {
      const node = root.querySelector(`[data-workflow-step="${step.id}"]`);
      if (!node) continue;
      const state = names[step.status] ? step.status : 'pending';
      node.dataset.state = state;
      node.querySelector('.workflow-number').textContent = symbols[state] || String(index + 1);
      node.querySelector('.workflow-state').textContent = names[state] + (step.percent === null ? '' : ` · ${step.percent}%`);
      node.querySelector('.workflow-detail').textContent = step.detail;
      const bar = node.querySelector('progress');
      if (step.percent === null) bar.removeAttribute('value');
      else bar.value = step.percent;
      const button = node.querySelector('button');
      if (!current && state !== 'completed') { button.setAttribute('aria-current', 'step'); current = true; }
      else button.removeAttribute('aria-current');
    }
    overall.value = data.percent;
    const message = `완료 ${data.completed_steps}/${data.total_steps}단계 · 단계 진행률 ${data.percent}%`;
    if (lastAnnouncement !== message) { summary.textContent = message; lastAnnouncement = message; }
    document.getElementById('workflow-note').textContent = data.note + ' 초록: 완료 · 파랑: 진행 중 · 주황: 확인 필요 · 빨강: 실패 · 회색: 대기';
  }

  async function update() {
    if (loading) return;
    loading = true; refresh.disabled = true;
    try {
      const response = await fetch('api/workflow', {cache: 'no-store'});
      if (!response.ok) throw new Error(`진행 상태 조회 실패 (HTTP ${response.status}). 새로고침하여 다시 확인하세요.`);
      render(await response.json());
      error.hidden = true; root.removeAttribute('data-stale');
    } catch (failure) {
      error.textContent = `${failure.message} 표시된 이전 상태는 최신 정보가 아닐 수 있습니다.`;
      error.hidden = false; root.dataset.stale = 'true';
    } finally { loading = false; refresh.disabled = false; }
  }

  function poll() {
    clearTimeout(timer);
    if (!document.hidden) update();
    timer = setTimeout(poll, 2000);
  }
  refresh.onclick = update;
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  window.addEventListener('pagehide', () => clearTimeout(timer));
  root.querySelectorAll('[data-workflow-target]').forEach(button => {
    button.onclick = () => {
      if (document.body.classList.contains('jobs-page')) {
        window.location.href = `./?panel=sources#${button.dataset.workflowTarget}`;
        return;
      }
      const tab = document.querySelector('[data-tab="sources-panel"]');
      if (document.getElementById('sources-panel').hidden) tab.click();
      const target = document.getElementById(button.dataset.workflowTarget);
      target.scrollIntoView({block: 'center'});
      const focus = target.matches('button') ? target : target.querySelector('input, button');
      if (focus) focus.focus({preventScroll: true});
    };
  });
  poll();
})();
