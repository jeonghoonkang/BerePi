const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let player, device, mode = null, queue = [], index = -1, pagePath = '', offset = 0;
let busy = false, spotifyStarted = false, lastPosition = 0;
const audio = $('audio');
function status(message) { $('status').textContent = message; }
function action(fn) { return async event => { event?.preventDefault(); try { await fn(); } catch (e) { status(e.message); } }; }
async function api(path, method = 'GET', body) {
  const response = await fetch('/api/' + path, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (response.status === 204) return {};
  const data = await response.json();
  if (!response.ok) throw Error(data.error?.message || data.error || `Spotify ${response.status}`);
  return data;
}
function button(label, handler, parent) { const b = document.createElement('button'); b.textContent = label; b.onclick = action(handler); parent.append(b); return b; }
function trackItem(track) {
  if (!track || track.type !== 'track' || track.is_local || track.is_playable === false || !track.uri) return null;
  return {source:'spotify', uri:track.uri, name:track.name + ' — ' + (track.artists || []).map(a=>a.name).join(', '), link:track.external_urls?.spotify};
}
function add(item) { queue.push(item); renderQueue(); status('큐에 추가: ' + item.name); }
function renderQueue() {
  $('queue').replaceChildren();
  queue.forEach((item, n) => { const li = document.createElement('li');
    button(`${n === index ? '▶ ' : ''}[${item.source === 'spotify' ? 'Spotify' : 'HTTP 파일'}] ${item.name}`, ()=>play(n), li);
    if (item.source === 'spotify' && item.link) { const a=document.createElement('a'); a.href=item.link; a.textContent='Spotify에서 보기'; a.target='_blank'; a.rel='noopener'; li.append(a); }
    $('queue').append(li);
  });
}
async function play(n) {
  if (busy || !queue[n]) return;
  busy = true;
  try {
    const item = queue[n];
    if (item.source === 'spotify' && !device) throw Error('먼저 Spotify 로그인 후 브라우저 플레이어를 연결하세요.');
    // Await pause before switching sources so both cannot play simultaneously.
    if (mode === 'spotify') await player.pause();
    audio.pause();
    spotifyStarted = false; lastPosition = 0; mode = null;
    if (item.source === 'spotify') {
      await player.activateElement();
      await api('me/player/play?device_id=' + encodeURIComponent(device), 'PUT', {uris:[item.uri]});
    } else { audio.src = item.url; await audio.play(); }
    mode = item.source; index = n;
    $('now').textContent = `[${mode === 'spotify' ? 'Spotify' : 'HTTP 파일'}] ${item.name}`;
    renderQueue(); status('재생 중');
  } finally { busy = false; }
}
async function loadPage(reset = false) {
  if (reset) { offset = 0; $('library').replaceChildren(); }
  const data = await api(pagePath + '?limit=20&offset=' + offset);
  for (const entry of data.items || []) {
    if (pagePath === 'me/playlists') {
      if (entry) button('재생목록: ' + entry.name, async()=> {pagePath='playlists/'+entry.id+'/items'; await loadPage(true);}, $('library'));
    } else {
      const item = trackItem(entry?.item || entry?.track);
      if (item) button('[Spotify] + ' + item.name, ()=>add(item), $('library'));
    }
  }
  offset += (data.items || []).length;
  $('more').hidden = !data.next;
}
function httpUrl(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw Error('인증정보를 포함하지 않은 HTTP(S) URL을 입력하세요.');
  if (url.hostname === 'open.spotify.com' || url.hostname.endsWith('.spotify.com')) throw Error('Spotify 음악은 Spotify 목록에서 추가하세요.');
  return url;
}
function fileItem(value) { const url=httpUrl(value); return {source:'http', url:url.href, name:decodeURIComponent(url.pathname.split('/').pop()) || url.hostname}; }
async function directory(value) {
  const url = httpUrl(value);
  status('폴더 읽는 중…');
  const response = await fetch(url.href, {signal:AbortSignal.timeout(20000)});
  if (!response.ok) throw Error('폴더 조회 실패: ' + response.status);
  const base = httpUrl(response.url);
  const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
  $('directory').replaceChildren(); let count = 0;
  const seen = new Set();
  for (const a of doc.querySelectorAll('a[href]')) {
    let target;
    try { target = httpUrl(new URL(a.getAttribute('href'), base).href); } catch { continue; }
    if (target.origin !== base.origin || seen.has(target.href)) continue;
    seen.add(target.href);
    if (target.pathname.endsWith('/')) {
      button('폴더: ' + (a.textContent.trim() || target.pathname), ()=>directory(target.href), $('directory')); count++;
    } else if (/\.(mp3|m4a|aac|wav|ogg|flac)$/i.test(target.pathname)) {
      const item=fileItem(target.href); button('[HTTP 파일] + ' + item.name, ()=>add(item), $('directory')); count++;
    }
  }
  status(count ? '폴더를 불러왔습니다.' : '오디오 링크가 없습니다. 서버의 디렉토리 목록 설정을 확인하세요.');
}
let sdkReadyResolve;
const sdkReady = new Promise(resolve => { sdkReadyResolve=resolve; });
window.onSpotifyWebPlaybackSDKReady = ()=>sdkReadyResolve();
$('connect').onclick = action(async()=> {
  if (player) { if (!device) await player.connect(); return; }
  const auth=await fetch('/token'); if (!auth.ok) throw Error('Spotify 로그인이 필요합니다.');
  if (!window.isSecureContext) throw Error('Spotify 재생은 HTTPS 또는 로컬 127.0.0.1에서 접속하세요.');
  if (!document.querySelector('#sdk')) { const script=document.createElement('script'); script.id='sdk'; script.src='https://sdk.scdn.co/spotify-player.js'; script.onerror=()=>status('Spotify SDK 로드 실패. 네트워크를 확인하세요.'); document.head.append(script); }
  await Promise.race([sdkReady, new Promise((_,reject)=>setTimeout(()=>reject(Error('SDK 연결 시간 초과. 새로고침 후 재시도하세요.')),20000))]);
  player = new Spotify.Player({name:'BerePi Browser', volume:0.5, getOAuthToken: cb => {
    fetch('/token').then(async r=>{if(!r.ok) throw Error('로그인이 만료되었습니다. 다시 로그인하세요.'); return r.json();}).then(d=>cb(d.access_token)).catch(e=>status(e.message));
  }});
  player.addListener('ready', ({device_id})=>{device=device_id; status('브라우저 플레이어 연결 완료. 큐에서 곡을 선택하세요.');});
  player.addListener('not_ready', ()=>{device=null; status('Spotify 장치 연결이 끊겼습니다. 다시 연결하세요.');});
  for (const event of ['initialization_error','authentication_error','account_error','playback_error']) player.addListener(event, e=>status(e.message));
  player.addListener('player_state_changed', state=>{
    if (!state || mode !== 'spotify') return;
    $('spotifyState').textContent = `${state.track_window.current_track.name} · ${state.paused ? '일시정지' : '재생 중'}`;
    if (!state.paused) spotifyStarted=true;
    if (spotifyStarted && state.paused && state.position === 0 && lastPosition > 0) {spotifyStarted=false; action(()=>play(index+1))();}
    lastPosition=state.position;
  });
  if (!await player.connect()) {player=null; throw Error('브라우저 플레이어 연결 실패');}
});
$('likes').onclick=action(async()=>{pagePath='me/tracks'; await loadPage(true);});
$('playlists').onclick=action(async()=>{pagePath='me/playlists'; await loadPage(true);});
$('more').onclick=action(()=>loadPage());
$('fileForm').onsubmit=action(()=>add(fileItem($('fileUrl').value)));
$('directoryForm').onsubmit=action(()=>directory($('directoryUrl').value));
$('previous').onclick=action(()=>play(index-1));
$('next').onclick=action(()=>play(index+1));
$('toggle').onclick=action(async()=>{if(mode==='spotify') await player.togglePlay(); else if(mode==='http') {if(audio.paused) await audio.play(); else audio.pause();} else await play(0);});
$('clear').onclick=action(async()=>{if(mode==='spotify') await player.pause(); audio.pause(); audio.removeAttribute('src'); audio.load(); queue=[];index=-1;mode=null;renderQueue();$('now').textContent='선택된 곡 없음';$('spotifyState').textContent='';});
audio.addEventListener('ended', action(()=>play(index+1)));
audio.addEventListener('error', ()=>status('HTTP 파일 재생 실패: URL, 접근 권한, 코덱 및 HTTPS 혼합 콘텐츠 차단을 확인하세요.'));
$('logout').onclick=action(async()=>{if(player) await player.disconnect();audio.pause();await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}});location.reload();});
action(async()=>{const me=await api('me'); $('profile').textContent='연결됨: '+(me.display_name || me.id);})().catch(()=>{});
