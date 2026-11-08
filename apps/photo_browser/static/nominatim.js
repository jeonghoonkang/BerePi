(() => {
  const panel = document.getElementById('nominatim-panel');
  const el = id => document.getElementById(id);
  const names = {disabled: '실행 옵션 비활성', checking: '사전 점검 중',
    image_download: 'Docker 이미지 다운로드 중', map_download: '지도 다운로드 중',
    database_import: '지도 DB 구축 중', starting: 'Nominatim 시작 중', ready: '실행 중 · 준비 완료',
    unavailable: '서비스 상태 확인 실패', error: '오류 · 준비되지 않음', stopping: '종료 처리 중', stopped: '중지됨'};
  let busy = false;
  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch('api/nominatim/status', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      el('nominatim-fetch-error').hidden = true;
      el('nominatim-state').textContent = names[data.phase] || data.phase;
      const info = el('nominatim-info');
      info.replaceChildren();
      for (const [label, value] of [['사용 가능', data.ready ? '예' : '아니요'],
        ['현재 안내', data.message], ['컨테이너', data.container], ['이미지', data.image],
        ['지도 DB 볼륨', data.volume], ['조회 주소', data.endpoint], ['시작 시각', data.started_at],
        ['준비 완료 시각', data.ready_at], ['최근 상태 확인', data.checked_at], ['최근 갱신', data.updated_at]]) {
        const dt = document.createElement('dt'), dd = document.createElement('dd');
        dt.textContent = label; dd.textContent = value || '—'; info.append(dt, dd);
      }
      el('nominatim-progress').textContent = data.progress || '다운로드 진행 정보 없음';
      el('nominatim-error').hidden = !data.error;
      el('nominatim-error').textContent = data.error || '';
      const logs = el('nominatim-logs');
      const atBottom = logs.scrollHeight - logs.scrollTop - logs.clientHeight < 40;
      logs.textContent = data.events.map(event => `${event.time}  ${event.message}`).join('\n');
      if (atBottom) logs.scrollTop = logs.scrollHeight;
    } catch (error) {
      el('nominatim-fetch-error').hidden = false;
      el('nominatim-fetch-error').textContent = `상태 조회 실패: ${error.message}. 표시된 정보는 이전 결과입니다.`;
    } finally { busy = false; }
  }
  el('nominatim-refresh').addEventListener('click', refresh);
  new MutationObserver(() => { if (!panel.hidden) refresh(); }).observe(panel, {attributes: true, attributeFilter: ['hidden']});
  setInterval(() => { if (!panel.hidden && !document.hidden) refresh(); }, 2000);
})();
