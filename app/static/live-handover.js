(() => {
  scheduleLiveRefresh = function schedulePersistentProxyRefresh() {
    if (state.liveRefreshTimer) {
      clearTimeout(state.liveRefreshTimer);
      state.liveRefreshTimer = null;
    }
  };

  refreshHlsJsSession = async function refreshPersistentProxySession() {
    console.info('Browser-Handover deaktiviert: Dauerhafter TS-Proxy hält die Live-Sitzung aktiv.');
  };

  const originalDestroyPlayer = destroyPlayer;
  destroyPlayer = function destroyPlayerWithProxyCleanup() {
    if (state.liveRefreshTimer) {
      clearTimeout(state.liveRefreshTimer);
      state.liveRefreshTimer = null;
    }
    if (state.standbyHls) {
      state.standbyHls.destroy();
      state.standbyHls = null;
    }
    document.querySelectorAll('video:not(#player)').forEach((video) => {
      if (video.closest('#playerDialog')) video.remove();
    });
    originalDestroyPlayer();
  };

  console.info('Dauerhafter TS-Proxy aktiv; Dual-Player-Handover deaktiviert.');
})();
