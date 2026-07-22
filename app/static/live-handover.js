(() => {
  const HANDOVER_AFTER_MS = 30000;
  const MIN_STANDBY_BUFFER_SECONDS = 3;
  const STANDBY_TIMEOUT_MS = 15000;

  function releaseOldSession(ticket) {
    if (!ticket) return;
    fetch(`/api/live-release/${encodeURIComponent(ticket)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch((error) => console.warn('Alte Live-Session konnte nicht freigegeben werden:', error));
  }

  function standbyHlsOptions() {
    const options = { ...hlsOptions() };
    options.startPosition = -1;
    options.liveSyncDurationCount = 3;
    options.maxBufferLength = 20;
    options.backBufferLength = 5;
    options.maxBufferHole = 0.5;
    return options;
  }

  function bufferedAhead(video) {
    for (let index = 0; index < video.buffered.length; index += 1) {
      const start = video.buffered.start(index);
      const end = video.buffered.end(index);
      if (video.currentTime >= start - 0.1 && video.currentTime <= end + 0.1) {
        return Math.max(0, end - video.currentTime);
      }
    }
    return 0;
  }

  function makeStandbyVideo(activeVideo) {
    const standby = document.createElement('video');
    standby.autoplay = true;
    standby.playsInline = true;
    standby.muted = true;
    standby.controls = activeVideo.controls;
    standby.preload = 'auto';
    standby.setAttribute('aria-hidden', 'true');
    standby.style.display = 'none';
    return standby;
  }

  function waitForStandby(standby, freshHls, generation) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const startedAt = Date.now();

      const cleanup = () => {
        clearInterval(interval);
        clearTimeout(timeout);
        freshHls.off(Hls.Events.ERROR, onError);
      };

      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        cleanup();
        callback(value);
      };

      const check = () => {
        if (generation !== state.playerGeneration || freshHls !== state.standbyHls) {
          finish(reject, new Error('Live-Handover wurde verworfen.'));
          return;
        }
        const ahead = bufferedAhead(standby);
        if (!standby.paused && standby.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA && ahead >= MIN_STANDBY_BUFFER_SECONDS) {
          console.info('Live-Handover-Ersatzplayer gepuffert', {
            bufferedAhead: ahead,
            currentTime: standby.currentTime,
            readyState: standby.readyState,
            preparationMs: Date.now() - startedAt,
          });
          finish(resolve, ahead);
        }
      };

      const onError = (_, data) => {
        if (data.fatal) finish(reject, new Error(`Ersatzplayer: ${data.details}`));
      };

      freshHls.on(Hls.Events.ERROR, onError);
      const interval = setInterval(check, 100);
      const timeout = setTimeout(
        () => finish(reject, new Error('Ersatzplayer wurde nicht rechtzeitig abspielbereit.')),
        STANDBY_TIMEOUT_MS,
      );
      standby.addEventListener('playing', check);
      standby.addEventListener('progress', check);
      standby.addEventListener('canplay', check);
    });
  }

  function activateStandby(activeVideo, standby, freshHls, oldHls, oldTicket, freshSource, generation) {
    const wasMuted = activeVideo.muted;
    const volume = activeVideo.volume;
    const playbackRate = activeVideo.playbackRate;

    activeVideo.id = 'player-retired';
    standby.id = 'player';
    standby.controls = activeVideo.controls;
    standby.removeAttribute('aria-hidden');
    standby.style.display = '';
    standby.muted = wasMuted;
    standby.volume = volume;
    standby.playbackRate = playbackRate;

    activeVideo.replaceWith(standby);
    state.hls = freshHls;
    state.standbyHls = null;

    document.dispatchEvent(new CustomEvent('stalker-player-replaced', {
      detail: { video: standby },
    }));

    requestAnimationFrame(() => {
      standby.play().catch((error) => {
        $('playerMeta').textContent = `Playerfehler: ${error.message}`;
      });
    });

    oldHls.stopLoad();
    oldHls.detachMedia();
    oldHls.destroy();
    activeVideo.pause();
    activeVideo.removeAttribute('src');
    activeVideo.load();

    releaseOldSession(oldTicket);
    $('playerMeta').textContent = '';
    scheduleLiveRefresh(freshSource, generation);
    console.info('Live-Handover ohne Player-Neustart abgeschlossen');
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
    const activeVideo = $('player');
    let standby = null;
    let freshHls = null;
    $('playerMeta').textContent = 'Nächste Live-Session wird im Hintergrund vorbereitet …';

    try {
      const payload = await api(`/api/live-refresh/${encodeURIComponent(oldTicket)}`, { method: 'POST' });
      if (generation !== state.playerGeneration || oldHls !== state.hls || !payload.url) return;

      const freshSource = new URL(`${payload.url}?_handover=${Date.now()}`, window.location.href).href;
      standby = makeStandbyVideo(activeVideo);
      activeVideo.parentNode.insertBefore(standby, activeVideo.nextSibling);

      freshHls = new Hls(standbyHlsOptions());
      state.standbyHls = freshHls;
      freshHls.attachMedia(standby);
      freshHls.on(Hls.Events.MEDIA_ATTACHED, () => freshHls.loadSource(freshSource));
      freshHls.on(Hls.Events.MANIFEST_PARSED, () => {
        standby.play().catch((error) => console.warn('Ersatzplayer konnte nicht vorab starten:', error));
      });

      await waitForStandby(standby, freshHls, generation);
      if (generation !== state.playerGeneration || oldHls !== state.hls || freshHls !== state.standbyHls) return;

      $('playerMeta').textContent = 'Live-Session wird übergeben …';
      activateStandby(activeVideo, standby, freshHls, oldHls, oldTicket, freshSource, generation);
    } catch (error) {
      console.warn('Vorgewärmte Live-Session konnte nicht übernommen werden:', error);
      if (freshHls) freshHls.destroy();
      if (standby && standby.isConnected) standby.remove();
      if (state.standbyHls === freshHls) state.standbyHls = null;
      if (generation === state.playerGeneration && oldHls === state.hls) {
        $('playerMeta').textContent = 'Vorbereitung der nächsten Live-Session fehlgeschlagen; aktueller Stream läuft weiter.';
        scheduleLiveRefresh(source, generation);
      }
    } finally {
      state.liveSwitching = false;
    }
  };

  const originalDestroyPlayer = destroyPlayer;
  destroyPlayer = function destroyPlayerWithStandbyCleanup() {
    if (state.standbyHls) {
      state.standbyHls.destroy();
      state.standbyHls = null;
    }
    document.querySelectorAll('video:not(#player)').forEach((video) => {
      if (video.closest('#playerDialog')) video.remove();
    });
    originalDestroyPlayer();
  };
})();