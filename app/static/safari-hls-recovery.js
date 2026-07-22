(() => {
  const STALL_SECONDS = 8;
  const RELOAD_DELAY_MS = 4500;
  const CHECK_INTERVAL_MS = 2000;

  function isNativeHlsPlayer(video) {
    const hlsJsActive = window.Hls && Hls.isSupported();
    return !hlsJsActive && Boolean(video.canPlayType('application/vnd.apple.mpegurl'));
  }

  function installRecovery() {
    const video = document.getElementById('player');
    const meta = document.getElementById('playerMeta');
    if (!video || !isNativeHlsPlayer(video)) return;

    let lastTime = 0;
    let lastProgressAt = performance.now();
    let recovering = false;
    let reloadTimer = null;
    let reloads = 0;
    let reloadWindowStartedAt = performance.now();

    const markProgress = () => {
      lastTime = video.currentTime || 0;
      lastProgressAt = performance.now();
      recovering = false;
      if (reloadTimer) {
        clearTimeout(reloadTimer);
        reloadTimer = null;
      }
    };

    const jumpToLiveEdge = () => {
      if (!video.seekable || video.seekable.length === 0) return false;
      const end = video.seekable.end(video.seekable.length - 1);
      if (!Number.isFinite(end)) return false;
      const target = Math.max(0, end - 1.5);
      if (Math.abs((video.currentTime || 0) - target) > 0.5) video.currentTime = target;
      return true;
    };

    const reloadNativeStream = () => {
      const now = performance.now();
      if (now - reloadWindowStartedAt > 60000) {
        reloadWindowStartedAt = now;
        reloads = 0;
      }
      if (reloads >= 3 || !video.currentSrc) {
        if (meta) meta.textContent = 'Safari konnte den Live-Stream nicht automatisch fortsetzen. Bitte den Sender erneut öffnen.';
        recovering = false;
        return;
      }
      reloads += 1;
      const source = new URL(video.currentSrc, window.location.href);
      source.searchParams.set('_safari_recover', String(Date.now()));
      video.src = source.href;
      video.load();
      video.play().catch(() => {});
      lastProgressAt = performance.now();
    };

    const recover = () => {
      if (recovering || video.paused || video.ended || !video.currentSrc) return;
      recovering = true;
      if (meta) meta.textContent = 'Safari verbindet den Live-Stream neu …';
      jumpToLiveEdge();
      video.play().catch(() => {});
      reloadTimer = setTimeout(() => {
        const stalledFor = (performance.now() - lastProgressAt) / 1000;
        if (stalledFor >= STALL_SECONDS) reloadNativeStream();
        else recovering = false;
      }, RELOAD_DELAY_MS);
    };

    video.addEventListener('playing', markProgress);
    video.addEventListener('timeupdate', () => {
      const current = video.currentTime || 0;
      if (current > lastTime + 0.2) {
        if (meta && meta.textContent === 'Safari verbindet den Live-Stream neu …') meta.textContent = '';
        markProgress();
      }
    });
    video.addEventListener('waiting', recover);
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
