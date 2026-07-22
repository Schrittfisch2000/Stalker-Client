(() => {
  const originalCreateCard = createCard;

  async function startDownload(item, series = null) {
    const mediaType = item.type || state.type;
    const cmd = commandOf(item);
    if (!['vod', 'series'].includes(mediaType)) return;
    if (!validCommand(cmd)) return showMessage('Dieser Eintrag kann nicht heruntergeladen werden.');

    showMessage('Download wird vorbereitet …');
    try {
      const result = await api('/api/download', {
        method: 'POST',
        body: JSON.stringify({
          type: mediaType,
          cmd,
          category: item.category || state.category,
          series,
          item,
          title: item.download_title || titleOf(item),
        }),
      });
      const link = document.createElement('a');
      link.href = result.url;
      link.download = result.filename || '';
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      showMessage(`Download gestartet: ${result.filename || titleOf(item)}`);
      window.setTimeout(() => showMessage(''), 3500);
    } catch (error) {
      showMessage(`Download fehlgeschlagen: ${error.message}`);
    }
  }

  window.downloadItem = startDownload;

  createCard = function createCardWithDownload(item) {
    const card = originalCreateCard(item);
    const mediaType = item.type || state.type;
    if (mediaType !== 'vod') return card;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'download-button';
    button.textContent = '↓ Download';
    button.setAttribute('aria-label', `${titleOf(item)} herunterladen`);
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      startDownload({ ...item, type: 'vod', category: item.category || state.category });
    });
    card.querySelector('.card-body')?.append(button);
    return card;
  };
})();
