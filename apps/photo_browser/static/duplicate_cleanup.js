/* Scoped catalog-only duplicate archiving with durable undo snapshots. */
(() => {
  const el = id => document.getElementById(id);
  const make = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  const number = value => Number(value || 0).toLocaleString('ko-KR');
  const statusNames = {preview: '미리보기', applying: '반영 중 · 복구 확인 필요', completed: '정리 완료', undoing: '복구 중', undone: '되돌림 완료'};
  let options, plan, offset = 0, busy = false, executable = false, refreshing = false, pageVersion = 0;
  const message = text => { el('duplicate-db-status').textContent = text; };
  async function api(url, data) {
    const response = await fetch(url, {cache: 'no-store', method: data === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'}, body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function invalidate() { plan = null; executable = false; pageVersion++; el('duplicate-db-run').disabled = true; el('duplicate-db-preview-result').hidden = true; }
  function categories(side) {
    const select = el(`cleanup-${side}-category`), previous = select.value;
    select.replaceChildren(new Option('카테고리 선택', ''));
    const values = options.sources.find(source => source.source_id === el(`cleanup-${side}-source`).value)?.categories || [];
    for (const category of values) select.add(new Option(category, category));
    select.value = values.includes(previous) ? previous : '';
  }
  async function loadOptions() {
    options = await api('api/source-comparisons/options');
    for (const side of ['remove', 'keep']) {
      const select = el(`cleanup-${side}-source`), previous = select.value;
      select.replaceChildren(new Option('소스 ID 선택', ''));
      for (const source of options.sources) select.add(new Option(`${source.source_id}${source.registered ? '' : ' (DB 기록)'}`, source.source_id));
      select.value = options.sources.some(source => source.source_id === previous) ? previous : '';
      categories(side);
    }
  }
  function scope(side) { return {source_id: el(`cleanup-${side}-source`).value, category: el(`cleanup-${side}-category`).value}; }
  const scopeText = scope => `${scope.source_id} / ${scope.category}`;
  function lock(value) {
    busy = value;
    el('duplicate-db-form').querySelectorAll('select, button').forEach(node => { node.disabled = value; });
    el('duplicate-db-history').querySelectorAll('button').forEach(node => { node.disabled = value; });
    el('duplicate-db-run').disabled = value || !plan || !executable;
  }
  async function job(url, data) {
    const started = await api(url, data || {});
    let state;
    do {
      state = await api(`api/jobs/${encodeURIComponent(started.job_id)}`);
      message(state.status === 'queued' ? 'DB 정리 작업 대기 중…' : 'DB 정리 작업 처리 중…');
      if (['queued', 'running', 'stopping'].includes(state.status)) await new Promise(resolve => setTimeout(resolve, 1000));
    } while (['queued', 'running', 'stopping'].includes(state.status));
    if (state.status !== 'completed') throw new Error(state.error || '작업이 중단되었습니다. 정리 기록을 확인하세요.');
    return state.result;
  }
  async function page(id = plan) {
    const version = ++pageVersion;
    const record = await api(`api/duplicate-db-cleanups/${encodeURIComponent(id)}?offset=${offset}`);
    if (version !== pageVersion) return;
    const skippedNames = {shared_item: '양쪽 공통 DB 항목 보존', shared_source: '여러 소스 연결 항목 보존', unknown_hash: '해시 정보 부족', no_duplicate: '일치하는 내용 없음'};
    const skipped = Object.entries(record.skipped).map(([key, count]) => `${skippedNames[key] || key} ${number(count)}개`).join(' · ');
    el('duplicate-db-preview-summary').textContent = `정리: ${scopeText(record.remove)} → 유지: ${scopeText(record.keep)}\n정리 범위 ${number(record.remove_items)}개 중 중복 ${number(record.archive_count)}개 비활성 보관 예정 · ${statusNames[record.status]}\n${skipped || '제외 항목 없음'}\n${record.basis}`;
    const body = el('duplicate-db-preview-rows'); body.replaceChildren();
    for (const row of record.rows) {
      const tr = document.createElement('tr'), file = document.createElement('td'), paths = document.createElement('td');
      file.append(make('strong', row.name), make('small', row.sha256), make('small', `${number(row.size_bytes)} B`));
      for (const location of row.locations) paths.append(make('span', `${location.role}: ${location.path || location.uri || '—'} [${location.status || 'unknown'}]`));
      tr.append(file, make('td', `${row.media_id} / ${row.owner_id}`), make('td', row.keeper_id), paths); body.append(tr);
    }
    el('duplicate-db-preview-result').hidden = false;
    el('duplicate-db-page-status').textContent = `${number(record.total)}개 중 ${number(record.total ? offset + 1 : 0)}~${number(Math.min(offset + record.rows.length, record.total))} 표시`;
    el('duplicate-db-prev').disabled = !offset;
    el('duplicate-db-next').disabled = offset + 100 >= record.total;
    executable = Boolean(record.archive_count && ['preview', 'applying'].includes(record.status));
    el('duplicate-db-run').disabled = busy || !executable;
  }
  async function history() {
    const records = await api('api/duplicate-db-cleanups');
    const root = el('duplicate-db-history'); root.replaceChildren();
    for (const record of records.items) {
      const row = document.createElement('div'); row.className = 'source-row';
      row.append(make('p', `${scopeText(record.remove)} → 유지 ${scopeText(record.keep)} · ${statusNames[record.status]} · ${number(record.archive_count)}개 · ${new Date(record.created_at).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'})} (KST)`));
      const button = (text, action) => { const node = make('button', text); node.type = 'button'; node.disabled = busy; node.onclick = async () => { try { await action(); } catch (error) { message(error.message); } }; row.append(node); };
      button('대상 확인', async () => { if (busy) return; invalidate(); plan = record.operation_id; offset = 0; await page(); });
      if (['preview', 'applying'].includes(record.status) && record.archive_count) button('미리본 DB 정리 실행 / 복구', () => execute(record));
      if (['completed', 'applying', 'undoing'].includes(record.status)) button('DB 정리 되돌리기', async () => {
        if (busy || !confirm(`${scopeText(record.remove)}의 정리된 DB 항목 ${number(record.archive_count)}개를 복원하시겠습니까?\n원본·관리 파일과 유지측 항목은 변경하지 않습니다.`)) return;
        lock(true); invalidate();
        try { await job(`api/duplicate-db-cleanups/${encodeURIComponent(record.operation_id)}/undo`); message('정리한 DB 항목을 복원했습니다.'); }
        finally { lock(false); await history(); await loadOptions(); }
      });
      root.append(row);
    }
    if (!records.items.length) root.append(make('p', 'DB 정리 기록이 없습니다.'));
  }
  async function execute(record) {
    if (busy || !record.archive_count || !confirm(`정리할 범위: ${scopeText(record.remove)}\n유지할 범위: ${scopeText(record.keep)}\n중복 DB 항목 ${number(record.archive_count)}개만 비활성 보관하시겠습니까?\n원본·관리 파일과 다른 카테고리는 변경하지 않습니다. 다른 접속자의 라이브러리에도 적용됩니다.`)) return;
    lock(true); invalidate();
    try { await job(`api/duplicate-db-cleanups/${encodeURIComponent(record.operation_id)}/run`); message(`${number(record.archive_count)}개 중복 DB 항목을 정리했습니다. 기록에서 되돌릴 수 있습니다.`); }
    finally { lock(false); await history(); await loadOptions(); }
  }
  el('duplicate-db-form').onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    const remove = scope('remove'), keep = scope('keep');
    if (!remove.source_id || !remove.category || !keep.source_id || !keep.category || JSON.stringify(remove) === JSON.stringify(keep)) { message('서로 다른 소스·카테고리 범위를 각각 지정하세요.'); return; }
    invalidate(); lock(true);
    try {
      const result = await job('api/duplicate-db-cleanups/preview', {remove, keep});
      plan = result.operation_id; offset = 0; lock(false); await page();
      message('미리보기만 완료했습니다. 대상·유지 범위와 항목 수를 확인한 뒤 실행하세요.');
    } catch (error) { message(error.message); }
    finally { lock(false); await history(); }
  };
  el('duplicate-db-run').onclick = async () => { try { if (plan && !busy) await execute(await api(`api/duplicate-db-cleanups/${encodeURIComponent(plan)}`)); } catch (error) { message(error.message); } };
  for (const side of ['remove', 'keep']) {
    el(`cleanup-${side}-source`).onchange = () => { categories(side); invalidate(); };
    el(`cleanup-${side}-category`).onchange = invalidate;
  }
  el('duplicate-db-prev').onclick = async () => { if (!plan || busy) return; offset = Math.max(0, offset - 100); try { await page(); } catch (error) { message(error.message); } };
  el('duplicate-db-next').onclick = async () => { if (!plan || busy) return; offset += 100; try { await page(); } catch (error) { message(error.message); } };
  async function refresh() { if (busy || refreshing) return; refreshing = true; invalidate(); try { await loadOptions(); await history(); message(options.sources.length ? '정리할 범위와 유지할 범위의 소스 ID·카테고리를 선택하세요.' : '등록 또는 DB 기록 소스가 없습니다. 소스를 등록하고 스캔하세요.'); } catch (error) { message(`선택 목록·기록 조회 실패: ${error.message}. 새로고침으로 다시 시도하세요.`); } finally { refreshing = false; } }
  el('duplicate-db-refresh').onclick = refresh;
  document.querySelector('[data-tab="source-comparison-panel"]').addEventListener('click', () => { if (!options) refresh(); });
  refresh();
})();
