/* Collapsible DB summary. Render all recorded identifiers strictly as text. */
(() => {
  const el = id => document.getElementById(id);
  const panel = el('library-summary');
  if (!panel) return;
  let data, loading = false, timer, limit = 100;
  const number = value => Number(value || 0).toLocaleString('ko-KR');
  function make(tag, text) { const node = document.createElement(tag); node.textContent = text; return node; }
  function size(bytes) {
    if (bytes < 1024) return `${number(bytes)} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KiB`;
    if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MiB`;
    return `${(bytes / 1073741824).toFixed(2)} GiB`;
  }
  function counts(row) {
    return [row.media_count, row.source_file_count, row.source_directory_count,
      row.managed_file_count, row.managed_directory_count].map(number).concat(size(row.media_bytes));
  }
  function renderGroups() {
    if (!data) return;
    const query = el('summary-filter').value.trim().toLocaleLowerCase();
    const groups = data.groups.filter(row => [row.source_id || '소스 연결 없음', row.category_id, row.owner_id]
      .join(' ').toLocaleLowerCase().includes(query));
    const body = el('summary-groups'); body.replaceChildren();
    for (const row of groups.slice(0, limit)) {
      const tr = document.createElement('tr');
      for (const value of [row.source_id || '소스 연결 없음', row.category_id, row.owner_id, ...counts(row)]) tr.append(make('td', value));
      body.append(tr);
    }
    if (!groups.length) { const cell = make('td', query ? '검색 조건에 맞는 조합이 없습니다.' : '아직 활성 DB 항목이 없습니다.'); cell.colSpan = 9; const row = document.createElement('tr'); row.append(cell); body.append(row); }
    el('summary-group-count').textContent = `${number(Math.min(limit, groups.length))}/${number(groups.length)}개 조합 표시 · 전체 ${number(data.groups.length)}개 조합`;
    el('summary-more').hidden = limit >= groups.length;
  }
  function render() {
    const totals = data.totals;
    el('summary-badge').textContent = `소스 ${number(data.source_count)} · DB 분류 ${number(data.category_ids.length)} · DB 사용자 ${number(data.owner_ids.length)}`;
    const metrics = [
      ['등록 소스', number(data.configured_source_count)], ['DB에 기록된 소스', number(data.catalog_source_count)],
      ['활성 분류', number(data.category_ids.length)], ['활성 사용자 ID', number(data.owner_ids.length)],
      ['활성 항목', number(totals.media_count)], ['원본 파일 (DB)', number(totals.source_file_count)],
      ['관리 파일 (DB)', number(totals.managed_file_count)],
      ['디렉토리 (원본 / 관리)', `${number(totals.source_directory_count)} / ${number(totals.managed_directory_count)}`],
    ];
    const cards = el('summary-metrics'); cards.replaceChildren();
    for (const [label, value] of metrics) { const card = document.createElement('div'); card.append(make('span', label), make('strong', value)); cards.append(card); }
    const sources = el('summary-sources'); sources.replaceChildren();
    for (const row of data.sources) {
      const tr = document.createElement('tr'), source = document.createElement('td');
      source.append(make('strong', row.source_id), make('small', row.registered ? '등록됨' : 'DB 기록만 있음'), make('small', row.root || '현재 설정에 원본 루트 없음'));
      tr.append(source);
      for (const [actual, configured] of [[row.category_ids, row.configured_category_ids], [row.owner_ids, row.configured_owner_ids]]) {
        const cell = document.createElement('td'); cell.append(make('span', `DB: ${actual.join(', ') || '—'}`), make('small', `설정: ${configured.join(', ') || '—'}`)); tr.append(cell);
      }
      for (const value of counts(row)) tr.append(make('td', value));
      sources.append(tr);
    }
    if (!data.sources.length) { const cell = make('td', '등록 또는 DB에 기록된 소스가 없습니다.'); cell.colSpan = 9; const row = document.createElement('tr'); row.append(cell); sources.append(row); }
    el('summary-status').textContent = `현재 청크 ${number(data.current_chunk_count)}개 집계 · 비활성 항목 ${number(data.inactive_media_count)}개 별도 · 누락 표시 원본 ${number(totals.missing_source_file_count)}개 · ${new Date(data.observed_at).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'})} (KST)`;
    el('summary-note').textContent = data.note;
    renderGroups();
  }
  async function update(force = false) {
    if (loading || !panel.open || document.hidden) return;
    loading = true; el('summary-refresh').disabled = true;
    if (!data) el('summary-status').textContent = '현재 DB의 모든 청크를 읽는 중…';
    try {
      const response = await fetch(`api/library-summary${force ? '?refresh=1' : ''}`, {cache: 'no-store'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      data = result; render(); panel.removeAttribute('data-stale');
    } catch (error) {
      el('summary-status').textContent = `집계 실패: ${error.message} 이전 표시가 있다면 최신 정보가 아닐 수 있습니다.`;
      panel.dataset.stale = 'true';
    } finally { loading = false; el('summary-refresh').disabled = false; }
  }
  function poll() { clearTimeout(timer); if (!panel.open) return; update(); timer = setTimeout(poll, 5000); }
  const toggle = el('summary-toggle');
  toggle.onclick = () => { panel.open = !panel.open; if (panel.open) panel.scrollIntoView({block: 'start'}); };
  panel.addEventListener('toggle', () => { toggle.setAttribute('aria-expanded', String(panel.open)); poll(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && panel.open) poll(); });
  window.addEventListener('pagehide', () => clearTimeout(timer));
  el('summary-refresh').onclick = () => update(true);
  el('summary-filter').oninput = () => { limit = 100; renderGroups(); };
  el('summary-more').onclick = () => { limit += 100; renderGroups(); };
  if (panel.open) poll();
})();
