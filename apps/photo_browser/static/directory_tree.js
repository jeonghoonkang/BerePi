/* Load only expanded directories; names and paths are always text nodes. */
(() => {
  const el = id => document.getElementById(id);
  let roots, selection, nextOffset = null, generation = 0, navigating = false;
  async function api(path) {
    const response = await fetch(path, {cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function query(root, path, extra = {}) {
    return new URLSearchParams({scope: root.scope, source_id: root.source_id || '', path, ...extra});
  }
  function mediaURL(root, path, download = false) {
    return 'api/directory-tree/media?' + query(root, path, download ? {download: '1'} : {});
  }
  function show(item, root) {
    const media = document.createElement(item.video ? 'video' : 'img');
    media.src = mediaURL(root, item.path);
    if (item.video) media.controls = true; else media.alt = item.name;
    el('tree-viewer-title').textContent = item.path;
    el('tree-viewer-media').replaceChildren(media);
    el('tree-viewer-download').href = mediaURL(root, item.path, true);
    el('tree-viewer').showModal();
  }
  async function files(root, path, append = false) {
    const token = ++generation;
    selection = {root, path};
    el('tree-selected-path').textContent = path;
    el('tree-media-status').textContent = '사진·동영상을 불러오고 있습니다…';
    el('tree-more-files').disabled = true;
    if (!append) {
      el('tree-gallery').replaceChildren(); nextOffset = null; el('tree-more-files').hidden = true;
    }
    try {
      const result = await api('api/directory-tree?' + query(root, path, {kind: 'media', offset: append ? nextOffset : 0}));
      if (token !== generation) return;
      for (const item of result.items) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'card';
        if (item.video) {
          const label = document.createElement('div'); label.className = 'video-placeholder'; label.textContent = '▶ 동영상'; button.append(label);
        } else {
          const image = document.createElement('img'); image.src = mediaURL(root, item.path);
          image.alt = item.name; image.loading = 'lazy'; button.append(image);
        }
        const name = document.createElement('span'); name.textContent = item.name; button.append(name);
        button.onclick = () => show(item, root); el('tree-gallery').append(button);
      }
      nextOffset = result.next_offset;
      el('tree-more-files').hidden = nextOffset === null;
      el('tree-media-status').textContent = `이 폴더의 사진·동영상 ${result.total.toLocaleString()}개` +
        (result.skipped ? ` · 읽기 실패 ${result.skipped}개` : '');
    } catch (error) {
      if (token === generation) el('tree-media-status').textContent = error.message;
    } finally { if (token === generation) el('tree-more-files').disabled = false; }
  }
  function directory(root, name, path) {
    const row = document.createElement('li'), details = document.createElement('details');
    const summary = document.createElement('summary'); summary.textContent = '📁 ' + name;
    summary.title = path;
    const children = document.createElement('ul');
    details.append(summary, children); row.append(details);
    let loaded = false, loading = false;
    summary.addEventListener('click', () => files(root, path));
    async function load(offset = 0, more) {
      if (loading) return;
      loading = true;
      const message = document.createElement('li'); message.textContent = '하위 폴더 확인 중…'; children.append(message);
      try {
        const result = await api('api/directory-tree?' + query(root, path, {offset}));
        if (more) more.remove();
        for (const child of result.items) children.append(directory(root, child.name, child.path));
        if (result.next_offset !== null) {
          const entry = document.createElement('li'), button = document.createElement('button');
          button.type = 'button'; button.textContent = '하위 폴더 100개 더 보기';
          button.onclick = () => load(result.next_offset, entry); entry.append(button); children.append(entry);
        } else if (!children.querySelector('details')) {
          const empty = document.createElement('li'); empty.textContent = '하위 폴더 없음'; children.append(empty);
        }
        loaded = true;
      } catch (error) {
        const failed = document.createElement('li'); failed.textContent = error.message; children.append(failed);
      } finally { message.remove(); loading = false; }
    }
    details.addEventListener('toggle', () => { if (details.open && !loaded) load(); });
    return row;
  }
  async function refresh() {
    generation++; selection = null; nextOffset = null;
    el('tree-gallery').replaceChildren(); el('tree-more-files').hidden = true;
    el('tree-selected-path').textContent = '왼쪽 트리에서 폴더를 선택하세요.';
    el('tree-media-status').textContent = '';
    el('directory-tree-roots').replaceChildren();
    try {
      roots = await api('api/directory-tree/roots');
      const selected = el('tree-scope').value === 'source' ? roots.sources : roots.managed;
      for (const root of selected) el('directory-tree-roots').append(directory(root, root.name, root.path));
      if (!selected.length) el('tree-media-status').textContent = '등록된 로컬 소스가 없습니다. 소스·스캔·병합에서 등록하세요.';
    } catch (error) { el('tree-media-status').textContent = error.message; }
  }
  el('tree-more-files').onclick = () => { if (selection && nextOffset !== null) return files(selection.root, selection.path, true); };
  el('tree-scope').onchange = refresh;
  el('tree-refresh').onclick = refresh;
  el('tree-viewer-close').onclick = () => el('tree-viewer').close();
  el('tree-viewer').onclose = () => el('tree-viewer-media').replaceChildren();
  window.photoBrowserOpenDirectory = async ({scope = 'source', source_id, path}) => {
    navigating = true;
    try {
      document.querySelector('[data-tab="directory-tree-panel"]').click();
      el('tree-scope').value = scope;
      await refresh();
      const root = scope === 'managed' ? roots.managed[0] : roots.sources.find(root => root.source_id === source_id);
      if (!root) throw new Error('트리에서 찾을 수 없는 소스입니다. 소스 등록을 확인하세요.');
      await files(root, path);
      el('directory-tree-panel').scrollIntoView({block: 'start'});
    } finally { navigating = false; }
  };
  new MutationObserver(() => { if (!navigating && !el('directory-tree-panel').hidden) refresh(); })
    .observe(el('directory-tree-panel'), {attributes: true, attributeFilter: ['hidden']});
})();
