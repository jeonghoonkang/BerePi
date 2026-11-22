/* Explicit batches only: adding files never starts a scan without user action. */
(() => {
  const el = id => document.getElementById(id);
  let settings = [], busy = false, jobId;
  const active = ['queued', 'running', 'stopping'];
  async function api(path, data) {
    const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'},
      body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function render(setting) {
    el('source-folder-items').replaceChildren();
    for (const source of setting?.sources || []) {
      const row = document.createElement('li');
      row.textContent = `${source.source_id} → ${source.root} · ${source.category} / ${source.owner_id}`;
      el('source-folder-items').append(row);
    }
  }
  async function refresh(selected = el('source-folder-root').value) {
    settings = (await api('api/source-folders')).items;
    const choices = el('source-folder-saved');
    choices.replaceChildren(new Option('새 기준 디렉토리', ''));
    for (const setting of settings) choices.add(new Option(setting.root, setting.root));
    choices.value = settings.some(setting => setting.root === selected) ? selected : '';
    const setting = settings.find(setting => setting.root === choices.value);
    if (setting) {
      el('source-folder-root').value = setting.root;
      el('source-folder-category').value = setting.category;
      el('source-folder-owner').value = setting.owner_id;
    }
    render(setting);
  }
  function lock(value) {
    busy = value;
    for (const id of ['source-folder-register', 'source-folder-sync', 'source-folder-saved',
      'source-folder-root', 'source-folder-category', 'source-folder-owner']) el(id).disabled = value;
    el('source-folder-stop').hidden = !value || !jobId;
    el('source-folder-stop').disabled = false;
  }
  el('source-folder-saved').onchange = () => {
    const setting = settings.find(entry => entry.root === el('source-folder-saved').value);
    if (setting) {
      el('source-folder-root').value = setting.root;
      el('source-folder-category').value = setting.category;
      el('source-folder-owner').value = setting.owner_id;
    }
    render(setting);
  };
  el('source-folders-form').onsubmit = async event => {
    event.preventDefault();
    if (busy) return;
    lock(true);
    let saved = false;
    try {
      const result = await api('api/source-folders', {root: el('source-folder-root').value.trim(),
        category: el('source-folder-category').value.trim(), owner_id: el('source-folder-owner').value.trim()});
      saved = true;
      el('source-folder-root').value = result.root;
      await refresh(result.root);
      if (result.items.length) await window.photoBrowserSourceUpdated(result.items[0].source);
      el('source-folder-status').textContent = `${result.items.length}개 하위 소스 확인 · 신규 ${result.added}개. ` +
        '기존 ID와 분류는 유지했습니다. 새 파일 스캔·병합 버튼을 누르면 라이브러리에 복사합니다.' +
        (result.skipped.length ? '\n제외: ' + result.skipped.map(item => `${item.name} (${item.reason})`).join(', ') : '');
    } catch (error) {
      el('source-folder-status').textContent = (saved ? '등록은 저장됐지만 화면 갱신에 실패했습니다. ' : '') + error.message;
    } finally { lock(false); }
  };
  el('source-folder-sync').onclick = async () => {
    if (busy || !el('source-folders-form').reportValidity()) return;
    const setting = settings.find(entry => entry.root === el('source-folder-root').value.trim());
    if (!setting || setting.category !== el('source-folder-category').value.trim() ||
        setting.owner_id !== el('source-folder-owner').value.trim()) {
      el('source-folder-status').textContent = '변경한 기준 경로·새 소스 분류를 먼저 저장하세요.';
      return;
    }
    lock(true);
    try {
      el('source-folder-status').textContent = '새 파일 스캔·병합을 요청하고 있습니다…';
      const started = await api('api/source-folders/sync', {root: el('source-folder-root').value.trim()});
      jobId = started.job_id; el('source-folder-stop').hidden = false;
      let status;
      do {
        status = await api(`api/jobs/${encodeURIComponent(jobId)}`);
        const progress = status.progress || {};
        el('source-folder-status').textContent = `${progress.folder_source_id || '대기'} · ` +
          `${progress.folder_processed || 0}/${progress.folder_total || 0}개 소스 · ` +
          `${progress.phase || status.status} · ${progress.processed || 0}/${progress.total || 0}개 파일`;
        if (active.includes(status.status)) await new Promise(resolve => setTimeout(resolve, 1000));
      } while (active.includes(status.status));
      const result = status.result;
      if (!result) throw new Error(status.error || '결과를 확인할 수 없습니다. 전체 작업 내역을 확인하세요.');
      await refresh(result.root);
      const sources = result.registration?.items || [];
      if (sources.length) await window.photoBrowserSourceUpdated(sources[0].source);
      const name = {completed: '스캔·병합 완료', stopped: '안전하게 중지됨', paused_low_space: '공간 부족으로 중지됨',
        blocked_low_space: '공간 부족으로 병합하지 못했습니다', failed: '오류가 있어 일부 소스를 완료하지 못했습니다'};
      el('source-folder-status').textContent = `${name[result.status] || result.status} · ${result.items.length}개 소스 처리 · 오류 ${result.error_count || 0}건. ` +
        '추가 파일을 넣은 뒤 같은 버튼으로 다시 실행할 수 있습니다.' +
        result.items.filter(item => item.error).map(item => `\n${item.source_id}: ${item.error}`).join('');
    } catch (error) { el('source-folder-status').textContent = error.message; }
    finally { jobId = null; lock(false); }
  };
  el('source-folder-stop').onclick = async () => {
    try {
      if (jobId) await api(`api/jobs/${encodeURIComponent(jobId)}/stop`, {});
      el('source-folder-stop').disabled = true;
    } catch (error) { el('source-folder-status').textContent = error.message; }
  };
  refresh().catch(error => { el('source-folder-status').textContent = error.message; });
})();
