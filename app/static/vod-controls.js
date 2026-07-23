(() => {
  let ticket = '';
  let duration = 0;
  let baseOffset = 0;
  let seeking = false;

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
    if (!ticket || !duration) return;
    const video = $('player');
    const wasPaused = video.paused;
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
    if (window.Hls && Hls.isSupported()) {
      state.hls = new Hls(hlsOptions());
      configureHlsInstance(state.hls, nextSource, generation, false);
      if (wasPaused) state.hls.once(Hls.Events.MANIFEST_PARSED, () => video.pause());
    } else {
      video.src = nextSource;
      if (!wasPaused) video.play().catch(() => {});
    }
    $('playerMeta').textContent = '';
    updateControls();
  }

  window.configureVodControls = function configureVodControls(source, isLive, playback = {}) {
    const video = $('player');
    const match = new URL(source).pathname.match(/^\/hls\/([^/]+)\/index\.m3u8$/);
    ticket = match ? match[1] : '';
    duration = Number(playback.duration) || 0;
    baseOffset = 0;
    const seekable = playback.seekable === true || playback.seekable === 'true';
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
