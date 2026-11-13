/* Managed-only category consolidation; all file names are rendered as text. */
(() => {
  const el = id => document.getElementById(id);
  const active = ['queued', 'running', 'stopping'];
  const names = {preview: '미리보기', running: '실행 중', stopped: '중지됨', recovery_required: '복구/이어하기 필요', completed: '완료', undone: '되돌림 완료'};
  let plan, busy = false, jobId;
  const choiceFilters = {source_id: '*', category: '*', owner_id: '*'};
  const message = text => { el('category-status').textContent = text; };
  async function api(path, method = 'GET', data) {
    const response = await fetch(path, {method, cache: 'no-store', headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'}, body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function invalidate() { plan = null; el('category-run').disabled = true; el('category-preview-result').textContent = ''; }
  function button(label, action) {
    const node = document.createElement('button'); node.type = 'button'; node.textContent = label;
    node.onclick = async () => { try { await action(); } catch (error) { message(error.message); } };
    return node;
  }
  function drawChoices(groups, selected = new Set()) {
    const legend = document.createElement('legend'); legend.textContent = '통합할 소스 ID · 카테고리 · 소유자 ID 조합'; el('category-choices').replaceChildren(legend);
    const help = document.createElement('p'); help.textContent = '필터로 범위를 좁힌 뒤 조합을 체크하세요. 필터 변경 시 체크 선택이 초기화됩니다. 소유자 ID는 유지됩니다. 여러 소스에 연결된 동일 DB 항목은 한 번만 처리하며 해당 항목의 카테고리가 함께 변경됩니다.';
    el('category-choices').append(help);
    const filters = document.createElement('div'); filters.className = 'tools';
    for (const [key, title] of [['source_id', '소스 ID'], ['category', '카테고리'], ['owner_id', '사용자 (소유자 ID)']]) {
      const label = document.createElement('label'), select = document.createElement('select');
      select.id = `category-filter-${key}`; select.add(new Option('전체', '*'));
      const values = [...new Set(groups.map(item => item[key] ?? ''))].sort();
      for (const value of values) select.add(new Option(value || '(소스 연결 없음)', value));
      if (choiceFilters[key] !== '*' && !values.includes(choiceFilters[key])) choiceFilters[key] = '*';
      select.value = choiceFilters[key];
      select.onchange = () => { choiceFilters[key] = select.value; invalidate(); drawChoices(groups); message('필터가 변경되었습니다. 통합할 조합을 다시 선택하세요.'); };
      label.append(document.createTextNode(`${title} `), select); filters.append(label);
    }
    el('category-choices').append(filters);
    const visible = groups.filter(item => Object.entries(choiceFilters).every(([key, value]) => value === '*' || (item[key] ?? '') === value));
    const count = document.createElement('p'); count.textContent = `표시 조합 ${visible.length.toLocaleString()}개 / 전체 ${groups.length.toLocaleString()}개`;
    el('category-choices').append(count);
    for (const item of visible) {
      const label = document.createElement('label'), input = document.createElement('input');
      input.type = 'checkbox'; input.value = JSON.stringify({source_id: item.source_id, category: item.category, owner_id: item.owner_id}); input.checked = selected.has(input.value); input.disabled = busy;
      input.onchange = invalidate; label.append(input, document.createTextNode(` 소스: ${item.source_id ?? '(소스 연결 없음)'} · 카테고리: ${item.category} · 소유자: ${item.owner_id} (${item.count.toLocaleString()}개)`));
      label.style.display = 'block'; el('category-choices').append(label);
    }
  }
  async function refresh() {
    const [choices, history] = await Promise.all([api('api/category-merges/categories'), api('api/category-merges')]);
    const selected = new Set([...el('category-choices').querySelectorAll('input:checked')].map(node => node.value));
    drawChoices(choices.groups, selected);
    el('category-history').replaceChildren();
    for (const record of history.items) {
      const row = document.createElement('div'); row.className = 'source-row';
      const text = document.createElement('p');
      text.textContent = `${record.source_categories.join(', ')} → ${record.target_category} · ${names[record.status] || record.status} · ${record.file_count.toLocaleString()}개 · ${new Date(record.created_at).toLocaleString('ko-KR')} · 단계 ${record.stage}`;
      row.append(text);
      if (record.source_selections) {
        const scope = document.createElement('p');
        scope.textContent = '선택 범위: ' + record.source_selections.map(item => `${item.source_id ?? '(소스 연결 없음)'} / ${item.category} / ${item.owner_id}`).join(', ');
        row.append(scope);
      }
      if (record.error) { const error = document.createElement('p'); error.textContent = record.error; row.append(error); }
      const link = document.createElement('a'); link.textContent = 'JSON 기록'; link.href = `api/category-merges/${encodeURIComponent(record.operation_id)}`; link.target = '_blank'; link.rel = 'noopener'; row.append(link);
      if (record.status !== 'undone') {
        if (!record.stage.startsWith('undo') && record.status !== 'completed') row.append(button(record.status === 'preview' ? '통합 실행' : '통합 이어하기', () => run(record.operation_id)));
        if (record.status !== 'preview') row.append(button('통합 되돌리기', async () => {
          if (!confirm('이 작업의 카테고리와 관리 위치를 이전 상태로 되돌립니까? 이후 수정과 충돌하면 중단하며 파일을 덮어쓰지 않습니다.')) return;
          await launch(`api/category-merges/${encodeURIComponent(record.operation_id)}/undo`);
        }));
      }
      row.querySelectorAll('button').forEach(node => { node.disabled = busy; });
      el('category-history').append(row);
    }
  }
  async function launch(path, data, preview = false) {
    if (busy) return;
    busy = true; el('category-preview').disabled = true; el('category-run').disabled = true;
    el('category-choices').disabled = true; el('category-target').disabled = true;
    el('category-history').querySelectorAll('button').forEach(node => { node.disabled = true; });
    el('category-progress').hidden = false; el('category-progress').value = 0;
    message('작업을 요청하고 있습니다…');
    try {
      const started = await api(path, 'POST', data || {}); jobId = started.job_id;
      el('category-stop').hidden = preview || path.endsWith('/undo'); el('category-stop').disabled = false;
      let status;
      do {
        status = await api(`api/jobs/${encodeURIComponent(jobId)}`);
        const p = status.progress || {};
        el('category-progress').value = p.percent || 0;
        const phases = {category_planning: '관리 파일 검증·미리보기', category_copying: '새 카테고리로 경로 전환·검증 (필요 시 복사)', category_archiving: '이전 파일 복구용 보관', category_restoring: '이전 위치 복원'};
        message(`${phases[p.phase] || status.status} · ${p.processed || 0}/${p.total || 0}개${p.current_file ? '\n처리 대상: ' + p.current_file : ''}${p.source_file ? '\n입력 managed: ' + p.source_file : ''}${p.target_file ? '\n출력/보관 위치: ' + p.target_file : ''}`);
        if (active.includes(status.status)) await new Promise(resolve => setTimeout(resolve, 1000));
      } while (active.includes(status.status));
      if (status.status === 'failed') throw new Error(status.error || '작업에 실패했습니다. 통합 기록에서 복구 상태를 확인하세요.');
      const result = status.result;
      if (preview && result?.operation_id) {
        plan = result.operation_id;
        const samples = result.rows.slice(0, 100).map(row => `${row.source}\n  → ${row.destination}${row.renamed ? ' (충돌 이름 구분)' : ''}`).join('\n');
        el('category-preview-result').textContent = `${result.rows.length.toLocaleString()}개 · 복사 없는 경로 전환 예상 ${(result.link_files || 0).toLocaleString()}개 · 신규 복사 파일 ${result.copy_files.toLocaleString()}개 · 예상 복사 ${(result.copy_bytes / 1073741824).toFixed(2)} GiB\n${result.warning}\n\n처음 최대 100개 경로:\n${samples}`;
        message('미리보기가 완료되었습니다. 경로와 공간 사용을 확인한 뒤 실행하세요.');
      } else {
        invalidate();
        message(`${names[result?.status] || status.status} · 단계 ${result?.stage || ''}. 카테고리·원본 위치·보관 목록은 JSON 기록에서 확인할 수 있습니다.`);
      }
    } finally {
      jobId = null; busy = false; el('category-stop').hidden = true; el('category-preview').disabled = false;
      el('category-choices').disabled = false; el('category-target').disabled = false;
      el('category-run').disabled = !plan;
      await refresh();
    }
  }
  async function run(id) {
    if (!confirm('검증한 managed 파일로 카테고리를 통합합니까? 이전 관리 파일은 복구용으로 보관하며 자동 삭제하지 않습니다.')) return;
    await launch(`api/category-merges/${encodeURIComponent(id)}/run`);
  }
  el('category-merge-form').onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    const selections = [...el('category-choices').querySelectorAll('input:checked')].map(node => JSON.parse(node.value));
    if (!selections.length) { message('통합할 소스·카테고리·소유자 조합을 선택하세요.'); return; }
    invalidate();
    try { await launch('api/category-merges/preview', {selections, target_category: el('category-target').value.trim()}, true); }
    catch (error) { message(error.message); }
  };
  el('category-run').onclick = async () => { try { if (plan) await run(plan); } catch (error) { message(error.message); } };
  el('category-target').oninput = invalidate;
  el('category-refresh').onclick = async () => { if (busy) return; invalidate(); try { await refresh(); } catch (error) { message(error.message); } };
  el('category-stop').onclick = async () => {
    if (!jobId || !confirm('카테고리 통합 작업을 중지하시겠습니까?\n다른 접속자에게도 적용됩니다. 진행 상황을 저장한 뒤 중지합니다.')) return;
    try { await api(`api/jobs/${jobId}/stop`, 'POST', {}); el('category-stop').disabled = true; message('안전한 단계까지 처리한 뒤 중지하고 기록합니다.'); }
    catch (error) { message(error.message); }
  };
  document.querySelector('[data-tab="category-merge-panel"]').addEventListener('click', async () => { try { await refresh(); } catch (error) { message(error.message); } });
})();
