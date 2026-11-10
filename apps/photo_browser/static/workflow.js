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

  function storageText(storage) {
    if (!storage) return '';
    if (storage.size_bytes === null || storage.size_bytes === undefined) return storage.state === 'error' ? 'DB 전체 용량: 조회 실패 · 접근 권한을 확인하세요.' : 'DB 전체 용량: 집계 중…';
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    let value = storage.size_bytes, index = 0;
    while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
    const formatted = `${value.toLocaleString('ko-KR', {maximumFractionDigits: 2})} ${units[index]}`;
    let text = `DB 전체 용량: ${formatted} · ${storage.file_count.toLocaleString('ko-KR')}개 파일`;
    if (storage.state === 'error') text += ' · 이전 집계값 (재조회 실패)';
    else if (storage.state === 'partial') text += ` · 일부 제외 ${storage.skipped.toLocaleString('ko-KR')}개`;
    if (storage.running) text += ' · 갱신 중';
    return text;
  }

  function render(data) {
    let current = false;
    for (const [index, step] of data.steps.entries()) {
      const node = root.querySelector(`[data-workflow-step="${step.id}"]`);
      if (!node) continue;
      const state = names[step.status] ? step.status : 'pending';
      node.dataset.state = state;
      node.querySelector('.workflow-number').textContent = symbols[state] || String(index + 1);
      node.querySelector('.workflow-state').textContent = names[state] + (step.percent === null ? '' : ` · ${step.percent}%`);
      const detail = node.querySelector('.workflow-detail');
      detail.textContent = [step.detail, storageText(step.storage)].filter(Boolean).join('\n');
      if (step.storage) {
        detail.title = `DB 디렉토리 아래 전체 일반 파일의 논리적 크기 합계입니다. 이전 JSON 세대·캐시·다운로드·작업 기록을 포함하며 managed 사진 용량과 파일시스템 할당 용량은 아닙니다. 약 ${step.storage.refresh_seconds}초마다 갱신합니다. 링크와 읽지 못한 항목은 제외합니다.`
          + (step.storage.checked_at ? ` 마지막 집계: ${new Date(step.storage.checked_at).toLocaleString('ko-KR')}` : '');
      }
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

  async function update(forceUsage = false) {
    if (loading) return;
    loading = true; refresh.disabled = true;
    try {
      const response = await fetch(forceUsage ? 'api/workflow?refresh_usage=1' : 'api/workflow', {cache: 'no-store'});
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
  refresh.onclick = () => update(true);
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
