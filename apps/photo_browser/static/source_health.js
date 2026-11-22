/* Original-path alerts and incidents: never infer a move from missing alone. */
(() => {
  const el = id => document.getElementById(id);
  const active = ['queued', 'running', 'stopping'];
  const states = {open: '미해결', resolved: '해결', closed: '참조 정리로 종료'};
  const resolutions = {original_access_restored: '원본 접근 복구', verified_db_path_updated: '검증한 새 원본 경로로 DB 갱신',
    source_root_updated: '변경한 소스 루트의 접근 확인 (파일별 DB 경로는 별도 점검)',
    db_reference_removed_or_changed: 'DB 원본 참조 정리·변경 (파일 복구를 의미하지 않음)'};
  const rows = new Map();
  let offset = 0, total = 0, loading = false, busy = false;
  const time = value => value ? new Date(value).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'}) + ' KST' : '점검 전';
  async function api(path, data) {
    const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'},
      body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function node(tag, text) { const result = document.createElement(tag); if (text) result.textContent = text; return result; }
  function button(label, callback) {
    const result = node('button', label); result.type = 'button';
    result.onclick = async () => { try { await callback(); } catch (error) { el('health-message').textContent = error.message; } };
    return result;
  }
  async function job(path, data) {
    if (busy) throw new Error('현재 경로 작업을 마친 뒤 다시 시도하세요.');
    busy = true; el('health-check').disabled = true;
    try {
      const started = await api(path, data || {});
      let status;
      do {
        status = await api(`api/jobs/${encodeURIComponent(started.job_id)}`);
        if (active.includes(status.status)) await new Promise(resolve => setTimeout(resolve, 500));
      } while (active.includes(status.status));
      if (status.status === 'failed') throw new Error(status.error || '경로 작업이 실패했습니다. 작업 내역을 확인하세요.');
      return status.result;
    } finally { busy = false; el('health-check').disabled = false; }
  }
  function issueRow(issue) {
    const root = node('article'); root.className = 'source-row';
    const title = node('h3'), info = node('p'), details = node('p');
    info.className = 'source-health-detail'; details.className = 'source-health-detail';
    root.append(title, info, details);
    if (issue.status === 'open' && issue.media_id) {
      const field = node('input'); field.type = 'text'; field.placeholder = '새 원본 파일의 전체 경로';
      field.setAttribute('aria-label', issue.name + ' 새 원본 경로'); field.className = 'source-health-path';
      const candidates = node('div');
      root.append(button('이동 파일 후보 찾기', async () => {
        const result = await job('api/source-path-health/find', {issue_id: issue.issue_id});
        candidates.replaceChildren(node('p', `${result.checked_files}개 확인 · ${result.candidates.length}개 후보` +
          (result.limited ? ' · 검색 한도에 도달해 전체 검색은 아닙니다.' : '') + '\n' + result.warning));
        for (const path of result.candidates) candidates.append(button(path, () => { field.value = path; }));
      }), field, button('경로 검증·DB 반영', async () => {
        if (!field.value.trim()) throw new Error('검증할 새 원본 파일 경로를 입력하세요.');
        if (!confirm('새 원본의 크기·SHA-256을 검증한 뒤 이 사진의 DB 원본 경로를 변경합니까? 사진 파일은 이동하지 않습니다.')) return;
        const result = await job('api/source-path-health/repair', {issue_id: issue.issue_id, path: field.value.trim()});
        el('health-message').textContent = `원본 경로 반영: ${result.new_path}`;
        await refresh();
      }), candidates);
    }
    if (issue.status === 'open') root.append(button('소스 경로 설정', async () => {
      const config = await api('api/config');
      const source = config.sources.find(source => source.source_id === issue.source_id);
      if (!source) throw new Error('소스 등록이 변경되었습니다. 다시 점검하세요.');
      await window.photoBrowserSourceUpdated(source);
      document.querySelector('[data-tab="sources-panel"]').click();
      el('source-form').scrollIntoView({block: 'start'});
    }));
    return {root, title, info, details};
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const summary = await api('api/source-path-health');
      const count = summary.active_count || 0;
      el('source-health-banner').dataset.state = summary.error ? 'error' : !summary.checked_at ? 'pending' : count ? 'warning' : 'ok';
      el('source-health-banner-text').textContent = summary.error ? '원본 경로 점검 오류: ' + summary.error :
        !summary.checked_at ? '원본 경로 점검 대기' : `원본 경로 미해결 ${count}건 · 해결·종료 ${summary.resolved_count || 0}건 · 마지막 점검 ${time(summary.checked_at)}`;
      el('health-summary').textContent = `${summary.monitoring ? `자동 점검 ${summary.interval}초 간격` : '자동 감시가 실행 중이지 않습니다. 지금 점검 또는 CLI 감시를 사용할 수 있습니다.'}` +
        (summary.checking ? ` · 점검 중 ${summary.processed}/${summary.total}개` : '') +
        ` · 마지막 완료 ${time(summary.checked_at)}`;
      if (el('source-health-panel').hidden || busy) return;
      const result = await api('api/source-path-health/issues?' + new URLSearchParams({view: el('health-view').value, offset}));
      total = result.total;
      const ids = new Set(result.items.map(issue => issue.issue_id));
      for (const [id, row] of rows) if (!ids.has(id)) { row.root.remove(); rows.delete(id); }
      for (const issue of result.items) {
        let row = rows.get(issue.issue_id);
        if (!row) { row = issueRow(issue); rows.set(issue.issue_id, row); el('health-issues').append(row.root); }
        row.title.textContent = `${issue.source_id} · ${issue.name || '소스 루트'} · ${states[issue.status] || issue.status}`;
        row.info.textContent = `${issue.path}\n${issue.problem}`;
        row.details.textContent = `최초 ${time(issue.first_seen_at)} · 최근 ${time(issue.last_seen_at)} · ${issue.observations}회 관측` +
          (issue.resolved_at ? `\n종료 ${time(issue.resolved_at)} · ${resolutions[issue.resolution] || issue.resolution}${issue.new_path ? '\n현재 DB 경로: ' + issue.new_path : ''}` : '');
      }
      el('health-empty').hidden = result.items.length > 0;
      el('health-page').textContent = `${total}건 · ${offset + (result.items.length ? 1 : 0)}–${offset + result.items.length}`;
      el('health-prev').disabled = offset === 0; el('health-next').disabled = offset + 100 >= total;
    } catch (error) {
      el('source-health-banner').dataset.state = 'error';
      el('source-health-banner-text').textContent = '원본 경로 상태 조회 실패: ' + error.message;
    } finally { loading = false; }
  }
  el('health-check').onclick = async () => {
    try {
      const result = await job('api/source-path-health/check');
      el('health-message').textContent = result.status === 'completed' ? '경로 점검을 완료했습니다.' : result.message || '다른 점검이 실행 중입니다.';
      await refresh();
    } catch (error) { el('health-message').textContent = error.message; }
  };
  el('health-view').onchange = () => { offset = 0; rows.clear(); el('health-issues').replaceChildren(); refresh(); };
  el('health-prev').onclick = () => { offset = Math.max(0, offset - 100); refresh(); };
  el('health-next').onclick = () => { offset += 100; refresh(); };
  el('detail-original-check').onclick = async () => {
    const mediaId = el('library-detail').dataset.mediaId;
    const target = el('detail-original-locations'); target.textContent = 'DB 원본 위치를 확인하고 있습니다…';
    try {
      const result = await api(`api/library/${encodeURIComponent(mediaId)}/sources`);
      if (el('library-detail').dataset.mediaId !== mediaId) return;
      target.replaceChildren();
      for (const location of result.items) {
        const row = node('p', `${location.source_id || ''} · ${location.path || location.uri}\n${location.problem || '원본 접근 가능'}`);
        if (location.folder) row.append(button('원본 폴더로 이동', async () => {
          el('library-detail').close();
          await window.photoBrowserOpenDirectory({source_id: location.source_id, path: location.folder});
        }));
        target.append(row);
      }
    } catch (error) { target.textContent = error.message; }
  };
  new MutationObserver(() => { if (!el('source-health-panel').hidden) refresh(); })
    .observe(el('source-health-panel'), {attributes: true, attributeFilter: ['hidden']});
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 2000);
})();
