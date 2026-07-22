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

  function appendEpisodeRow(item, seriesValue, label = titleOf(item)) {
    const row = document.createElement('div');
    row.className = 'episode-row';

    const playButton = document.createElement('button');
    playButton.type = 'button';
    playButton.className = 'episode-play';
    playButton.textContent = label;
    playButton.onclick = () => {
      $('seriesDialog').close();
      playItem(item, seriesValue);
    };

    const downloadButton = document.createElement('button');
    downloadButton.type = 'button';
    downloadButton.className = 'download-button episode-download';
    downloadButton.textContent = '↓';
    downloadButton.title = `${label} herunterladen`;
    downloadButton.setAttribute('aria-label', downloadButton.title);
    downloadButton.onclick = () => startDownload(item, seriesValue);

    row.append(playButton, downloadButton);
    $('episodes').append(row);
  }

  function showEmbeddedEpisodes(seriesItem, seasonItem, season, heading) {
    const episodes = serienFolgenwerte(seasonItem);
    if (!episodes.length) return false;

    const baseCommand = commandOf(seasonItem) || commandOf(seriesItem);
    $('seriesTitle').textContent = heading;
    $('episodes').innerHTML = '';

    for (const episode of episodes) {
      const number = String(episode).replace(/^episode\s*/i, '').trim();
      const label = `Episode ${number}`;
      const item = {
        ...seriesItem,
        ...seasonItem,
        type: 'series',
        name: label,
        title: label,
        episode_name: label,
        download_title: `${titleOf(seriesItem)} - Staffel ${season} - ${label}`,
        cmd: baseCommand,
        command: baseCommand,
        series: number,
        series_number: number,
        episode_id: number,
        season_id: season,
        season_number: season,
      };
      appendEpisodeRow(item, number, label);
    }
    return true;
  }

  async function renderSeriesLevelWithDownloads(
    seriesId,
    season = null,
    heading = '',
    seriesItem = null,
    seasonItem = null,
  ) {
    const currentSeries = seriesItem || state.currentSeriesItem || {};
    $('seriesTitle').textContent = heading || 'Episoden';
    $('episodes').innerHTML = '<span class="muted">Lade …</span>';
    $('seriesDialog').showModal();

    if (
      season
      && seasonItem
      && showEmbeddedEpisodes(currentSeries, seasonItem, season, heading || `Staffel ${season}`)
    ) return;

    const suffix = season ? `?season=${encodeURIComponent(season)}` : '';
    try {
      const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(seriesId)}${suffix}`));
      $('episodes').innerHTML = '';

      if (
        season
        && values.length === 1
        && looksLikeSeason(values[0])
        && String(seasonOf(values[0])) === String(season)
      ) {
        if (showEmbeddedEpisodes(currentSeries, values[0], season, heading || `Staffel ${season}`)) return;
        if (seasonItem && showEmbeddedEpisodes(currentSeries, seasonItem, season, heading || `Staffel ${season}`)) return;
        $('episodes').textContent = 'Das Portal liefert für diese Staffel keine Episodendaten.';
        return;
      }

      for (const entry of values) {
        if (looksLikeSeason(entry)) {
          const button = document.createElement('button');
          button.textContent = titleOf(entry);
          const seasonId = seasonOf(entry);
          if (!seasonId) {
            button.disabled = true;
            button.title = 'Das Portal hat keine Staffelnummer geliefert.';
          } else {
            button.onclick = () => renderSeriesLevelWithDownloads(
              seriesId,
              seasonId,
              `${heading || titleOf(currentSeries) || 'Serie'} – ${titleOf(entry)}`,
              currentSeries,
              entry,
            );
          }
          $('episodes').append(button);
          continue;
        }

        const seriesValue = entry.series || entry.series_number || entry.episode_id || null;
        const downloadableEntry = {
          ...entry,
          type: 'series',
          download_title: `${titleOf(currentSeries) || heading || 'Serie'} - ${titleOf(entry)}`,
        };
        appendEpisodeRow(downloadableEntry, seriesValue);
      }

      if (!values.length) $('episodes').textContent = 'Keine Staffeln oder Episoden gefunden.';
    } catch (error) {
      $('episodes').textContent = error.message;
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
      startDownload({ ...item, type: 'vod' });
    });
    card.querySelector('.card-body')?.append(button);
    return card;
  };

  renderSeriesLevelNeu = renderSeriesLevelWithDownloads;
  renderSeriesLevel = renderSeriesLevelWithDownloads;
  openSeries = async function openSeriesWithDownloads(item) {
    const id = cleanId(item.movie_id || item.series_id || item.id);
    if (!id) return showMessage('Keine Serien-ID vorhanden.');
    state.currentSeriesItem = item;
    await renderSeriesLevelWithDownloads(id, null, titleOf(item), item, null);
  };
})();
