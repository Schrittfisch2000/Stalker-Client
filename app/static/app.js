const state = { type: 'itv', category: '*', items: [], hls: null, configured: false, contentController: null, liveRefreshTimer: null, liveSwitching: false, playerGeneration: 0 };
const $ = (id) => document.getElementById(id);
const sectionTitles = { itv: 'Live-TV', vod: 'Filme', series: 'Serien' };
const LIVE_REFRESH_MS = 70000;

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Verbindung zum Client unterbrochen. Bitte erneut versuchen.');
  }
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
function commandOf(item) { return item.cmd || item.command || item.stream_url || item.video_url || item.file || item.path || item.url || ''; }
function cleanId(value) { return String(value || '').split(':', 1)[0].trim(); }
function validCommand(value) { return Boolean(value && !['', '.', 'null', 'none'].includes(String(value).trim().toLowerCase())); }
function seasonOf(item) {
  const explicit = cleanId(item.season_id || item.season || item.season_number);
  if (explicit) return explicit;
  const match = titleOf(item).match(/(?:season|staffel)\s*(\d+)/i);
  return match ? match[1] : '';
}
function looksLikeSeason(item) {
  const title = titleOf(item).toLowerCase();
  return !validCommand(commandOf(item)) || /^season\s*\d+/.test(title) || /^staffel\s*\d+/.test(title) || item.is_season === 1 || item.is_season === '1';
}

async function loadConfig(openWhenMissing = false) {
  const config = await api('/api/config');
  state.configured = config.configured;
  $('portalUrl').value = config.portal_url || '';
  $('portalMac').value = config.portal_mac || '';
  if (!config.configured && openWhenMissing) $('settingsDialog').showModal();
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
    const seen = new Set();
    $('categories').innerHTML = '';
    for (const category of all) {
      const id = String(category.id ?? category.genre_id ?? category.category_id ?? category.tv_genre_id ?? '*');
      if (seen.has(id)) continue;
      seen.add(id);
      const button = document.createElement('button');
      button.textContent = category.title || category.name || category.genre_name || category.category_name || `Kategorie ${id}`;
      button.className = id === state.category ? 'active' : '';
      button.onclick = async () => {
        state.category = id;
        document.querySelectorAll('#categories button').forEach((node) => node.classList.toggle('active', node === button));
        await loadContent();
      };
      $('categories').append(button);
    }
  } catch (error) {
    $('categories').replaceChildren();
    const message = document.createElement('span');
    message.className = 'error';
    message.textContent = error.message;
    $('categories').append(message);
  }
}

function createCard(item) {
  const card = document.createElement('article');
  card.className = 'card';

  const image = item.image_proxy || item.image || imageOf(item);
  if (image) {
    const imageElement = document.createElement('img');
    imageElement.src = image;
    imageElement.alt = '';
    imageElement.loading = 'lazy';
    imageElement.referrerPolicy = 'no-referrer';
    card.append(imageElement);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'placeholder';
    placeholder.textContent = '▶';
    card.append(placeholder);
  }

  const body = document.createElement('div');
  body.className = 'card-body';
  const title = document.createElement('h3');
  title.textContent = titleOf(item);
  const description = document.createElement('p');
  description.textContent = String(item.description || item.plot || item.descr || item.year || '').slice(0, 180);
  body.append(title, description);
  card.append(body);
  card.onclick = () => state.type === 'series' ? openSeries(item) : playItem(item);
  return card;
}

async function loadContent() {
  if (!state.configured) return showMessage('Bitte zuerst Portal-URL und MAC-Adresse eintragen.');
  if (state.contentController) state.contentController.abort();
  const controller = new AbortController();
  state.contentController = controller;
  showMessage('Lade Inhalte …');
  $('items').innerHTML = '';
  const search = encodeURIComponent($('search').value.trim());
  try {
    const values = normalizeArray(await api(`/api/content/${state.type}?category=${encodeURIComponent(state.category)}&search=${search}`, { signal: controller.signal }));
    if (state.contentController !== controller) return;
    state.items = values;
    showMessage(values.length ? '' : 'Keine Inhalte gefunden.');
    for (const item of values) $('items').append(createCard(item));
  } catch (error) {
    if (error.name !== 'AbortError') showMessage(error.message);
  } finally {
    if (state.contentController === controller) state.contentController = null;
  }
}

function renderMediaInfo(item, mediaType) {
  const container = $('epg');
  container.textContent = '';
  if (mediaType === 'itv') return;

  const fields = [
    ['Beschreibung', item.description || item.plot || item.descr],
    ['Jahr', item.year],
    ['Genre', item.genre || item.genres || item.category_name],
    ['Laufzeit', item.time || item.duration || item.length],
    ['Regie', item.director],
    ['Besetzung', item.actors || item.cast],
    ['Bewertung', item.rating || item.rating_imdb || item.imdb_rating],
  ].filter(([, value]) => value !== undefined && value !== null && String(value).trim());

  if (!fields.length) {
    const row = document.createElement('div');
    row.innerHTML = '<strong>Information</strong><span>Für diesen Titel wurden keine weiteren Angaben geliefert.</span>';
    container.append(row);
    return;
  }

  for (const [label, value] of fields) {
    const row = document.createElement('div');
    row.innerHTML = '<strong></strong><span></span>';
    row.querySelector('strong').textContent = label;
    row.querySelector('span').textContent = String(value);
    container.append(row);
  }
}

async function playItem(item, series = null) {
  const mediaType = state.type;
  const cmd = commandOf(item);
  if (!validCommand(cmd)) return showMessage('Dieser Eintrag ist keine abspielbare Episode.');
  showMessage('Stream wird vorbereitet …');
  $('epg').textContent = '';
  try {
    const result = await api('/api/play', { method: 'POST', body: JSON.stringify({ type: mediaType, cmd, series, item }) });
    $('playerTitle').textContent = titleOf(item);
    $('playerMeta').textContent = item.description || item.plot || 'Stream wird geladen …';
    $('playerDialog').showModal();
    attachPlayer(result.url, mediaType === 'itv');
    showMessage('');
    if (mediaType === 'itv') loadEpg(item);
    else renderMediaInfo(item, mediaType);
  } catch (error) {
    showMessage(error.message);
    $('playerMeta').textContent = error.message;
  }
}

function clearLiveRefresh() {
  if (state.liveRefreshTimer) clearTimeout(state.liveRefreshTimer);
  state.liveRefreshTimer = null;
  state.liveSwitching = false;
}

function ticketFromSource(source) {
  try {
    const url = new URL(source, window.location.href);
    const match = url.pathname.match(/^\/hls\/([^/]+)\/index\.m3u8$/);
    return match ? match[1] : '';
  } catch (_) {
    return '';
  }
}

function hlsOptions() {
  return {
    enableWorker: true,
    lowLatencyMode: false,
    liveSyncDurationCount: 3,
    maxBufferLength: 30,
    backBufferLength: 10,
    manifestLoadingTimeOut: 30000,
    fragLoadingTimeOut: 30000
  };
}

function scheduleLiveRefresh(source, generation) {
  if (!ticketFromSource(source) || generation !== state.playerGeneration) return;
  if (state.liveRefreshTimer) clearTimeout(state.liveRefreshTimer);
  state.liveRefreshTimer = setTimeout(() => refreshHlsJsSession(source, generation), LIVE_REFRESH_MS);
}

function configureHlsInstance(instance, source, generation, isLive, switching = false) {
  const video = $('player');
  instance.loadSource(source);
  instance.attachMedia(video);
  instance.on(Hls.Events.MANIFEST_PARSED, () => {
    if (generation !== state.playerGeneration || instance !== state.hls) return;
    video.play().catch((error) => { $('playerMeta').textContent = `Playerfehler: ${error.message}`; });
    if (switching) $('playerMeta').textContent = '';
    if (isLive) scheduleLiveRefresh(source, generation);
  });
  instance.on(Hls.Events.ERROR, (_, data) => {
    if (generation !== state.playerGeneration || instance !== state.hls || !data.fatal) return;
    $('playerMeta').textContent = `Playerfehler: ${data.details}`;
    if (data.type === Hls.ErrorTypes.NETWORK_ERROR) instance.startLoad();
    else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) instance.recoverMediaError();
    else destroyPlayer();
  });
}

async function refreshHlsJsSession(source, generation) {
  if (state.liveSwitching || generation !== state.playerGeneration || !state.hls) return;
  const ticket = ticketFromSource(source);
  if (!ticket) return;

  state.liveSwitching = true;
  state.liveRefreshTimer = null;
  const oldHls = state.hls;
  const video = $('player');
  const wasMuted = video.muted;
  const volume = video.volume;
  $('playerMeta').textContent = 'Nächste Live-Session wird vorbereitet …';

  try {
    const payload = await api(`/api/live-refresh/${encodeURIComponent(ticket)}`, { method: 'POST' });
    if (generation !== state.playerGeneration || oldHls !== state.hls || !payload.url) return;

    const freshSource = new URL(`${payload.url}?_handover=${Date.now()}`, window.location.href).href;
    const freshHls = new Hls(hlsOptions());

    oldHls.stopLoad();
    oldHls.detachMedia();
    oldHls.destroy();
    state.hls = freshHls;
    video.muted = wasMuted;
    video.volume = volume;
    $('playerMeta').textContent = 'Live-Session wird nahtlos gewechselt …';
    configureHlsInstance(freshHls, freshSource, generation, true, true);
  } catch (error) {
    console.warn('Vorgewärmte Live-Session konnte nicht übernommen werden:', error);
    if (generation === state.playerGeneration && oldHls === state.hls) {
      $('playerMeta').textContent = 'Vorbereitung der nächsten Live-Session fehlgeschlagen; aktueller Stream läuft weiter.';
      scheduleLiveRefresh(source, generation);
    }
  } finally {
    state.liveSwitching = false;
  }
}

function destroyPlayer() {
  const video = $('player');
  state.playerGeneration += 1;
  clearLiveRefresh();
  if (state.hls) { state.hls.destroy(); state.hls = null; }
  video.pause();
  video.removeAttribute('src');
  video.onerror = null;
  video.onplaying = null;
  video.load();
  $('epg').textContent = '';
}

function attachPlayer(url, isLive = false) {
  const video = $('player');
  destroyPlayer();
  const generation = state.playerGeneration;
  const absoluteUrl = new URL(url, window.location.href).href;
  video.onerror = () => {
    const error = video.error;
    $('playerMeta').textContent = error ? `Playerfehler ${error.code}: ${error.message || 'Wiedergabe nicht möglich'}` : 'Playerfehler: Wiedergabe nicht möglich';
  };
  video.onplaying = () => { if ($('playerMeta').textContent === 'Stream wird geladen …') $('playerMeta').textContent = ''; };

  if (window.Hls && Hls.isSupported()) {
    state.hls = new Hls(hlsOptions());
    configureHlsInstance(state.hls, absoluteUrl, generation, isLive);
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = absoluteUrl;
    video.play().catch((error) => { $('playerMeta').textContent = `Playerfehler: ${error.message}`; });
  } else {
    $('playerMeta').textContent = 'HLS-Wiedergabe wird von diesem Browser nicht unterstützt.';
  }
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

async function renderSeriesLevel(seriesId, season = null, heading = '') {
  $('seriesTitle').textContent = heading || 'Episoden';
  $('episodes').innerHTML = '<span class="muted">Lade …</span>';
  $('seriesDialog').showModal();
  const suffix = season ? `?season=${encodeURIComponent(season)}` : '';
  try {
    const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(seriesId)}${suffix}`));
    $('episodes').innerHTML = '';
    for (const entry of values) {
      const button = document.createElement('button');
      button.textContent = titleOf(entry);
      if (looksLikeSeason(entry)) {
        const seasonId = seasonOf(entry);
        if (!seasonId) {
          button.disabled = true;
          button.title = 'Das Portal hat keine Staffelnummer geliefert.';
        } else if (season && String(seasonId) === String(season)) {
          button.disabled = true;
          button.title = 'Das Portal hat erneut dieselbe Staffel statt Episoden geliefert.';
        } else {
          button.onclick = () => renderSeriesLevel(seriesId, seasonId, `${heading || 'Serie'} – ${titleOf(entry)}`);
        }
      } else {
        const seriesValue = entry.series || entry.series_number || entry.episode_id || null;
        button.onclick = () => { $('seriesDialog').close(); playItem(entry, seriesValue); };
      }
      $('episodes').append(button);
    }
    if (!values.length) $('episodes').textContent = 'Keine Staffeln oder Episoden gefunden.';
  } catch (error) { $('episodes').textContent = error.message; }
}

async function openSeries(item) {
  const id = cleanId(item.movie_id || item.series_id || item.id);
  if (!id) return showMessage('Keine Serien-ID vorhanden.');
  await renderSeriesLevel(id, null, titleOf(item));
}

$('settingsForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('settingsError').textContent = '';
  try {
    await api('/api/config', { method: 'PUT', body: JSON.stringify({ portal_url: $('portalUrl').value, portal_mac: $('portalMac').value }) });
    state.configured = true;
    $('settingsDialog').close();
    await loadStatus(); await loadCategories(); await loadContent();
  } catch (error) { $('settingsError').textContent = error.message; }
});

for (const button of document.querySelectorAll('#tabs button')) {
  button.onclick = async () => {
    state.type = button.dataset.type; state.category = '*';
    $('sectionTitle').textContent = sectionTitles[state.type];
    showMessage('');
    document.querySelectorAll('#tabs button').forEach((node) => node.classList.toggle('active', node === button));
    await loadCategories(); await loadContent();
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

(async () => { await loadConfig(true); await loadStatus(); await loadCategories(); await loadContent(); })();
