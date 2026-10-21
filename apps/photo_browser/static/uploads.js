/* Sequential uploads keep browser and server memory independent of file size. */
(() => {
  const el = id => document.getElementById(id);
  let settings, running = false, stopping = false, savedDirectory;
  const bytes = value => `${(value / 1048576).toLocaleString(undefined, {maximumFractionDigits: 2})} MiB`;
  const status = value => { el('upload-status').textContent = value; };
  const settingsReady = fetch('api/uploads/settings', {cache: 'no-store'}).then(async response => {
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || '업로드 설정을 불러오지 못했습니다.');
    settings = value;
    el('upload-limits').textContent = `파일당 최대 ${bytes(value.max_file_bytes)} · 지원 형식: ${value.extensions.join(', ')}`;
  }).catch(error => { el('upload-limits').textContent = error.message; });

  el('upload-use-current').onclick = () => { el('upload-directory').value = el('directory-path').value; };
  el('upload-stop').onclick = () => {
    stopping = true; el('upload-stop').disabled = true;
    status('현재 파일이 완료되면 나머지 업로드를 중지합니다.');
  };
  el('upload-open-folder').onclick = () => {
    el('directory-path').value = savedDirectory;
    el('directory-update').requestSubmit();
  };
  function send(file, directory, index, count) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', 'api/uploads?' + new URLSearchParams({directory, name: file.name, modified: file.lastModified}));
      xhr.setRequestHeader('X-Photo-Browser', '1');
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.upload.onprogress = event => {
        el('upload-progress').value = event.lengthComputable ? event.loaded * 100 / event.total : 0;
        if (!stopping) status(`${index + 1}/${count} · ${file.name} · ${bytes(event.loaded)} / ${bytes(file.size)}${event.loaded === event.total ? ' · 서버 저장 확인 중…' : ''}`);
      };
      xhr.onload = () => {
        let result;
        try { result = JSON.parse(xhr.responseText); }
        catch { reject(new Error(`서버 응답을 확인할 수 없습니다 (HTTP ${xhr.status}). 저장 폴더를 확인하세요.`)); return; }
        if (xhr.status >= 200 && xhr.status < 300) resolve(result);
        else { const error = new Error(result.error || `HTTP ${xhr.status}`); error.status = xhr.status; reject(error); }
      };
      xhr.onerror = () => reject(new Error('연결이 끊겼습니다. 저장 폴더를 확인한 뒤 다시 시도하세요.'));
      xhr.send(file);
    });
  }
  el('upload-form').onsubmit = async event => {
    event.preventDefault();
    if (running) return;
    await settingsReady;
    if (!settings) { status('업로드 설정을 확인하지 못했습니다. 페이지를 새로고침하세요.'); return; }
    const files = [...el('upload-files').files], directory = el('upload-directory').value.trim();
    if (!directory || !files.length || files.length > 100) { status('저장 경로와 업로드할 파일 1~100개를 지정하세요.'); return; }
    const invalid = files.find(file => !file.size || file.size > settings.max_file_bytes || !settings.extensions.includes('.' + file.name.split('.').pop().toLowerCase()));
    if (invalid) { status(`${invalid.name}: 지원 형식과 파일당 용량 한도를 확인하세요. 빈 파일은 업로드할 수 없습니다.`); return; }
    running = true; stopping = false;
    for (const id of ['upload-start', 'upload-files', 'upload-directory', 'upload-use-current']) el(id).disabled = true;
    el('upload-stop').disabled = false; el('upload-open-folder').hidden = true;
    el('upload-progress').hidden = false; el('upload-results').replaceChildren();
    const rows = files.map(file => { const row = document.createElement('li'); row.textContent = `${file.name} · 대기`; el('upload-results').append(row); return row; });
    let success = 0, failed = 0, processed = 0;
    try {
      for (let index = 0; index < files.length && !stopping; index++) {
        el('upload-progress').value = 0;
        const file = files[index]; rows[index].textContent = `${file.name} · 전송 중`;
        status(`${index + 1}/${files.length} · ${file.name} · 업로드 시작…`);
        try {
          const result = await send(file, directory, index, files.length);
          success++; savedDirectory = result.directory;
          el('upload-open-folder').hidden = false;
          rows[index].textContent = `${file.name} · 완료${result.renamed ? ' → ' + result.name : ''} · ${bytes(result.size_bytes)}`;
        } catch (error) {
          failed++; rows[index].textContent = `${file.name} · 실패: ${error.message}`;
          // A storage/auth/network failure also affects following files.
          if (!error.status || [401, 403, 409, 413, 507].includes(error.status)) stopping = true;
        }
        processed++;
      }
      for (let index = processed; index < files.length; index++) rows[index].textContent = `${files[index].name} · 미전송`;
      status(`업로드 ${stopping ? '중지' : '완료'} · 성공 ${success}개 · 실패 ${failed}개 · 미전송 ${files.length - processed}개. 성공한 파일은 서버에 저장되었습니다.`);
    } finally {
      running = false;
      for (const id of ['upload-start', 'upload-files', 'upload-directory', 'upload-use-current']) el(id).disabled = false;
      el('upload-stop').disabled = true;
    }
  };
})();
