(() => {
  const HANDOVER_AFTER_MS = 30000;
  const LIVE_EDGE_MARGIN_SECONDS = 0.35;

  function releaseOldSession(ticket) {
    if (!ticket) return;
    fetch(`/api/live-release/${encodeURIComponent(ticket)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch((error) => console.warn('Alte Live-Session konnte nicht freigegeben werden:', error));
  }

  function handoverHlsOptions() {
    const options = { ...hlsOptions() };
    delete options.liveSyncDurationCount;
    delete options.liveMaxLatencyDurationCount;
    options.startPosition = -1;
    options.liveSyncDuration = 0.75;
    options.liveMaxLatencyDuration = 3;
    options.maxBufferHole = 0.5;
    return options;
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
      const freshHls = new Hls(handoverHlsOptions());
      let released = false;
      let liveEdge = Number.NaN;
      let edgeApplied = false;

      const releaseAfterPlaying = () => {
        if (released) return;
        released = true;
        releaseOldSession(oldTicket);
      };

      const seekToLiveEdge = () => {
        if (edgeApplied || generation !== state.playerGeneration || freshHls !== state.hls) return;
        if (!video.seekable || video.seekable.length === 0) return;

        const seekableStart = video.seekable.start(video.seekable.length - 1);
        const seekableEnd = video.seekable.end(video.seekable.length - 1);
        const desired = Number.isFinite(liveEdge)
          ? liveEdge - LIVE_EDGE_MARGIN_SECONDS
          : seekableEnd - LIVE_EDGE_MARGIN_SECONDS;
        const target = Math.max(seekableStart, Math.min(desired, seekableEnd - 0.05));

        if (!Number.isFinite(target)) return;
        video.currentTime = target;
        edgeApplied = true;
        console.info('Live-Handover am Live-Rand gestartet', {
          target,
          liveEdge,
          seekableStart,
          seekableEnd,
        });
      };

      freshHls.on(Hls.Events.LEVEL_LOADED, (_, data) => {
        const edge = Number(data?.details?.edge);
        if (Number.isFinite(edge)) liveEdge = edge;
      });
      freshHls.on(Hls.Events.FRAG_BUFFERED, seekToLiveEdge);
      video.addEventListener('loadedmetadata', seekToLiveEdge, { once: true });
      video.addEventListener('canplay', seekToLiveEdge, { once: true });
      video.addEventListener('playing', releaseAfterPlaying, { once: true });

      oldHls.stopLoad();
      oldHls.detachMedia();
      oldHls.destroy();
      state.hls = freshHls;
      video.muted = wasMuted;
      video.volume = volume;
      $('playerMeta').textContent = 'Live-Session wird am Live-Rand gewechselt …';
      configureHlsInstance(freshHls, freshSource, generation, true, true);

      setTimeout(seekToLiveEdge, 500);
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
