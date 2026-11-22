/* Folder totals and filesystem capacity have different scopes; never sum disks. */
(() => {
  const el = id => document.getElementById(id);
  let loading = false;
  const bytes = value => {
    if (value === null || value === undefined) return '미집계';
    let size = Number(value), index = 0;
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
    while (size >= 1024 && index < units.length - 1) { size /= 1024; index++; }
    return `${size.toLocaleString('ko-KR', {maximumFractionDigits: 2})} ${units[index]}`;
  };
  function node(tag, text) { const result = document.createElement(tag); if (text !== undefined) result.textContent = text; return result; }
  async function refresh(force = false) {
    if (loading) return;
    loading = true; el('storage-refresh').disabled = true;
    try {
      const response = await fetch('api/storage-usage' + (force ? '?refresh=1' : ''), {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      for (const kind of ['db', 'sources', 'managed']) {
        const usage = data.categories?.[kind];
        el(`storage-${kind}-size`).textContent = bytes(usage?.logical_bytes);
        el(`storage-${kind}-allocation`).textContent = usage ?
          `파일 할당량 ${bytes(usage.allocated_bytes)}${usage.allocation_estimated ? ' (논리 크기 추정)' : ''} · 파일 경로 ${(usage.file_count || 0).toLocaleString()}개` +
          (usage.state === 'partial' ? ' · 일부만 집계' : usage.state === 'error' ? ' · 집계 불가' : '') : '폴더 용량 집계 대기';
      }
      const managed = (data.volumes || []).filter(volume => volume.roles.includes('managed'));
      el('storage-library-free').textContent = managed.length === 1 ? bytes(managed[0].free_bytes) :
        managed.length ? `${managed.length}개 파일시스템` : '확인 불가';
      el('storage-library-total').textContent = managed.length === 1 ? `전체 ${bytes(managed[0].total_bytes)} 중 사용 가능` : '파일시스템별 여유 공간은 아래 표에서 확인하세요.';
      el('storage-volumes').replaceChildren();
      for (const volume of data.volumes || []) {
        const row = node('tr'), name = node('td', volume.labels.join(' / '));
        name.append(node('small', volume.path));
        row.append(name, node('td', bytes(volume.total_bytes)), node('td', bytes(volume.used_bytes)),
          node('td', bytes(volume.free_bytes)), node('td', volume.used_percent === null ? '확인 불가' : `${volume.used_percent}%`));
        el('storage-volumes').append(row);
      }
      const checked = data.checked_at ? new Date(data.checked_at).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'}) + ' KST' : '아직 집계하지 않았습니다.';
      el('storage-status').textContent = `${data.running ? '백그라운드 집계 중 · ' : ''}${data.state === 'partial' ? '일부만 집계 · ' : ''}최근 폴더 집계: ${checked} · 자동 갱신 ${data.refresh_seconds || 30}초`;
      el('storage-errors').replaceChildren();
      for (const error of data.errors || []) el('storage-errors').append(node('li', `${error.label || ''} ${error.path || ''}: ${error.error}`));
      for (const [kind, usage] of Object.entries(data.categories || {}))
        for (const error of usage.errors || []) el('storage-errors').append(node('li', `${usage.label || kind}: ${error}`));
      el('storage-overview').dataset.state = data.state;
      el('storage-error').hidden = data.state !== 'error';
      if (data.state === 'error') el('storage-error').textContent = '폴더 용량 집계 오류가 있습니다. 표시된 수치는 이전 값일 수 있으므로 집계 기준·오류 내용을 확인하세요.';
    } catch (error) {
      el('storage-error').hidden = false;
      el('storage-error').textContent = '저장 공간 조회 실패: ' + error.message + ' · 표시된 수치는 이전 값일 수 있습니다.';
      el('storage-overview').dataset.state = 'error';
    } finally { loading = false; el('storage-refresh').disabled = false; }
  }
  el('storage-refresh').onclick = () => refresh(true);
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
