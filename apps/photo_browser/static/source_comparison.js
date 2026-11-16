/* Read-only catalog comparison. All recorded paths are rendered as text. */
(() => {
  const el = id => document.getElementById(id);
  let choices, comparisonId, offset = 0, busy = false, requestVersion = 0;
  const labels = {same: '동일 내용', left_only: 'A에만 있는 내용', right_only: 'B에만 있는 내용', unknown: '해시 정보 부족'};
  const number = n => Number(n || 0).toLocaleString('ko-KR');
  const make = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  const message = text => { el('source-comparison-status').textContent = text; };
  async function api(url, data) {
    const response = await fetch(url, {cache: 'no-store', method: data === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'}, body: data === undefined ? undefined : JSON.stringify(data)});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
    return value;
  }
  function clear() { comparisonId = null; requestVersion++; el('source-comparison-result').hidden = true; message('선택 범위가 변경되었습니다. 비교를 실행하세요.'); }
  function categories(side) {
    const select = el(`compare-${side}-category`), previous = select.value;
    select.replaceChildren(new Option('전체 카테고리', ''));
    const values = [...new Set(choices.groups.filter(row => row.source_id === el(`compare-${side}-source`).value).map(row => row.category_id))].sort();
    for (const value of values) select.add(new Option(value, value));
    select.value = values.includes(previous) ? previous : '';
  }
  async function loadChoices() {
    choices = await api('api/library-summary?refresh=1');
    for (const [index, side] of ['left', 'right'].entries()) {
      const select = el(`compare-${side}-source`), previous = select.value;
      select.replaceChildren();
      for (const source of choices.sources) select.add(new Option(`${source.source_id}${source.registered ? '' : ' (DB 기록)'}`, source.source_id));
      select.value = choices.sources.some(source => source.source_id === previous) ? previous : (choices.sources[index]?.source_id || choices.sources[0]?.source_id || '');
      categories(side);
    }
    message('A와 B의 소스 ID·카테고리를 선택하세요.');
  }
  function scope(side) { return {source_id: el(`compare-${side}-source`).value, category: el(`compare-${side}-category`).value || null}; }
  function render(data) {
    el('source-comparison-result').hidden = false;
    el('source-comparison-verdict').textContent = !data.left_items || !data.right_items ? '비교 대상이 없는 범위가 있어 동일 여부를 판정할 수 없습니다.'
      : data.same_contents ? (data.same_multiplicity ? 'DB 기준: 사진 내용과 내용별 등록 수가 모두 같습니다.' : 'DB 기준: 사진 내용 집합은 같지만 중복 등록 수가 다릅니다.')
      : 'DB 기준: 내용 차이가 있거나 해시 정보가 부족합니다.';
    el('source-comparison-scope').textContent = `A: ${data.left.source_id} / ${data.left.category || '전체 카테고리'} ↔ B: ${data.right.source_id} / ${data.right.category || '전체 카테고리'} · ${new Date(data.created_at).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'})} (KST)`;
    const metrics = [['A / B 활성 항목', `${number(data.left_items)} / ${number(data.right_items)}`],
      ['동일 내용 그룹', number(data.counts.same)], ['동일 내용 항목 A / B', `${number(data.counts.matched_left_items)} / ${number(data.counts.matched_right_items)}`],
      ['A만 / B만 내용 그룹', `${number(data.counts.left_only)} / ${number(data.counts.right_only)}`],
      ['공통 원본 경로', number(data.shared_source_paths)], ['공통 관리 경로', number(data.shared_managed_paths)],
      ['같은 원본 경로의 내용 불일치', number(data.conflicting_source_paths)], ['같은 DB 항목 ID', number(data.shared_media_ids)],
      ['누락 표시 원본 항목 A / B', `${number(data.missing_left_items)} / ${number(data.missing_right_items)}`], ['해시 정보 부족 그룹', number(data.counts.unknown)]];
    const cards = el('source-comparison-metrics'); cards.replaceChildren();
    for (const [title, value] of metrics) { const card = document.createElement('div'); card.append(make('span', title), make('strong', value)); cards.append(card); }
    el('source-comparison-basis').textContent = data.basis;
    el('source-comparison-download').href = `api/source-comparisons/${encodeURIComponent(comparisonId)}/download`;
    const body = el('source-comparison-rows'); body.replaceChildren();
    for (const row of data.rows) {
      const tr = document.createElement('tr'), title = document.createElement('td');
      title.append(make('strong', labels[row.status]), make('small', row.sha256 || '유효한 SHA-256 없음'), make('small', `${row.size_bytes == null ? '크기 확인 불가' : number(row.size_bytes) + ' B'} · A ${number(row.left_count)} / B ${number(row.right_count)}개`));
      if (row.source_path_conflict) title.append(make('small', '같은 원본 경로의 내용 불일치 있음'));
      tr.append(title);
      for (const [side, key] of [['left', 'source_paths'], ['right', 'source_paths'], ['left', 'managed_paths'], ['right', 'managed_paths']]) {
        const td = document.createElement('td');
        if (!row[side].length) td.append(make('span', '—'));
        for (const item of row[side]) {
          const block = document.createElement('details');
          block.append(make('summary', `${item.name} · ${item.category} / ${item.owner_id}`), make('small', `DB ID: ${item.media_id}`));
          if (!item[key].length) block.append(make('small', '등록 경로 없음'));
          for (const location of item[key]) block.append(make('span', `${location.path} [${location.status}]`));
          td.append(block);
        }
        if (row[`${side}_count`] > row[side].length) td.append(make('small', '나머지 항목은 전체 JSON 기록에서 확인하세요.'));
        tr.append(td);
      }
      body.append(tr);
    }
    el('source-comparison-page-status').textContent = `${number(data.total)}개 내용 그룹 중 ${number(data.total ? offset + 1 : 0)}~${number(Math.min(offset + data.rows.length, data.total))} 표시`;
    el('source-comparison-prev').disabled = offset === 0;
    el('source-comparison-next').disabled = offset + data.limit >= data.total;
  }
  async function page() {
    const version = ++requestVersion;
    try {
      const data = await api(`api/source-comparisons/${encodeURIComponent(comparisonId)}?offset=${offset}&status=${encodeURIComponent(el('source-comparison-filter').value)}`);
      if (version === requestVersion) { render(data); return true; }
    } catch (error) { if (version === requestVersion) message(error.message); }
    return false;
  }
  el('source-comparison-form').onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    const left = scope('left'), right = scope('right');
    if (!left.source_id || !right.source_id || JSON.stringify(left) === JSON.stringify(right)) { message('서로 다른 소스 또는 카테고리를 선택하세요.'); return; }
    clear(); busy = true;
    el('source-comparison-form').querySelectorAll('select, button').forEach(node => { node.disabled = true; });
    try {
      const started = await api('api/source-comparisons', {left, right});
      let job;
      do {
        job = await api(`api/jobs/${encodeURIComponent(started.job_id)}`);
        message(job.status === 'queued' ? '비교 대기 중입니다. 앞선 서버 작업이 끝나면 실행합니다.' : `DB 정보 비교 중… ${number(job.progress?.processed)} / ${number(job.progress?.total)}개 확인`);
        if (['queued', 'running', 'stopping'].includes(job.status)) await new Promise(resolve => setTimeout(resolve, 1000));
      } while (['queued', 'running', 'stopping'].includes(job.status));
      if (job.status !== 'completed') throw new Error(job.error || '비교가 중단되었습니다. 다시 실행하세요.');
      comparisonId = job.result.comparison_id; offset = 0; el('source-comparison-filter').value = 'all';
      if (await page()) message('비교가 완료되었습니다. 경로를 펼쳐 확인하거나 전체 JSON 기록을 다운로드하세요.');
    } catch (error) { message(error.message); }
    finally { busy = false; el('source-comparison-form').querySelectorAll('select, button').forEach(node => { node.disabled = false; }); }
  };
  for (const side of ['left', 'right']) {
    el(`compare-${side}-source`).onchange = () => { categories(side); clear(); };
    el(`compare-${side}-category`).onchange = clear;
  }
  el('source-comparison-refresh').onclick = async () => { if (busy) return; clear(); try { await loadChoices(); } catch (error) { message(error.message); } };
  document.querySelector('[data-tab="source-comparison-panel"]').addEventListener('click', async () => { if (!choices && !busy) { try { await loadChoices(); } catch (error) { message(error.message); } } });
  el('source-comparison-filter').onchange = () => { offset = 0; page(); };
  el('source-comparison-prev').onclick = () => { offset = Math.max(0, offset - 100); page(); };
  el('source-comparison-next').onclick = () => { offset += 100; page(); };
})();
