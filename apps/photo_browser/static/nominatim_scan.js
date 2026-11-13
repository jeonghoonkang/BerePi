(() => {
  const el = name => document.getElementById(`nominatim-scan-${name}`);
  const panel = document.getElementById('nominatim-panel');
  const activeStates = ['queued', 'running', 'stopping'];
  const labels = {queued: '대기', running: '스캔 중', stopping: '중지·저장 중', stopped: '중지됨',
    completed: '완료', failed: '오류', interrupted: '서버 재시작으로 중단됨 · 다시 실행하세요'};
  let jobId, active = false, busy = false, lastFinished, missingCount;
  function controls() {
    el('start').disabled = active;
    el('stop').hidden = !active;
  }
  async function api(path, method = 'GET') {
    const response = await fetch(path, {method, cache: 'no-store',
      headers: {'X-Photo-Browser': '1', 'Content-Type': 'application/json'},
      body: method === 'POST' ? '{}' : undefined});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  function error(message) { el('error').hidden = !message; el('error').textContent = message || ''; }
  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      if (!jobId) {
        const jobs = await api('api/jobs?limit=100');
        if (!jobId) {
          const job = jobs.items.find(item => item.kind === 'location_scan');
          if (!job) return;
          jobId = job.job_id;
        }
      }
      const job = await api(`api/jobs/${encodeURIComponent(jobId)}`);
      active = activeStates.includes(job.status);
      controls();
      const result = job.result || job.progress || {};
      el('state').textContent = `${labels[job.status] || job.status} · 처리 ${result.processed || 0} / ${result.total || 0}개 · 위치 추가 ${result.updated || 0}개`;
      el('progress').hidden = false;
      el('progress').value = result.percent || 0;
      const details = [
        `GPS 없음 · 조회 제외: ${result.no_gps || 0}개 · no_gps 태그 신규 저장: ${result.no_gps_tagged || 0}개`,
        `위치 이름 미확인: ${result.unresolved || 0}개 · 처리 오류: ${result.error_count ?? result.errors?.length ?? 0}개`,
        `현재 파일: ${result.current_file || '—'}`,
        `시작: ${job.started_at || '—'} · 종료: ${job.finished_at || '—'}`,
      ];
      if (result.warning) details.push(result.warning);
      for (const item of (result.errors || []).slice(0, 10)) details.push(`${item.file}: ${item.error}`);
      el('detail').textContent = details.join('\n');
      error(job.error);
      if (!active && lastFinished !== jobId) {
        lastFinished = jobId;
        panel.dispatchEvent(new CustomEvent('nominatim-scan-complete'));
      }
    } catch (err) { error(`작업 상태 조회 실패: ${err.message}`); }
    finally { busy = false; }
  }
  el('start').addEventListener('click', async () => {
    if (active) return;
    active = true; controls(); error();
    try {
      const job = await api('api/nominatim/scan-missing', 'POST');
      jobId = job.job_id;
      await refresh();
    } catch (err) { active = false; controls(); error(err.message); }
  });
  el('stop').addEventListener('click', async () => {
    if (!jobId || !active) return;
    if (!confirm('위치 태그 추가 스캔 작업을 중지하시겠습니까?\n다른 접속자에게도 적용됩니다. 중지 요청 후 현재 처리 결과를 정리합니다.')) return;
    try { await api(`api/jobs/${encodeURIComponent(jobId)}/stop`, 'POST'); await refresh(); }
    catch (err) { error(err.message); }
  });
  panel.addEventListener('nominatim-statistics-updated', event => {
    missingCount = event.detail.location_scan_candidate_count;
    el('start').title = `위치 조회 대상 ${missingCount ?? '확인 중'}개. GPS 없는 사진은 no_gps 태그로 저장합니다.`;
    controls();
  });
  new MutationObserver(() => { if (!panel.hidden) refresh(); }).observe(panel, {attributes: true, attributeFilter: ['hidden']});
  setInterval(() => { if (active || (!panel.hidden && !document.hidden)) refresh(); }, 2000);
})();
