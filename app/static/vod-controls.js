(() => {
  let ticket = '';
  let duration = 0;
  let baseOffset = 0;
  let seeking = false;
  let directSeek = false;
  let seekPending = false;

  function formatTime(value) {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const rest = seconds % 60;
    return hours
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
      : `${minutes}:${String(rest).padStart(2, '0')}`;
  }

  function updateControls() {
    const video = $('player');
    const position = Math.min(duration || Infinity, baseOffset + (video.currentTime || 0));
    const seek = $('vodSeek');
    seek.max = String(duration || Math.max(1, position));
    if (!seeking) seek.value = String(position);
    const buffered = video.buffered.length
      ? Math.min(duration || Infinity, baseOffset + video.buffered.end(video.buffered.length - 1))
      : position;
    const maximum = duration || Math.max(1, buffered);
    const playedPercent = Math.min(100, (position / maximum) * 100);
    const bufferedPercent = Math.min(100, (buffered / maximum) * 100);
    seek.style.background = `linear-gradient(to right,#20bde8 0 ${playedPercent}%,#777 ${playedPercent}% ${bufferedPercent}%,#333 ${bufferedPercent}% 100%)`;
    $('vodTime').textContent = `${formatTime(position)} / ${duration ? formatTime(duration) : '--:--'}`;
    $('vodPlayPause').textContent = video.paused ? '▶' : '❚❚';
  }

  async function seekTo(position) {
    if (!ticket || !duration || seekPending) return;
    const video = $('player');
    if (directSeek) {
      video.currentTime = position;
      updateControls();
      return;
    }
    seekPending = true;
    $('vodSeek').disabled = true;
    const wasPaused = video.paused;
    try {
      $('playerMeta').textContent = `Springe zu ${formatTime(position)} …`;
      const result = await api(`/api/vod-seek/${encodeURIComponent(ticket)}`, {
        method: 'POST',
        body: JSON.stringify({ position }),
      });
      baseOffset = Number(result.position) || 0;
      const generation = ++state.playerGeneration;
      if (state.hls) {
        state.hls.destroy();
        state.hls = null;
      }
      const nextSource = new URL(result.url, window.location.href).href;
      if (window.prefersNativeHlsPlayback?.()) {
        video.src = nextSource;
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Der neue Streamabschnitt wurde nicht rechtzeitig bereitgestellt.')), 20000);
          video.addEventListener('canplay', () => {
            clearTimeout(timeout);
            resolve();
          }, { once: true });
          video.addEventListener('error', () => {
            clearTimeout(timeout);
            reject(new Error('Der neue Streamabschnitt konnte nicht geladen werden.'));
          }, { once: true });
          video.load();
        });
        if (!wasPaused) await video.play();
      } else if (window.Hls && Hls.isSupported()) {
        state.hls = new Hls(hlsOptions());
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Der neue Streamabschnitt wurde nicht rechtzeitig bereitgestellt.')), 20000);
          state.hls.once(Hls.Events.MANIFEST_PARSED, () => {
            clearTimeout(timeout);
            resolve();
          });
          configureHlsInstance(state.hls, nextSource, generation, false);
        });
        if (wasPaused) video.pause();
      } else {
        video.src = nextSource;
        if (!wasPaused) await video.play();
      }
      $('playerMeta').textContent = '';
      updateControls();
    } finally {
      seekPending = false;
      $('vodSeek').disabled = false;
    }
  }

  window.configureVodControls = function configureVodControls(source, isLive, playback = {}) {
    const video = $('player');
    const path = new URL(source).pathname;
    const match = path.match(/^\/hls\/([^/]+)\/index\.m3u8$/) || path.match(/^\/stream\/([^/]+)$/);
    ticket = match ? match[1] : '';
    duration = Number(playback.duration) || 0;
    baseOffset = 0;
    const seekable = playback.seekable === true || playback.seekable === 'true';
    directSeek = playback.stream_type === 'mpegts';
    const customControls = !isLive && duration > 0 && seekable;
    $('vodControls').hidden = !customControls;
    video.toggleAttribute('controls', !customControls);
    video.controls = !customControls;
    video.dataset.knownDuration = duration ? String(duration) : '';
    updateControls();
  };

  window.playerAbsolutePosition = () => baseOffset + ($('player').currentTime || 0);
  window.playerKnownDuration = () => duration || $('player').duration || 0;
  window.seekVodTo = seekTo;

  window.addEventListener('DOMContentLoaded', () => {
    const video = $('player');
    video.addEventListener('timeupdate', updateControls);
    video.addEventListener('progress', updateControls);
    video.addEventListener('play', updateControls);
    video.addEventListener('pause', updateControls);
    $('vodPlayPause').onclick = () => video.paused ? video.play() : video.pause();
    $('vodFullscreen').onclick = () => video.requestFullscreen?.();
    $('vodSeek').addEventListener('input', () => {
      seeking = true;
      $('vodTime').textContent = `${formatTime($('vodSeek').value)} / ${formatTime(duration)}`;
    });
    $('vodSeek').addEventListener('change', async () => {
      try {
        await seekTo(Number($('vodSeek').value));
      } catch (error) {
        $('playerMeta').textContent = `Sprung fehlgeschlagen: ${error.message}`;
      } finally {
        seeking = false;
      }
    });
  });
})();
