(() => {
  const mediaState = { favorites: [], progress: [], current: null, lastSaved: 0 };

  function mediaId(item, type = state.type) {
    return String(item.id || item.movie_id || item.series_id || item.episode_id || item.ch_id || `${type}:${titleOf(item)}`);
  }

  function payloadFor(item, type = state.type) {
    return {
      ...item,
      type,
      id: mediaId(item, type),
      title: titleOf(item),
      image: imageOf(item),
      command: commandOf(item),
      category: state.category,
    };
  }

  function favoriteKey(type, id) { return `${type}:${id}`; }
  function favoriteSet() { return new Set(mediaState.favorites.map((item) => favoriteKey(item.type, item.id))); }
  function progressMap() { return new Map(mediaState.progress.map((item) => [favoriteKey(item.type, item.id), item])); }

  async function refreshMediaState() {
    try {
      [mediaState.favorites, mediaState.progress] = await Promise.all([api('/api/favorites'), api('/api/progress')]);
    } catch (_) {
      mediaState.favorites = [];
      mediaState.progress = [];
    }
  }

  async function toggleFavorite(item, type, button) {
    const id = mediaId(item, type);
    const active = favoriteSet().has(favoriteKey(type, id));
    button.disabled = true;
    try {
      if (active) {
        await api(`/api/favorites/${encodeURIComponent(type)}/${encodeURIComponent(id)}`, { method: 'DELETE' });
        mediaState.favorites = mediaState.favorites.filter((entry) => !(entry.type === type && String(entry.id) === id));
      } else {
        const result = await api('/api/favorites', { method: 'PUT', body: JSON.stringify(payloadFor(item, type)) });
        mediaState.favorites = [result.item, ...mediaState.favorites.filter((entry) => !(entry.type === type && String(entry.id) === id))];
      }
      button.textContent = active ? '☆' : '★';
      button.title = active ? 'Zu Favoriten hinzufügen' : 'Aus Favoriten entfernen';
    } catch (error) {
      showMessage(error.message);
    } finally {
      button.disabled = false;
    }
  }

  const originalCreateCard = createCard;
  createCard = function enhancedCreateCard(item) {
    const type = item.type || state.type;
    const card = originalCreateCard(item);
    card.style.position = 'relative';

    const favorite = document.createElement('button');
    const active = favoriteSet().has(favoriteKey(type, mediaId(item, type)));
    favorite.className = 'media-favorite-button';
    favorite.textContent = active ? '★' : '☆';
    favorite.title = active ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen';
    favorite.onclick = (event) => { event.preventDefault(); event.stopPropagation(); toggleFavorite(item, type, favorite); };
    card.append(favorite);

    const progress = progressMap().get(favoriteKey(type, mediaId(item, type)));
    if (progress && progress.percent > 0) {
      const bar = document.createElement('div');
      bar.className = 'media-progress';
      bar.innerHTML = `<span style="width:${Math.min(100, Number(progress.percent) || 0)}%"></span>`;
      card.append(bar);
    }
    if (progress?.finished) {
      const watched = document.createElement('span');
      watched.className = 'media-watched';
      watched.textContent = '✓ Gesehen';
      card.append(watched);
    }
    return card;
  };

  const originalPlayItem = playItem;
  playItem = async function enhancedPlayItem(item, series = null) {
    const type = item.type || state.type;
    mediaState.current = payloadFor(item, type);
    await originalPlayItem(item, series);
  };

  async function saveCurrentProgress(force = false) {
    const video = $('player');
    const item = mediaState.current;
    if (!item || item.type === 'itv' || !Number.isFinite(video.currentTime)) return;
    const now = Date.now();
    if (!force && now - mediaState.lastSaved < 15000) return;
    mediaState.lastSaved = now;
    try {
      const result = await api('/api/progress', {
        method: 'PUT',
        body: JSON.stringify({ ...item, position: video.currentTime, duration: Number.isFinite(video.duration) ? video.duration : 0, finished: video.ended }),
      });
      mediaState.progress = [result.item, ...mediaState.progress.filter((entry) => !(entry.type === result.item.type && String(entry.id) === String(result.item.id)))];
    } catch (_) {}
  }

  function installPlayerTracking() {
    const video = $('player');
    video.addEventListener('timeupdate', () => saveCurrentProgress(false));
    video.addEventListener('pause', () => saveCurrentProgress(true));
    video.addEventListener('ended', () => saveCurrentProgress(true));
    video.addEventListener('loadedmetadata', () => {
      const item = mediaState.current;
      if (!item) return;
      const saved = progressMap().get(favoriteKey(item.type, item.id));
      if (saved && !saved.finished && saved.position > 5 && saved.position < video.duration - 10) video.currentTime = saved.position;
    });
    $('playerDialog').addEventListener('close', () => { saveCurrentProgress(true); mediaState.current = null; });
  }

  function renderStored(items, title, emptyText) {
    $('sectionTitle').textContent = title;
    $('categories').innerHTML = '';
    $('items').innerHTML = '';
    showMessage(items.length ? '' : emptyText);
    for (const item of items) {
      const card = createCard(item);
      card.onclick = () => {
        state.type = item.type;
        if (item.type === 'series' && !validCommand(item.command)) openSeries({ ...item, series_id: item.series_id || item.id });
        else playItem({ ...item, cmd: item.command });
      };
      $('items').append(card);
    }
  }

  function installToolbar() {
    const head = document.querySelector('.section-head');
    const actions = document.createElement('div');
    actions.className = 'media-library-actions';
    actions.innerHTML = '<button type="button" id="showFavorites">★ Favoriten</button><button type="button" id="showContinue">▶ Weiterschauen</button>';
    head.append(actions);
    $('showFavorites').onclick = async () => { await refreshMediaState(); renderStored(mediaState.favorites, 'Meine Favoriten', 'Noch keine Favoriten gespeichert.'); };
    $('showContinue').onclick = async () => {
      await refreshMediaState();
      renderStored(mediaState.progress.filter((item) => !item.finished && item.position > 0), 'Weiterschauen', 'Keine angefangenen Filme oder Episoden.');
    };
  }

  function installStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .media-library-actions{display:flex;gap:.6rem;flex-wrap:wrap}.media-library-actions button{padding:.65rem .9rem;border:1px solid rgba(255,255,255,.16);border-radius:.6rem;background:rgba(255,255,255,.07);color:inherit;cursor:pointer}
      .media-favorite-button{position:absolute;top:.55rem;right:.55rem;z-index:3;width:2.35rem;height:2.35rem;border:0;border-radius:999px;background:rgba(0,0,0,.72);color:#ffd54a;font-size:1.35rem;cursor:pointer}
      .media-progress{position:absolute;left:0;right:0;bottom:0;height:5px;background:rgba(255,255,255,.2);overflow:hidden;border-radius:0 0 .7rem .7rem}.media-progress span{display:block;height:100%;background:#e50914}
      .media-watched{position:absolute;left:.55rem;top:.55rem;padding:.3rem .5rem;border-radius:.4rem;background:rgba(0,0,0,.75);font-size:.75rem;font-weight:700}
    `;
    document.head.append(style);
  }

  window.addEventListener('DOMContentLoaded', async () => {
    installStyles();
    installToolbar();
    installPlayerTracking();
    await refreshMediaState();
  });
})();
