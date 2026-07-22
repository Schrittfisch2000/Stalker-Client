(() => {
  const STALL_SECONDS = 8;
  const CHECK_INTERVAL_MS = 2000;

  function isNativeHlsPlayer(video) {
    const hlsJsActive = window.Hls && Hls.isSupported();
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
    let recovering = false;
    let refreshes = 0;
    let refreshWindowStartedAt = performance.now();

    const markProgress = () => {
      lastTime = video.currentTime || 0;
      lastProgressAt = performance.now();
      recovering = false;
      if (meta && meta.textContent === 'Safari wechselt auf eine neue Live-Session …') {
        meta.textContent = '';
      }
    };

    const switchToFreshSession = async () => {
      const now = performance.now();
      if (now - refreshWindowStartedAt > 120000) {
        refreshWindowStartedAt = now;
        refreshes = 0;
      }
      if (refreshes >= 3) {
        if (meta) meta.textContent = 'Safari konnte den Live-Stream nicht automatisch fortsetzen. Bitte den Sender erneut öffnen.';
        recovering = false;
        return;
      }

      const ticket = ticketFromSource(video.currentSrc || video.src);
      if (!ticket) {
        recovering = false;
        return;
      }

      refreshes += 1;
      if (meta) meta.textContent = 'Safari wechselt auf eine neue Live-Session …';

      try {
        const response = await fetch(`/api/live-refresh/${encodeURIComponent(ticket)}`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (!payload.url) throw new Error('Keine neue Stream-URL erhalten');

        video.pause();
        video.removeAttribute('src');
        video.load();
        video.src = `${payload.url}?_safari_session=${Date.now()}`;
        video.load();
        await video.play().catch(() => {});
        lastProgressAt = performance.now();
      } catch (error) {
        console.warn('Safari Live-Session konnte nicht erneuert werden:', error);
        if (meta) meta.textContent = 'Neue Live-Session fehlgeschlagen. Bitte den Sender erneut öffnen.';
        recovering = false;
      }
    };

    const recover = () => {
      if (recovering || video.paused || video.ended || !video.currentSrc) return;
      recovering = true;
      switchToFreshSession();
    };

    video.addEventListener('playing', markProgress);
    video.addEventListener('timeupdate', () => {
      const current = video.currentTime || 0;
      if (current > lastTime + 0.2) markProgress();
    });
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
