(() => {
  function openRecoveredDialog(initialPanel) {
    window.setTimeout(() => {
      const dialog = document.getElementById('userAdminDialog');
      if (!dialog) return;

      const panelName = initialPanel === 'portal' ? 'portal' : 'users';
      dialog.querySelectorAll('.admin-tabs button').forEach((button) => {
        button.classList.toggle('active', button.dataset.panel === panelName);
      });
      dialog.querySelectorAll('.admin-panel').forEach((panel) => {
        panel.hidden = panel.dataset.panel !== panelName;
      });

      if (!dialog.open) {
        try { dialog.showModal(); } catch (_) {}
      }
    }, 200);
  }

  document.addEventListener('click', (event) => {
    const settingsButton = event.target.closest('#openSettings');
    if (settingsButton) {
      openRecoveredDialog('portal');
      return;
    }

    const userButton = event.target.closest('.user-name-button');
    if (userButton && userButton.title === 'Administration öffnen') {
      openRecoveredDialog('users');
    }
  }, true);
})();
