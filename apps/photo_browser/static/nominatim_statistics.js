(() => {
  const el = suffix => document.getElementById(`nominatim-statistics-${suffix}`);
  const panel = document.getElementById('nominatim-panel');
  const number = value => Number(value).toLocaleString('ko-KR');
  const percent = value => `${Number(value).toFixed(2)}%`;
  let offset = 0, revision = 0, searchTimer, loading = false, reload = false, reloadForce = false;
  async function refresh(force = false) {
    if (loading) { reload = true; reloadForce = reloadForce || force; return; }
    loading = true;
    const current = revision;
    el('status').textContent = '태그 통계 집계 중…';
    try {
      const params = new URLSearchParams({kind: el('kind').value, q: el('search').value,
        offset: String(offset), refresh: force ? '1' : '0'});
      const response = await fetch(`api/nominatim/statistics?${params}`, {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      if (current !== revision) return;
      // A catalog update can shrink the result while the user is on a later page.
      if (offset >= data.matched_tags && offset > 0) { offset = 0; reload = true; return; }
      el('error').hidden = true;
      const summary = el('summary');
      summary.replaceChildren();
      const location = data.groups.location_tags, tags = data.groups.tags;
      for (const [label, value] of [
        ['모든 사진 수', `${number(data.total_photos)}개`],
        ['행정구역 이름이 없는 사진', `${number(data.missing_place_photo_count)}개`],
        ['GPS 있음 · 행정구역 이름 없음 · 위치 조회 대상', `${number(data.location_scan_candidate_count)}개`],
        ['GPS 정보가 없는 사진', `${number(data.missing_gps_photo_count)}개 (${percent(data.missing_gps_percent)})`],
        ['사용 중인 고유 태그 수', `${number(data.tag_count)}개 (위치·일반 태그 이름 중복 제거)`],
        ['위치 태그 종류', `${number(location.tag_count)}개`],
        ['위치 태그가 전혀 없는 사진', `${number(location.empty_photo_count)}개 (${percent(location.empty_percent)})`],
        ['일반 태그 종류', `${number(tags.tag_count)}개`],
        ['일반 태그가 전혀 없는 사진', `${number(tags.empty_photo_count)}개 (${percent(tags.empty_percent)})`],
        ['통계 집계 시각', data.observed_at],
      ]) {
        const dt = document.createElement('dt'), dd = document.createElement('dd');
        dt.textContent = label; dd.textContent = value; summary.append(dt, dd);
      }
      const rows = el('rows');
      rows.replaceChildren();
      for (const item of data.items) {
        const tr = document.createElement('tr');
        for (const value of [item.tag, number(item.photo_count), percent(item.percent),
          number(item.missing_photo_count), percent(item.missing_percent)]) {
          const td = document.createElement('td'); td.textContent = value; tr.append(td);
        }
        rows.append(tr);
      }
      if (!data.items.length) {
        const tr = document.createElement('tr'), td = document.createElement('td');
        td.colSpan = 5; td.textContent = '표시할 태그가 없습니다.'; tr.append(td); rows.append(tr);
      }
      el('previous').disabled = offset === 0;
      el('next').disabled = offset + data.items.length >= data.matched_tags;
      el('status').textContent = `태그 ${number(data.matched_tags)}개 중 ${data.items.length ? number(offset + 1) : 0}–${number(offset + data.items.length)}개 표시 · 30초마다 갱신`;
      panel.dispatchEvent(new CustomEvent('nominatim-statistics-updated', {detail: data}));
    } catch (error) {
      if (current === revision) {
        el('error').hidden = false;
        el('error').textContent = `통계 조회 실패: ${error.message}. 이전 통계는 최신이 아닐 수 있습니다.`;
        el('status').textContent = '태그 통계 조회 실패';
      }
    } finally {
      loading = false;
      if (reload) { const forceReload = reloadForce; reload = false; reloadForce = false; refresh(forceReload); }
    }
  }
  function change() { offset = 0; revision++; refresh(); }
  el('refresh').addEventListener('click', () => refresh(true));
  panel.addEventListener('nominatim-scan-complete', () => refresh(true));
  el('kind').addEventListener('change', change);
  el('search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(change, 300); });
  el('previous').addEventListener('click', () => { offset = Math.max(0, offset - 100); revision++; refresh(); });
  el('next').addEventListener('click', () => { offset += 100; revision++; refresh(); });
  new MutationObserver(() => { if (!panel.hidden) refresh(); }).observe(panel, {attributes: true, attributeFilter: ['hidden']});
  setInterval(() => { if (!panel.hidden && !document.hidden) refresh(); }, 30000);
})();
