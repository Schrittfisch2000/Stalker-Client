(() => {
  const video = document.getElementById('player');
  if (!video) return;

  let lastTimeUpdateLog = 0;

  function bufferedRanges() {
    const ranges = [];
    for (let index = 0; index < video.buffered.length; index += 1) {
      ranges.push(`${video.buffered.start(index).toFixed(2)}-${video.buffered.end(index).toFixed(2)}`);
    }
    return ranges.join(',');
  }

  function details(extra = {}) {
    return {
      currentTime: Number(video.currentTime || 0).toFixed(3),
      readyState: video.readyState,
      networkState: video.networkState,
      paused: video.paused,
      ended: video.ended,
      muted: video.muted,
      volume: video.volume,
      playbackRate: video.playbackRate,
      buffered: bufferedRanges(),
      currentSrc: video.currentSrc || video.src || '',
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

  function send(event, extra = {}) {
    fetch('/api/client-log', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, details: details(extra) })
    }).catch(() => {});
  }

  ['loadstart', 'loadedmetadata', 'loadeddata', 'canplay', 'canplaythrough', 'play', 'playing', 'pause', 'waiting', 'stalled', 'suspend', 'emptied', 'ended', 'abort'].forEach((eventName) => {
    video.addEventListener(eventName, () => send(eventName));
  });

  video.addEventListener('error', () => {
    const error = video.error;
    send('error', {
      errorCode: error ? error.code : 0,
      errorMessage: error ? error.message : 'unknown'
    });
  });

  video.addEventListener('timeupdate', () => {
    const now = Date.now();
    if (now - lastTimeUpdateLog >= 30000) {
      lastTimeUpdateLog = now;
      send('timeupdate-30s');
    }
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