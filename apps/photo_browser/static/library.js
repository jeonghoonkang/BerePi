/* Library UI. All untrusted names and metadata are rendered as text. */
(() => {
  const el = id => document.getElementById(id);
  let config, page = [], offset = 0, total = 0, chosen = new Set(), undoId;
  const watchers = new Map(), jobCards = new Map();
  const jobsPage = document.body.classList.contains('jobs-page');
  let jobsOffset = 0, visibleJobs = new Set();
  const activeStates = ['queued', 'running', 'stopping'];
  const stateNames = {queued:'대기', running:'실행 중', stopping:'중지 요청 · 저장 대기', stopped:'중지됨', paused_low_space:'공간 부족 · 일시 정지', completed:'완료', failed:'오류 · 중단', interrupted:'서버 재시작 · 중단'};
  const notify = message => { el('notice').textContent = message; };
  async function api(path, method = 'GET', data) {
    const response = await fetch(path, {method, cache: 'no-store', headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'}, body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  const safe = fn => async (...args) => { try { await fn(...args); } catch (error) { notify(error.message); } };
  function make(tag, text, className) { const node = document.createElement(tag); if (text) node.textContent = text; if (className) node.className = className; return node; }
  function action(text, fn) { const node = make('button', text); node.type = 'button'; node.onclick = safe(fn); return node; }
  function tab(id) {
    document.querySelectorAll('.panel').forEach(panel => { panel.hidden = panel.id !== id; });
    document.querySelectorAll('[data-tab]').forEach(button => { button.setAttribute('aria-pressed', button.dataset.tab === id); });
  }
  document.querySelectorAll('[data-tab]').forEach(button => { button.onclick = safe(async () => { tab(button.dataset.tab); if (button.dataset.tab === 'trash-panel') await loadTrash(); if (button.dataset.tab === 'duplicates-panel') await loadDuplicates(); }); });
  function selection() { el('selection-count').textContent = `${chosen.size}개 선택`; }
  async function facets() {
    const values = await api('api/facets');
    for (const [id, key] of Object.entries({'filter-event':'events', 'filter-tag':'tags', 'filter-person':'person_ids', 'filter-category':'category_id', 'filter-owner':'owner_id'})) {
      const select = el(id), current = select.value;
      select.replaceChildren(new Option('전체', ''));
      values[key].forEach(value => select.add(new Option(value, value)));
      select.value = current;
    }
  }
  function detail(item) {
    const container = el('detail-preview'); container.replaceChildren();
    const media = make(item.media_type === 'video' ? 'video' : 'img');
    media.src = `api/library/${encodeURIComponent(item.media_id)}/file`;
    if (item.media_type === 'video') media.controls = true; else media.alt = item.name;
    container.append(media);
    el('detail-info').textContent = JSON.stringify(item, null, 2);
    el('library-detail').showModal();
  }
  el('detail-close').onclick = () => el('library-detail').close();
  el('library-detail').onclose = () => el('detail-preview').replaceChildren();
  async function load() {
    const params = new URLSearchParams(new FormData(el('library-filters')));
    if (offset !== null) params.set('offset', offset);
    const result = await api('api/library?' + params);
    page = result.items; total = result.total; offset = result.offset; chosen.clear(); selection(); el('select-page').checked = false;
    el('library-count').textContent = `${total.toLocaleString()}개 · ${offset + (page.length ? 1 : 0)}–${offset + page.length}` + (result.window ? ` · 기준 ${result.window.date}: 당일 ${result.window.on_date.toLocaleString()}개 · 이전 ${result.window.before.toLocaleString()}/${result.window.before_total.toLocaleString()}개 · 이후 ${result.window.after.toLocaleString()}/${result.window.after_total.toLocaleString()}개 · 전후 각각 최대 ${result.window.per_side.toLocaleString()}개 (다른 검색 조건 적용)` : '');
    el('library-prev').disabled = offset === 0; el('library-next').disabled = offset + page.length >= total;
    el('library-gallery').replaceChildren();
    for (const item of page) {
      const card = make('article', '', 'library-card'), check = make('input'); check.type = 'checkbox'; check.dataset.id = item.media_id; check.setAttribute('aria-label', item.name + ' 선택');
      check.onchange = () => { if (check.checked) chosen.add(item.media_id); else chosen.delete(item.media_id); selection(); };
      const button = action('', () => detail(item)); button.className = 'card';
      if (item.media_type === 'video') button.append(make('div', '▶ 동영상', 'video-placeholder'));
      else { const image = make('img'); image.src = `api/library/${encodeURIComponent(item.media_id)}/file`; image.loading = 'lazy'; image.alt = item.name; button.append(image); }
      button.append(make('span', item.name), make('span', item.capture.date_key + ' · ' + item.classification.events.join(', ')));
      card.append(check, button); el('library-gallery').append(card);
    }
  }
  el('library-filters').onsubmit = safe(async event => { event.preventDefault(); offset = null; await load(); });
  el('library-date').onchange = safe(async () => { offset = null; await load(); });
  el('library-filters').onreset = () => setTimeout(safe(async () => { offset = 0; await load(); }), 0);
  el('library-prev').onclick = safe(async () => { offset = Math.max(0, offset - 100); await load(); });
  el('library-next').onclick = safe(async () => { offset += 100; await load(); });
  el('select-page').onchange = event => { el('library-gallery').querySelectorAll('input[type=checkbox]').forEach(check => { check.checked = event.target.checked; if (check.checked) chosen.add(check.dataset.id); else chosen.delete(check.dataset.id); }); selection(); };
  function selected() { if (!chosen.size) throw new Error('파일을 선택하세요.'); return [...chosen]; }
  const fields = {events: '이벤트 이름', tags: '태그', person_ids: '사람 ID', category_id: '카테고리', owner_id: '소유자 ID'};
  for (const [key, label] of Object.entries(fields)) {
    const row = make('label', '', 'edit-row'), check = make('input'), input = make('input'); check.type = 'checkbox'; check.id = 'apply-' + key; input.id = 'edit-' + key;
    row.append(check, document.createTextNode(label + ' '), input); el('edit-fields').append(row);
  }
  el('edit-selected').onclick = safe(() => {
    selected(); el('edit-form').reset();
    if (chosen.size === 1) { const item = page.find(i => chosen.has(i.media_id)); for (const key of Object.keys(fields)) el('edit-' + key).value = Array.isArray(item.classification[key]) ? item.classification[key].join(', ') : item.classification[key]; }
    el('edit-dialog').showModal();
  });
  el('edit-close').onclick = () => el('edit-dialog').close();
  el('edit-form').onsubmit = safe(async event => {
    event.preventDefault(); const changes = {};
    for (const key of Object.keys(fields)) if (el('apply-' + key).checked) { const value = el('edit-' + key).value.trim(); changes[key] = ['category_id', 'owner_id'].includes(key) ? value : value.split(',').map(v => v.trim()).filter(Boolean); }
    await api('api/library', 'PATCH', {ids: selected(), changes}); el('edit-dialog').close(); await facets(); await load(); notify('분류를 저장했습니다.');
  });
  function progressText(progress) {
    if (!progress) return '시작 대기 중';
    if (!progress.inventory_complete) return `전체 파일 목록 집계 중 · 현재 ${progress.total.toLocaleString()}개 발견 · 전체 개수 확인 중`;
    return `전체 ${progress.total.toLocaleString()}개 · 처리 ${progress.processed.toLocaleString()}개 (${progress.percent ?? 0}%) · 신규 ${progress.added} · 갱신 ${progress.updated} · 변경 없음 ${progress.unchanged} · 제외 ${progress.ignored} · 오류 ${progress.error_count ?? progress.errors?.length ?? 0}`;
  }
  function jobSummary(status) {
    const result = status.result;
    if (!result) return [];
    const count = value => Number(value || 0).toLocaleString();
    if (status.kind === 'scan') {
      const lines = [
        `스캔 분석: 신규 ${count(result.added)}개 · 갱신 ${count(result.updated)}개 · 변경 없음 ${count(result.unchanged)}개`,
        `월별 JSON: ${result.published ? '반영 완료' : '반영 완료되지 않음 · 작업 상태와 경고를 확인하세요.'}`,
        '원본 사진·동영상은 변경하지 않았습니다. 사진 복사본 생성은 별도의 병합 실행이 필요합니다.',
      ];
      if (result.updated) lines.push('갱신은 스캔 분석 결과를 다시 반영한 개수이며, 사진 내용이나 태그가 변경된 개수는 아닙니다.');
      lines.push(`제외 ${count(result.ignored)}개 · 처리 오류 ${count(result.errors?.length ?? result.error_count)}개`);
      return lines;
    }
    if (status.kind === 'merge') {
      const operations = result.operations || [];
      const counts = {};
      operations.forEach(operation => { counts[operation.status] = (counts[operation.status] || 0) + 1; });
      return [
        result.preview ? `미리보기: 복사 예정 ${count(counts.planned)}개 · 실제 복사하지 않음` : `병합 결과: 새 복사 ${count(counts.copied)}개 · 기존 파일 재사용 ${count(counts.reused)}개 · 건너뜀 ${count(counts.skipped)}개 · 오류 ${count(counts.error)}개`,
        result.preview ? '병합 실행 시 관리 디렉토리에 복사본을 생성합니다.' : '성공한 복사본의 위치를 사진 JSON에 반영했습니다. 원본 파일은 유지합니다.',
      ];
    }
    if (status.kind === 'source_rename') {
      return ['소스 ID 변경 작업을 완료했습니다. 현재 ID는 소스 목록에서 확인하세요.',
        '사진 JSON과 스캔 기록의 소스 연결을 변경했습니다. 사진 파일의 위치와 태그는 유지합니다.'];
    }
    return [];
  }
  function drawJob(status) {
    if (jobsPage && !visibleJobs.has(status.job_id)) return;
    let card = jobCards.get(status.job_id);
    if (!card) {
      const row = make('details', '', 'source-row job-card'), title = make('summary'), text = make('p'), bar = make('progress'), file = make('p'), warning = make('p', '', 'scan-warning');
      const changes = make('section'), changesTitle = make('h4', '주요 처리 결과 · 반영 사항'), changesList = make('ul');
      changes.append(changesTitle, changesList);
      row.open = activeStates.includes(status.status);
      bar.max = 100; bar.setAttribute('aria-label', '작업 처리 진행률');
      const stop = action('중지하고 저장', async () => { const result = await api(`api/jobs/${status.job_id}/stop`, 'POST', {}); drawJob(result); notify('중지를 요청했습니다. 현재 작업을 정리하고 저장하는 동안 기다려 주세요.'); });
      const resume = action('병합 이어하기', () => job('api/merge', {preview: false, resume: card.mergeId}));
      row.append(title, text, bar, file, warning, changes, stop, resume); el('scan-jobs').prepend(row);
      card = {row, title, text, bar, file, warning, changes, changesList, stop, resume}; jobCards.set(status.job_id, card);
    }
    card.createdAt = status.created_at;
    if (!jobsPage) {
      const ordered = [...jobCards.entries()].sort((a, b) => b[1].createdAt.localeCompare(a[1].createdAt));
      for (const [id, old] of ordered.slice(3)) { old.row.remove(); jobCards.delete(id); }
      for (const [, entry] of ordered.slice(0, 3)) el('scan-jobs').append(entry.row);
    }
    const p = status.result || status.progress;
    const summary = jobSummary(status);
    card.changes.hidden = !summary.length;
    card.changesList.replaceChildren(...summary.map(line => make('li', line)));
    card.title.textContent = `${status.kind === 'source_rename' ? '소스 ID 변경 · ' + status.source_id : status.source_id || (status.kind === 'merge' ? '전체 병합' : '파일 작업')} · ${stateNames[status.status] || status.status}`;
    card.text.textContent = status.kind === 'merge' ? `전체 ${p?.total ?? 0}개 · 처리 ${p?.processed ?? 0}개 (${p?.percent ?? 0}%)` : status.kind === 'scan' ? progressText(p) : '결과는 아래 작업 결과에 표시합니다.';
    card.bar.hidden = !['scan', 'merge'].includes(status.kind);
    if (p?.inventory_complete || status.kind === 'merge') card.bar.value = p?.percent ?? 0; else card.bar.removeAttribute('value');
    card.file.textContent = p?.current_file ? `현재 파일: ${p.current_file}` : '';
    const disk = p?.disk;
    card.warning.textContent = [p?.warning || status.warning || status.error, disk ? `DB 여유 ${(disk.free_bytes / 1048576).toFixed(0)} MiB / 예상 필요 ${(disk.required_bytes / 1048576).toFixed(0)} MiB` : ''].filter(Boolean).join('\n');
    card.stop.hidden = !['scan', 'merge'].includes(status.kind) || !activeStates.includes(status.status);
    card.stop.disabled = status.status === 'stopping';
    card.mergeId = p?.merge_id;
    card.resume.hidden = status.kind !== 'merge' || !card.mergeId || !['stopped', 'interrupted', 'failed'].includes(status.status);
  }
  function watchJob(id) {
    if (watchers.has(id)) return watchers.get(id);
    const watching = (async () => {
      let status;
      do {
        status = await api('api/jobs/' + id); drawJob(status);
        el('job-status').textContent = `${stateNames[status.status] || status.status} · ${status.source_id || (status.kind === 'merge' ? '전체 병합' : '파일 작업')}`;
        if (activeStates.includes(status.status)) await new Promise(resolve => setTimeout(resolve, 1000));
      } while (activeStates.includes(status.status));
      el('job-result').textContent = JSON.stringify(status.result || status.error || status.warning, null, 2);
      await loadConfig(); await facets(); await load();
      const warning = status.result?.warning || status.error || status.warning;
      notify(warning || (status.status === 'stopped' ? '작업을 중지하고 저장했습니다. 이어하기로 재개할 수 있습니다.' : '작업이 완료되었습니다. 결과의 오류 항목도 확인하세요.'));
    })();
    watchers.set(id, watching);
    watching.finally(() => watchers.delete(id)).catch(() => {});
    return watching;
  }
  async function job(path, data) {
    const result = await api(path, 'POST', data);
    notify('작업을 시작했습니다. 소스·스캔 화면에서 진행률과 중지 버튼을 확인할 수 있습니다.');
    await watchJob(result.job_id);
  }
  async function loadJobs() {
    const result = await api(`api/jobs?limit=${jobsPage ? 20 : 3}&offset=${jobsOffset}`);
    visibleJobs = new Set(result.items.map(item => item.job_id));
    for (const [id, card] of jobCards) if (!visibleJobs.has(id)) { card.row.remove(); jobCards.delete(id); }
    if (jobsPage) {
      el('jobs-pagination').hidden = false;
      el('jobs-prev').disabled = jobsOffset === 0;
      el('jobs-next').disabled = jobsOffset + 20 >= result.total;
      el('jobs-page-info').textContent = `${Math.floor(jobsOffset / 20) + 1} / ${Math.max(1, Math.ceil(result.total / 20))}페이지 · 전체 ${result.total}개`;
    }
    for (const status of result.items.slice().reverse()) {
      drawJob(status);
      if (activeStates.includes(status.status)) safe(() => watchJob(status.job_id))();
    }
  }
  async function loadConfig() {
    config = await api('api/config'); el('managed-root').value = config.managed_root; el('scan-min-free').value = config.scan_min_free_mb ?? 512; el('source-list').replaceChildren();
    el('current-managed-path').textContent = config.managed_root;
    el('current-source-paths').textContent = config.sources.length
      ? config.sources.map(source => `${source.source_id}: ${source.root}`).join('\n')
      : '등록된 소스 없음';
    const sessions = (await api('api/scans')).items;
    config.sources.forEach(source => {
      const row = make('div', '', 'source-row'); row.append(make('p', `${source.source_id} · ${source.protocol} · ${source.root}`));
      const session = sessions.find(s => s.source_id === source.source_id);
      if (session) row.append(make('p', `${stateNames[session.status] || session.status} · ${progressText(session)}`));
      const resume = action('중단 지점부터 이어하기', () => job('api/scan', {source_id: source.source_id, mode: 'resume'}));
      resume.disabled = !session || session.status === 'completed' || session.status === 'running';
      row.append(action('소스 ID 변경', () => {
        el('rename-source-old').textContent = source.source_id;
        el('rename-source-new').value = source.source_id;
        el('rename-source-status').textContent = '';
        el('rename-source-dialog').showModal();
        el('rename-source-new').focus();
        el('rename-source-new').select();
      }));
      row.append(resume, action('처음부터 전체 재스캔', async () => { if (confirm('중단 지점 대신 처음부터 파일 목록과 메타데이터를 다시 검사합니까? 이벤트·태그와 원본은 유지됩니다.')) await job('api/scan', {source_id: source.source_id, mode: 'restart'}); }));
      row.append(action('스캔 / JSON 생성', () => job('api/scan', {source_id: source.source_id})), action('설정 불러오기', () => { for (const [key, value] of Object.entries(source)) { const input = el('source-form').elements.namedItem(key); if (input) { if (input.type === 'checkbox') input.checked = value; else input.value = value; } } }), action('등록 해제', async () => { if (!confirm('스캔 소스 등록을 해제합니까? 기존 JSON과 원본 파일은 유지됩니다.')) return; await api('api/config', 'PUT', {...config, sources: config.sources.filter(s => s.source_id !== source.source_id)}); await loadConfig(); }));
      el('source-list').append(row);
    });
  }
  let renaming = false;
  el('rename-source-cancel').onclick = () => el('rename-source-dialog').close();
  el('rename-source-dialog').addEventListener('cancel', event => { if (renaming) event.preventDefault(); });
  el('rename-source-form').onsubmit = async event => {
    event.preventDefault();
    if (renaming) return;
    const oldId = el('rename-source-old').textContent;
    const newId = el('rename-source-new').value.trim();
    if (!newId || newId === oldId) {
      el('rename-source-status').textContent = '현재 ID와 다른 새 ID를 입력하세요.';
      return;
    }
    renaming = true;
    el('rename-source-submit').disabled = el('rename-source-cancel').disabled = el('rename-source-new').disabled = true;
    el('rename-source-status').textContent = '사진 JSON과 스캔 기록을 변경하고 있습니다. 완료될 때까지 기다려 주세요…';
    let saved = false;
    try {
      const started = await api('api/sources/rename', 'POST', {old_id: oldId, new_id: newId, background: true});
      let status;
      do {
        await new Promise(resolve => setTimeout(resolve, 1000));
        status = await api(`api/jobs/${encodeURIComponent(started.job_id)}`);
        el('rename-source-status').textContent = '서버에서 사진 JSON과 스캔 기록을 변경 중입니다. 완료 여부를 확인하고 있습니다…';
      } while (['queued', 'running', 'stopping'].includes(status.status));
      if (status.status !== 'completed') throw new Error(status.error || status.warning || `작업 상태: ${status.status}`);
      config = status.result;
      saved = true;
      el('rename-source-old').textContent = newId;
      const sourceId = el('source-form').elements.namedItem('source_id');
      if (sourceId.value === oldId) sourceId.value = newId;
      await loadConfig();
      el('rename-source-dialog').close();
      notify(`소스 ID를 ${oldId} → ${newId}(으)로 저장했습니다. 사진·태그·스캔 기록의 연결을 유지했습니다.`);
    } catch (error) {
      el('rename-source-status').textContent = saved
        ? `ID는 ${newId}(으)로 저장됐지만 화면 갱신에 실패했습니다. 페이지를 새로고침하세요. ${error.message}`
        : `완료를 확인하지 못했습니다. ${error.message} · 연결이 끊겨도 서버 작업은 계속될 수 있습니다. 페이지를 새로고침해 현재 소스 ID와 작업 상태를 확인하세요.`;
    } finally {
      renaming = false;
      el('rename-source-submit').disabled = el('rename-source-cancel').disabled = el('rename-source-new').disabled = false;
    }
  };
  el('managed-form').onsubmit = safe(async event => { event.preventDefault(); await api('api/config', 'PUT', {...config, managed_root: el('managed-root').value, scan_min_free_mb: Number(el('scan-min-free').value)}); await loadConfig(); notify('관리 경로와 스캔 여유 공간 기준을 저장했습니다.'); });
  el('source-form').onsubmit = safe(async event => {
    event.preventDefault(); const form = el('source-form'), source = Object.fromEntries(new FormData(form)); source.recursive = form.elements.recursive.checked;
    const {existing} = await api('api/sources/check', 'POST', source);
    if (existing && existing.source_id !== source.source_id) {
      if (!confirm(`같은 경로의 기존 소스 ID는 ${existing.source_id}입니다.\n${source.source_id}(으)로 변경하시겠습니까? 취소하면 기존 ID를 불러옵니다.`)) {
        form.elements.source_id.value = existing.source_id;
        notify(`기존 소스 ID ${existing.source_id}를 사용합니다. 내용을 확인한 뒤 다시 등록하세요.`); return;
      }
      config = await api('api/sources/rename', 'POST', {old_id: existing.source_id, new_id: source.source_id});
    }
    await api('api/config', 'PUT', {...config, sources: [...config.sources.filter(s => s.source_id !== source.source_id), source]}); await loadConfig(); notify('소스를 저장했습니다. 스캔 버튼으로 JSON을 생성하세요.');
  });
  el('merge-preview').onclick = safe(() => job('api/merge', {preview: true}));
  el('merge-run').onclick = safe(async () => { if (confirm('활성 파일 전체를 월별 관리 디렉토리에 병합 복사합니까?')) await job('api/merge', {preview: false}); });
  el('verify-selected').onclick = safe(() => job('api/verify', {ids: selected(), full: true}));
  el('trash-selected').onclick = safe(async () => {
    const ids = selected(); if (!confirm(`${ids.length}개 항목을 휴지통으로 이동합니까? 소스 원본은 유지됩니다.`)) return;
    const result = await api('api/trash', 'POST', {ids}); undoId = result.trash_id; el('undo-trash').hidden = false; await load(); await loadTrash(); notify('휴지통으로 이동했습니다. 실행 취소 또는 휴지통에서 복원할 수 있습니다.');
  });
  el('undo-trash').onclick = safe(async () => { await api(`api/trash/${undoId}/restore`, 'POST', {}); el('undo-trash').hidden = true; await load(); await loadTrash(); notify('복원했습니다.'); });
  async function loadTrash() {
    const result = await api('api/trash'); el('trash-list').replaceChildren();
    for (const entry of result.items.reverse()) {
      const row = make('article', '', 'source-row'); row.append(make('p', `${entry.created_at} · ${entry.media_ids.length}개 · ${entry.status}`), make('pre', entry.moves.map(m => m.original).join('\n') || '관리 복사본 없음 / 공유 파일 유지'));
      if (['trashed', 'moving', 'recovery_required', 'restoring'].includes(entry.status)) row.append(action('복원', async () => { await api(`api/trash/${entry.trash_id}/restore`, 'POST', {}); await loadTrash(); await load(); notify('복원했습니다.'); }));
      if (['trashed', 'purge_failed'].includes(entry.status)) row.append(action('영구 삭제…', async () => {
        if (!confirm(`${entry.media_ids.length}개 항목의 휴지통 파일을 영구 삭제합니다. 목록을 확인했습니까?`)) return;
        const prepared = await api(`api/trash/${entry.trash_id}/prepare`, 'POST', {});
        const phrase = prompt(`복구할 수 없습니다. 다음 문구를 입력하세요:\n${prepared.phrase}`);
        if (phrase !== prepared.phrase) { notify('확인 문구가 달라 취소했습니다.'); return; }
        if (!confirm('최종 확인: 휴지통 파일을 영구 삭제합니까?')) return;
        const deleted = await api(`api/trash/${entry.trash_id}/purge`, 'POST', {token: prepared.token, phrase}); await loadTrash(); notify(deleted.status === 'purged' ? '영구 삭제했습니다.' : '일부 파일 삭제에 실패했습니다. 기록을 확인하세요.');
      }));
      el('trash-list').append(row);
    }
  }
  async function loadDuplicates() {
    const result = await api('api/duplicates'); el('duplicates-list').replaceChildren();
    for (const key of ['exact', 'candidates']) {
      el('duplicates-list').append(make('h3', key === 'exact' ? '동일 파일' : '촬영 시각·위치 후보'));
      for (const group of result[key]) {
        const row = make('div', '', 'source-row'); row.append(make('p', group.sha256 || group.reason));
        for (const id of group.members) row.append(action(id, async () => {
          const item = await api(`api/library/${id}`); detail(item);
        }));
        el('duplicates-list').append(row);
      }
      if (!result[key].length) el('duplicates-list').append(make('p', '해당 항목이 없습니다.'));
    }
  }
  el('refresh-trash').onclick = safe(loadTrash); el('refresh-duplicates').onclick = safe(loadDuplicates);
  el('refresh-jobs').onclick = safe(async () => { await loadConfig(); await loadJobs(); });
  el('jobs-prev').onclick = safe(async () => { jobsOffset = Math.max(0, jobsOffset - 20); await loadJobs(); });
  el('jobs-next').onclick = safe(async () => { jobsOffset += 20; await loadJobs(); });
  tab(jobsPage ? 'sources-panel' : 'library-panel'); safe(async () => { await loadConfig(); await facets(); await load(); await loadJobs(); })();
})();
