const $ = id => document.getElementById(id);
let data = null, filtered = [], shown = 0, selected = 0, controller;
const mediaURL = path => 'media?path=' + encodeURIComponent(path);
function button(text, action) { const el = document.createElement('button'); el.textContent = text; el.onclick = action; return el; }
function prepareScan(path) {
  if (controller) controller.abort();
  $('path').value = path;
  data = null; filtered = []; shown = 0;
  $('gallery').replaceChildren(); $('folders').replaceChildren();
  $('more').hidden = true; $('up').disabled = true;
  $('status').textContent = '경로와 하위 폴더 포함 여부를 선택한 후 스캔 시작을 누르세요.';
}
async function browse(path) {
  if (controller) controller.abort();
  controller = new AbortController();
  $('status').textContent = '폴더를 읽고 있습니다…';
  $('gallery').replaceChildren(); $('folders').replaceChildren(); $('more').hidden = true;
  try {
    const response = await fetch('api/browse?' + new URLSearchParams({path, recursive: $('recursive').checked ? '1' : '0'}), {signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '폴더를 열지 못했습니다.');
    data = result; $('path').value = data.path; $('up').disabled = !data.parent;
    for (const folder of data.directories) $('folders').append(button('📁 ' + folder.name, () => prepareScan(folder.path)));
    render();
  } catch (error) { if (error.name !== 'AbortError') { data = null; $('up').disabled = true; $('status').textContent = error.message; } }
}
function render() {
  if (!data) return;
  filtered = data.media.filter(item => (!$('date').value || item.date === $('date').value) && ($('type').value === 'all' || item.video === ($('type').value === 'video')));
  shown = 0; $('gallery').replaceChildren(); appendPage();
  $('status').textContent = `${filtered.length.toLocaleString()}개 미디어 · ${data.directories.length}개 폴더 · 파일 수정일 기준` + (data.skipped ? ` · 읽지 못한 항목 ${data.skipped}개` : '') + (data.truncated ? ` · ${data.limit.toLocaleString()}개까지만 검색했습니다. 더 작은 폴더를 선택하세요.` : '') + (!filtered.length ? ' · 표시할 미디어가 없습니다.' : '');
}
function appendPage() {
  const end = Math.min(shown + 100, filtered.length);
  for (let i = shown; i < end; i++) {
    const item = filtered[i];
    if (i === 0 || item.date !== filtered[i - 1].date) { const heading = document.createElement('h2'); heading.textContent = item.date; $('gallery').append(heading); }
    const card = button('', () => openViewer(i)); card.className = 'card';
    if (item.video) { const placeholder = document.createElement('div'); placeholder.className = 'video-placeholder'; placeholder.textContent = '▶ MP4'; card.append(placeholder); }
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
$('close').onclick = () => $('viewer').close();
$('viewer').addEventListener('close', () => $('preview').replaceChildren());
$('previous').onclick = () => openViewer(selected - 1); $('next').onclick = () => openViewer(selected + 1);
$('viewer').addEventListener('keydown', event => { if (event.key === 'ArrowLeft') openViewer(selected - 1); if (event.key === 'ArrowRight') openViewer(selected + 1); });
// Only submitting the scan form starts a directory scan.
