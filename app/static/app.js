const state = { type: 'itv', category: '*', items: [], hls: null, configured: false };
const $ = (id) => document.getElementById(id);
const sectionTitles = { itv: 'Live-TV', vod: 'Filme', series: 'Serien' };

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

function showMessage(text = '') {
  $('message').hidden = !text;
  $('message').textContent = text;
}

function normalizeArray(value) {
  if (Array.isArray(value)) return value.flatMap((entry) => Array.isArray(entry) ? entry : [entry]);
  if (value && Array.isArray(value.data)) return normalizeArray(value.data);
  if (value && Array.isArray(value.js)) return normalizeArray(value.js);
  if (value && typeof value.data === 'object' && value.data) return normalizeArray(Object.values(value.data));
  if (value && typeof value.js === 'object' && value.js) return normalizeArray(Object.values(value.js));
  if (value && typeof value === 'object') return Object.values(value).flatMap((entry) => Array.isArray(entry) ? entry : [entry]).filter((entry) => entry && typeof entry === 'object');
  return [];
}

function titleOf(item) { return item.name || item.title || item.o_name || item.ch_name || item.episode_name || 'Ohne Titel'; }
function imageOf(item) { return item.logo || item.screenshot_uri || item.cover || item.poster || ''; }
function commandOf(item) {
  return item.cmd || item.command || item.stream_url || item.video_url || item.file || item.path || item.url || '';
}
function cleanId(value) { return String(value || '').split(':', 1)[0].trim(); }

async function loadConfig(openWhenMissing = false) {
  const config = await api('/api/config');
  state.configured = config.configured;
  $('portalUrl').value = config.portal_url || '';
  $('portalMac').value = config.portal_mac || '';
  if (!config.configured && openWhenMissing) $('settingsDialog').showModal();
  return config.configured;
}

async function loadStatus() {
  if (!state.configured) {
    $('status').textContent = 'Zugangsdaten fehlen';
    $('status').className = 'status-badge error';
    return;
  }
  try {
    await api('/api/status');
    $('status').textContent = 'Portal verbunden';
    $('status').className = 'status-badge ok';
  } catch (error) {
    $('status').textContent = `Nicht verbunden: ${error.message}`;
    $('status').className = 'status-badge error';
  }
}

async function loadCategories() {
  if (!state.configured) return;
  $('categories').innerHTML = '<span class="muted">Lade …</span>';
  try {
    const values = normalizeArray(await api(`/api/categories/${state.type}`));
    const all = [{ id: '*', title: 'Alle' }, ...values];
    $('categories').innerHTML = '';
    for (const category of all) {
      const id = String(category.id ?? category.genre_id ?? category.category_id ?? category.tv_genre_id ?? '*');
      const button = document.createElement('button');
      button.textContent = category.title || category.name || category.genre_name || `Kategorie ${id}`;
      button.className = id === state.category ? 'active' : '';
      button.onclick = async () => { state.category = id; await loadCategories(); await loadContent(); };
      $('categories').append(button);
    }
  } catch (error) {
    $('categories').innerHTML = `<span class="error">${error.message}</span>`;
  }
}

function createCard(item) {
  const card = document.createElement('article');
  card.className = 'card';
  const image = imageOf(item);
  const imageNode = image ? `<img src="${image}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<div class="placeholder">▶</div>';
  const description = item.description || item.plot || item.descr || item.year || '';
  card.innerHTML = `${imageNode}<div class="card-body"><h3></h3><p></p></div>`;
  card.querySelector('h3').textContent = titleOf(item);
  card.querySelector('p').textContent = String(description).slice(0, 180);
  card.onclick = () => state.type === 'series' ? openSeries(item) : playItem(item);
  return card;
}

async function loadContent() {
  if (!state.configured) {
    showMessage('Bitte zuerst Portal-URL und MAC-Adresse eintragen.');
    return;
  }
  showMessage('Lade Inhalte …');
  $('items').innerHTML = '';
  const search = encodeURIComponent($('search').value.trim());
  try {
    const values = normalizeArray(await api(`/api/content/${state.type}?category=${encodeURIComponent(state.category)}&search=${search}`));
    state.items = values;
    showMessage(values.length ? '' : 'Keine Inhalte gefunden.');
    for (const item of values) $('items').append(createCard(item));
  } catch (error) { showMessage(error.message); }
}

async function playItem(item, series = null) {
  const cmd = commandOf(item);
  if (!cmd) return showMessage('Für diesen Eintrag wurde kein Wiedergabebefehl geliefert.');
  showMessage('Stream wird vorbereitet …');
  try {
    const result = await api('/api/play', {
      method: 'POST',
      body: JSON.stringify({ type: state.type, cmd, series, item })
    });
    $('playerTitle').textContent = titleOf(item);
    $('playerMeta').textContent = item.description || item.plot || 'Stream wird geladen …';
    $('playerDialog').showModal();
    attachPlayer(result.url, result.stream_type || 'hls');
    showMessage('');
    if (state.type === 'itv') loadEpg(item);
  } catch (error) {
    showMessage(error.message);
    $('playerMeta').textContent = error.message;
  }
}

function destroyPlayer() {
  const video = $('player');
  if (state.hls) { state.hls.destroy(); state.hls = null; }
  video.pause();
  video.removeAttribute('src');
  video.onerror = null;
  video.onplaying = null;
  video.load();
}

function attachPlayer(url, streamType = 'hls') {
  const video = $('player');
  destroyPlayer();
  const absoluteUrl = new URL(url, window.location.href).href;

  video.onerror = () => {
    const mediaError = video.error;
    $('playerMeta').textContent = mediaError ? `Playerfehler ${mediaError.code}: ${mediaError.message || 'Wiedergabe nicht möglich'}` : 'Playerfehler: Wiedergabe nicht möglich';
  };
  video.onplaying = () => {
    if ($('playerMeta').textContent === 'Stream wird geladen …') $('playerMeta').textContent = '';
  };

  if (streamType === 'hls' && window.Hls && Hls.isSupported()) {
    state.hls = new Hls({
      enableWorker: true,
      lowLatencyMode: false,
      liveSyncDurationCount: 3,
      maxBufferLength: 30,
      manifestLoadingTimeOut: 25000,
      levelLoadingTimeOut: 25000,
      fragLoadingTimeOut: 30000
    });
    state.hls.loadSource(absoluteUrl);
    state.hls.attachMedia(video);
    state.hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch((error) => { $('playerMeta').textContent = `Playerfehler: ${error.message}`; }));
    state.hls.on(Hls.Events.ERROR, (_, data) => {
      if (!data.fatal) return;
      $('playerMeta').textContent = `Playerfehler: ${data.details}`;
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) state.hls.startLoad();
      else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) state.hls.recoverMediaError();
      else destroyPlayer();
    });
    return;
  }

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = absoluteUrl;
    video.load();
    video.play().catch((error) => { $('playerMeta').textContent = `Playerfehler: ${error.message}`; });
    return;
  }

  $('playerMeta').textContent = 'HLS-Wiedergabe wird von diesem Browser nicht unterstützt.';
}

async function loadEpg(item) {
  const id = item.id || item.ch_id;
  $('epg').textContent = '';
  if (!id) return;
  try {
    const values = normalizeArray(await api(`/api/epg?channel_id=${encodeURIComponent(id)}&period=8`));
    for (const entry of values) {
      const row = document.createElement('div');
      const start = entry.time || entry.start_timestamp || entry.start || '';
      row.innerHTML = '<strong></strong><span></span>';
      row.querySelector('strong').textContent = `${start} ${entry.name || entry.title || ''}`.trim();
      row.querySelector('span').textContent = entry.descr || entry.description || '';
      $('epg').append(row);
    }
  } catch (_) {}
}

async function openSeries(item) {
  const id = cleanId(item.movie_id || item.series_id || item.id);
  if (!id) return showMessage('Keine Serien-ID vorhanden.');
  $('seriesTitle').textContent = titleOf(item);
  $('episodes').innerHTML = '<span class="muted">Lade Episoden …</span>';
  $('seriesDialog').showModal();
  try {
    const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(id)}`));
    $('episodes').innerHTML = '';
    for (const episode of values) {
      const button = document.createElement('button');
      const season = episode.season || episode.season_number || episode.season_id || '';
      const number = episode.episode || episode.episode_number || episode.series_number || '';
      const prefix = [season ? `S${season}` : '', number ? `E${number}` : ''].filter(Boolean).join(' ');
      button.textContent = `${prefix}${prefix ? ' – ' : ''}${titleOf(episode)}`;
      button.onclick = () => {
        $('seriesDialog').close();
        const seriesValue = episode.series || episode.series_number || episode.episode_id || null;
        playItem(episode, seriesValue);
      };
      $('episodes').append(button);
    }
    if (!values.length) $('episodes').textContent = 'Keine Episoden gefunden.';
  } catch (error) { $('episodes').textContent = error.message; }
}

$('settingsForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('settingsError').textContent = '';
  try {
    await api('/api/config', {
      method: 'PUT',
      body: JSON.stringify({ portal_url: $('portalUrl').value, portal_mac: $('portalMac').value })
    });
    state.configured = true;
    $('settingsDialog').close();
    await loadStatus();
    await loadCategories();
    await loadContent();
  } catch (error) { $('settingsError').textContent = error.message; }
});

for (const button of document.querySelectorAll('#tabs button')) {
  button.onclick = async () => {
    state.type = button.dataset.type;
    state.category = '*';
    $('sectionTitle').textContent = sectionTitles[state.type];
    showMessage('');
    document.querySelectorAll('#tabs button').forEach((node) => node.classList.toggle('active', node === button));
    await loadCategories();
    await loadContent();
  };
}

let searchTimer;
$('search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadContent, 350); });
$('openSettings').onclick = () => $('settingsDialog').showModal();
$('heroSettings').onclick = () => $('settingsDialog').showModal();
$('closeSettings').onclick = () => $('settingsDialog').close();
$('closePlayer').onclick = () => $('playerDialog').close();
$('closeSeries').onclick = () => $('seriesDialog').close();
$('playerDialog').addEventListener('close', destroyPlayer);

(async () => {
  await loadConfig(true);
  await loadStatus();
  await loadCategories();
  await loadContent();
})();
