(() => {
  const STALL_SECONDS = 8;
  const CHECK_INTERVAL_MS = 2000;
  const PROACTIVE_REFRESH_MS = 70000;

  function isNativeHlsPlayer(video) {
    if (window.prefersNativeHlsPlayback?.()) return true;
    const hlsJsActive = Boolean(window.state?.hls);
    return !hlsJsActive && Boolean(video.canPlayType('application/vnd.apple.mpegurl'));
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

  function installRecovery() {
    const video = document.getElementById('player');
    const meta = document.getElementById('playerMeta');
    if (!video || !isNativeHlsPlayer(video)) return;

    let lastTime = 0;
    let lastProgressAt = performance.now();
    let switching = false;
    let proactiveTimer = null;
    let refreshes = 0;
    let refreshWindowStartedAt = performance.now();

    const clearProactiveTimer = () => {
      if (proactiveTimer) {
        clearTimeout(proactiveTimer);
        proactiveTimer = null;
      }
    };

    const scheduleProactiveRefresh = () => {
      clearProactiveTimer();
      if (!ticketFromSource(video.currentSrc || video.src)) return;
      proactiveTimer = setTimeout(() => {
        switchToFreshSession(true);
      }, PROACTIVE_REFRESH_MS);
    };

    const markProgress = () => {
      lastTime = video.currentTime || 0;
      lastProgressAt = performance.now();
      if (meta && (
        meta.textContent === 'Safari wechselt auf eine vorgewärmte Live-Session …' ||
        meta.textContent === 'Safari wechselt auf eine neue Live-Session …'
      )) {
        meta.textContent = '';
      }
    };

    const switchToFreshSession = async (proactive = false) => {
      if (switching || video.ended || !video.currentSrc) return;

      const now = performance.now();
      if (now - refreshWindowStartedAt > 180000) {
        refreshWindowStartedAt = now;
        refreshes = 0;
      }
      if (refreshes >= 5) {
        if (meta) meta.textContent = 'Safari konnte den Live-Stream nicht automatisch fortsetzen. Bitte den Sender erneut öffnen.';
        return;
      }

      const ticket = ticketFromSource(video.currentSrc || video.src);
      if (!ticket) return;

      switching = true;
      clearProactiveTimer();
      refreshes += 1;
      if (meta) {
        meta.textContent = proactive
          ? 'Safari bereitet die nächste Live-Session vor …'
          : 'Safari wechselt auf eine neue Live-Session …';
      }

      try {
        const response = await fetch(`/api/live-refresh/${encodeURIComponent(ticket)}`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (!payload.url) throw new Error('Keine neue Stream-URL erhalten');

        if (meta) meta.textContent = 'Safari wechselt auf eine vorgewärmte Live-Session …';
        const freshSource = `${payload.url}?_safari_session=${Date.now()}`;

        video.pause();
        video.src = freshSource;
        video.load();
        await video.play().catch(() => {});
        lastProgressAt = performance.now();
        scheduleProactiveRefresh();
      } catch (error) {
        console.warn('Safari Live-Session konnte nicht erneuert werden:', error);
        if (meta) {
          meta.textContent = proactive
            ? 'Vorbereitung der nächsten Live-Session fehlgeschlagen; aktueller Stream läuft weiter.'
            : 'Neue Live-Session fehlgeschlagen. Bitte den Sender erneut öffnen.';
        }
        scheduleProactiveRefresh();
      } finally {
        switching = false;
      }
    };

    const recover = () => {
      if (switching || video.paused || video.ended || !video.currentSrc) return;
      switchToFreshSession(false);
    };

    video.addEventListener('playing', () => {
      markProgress();
      if (!proactiveTimer) scheduleProactiveRefresh();
    });
    video.addEventListener('timeupdate', () => {
      const current = video.currentTime || 0;
      if (current > lastTime + 0.2) markProgress();
    });
    video.addEventListener('emptied', clearProactiveTimer);
    video.addEventListener('waiting', () => {
      const stalledFor = (performance.now() - lastProgressAt) / 1000;
      if (stalledFor >= STALL_SECONDS) recover();
    });
    video.addEventListener('stalled', recover);

    setInterval(() => {
      if (video.paused || video.ended || !video.currentSrc) return;
      const stalledFor = (performance.now() - lastProgressAt) / 1000;
      if (stalledFor >= STALL_SECONDS) recover();
    }, CHECK_INTERVAL_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installRecovery);
  else installRecovery();
})();
