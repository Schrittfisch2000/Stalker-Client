(() => {
  let video = null;
  let lastTimeUpdateLog = 0;
  const boundVideos = new WeakSet();

  function bufferedRanges(target) {
    const ranges = [];
    for (let index = 0; index < target.buffered.length; index += 1) {
      ranges.push(`${target.buffered.start(index).toFixed(2)}-${target.buffered.end(index).toFixed(2)}`);
    }
    return ranges.join(',');
  }

  function details(target, extra = {}) {
    return {
      currentTime: Number(target.currentTime || 0).toFixed(3),
      readyState: target.readyState,
      networkState: target.networkState,
      paused: target.paused,
      ended: target.ended,
      muted: target.muted,
      volume: target.volume,
      playbackRate: target.playbackRate,
      buffered: bufferedRanges(target),
      currentSrc: target.currentSrc || target.src || '',
      visibility: document.visibilityState,
      online: navigator.onLine,
      memory: performance.memory ? JSON.stringify({
        usedJSHeapSize: performance.memory.usedJSHeapSize,
        totalJSHeapSize: performance.memory.totalJSHeapSize,
        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
      }) : 'unavailable',
      ...extra
    };
  }

  function send(event, extra = {}, target = video) {
    if (!target) return;
    fetch('/api/client-log', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, details: details(target, extra) })
    }).catch(() => {});
  }

  function bindPlayer(target, replacement = false) {
    if (!target || boundVideos.has(target)) return;
    video = target;
    boundVideos.add(target);

    ['loadstart', 'loadedmetadata', 'loadeddata', 'canplay', 'canplaythrough', 'play', 'playing', 'pause', 'waiting', 'stalled', 'suspend', 'emptied', 'ended', 'abort'].forEach((eventName) => {
      target.addEventListener(eventName, () => send(eventName, {}, target));
    });

    target.addEventListener('error', () => {
      const error = target.error;
      send('error', {
        errorCode: error ? error.code : 0,
        errorMessage: error ? error.message : 'unknown'
      }, target);
    });

    target.addEventListener('timeupdate', () => {
      const now = Date.now();
      if (now - lastTimeUpdateLog >= 30000) {
        lastTimeUpdateLog = now;
        send('timeupdate-30s', {}, target);
      }
    });

    if (replacement) send('diagnostics-player-rebound', {}, target);
  }

  bindPlayer(document.getElementById('player'));
  if (!video) return;

  document.addEventListener('stalker-player-replaced', (event) => {
    bindPlayer(event.detail?.video || document.getElementById('player'), true);
  });
  document.addEventListener('visibilitychange', () => send('visibilitychange'));
  window.addEventListener('online', () => send('network-online'));
  window.addEventListener('offline', () => send('network-offline'));

  send('diagnostics-installed', {
    browserLanguage: navigator.language,
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency || 0,
    deviceMemory: navigator.deviceMemory || 'unknown',
    screen: `${screen.width}x${screen.height}@${window.devicePixelRatio || 1}`,
    hlsJsSupported: Boolean(window.Hls && Hls.isSupported()),
    nativeHls: video.canPlayType('application/vnd.apple.mpegurl') || 'no'
  });
})();