const $ = id => document.getElementById(id);
let data = null, filtered = [], shown = 0, selected = 0, controller, loading = false;
const mediaURL = path => 'media?path=' + encodeURIComponent(path);
function button(text, action) { const el = document.createElement('button'); el.textContent = text; el.onclick = action; return el; }
function prepareScan(path) {
  if (controller) controller.abort();
  $('path').value = path;
  data = null; filtered = []; shown = 0;
  $('gallery').replaceChildren(); $('folders').replaceChildren();
  $('more').hidden = true; $('load-more').hidden = true; $('up').disabled = true;
  $('status').textContent = '경로와 하위 폴더 포함 여부를 선택한 후 스캔 시작을 누르세요.';
}
async function browse(path, append = false) {
  if (controller) controller.abort();
  controller = new AbortController();
  const activeController = controller;
  const recursive = $('recursive').checked;
  loading = true; $('load-more').disabled = true;
  $('status').textContent = '전체 파일 수와 용량을 집계하고 있습니다…';
  $('directory-update-status').textContent = '폴더를 불러오는 중…';
  if (!append) { data = null; $('gallery').replaceChildren(); $('folders').replaceChildren(); $('more').hidden = true; $('load-more').hidden = true; }
  try {
    const response = await fetch('api/browse?' + new URLSearchParams({path, recursive: recursive ? '1' : '0', offset: append ? data.next_offset : 0}), {signal: controller.signal});
    const result = await response.json();
    if (controller !== activeController) return;
    if (!response.ok) throw new Error(result.error || '폴더를 열지 못했습니다.');
    const previousShown = shown;
    data = append ? {...result, media: data.media.concat(result.media)} : result;
    data.media.sort((a, b) => b.modified - a.modified || a.path.localeCompare(b.path));
    $('path').value = data.path; $('up').disabled = !data.parent;
    $('directory-path').value = data.path;
    $('directory-update-status').textContent = `현재 표시 경로: ${data.path}`;
    $('folders').replaceChildren();
    for (const folder of data.directories) $('folders').append(button('📁 ' + folder.name, () => prepareScan(folder.path)));
    render(append ? previousShown + 100 : 100);
    if (!append) {
      try {
        const saved = await fetch('api/directory-history', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Photo-Browser': '1'}, body: JSON.stringify({path: result.path, recursive})});
        const history = await saved.json();
        if (!saved.ok) throw new Error(history.error || '히스토리를 저장하지 못했습니다.');
        await loadDirectoryHistory(history.item.id);
      } catch (error) { $('directory-history-status').textContent = `사진 조회는 완료했지만 히스토리 저장·갱신에 실패했습니다: ${error.message}`; }
    }
  } catch (error) { if (error.name !== 'AbortError' && controller === activeController) { if (!append) { data = null; $('up').disabled = true; } $('status').textContent = error.message; $('directory-update-status').textContent = error.message; } }
  finally { if (controller === activeController) { loading = false; $('load-more').disabled = false; } }
}
function formatBytes(bytes) {
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let value = bytes, index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
  return `${value.toLocaleString(undefined, {maximumFractionDigits: 2})} ${units[index]}`;
}
function render(target = 100) {
  if (!data) return;
  filtered = data.media.filter(item => (!$('date').value || item.date === $('date').value) && ($('type').value === 'all' || item.video === ($('type').value === 'video')));
  shown = 0; $('gallery').replaceChildren();
  const desired = typeof target === 'number' ? target : 100;
  do { appendPage(); } while (shown < Math.min(desired, filtered.length));
  $('load-more').hidden = !data.truncated;
  $('load-more').textContent = `다음 ${Math.min(data.limit, data.total - data.next_offset).toLocaleString()}개 불러오기`;
  $('status').textContent = `전체 ${data.total.toLocaleString()}개 · 총 용량 ${formatBytes(data.total_bytes)} (${data.total_bytes.toLocaleString()}바이트) · 불러옴 ${data.media.length.toLocaleString()}개 · 필터 결과 ${filtered.length.toLocaleString()}개 · 파일 수정일 기준` + (data.skipped ? ` · 읽지 못한 항목 ${data.skipped}개: 전체 집계에서 제외` : '') + (data.truncated ? ` · 남은 ${Math.max(0, data.total - data.next_offset).toLocaleString()}개는 다음 파일 불러오기로 조회하세요.` : ' · 전체 불러오기 완료');
}
function appendPage() {
  const end = Math.min(shown + 100, filtered.length);
  for (let i = shown; i < end; i++) {
    const item = filtered[i];
    if (i === 0 || item.date !== filtered[i - 1].date) { const heading = document.createElement('h2'); heading.textContent = item.date; $('gallery').append(heading); }
    const card = button('', () => openViewer(i)); card.className = 'card';
    if (item.video) { const placeholder = document.createElement('div'); placeholder.className = 'video-placeholder'; placeholder.textContent = '▶ 동영상'; card.append(placeholder); }
    else { const image = document.createElement('img'); image.src = mediaURL(item.path); image.alt = item.name; image.loading = 'lazy'; card.append(image); }
    const caption = document.createElement('span'); caption.textContent = item.name; card.title = item.path; card.append(caption); $('gallery').append(card);
  }
  shown = end; $('more').hidden = shown >= filtered.length;
}
function openViewer(index) {
  selected = (index + filtered.length) % filtered.length;
  const item = filtered[selected]; $('preview').replaceChildren();
  const element = document.createElement(item.video ? 'video' : 'img'); element.src = mediaURL(item.path);
  if (item.video) { element.controls = true; element.autoplay = true; } else element.alt = item.name;
  $('preview').append(element); $('title').textContent = item.name; $('original').href = mediaURL(item.path);
  if (!$('viewer').open) $('viewer').showModal();
}
$('location').onsubmit = event => { event.preventDefault(); browse($('path').value); };
$('directory-update').onsubmit = event => {
  event.preventDefault();
  const path = $('directory-path').value.trim();
  if (!path) { $('directory-update-status').textContent = '디렉토리 경로를 입력하세요.'; return; }
  $('path').value = path;
  $('date').value = ''; $('type').value = 'all';
  document.querySelector('[data-tab="folder-panel"]').click();
  browse(path);
};
let directoryHistory = [];
async function loadDirectoryHistory(selectedId = '') {
  try {
    const response = await fetch('api/directory-history', {cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '히스토리를 불러오지 못했습니다.');
    directoryHistory = result.items;
    $('directory-history').replaceChildren(new Option('이전 경로 선택', ''));
    for (const item of directoryHistory) {
      const date = new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'medium'}).format(new Date(item.recorded_at));
      $('directory-history').add(new Option(`${date} · ${item.path}${item.recursive ? ' · 하위 폴더 포함' : ''}`, item.id));
    }
    $('directory-history').value = selectedId;
    $('directory-history-status').textContent = `${result.total.toLocaleString()} / ${result.limit.toLocaleString()}개 저장 · 한국 표준시(KST)` + (result.invalid_lines ? ` · 읽지 못한 기록 ${result.invalid_lines}개` : '');
  } catch (error) { $('directory-history-status').textContent = error.message; }
}
$('directory-history-apply').onclick = () => {
  const item = directoryHistory.find(entry => entry.id === $('directory-history').value);
  if (!item) { $('directory-history-status').textContent = '적용할 경로를 선택하세요.'; return; }
  $('directory-path').value = item.path;
  $('recursive').checked = item.recursive;
  $('directory-update').requestSubmit();
};
$('directory-history-refresh').onclick = () => loadDirectoryHistory();
loadDirectoryHistory();
$('up').onclick = () => { if (data?.parent) prepareScan(data.parent); };
$('recursive').onchange = () => prepareScan($('path').value);
$('path').oninput = () => prepareScan($('path').value);
$('date').onchange = $('type').onchange = render;
$('reset').onclick = () => { $('date').value = ''; $('type').value = 'all'; render(); };
$('more').onclick = appendPage;
$('load-more').onclick = () => { if (data?.truncated && !loading) browse(data.path, true); };
$('close').onclick = () => $('viewer').close();
$('viewer').addEventListener('close', () => $('preview').replaceChildren());
$('previous').onclick = () => openViewer(selected - 1); $('next').onclick = () => openViewer(selected + 1);
$('viewer').addEventListener('keydown', event => { if (event.key === 'ArrowLeft') openViewer(selected - 1); if (event.key === 'ArrowRight') openViewer(selected + 1); });
// Only submitting the scan form starts a directory scan.
