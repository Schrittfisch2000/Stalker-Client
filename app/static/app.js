const state = { type: 'itv', category: '*', items: [], hls: null, mpegts: null, configured: false };
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
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.data)) return value.data;
  if (value && typeof value.data === 'object' && value.data) return Object.values(value.data);
  if (value && typeof value === 'object') return Object.values(value).filter((entry) => entry && typeof entry === 'object');
  return [];
}

function titleOf(item) { return item.name || item.title || item.o_name || item.ch_name || 'Ohne Titel'; }
function imageOf(item) { return item.logo || item.screenshot_uri || item.cover || item.poster || ''; }
function commandOf(item) { return item.cmd || item.command || item.stream_url || ''; }

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
    const result = await api('/api/play', { method: 'POST', body: JSON.stringify({ type: state.type, cmd, series }) });
    $('playerTitle').textContent = titleOf(item);
    $('playerMeta').textContent = item.description || item.plot || '';
    $('playerDialog').showModal();
    attachPlayer(result.url, result.stream_type || 'auto');
    showMessage('');
    if (state.type === 'itv') loadEpg(item);
  } catch (error) { showMessage(error.message); }
}

function destroyPlayer() {
  const video = $('player');
  if (state.hls) { state.hls.destroy(); state.hls = null; }
  if (state.mpegts) { state.mpegts.pause(); state.mpegts.unload(); state.mpegts.detachMediaElement(); state.mpegts.destroy(); state.mpegts = null; }
  video.pause();
  video.removeAttribute('src');
  video.load();
}

function attachPlayer(url, streamType = 'auto') {
  const video = $('player');
  destroyPlayer();

  if (streamType === 'mpegts' && window.mpegts && mpegts.isSupported()) {
    state.mpegts = mpegts.createPlayer({ type: 'mpegts', isLive: true, url }, { enableWorker: true, lazyLoad: false });
    state.mpegts.attachMediaElement(video);
    state.mpegts.load();
    state.mpegts.play().catch(() => {});
    state.mpegts.on(mpegts.Events.ERROR, (_, detail) => { $('playerMeta').textContent = `Playerfehler: ${detail}`; });
    return;
  }

  if ((streamType === 'hls' || streamType === 'auto') && window.Hls && Hls.isSupported()) {
    state.hls = new Hls({ enableWorker: true, lowLatencyMode: true });
    state.hls.loadSource(url);
    state.hls.attachMedia(video);
    state.hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
    state.hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) $('playerMeta').textContent = `Playerfehler: ${data.details}`; });
    return;
  }

  video.src = url;
  video.play().catch((error) => { $('playerMeta').textContent = `Playerfehler: ${error.message}`; });
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
  const id = item.id || item.movie_id || item.series_id;
  if (!id) return showMessage('Keine Serien-ID vorhanden.');
  $('seriesTitle').textContent = titleOf(item);
  $('episodes').innerHTML = '<span class="muted">Lade Episoden …</span>';
  $('seriesDialog').showModal();
  try {
    const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(id)}`));
    $('episodes').innerHTML = '';
    for (const episode of values) {
      const button = document.createElement('button');
      button.textContent = titleOf(episode);
      button.onclick = () => { $('seriesDialog').close(); playItem(episode, episode.series || episode.series_number || null); };
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
    state.type = button.dataset.type; state.category = '*';
    $('sectionTitle').textContent = sectionTitles[state.type];
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

(async () => {
  await loadConfig(true);
  await loadStatus();
  await loadCategories();
  await loadContent();
})();