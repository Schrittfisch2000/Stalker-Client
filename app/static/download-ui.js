(() => {
  const originalCreateCard = createCard;

  async function startDownload(item, series = null) {
    const mediaType = state.type;
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
          series,
          item,
          title: titleOf(item),
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

  window.createCard = function createCardWithDownload(item) {
    const card = originalCreateCard(item);
    if (state.type !== 'vod') return card;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'download-button';
    button.textContent = '↓ Download';
    button.setAttribute('aria-label', `${titleOf(item)} herunterladen`);
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      startDownload(item);
    });
    card.querySelector('.card-body')?.append(button);
    return card;
  };

  window.renderSeriesLevel = async function renderSeriesLevelWithDownloads(seriesId, season = null, heading = '') {
    $('seriesTitle').textContent = heading || 'Episoden';
    $('episodes').innerHTML = '<span class="muted">Lade …</span>';
    $('seriesDialog').showModal();
    const suffix = season ? `?season=${encodeURIComponent(season)}` : '';

    try {
      const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(seriesId)}${suffix}`));
      $('episodes').innerHTML = '';

      for (const entry of values) {
        if (looksLikeSeason(entry)) {
          const button = document.createElement('button');
          button.textContent = titleOf(entry);
          const seasonId = seasonOf(entry);
          if (!seasonId) {
            button.disabled = true;
            button.title = 'Das Portal hat keine Staffelnummer geliefert.';
          } else if (season && String(seasonId) === String(season)) {
            button.disabled = true;
            button.title = 'Das Portal hat erneut dieselbe Staffel statt Episoden geliefert.';
          } else {
            button.onclick = () => renderSeriesLevelWithDownloads(
              seriesId,
              seasonId,
              `${heading || 'Serie'} – ${titleOf(entry)}`,
            );
          }
          $('episodes').append(button);
          continue;
        }

        const seriesValue = entry.series || entry.series_number || entry.episode_id || null;
        const row = document.createElement('div');
        row.className = 'episode-row';

        const playButton = document.createElement('button');
        playButton.type = 'button';
        playButton.className = 'episode-play';
        playButton.textContent = titleOf(entry);
        playButton.onclick = () => {
          $('seriesDialog').close();
          playItem(entry, seriesValue);
        };

        const downloadButton = document.createElement('button');
        downloadButton.type = 'button';
        downloadButton.className = 'download-button episode-download';
        downloadButton.textContent = '↓';
        downloadButton.title = `${titleOf(entry)} herunterladen`;
        downloadButton.setAttribute('aria-label', downloadButton.title);
        downloadButton.onclick = () => startDownload(entry, seriesValue);

        row.append(playButton, downloadButton);
        $('episodes').append(row);
      }

      if (!values.length) $('episodes').textContent = 'Keine Staffeln oder Episoden gefunden.';
    } catch (error) {
      $('episodes').textContent = error.message;
    }
  };
})();
