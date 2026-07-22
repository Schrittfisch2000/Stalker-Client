(() => {
  const HANDOVER_AFTER_MS = 30000;

  function releaseOldSession(ticket) {
    if (!ticket) return;
    fetch(`/api/live-release/${encodeURIComponent(ticket)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch((error) => console.warn('Alte Live-Session konnte nicht freigegeben werden:', error));
  }

  scheduleLiveRefresh = function schedulePreparedLiveRefresh(source, generation) {
    if (!ticketFromSource(source) || generation !== state.playerGeneration) return;
    if (state.liveRefreshTimer) clearTimeout(state.liveRefreshTimer);
    state.liveRefreshTimer = setTimeout(
      () => refreshHlsJsSession(source, generation),
      HANDOVER_AFTER_MS,
    );
  };

  refreshHlsJsSession = async function refreshPreparedLiveSession(source, generation) {
    if (state.liveSwitching || generation !== state.playerGeneration || !state.hls) return;
    const oldTicket = ticketFromSource(source);
    if (!oldTicket) return;

    state.liveSwitching = true;
    state.liveRefreshTimer = null;
    const oldHls = state.hls;
    const video = $('player');
    const wasMuted = video.muted;
    const volume = video.volume;
    $('playerMeta').textContent = 'Nächste Live-Session wird vorbereitet …';

    try {
      const payload = await api(`/api/live-refresh/${encodeURIComponent(oldTicket)}`, { method: 'POST' });
      if (generation !== state.playerGeneration || oldHls !== state.hls || !payload.url) return;

      const freshSource = new URL(`${payload.url}?_handover=${Date.now()}`, window.location.href).href;
      const freshHls = new Hls(hlsOptions());
      let released = false;
      const releaseAfterPlaying = () => {
        if (released) return;
        released = true;
        releaseOldSession(oldTicket);
      };
      video.addEventListener('playing', releaseAfterPlaying, { once: true });

      oldHls.stopLoad();
      oldHls.detachMedia();
      oldHls.destroy();
      state.hls = freshHls;
      video.muted = wasMuted;
      video.volume = volume;
      $('playerMeta').textContent = 'Live-Session wird gewechselt …';
      configureHlsInstance(freshHls, freshSource, generation, true, true);

      setTimeout(releaseAfterPlaying, 8000);
    } catch (error) {
      console.warn('Vorgewärmte Live-Session konnte nicht übernommen werden:', error);
      if (generation === state.playerGeneration && oldHls === state.hls) {
        $('playerMeta').textContent = 'Vorbereitung der nächsten Live-Session fehlgeschlagen; aktueller Stream läuft weiter.';
        scheduleLiveRefresh(source, generation);
      }
    } finally {
      state.liveSwitching = false;
    }
  };
})();
