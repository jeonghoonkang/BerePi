(() => {
  function createControls(api) {
    const make = (tag, text) => { const node = document.createElement(tag); if (text) node.textContent = text; return node; };
    const root = make('details'), title = make('summary'), note = make('p', 'DB의 SHA-256·파일 크기로 확인한 동일 내용입니다. 기존 관리 파일의 현재 내용은 다시 해시 검사하지 않습니다. 소유자 ID와 소스 ID를 함께 표시합니다.');
    const message = make('p'), table = make('table'), head = make('thead'), headings = make('tr'), body = make('tbody');
    const inventory = make('pre');
    for (const label of ['스캔 파일', '기존 사진 ID', '카테고리 / 소유자 ID', '소스 ID', '관리 파일 저장 위치']) {
      const cell = make('th', label); cell.setAttribute('scope', 'col'); headings.append(cell);
    }
    head.append(headings); table.append(head, body);
    const scroll = make('div'); scroll.className = 'summary-table-scroll'; scroll.setAttribute('tabindex', '0'); scroll.append(table);
    const previous = make('button', '이전 100개'), next = make('button', '다음 100개'), reload = make('button', '다시 확인');
    for (const button of [previous, next, reload]) button.type = 'button';
    message.setAttribute('role', 'status');
    root.append(title, note, inventory, message, scroll, previous, next, reload);
    let scanId, offset = 0, busy = false, key, duplicateCount = 0;
    async function load() {
      if (!scanId || busy) return;
      if (!duplicateCount) { message.textContent = '2차 파일 내용 확인: 다른 분류·ID의 동일 파일이 아직 없습니다.'; return; }
      busy = true;
      try {
        const data = await api(`api/scans/${encodeURIComponent(scanId)}/duplicates?offset=${offset}`);
        body.replaceChildren();
        for (const item of data.items) {
          for (const match of item.matches) {
            const row = make('tr');
            const paths = match.managed_files.map(file => `${file.path}${file.exists === true ? '' : file.exists === false ? ' (현재 파일 없음)' : ' (존재 확인 실패)'}`);
            for (const value of [item.source_file, match.media_id, `${match.category_id} / ${match.owner_id}`,
              match.source_ids.join(', ') || '기록 없음', paths.join('\n') || 'DB 등록만 있음 · 관리 복사본 없음']) row.append(make('td', value));
            body.append(row);
          }
          if (item.matches_truncated) {
            const row = make('tr'), cell = make('td', `${item.source_file}: 기존 일치 ${item.match_count}개 중 50개 표시`);
            cell.colSpan = 5; row.append(cell); body.append(row);
          }
        }
        message.textContent = `다른 분류·ID에 동일한 스캔 파일 ${data.total}개 · ${data.items.length ? offset + 1 : 0}–${offset + data.items.length}개 표시`;
        previous.disabled = offset === 0; next.disabled = offset + data.items.length >= data.total;
      } catch (error) { message.textContent = `중복 확인 결과 조회 실패: ${error.message}`; }
      finally { busy = false; }
    }
    root.addEventListener('toggle', () => { if (root.open) load(); });
    previous.onclick = () => { offset = Math.max(0, offset - 100); load(); };
    next.onclick = () => { offset += 100; load(); };
    reload.onclick = () => load();
    return {root, update(status) {
      const state = status.result || status.progress || {};
      root.hidden = status.kind !== 'scan' || (!state.cross_group_duplicate_count && !state.source_inventory);
      if (root.hidden) return;
      scanId = state.scan_id;
      duplicateCount = state.cross_group_duplicate_count || 0;
      title.textContent = `소스 구성 비교 · 다른 분류·ID의 동일 파일 ${duplicateCount}개 · 상세보기`;
      const info = state.source_inventory;
      inventory.hidden = !info;
      if (info) {
        const sizes = value => value == null ? '용량 미확인' : `${Number(value).toLocaleString()} bytes`;
        const labels = {same_layout_candidate: '구성 일치 · 동일 소스 후보', different_source: '구성 다름 · 별도 소스 추정', insufficient_inventory: '비교 정보 부족'};
        inventory.textContent = [`1차 구성 확인: 디렉토리 ${info.current.directory_count}개 · 파일 ${info.current.file_count}개 · ${sizes(info.current.total_bytes)}`,
          '사진·동영상이 있는 상대 디렉토리 구조 기준입니다. 내용 일치 여부는 2차 SHA-256 비교로 확인합니다.',
          ...info.comparisons.map(row => `${row.source_id}: ${labels[row.status]} · 디렉토리 ${row.directory_count}개 · 파일 ${row.file_count}개 · ${sizes(row.total_bytes)}`)].join('\n');
      }
      const current = `${scanId}:${state.cross_group_duplicate_count}:${status.status}`;
      if (root.open && key !== current) load();
      key = current;
    }};
  }
  window.photoBrowserScanDuplicates = {createControls};
})();
