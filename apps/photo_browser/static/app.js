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
  loading = true; $('load-more').disabled = true;
  $('status').textContent = '전체 파일 수와 용량을 집계하고 있습니다…';
  if (!append) { data = null; $('gallery').replaceChildren(); $('folders').replaceChildren(); $('more').hidden = true; $('load-more').hidden = true; }
  try {
    const response = await fetch('api/browse?' + new URLSearchParams({path, recursive: $('recursive').checked ? '1' : '0', offset: append ? data.next_offset : 0}), {signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '폴더를 열지 못했습니다.');
    const previousShown = shown;
    data = append ? {...result, media: data.media.concat(result.media)} : result;
    data.media.sort((a, b) => b.modified - a.modified || a.path.localeCompare(b.path));
    $('path').value = data.path; $('up').disabled = !data.parent;
    $('folders').replaceChildren();
    for (const folder of data.directories) $('folders').append(button('📁 ' + folder.name, () => prepareScan(folder.path)));
    render(append ? previousShown + 100 : 100);
  } catch (error) { if (error.name !== 'AbortError') { if (!append) { data = null; $('up').disabled = true; } $('status').textContent = error.message; } }
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
