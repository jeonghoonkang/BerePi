/* Applying an input path adds a source while preserving previous source IDs. */
(() => {
  const el = id => document.getElementById(id);
  el('directory-update').onsubmit = async event => {
    event.preventDefault();
    const button = el('directory-update-button'), status = el('directory-update-status');
    const path = el('directory-path').value.trim();
    if (button.disabled) return;
    if (!path) { status.textContent = '디렉토리 경로를 입력하세요.'; return; }
    button.disabled = true;
    status.textContent = '소스 디렉토리를 확인하고 등록하고 있습니다…';
    let saved = false;
    try {
      const response = await fetch('api/sources/register-directory', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'},
        body: JSON.stringify({path}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      saved = true;
      const source = result.source;
      el('directory-path').value = source.root;
      el('path').value = source.root;
      el('date').value = ''; el('type').value = 'all';
      el('recursive').checked = source.recursive !== false;
      await window.photoBrowserSourceUpdated(source);
      const listing = await browse(source.root);
      const warning = listing ? '' : ` 폴더 미리보기 실패: ${status.textContent}`;
      status.textContent = `${result.added ? '신규 소스 추가' : '기존 소스 선택'}: ${source.source_id} · ${source.root}. ` +
        '이전 소스는 유지됩니다. 소스·스캔·병합에서 스캔 / JSON 생성 후 병합을 실행하세요.' + warning;
    } catch (error) {
      status.textContent = (saved ? '소스는 등록됐지만 화면 갱신에 실패했습니다. 새로고침해 등록 목록을 확인하세요. ' : '소스를 적용하지 못했습니다. ') + error.message;
    } finally {
      button.disabled = false;
    }
  };
})();
