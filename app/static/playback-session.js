(() => {
  let activeTicket = '';
  let releasePromise = null;

  function ticketFromPlaybackUrl(source) {
    try {
      const url = new URL(source, window.location.href);
      const hls = url.pathname.match(/^\/hls\/([^/]+)\/index\.m3u8$/);
      if (hls) return hls[1];
      const stream = url.pathname.match(/^\/stream\/([^/]+)$/);
      return stream ? stream[1] : '';
    } catch (_) {
      return '';
    }
  }

  async function releaseTicket(ticket, keepalive = false) {
    if (!ticket) return;
    const response = await fetch(`/api/session-release/${encodeURIComponent(ticket)}`, {
      method: 'POST',
      keepalive,
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok && response.status !== 404) {
      throw new Error(`Freigabe der vorherigen Wiedergabe fehlgeschlagen (HTTP ${response.status})`);
    }
  }

  async function releaseActivePlayback() {
    const ticket = activeTicket;
    activeTicket = '';
    state.activePlaybackTicket = '';
    if (!ticket) return;

    if (releasePromise) {
      try { await releasePromise; } catch (_) {}
    }
    releasePromise = releaseTicket(ticket, false);
    try {
      await releasePromise;
    } catch (error) {
      console.warn('Vorherige Portal-Wiedergabe konnte nicht sauber freigegeben werden:', error);
    } finally {
      releasePromise = null;
    }
  }

  function releaseOnClose() {
    const ticket = activeTicket;
    activeTicket = '';
    state.activePlaybackTicket = '';
    if (!ticket) return;
    releaseTicket(ticket, true).catch((error) => {
      console.warn('Portal-Wiedergabe konnte beim Schließen nicht freigegeben werden:', error);
    });
  }

  const originalAttachPlayer = attachPlayer;
  attachPlayer = function attachPlayerWithSessionTracking(url, isLive = false) {
    const result = originalAttachPlayer(url, isLive);
    activeTicket = ticketFromPlaybackUrl(url);
    state.activePlaybackTicket = activeTicket;
    return result;
  };

  const originalPlayItem = playItem;
  playItem = async function playItemWithPortalHandover(item, series = null) {
    await releaseActivePlayback();
    return originalPlayItem(item, series);
  };

  const originalDestroyPlayer = destroyPlayer;
  destroyPlayer = function destroyPlayerWithSessionRelease() {
    releaseOnClose();
    return originalDestroyPlayer();
  };

  $('playerDialog').addEventListener('close', releaseOnClose);
  window.releaseActivePlayback = releaseActivePlayback;
})();
