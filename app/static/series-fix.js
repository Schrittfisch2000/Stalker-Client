function serienFolgenwerte(eintrag) {
  const kandidaten = [
    eintrag?.series,
    eintrag?.episodes,
    eintrag?.episode_list,
    eintrag?.series_list,
    eintrag?.season_series,
  ];

  for (const wert of kandidaten) {
    if (Array.isArray(wert)) {
      const folgen = wert.map((teil) => String(teil).trim()).filter(Boolean);
      if (folgen.length) return folgen;
    }
    if (wert && typeof wert === 'object') {
      const folgen = Object.values(wert).flatMap((teil) => Array.isArray(teil) ? teil : [teil]).map((teil) => String(teil).trim()).filter(Boolean);
      if (folgen.length) return folgen;
    }
    if (typeof wert === 'string' && wert.trim()) {
      const folgen = wert.split(/[,;|\s]+/).map((teil) => teil.trim()).filter((teil) => teil && teil !== '.');
      if (folgen.length) return folgen;
    }
  }
  return [];
}

function serienFolgenNummer(eintrag) {
  const kandidaten = [
    eintrag?.episode_id,
    eintrag?.episode_number,
    eintrag?.episode,
    eintrag?.series_number,
    eintrag?.series,
  ];
  for (const wert of kandidaten) {
    if (Array.isArray(wert)) {
      if (wert.length !== 1) continue;
      const nummer = String(wert[0] ?? '').trim();
      if (nummer) return nummer;
      continue;
    }
    if (wert && typeof wert === 'object') continue;
    const nummer = String(wert ?? '').trim();
    if (nummer && nummer !== '.' && nummer.toLowerCase() !== 'null') return nummer;
  }
  return null;
}

function serienEpisodeZeile(eintrag, serienWert, beschriftung, downloadTitel = '') {
  const row = document.createElement('div');
  row.className = 'episode-row';

  const playButton = document.createElement('button');
  playButton.type = 'button';
  playButton.className = 'episode-play';
  playButton.textContent = beschriftung;
  playButton.onclick = () => {
    $('seriesDialog').close();
    playItem(eintrag, serienWert);
  };

  const downloadButton = document.createElement('button');
  downloadButton.type = 'button';
  downloadButton.className = 'download-button episode-download';
  downloadButton.textContent = '↓';
  downloadButton.title = `${beschriftung} herunterladen`;
  downloadButton.setAttribute('aria-label', downloadButton.title);
  downloadButton.onclick = () => {
    if (typeof window.downloadItem !== 'function') {
      showMessage('Die Download-Funktion ist noch nicht geladen. Bitte die Seite neu laden.');
      return;
    }
    window.downloadItem({
      ...eintrag,
      type: 'series',
      category: eintrag.category || state.category,
      download_title: downloadTitel || eintrag.download_title || beschriftung,
    }, serienWert);
  };

  row.append(playButton, downloadButton);
  $('episodes').append(row);
}

function serienFolgenAnzeigen(serie, staffelEintrag, staffel, ueberschrift) {
  const folgen = serienFolgenwerte(staffelEintrag);
  if (!folgen.length) return false;

  const grundBefehl = commandOf(staffelEintrag) || commandOf(serie);
  const serienId = cleanId(serie.movie_id || serie.series_id || serie.id);
  $('seriesTitle').textContent = ueberschrift;
  $('episodes').innerHTML = '';

  for (const folge of folgen) {
    const nummer = String(folge).replace(/^episode\s*/i, '').trim();
    const beschriftung = `Episode ${nummer}`;
    const eintrag = {
      ...serie,
      ...staffelEintrag,
      type: 'series',
      category: serie.category || state.category,
      series_parent_id: serienId,
      name: beschriftung,
      title: beschriftung,
      episode_name: beschriftung,
      cmd: grundBefehl,
      command: grundBefehl,
      series: nummer,
      series_number: nummer,
      episode_id: nummer,
      season_id: staffel,
      season_number: staffel,
    };
    serienEpisodeZeile(
      eintrag,
      nummer,
      beschriftung,
      `${titleOf(serie)} - Staffel ${staffel} - ${beschriftung}`,
    );
  }
  return true;
}

async function renderSeriesLevelNeu(seriesId, season = null, heading = '', serie = null, staffelEintrag = null) {
  const serienEintrag = serie || state.currentSeriesItem || {};
  $('seriesTitle').textContent = heading || 'Episoden';
  $('episodes').innerHTML = '<span class="muted">Lade …</span>';
  $('seriesDialog').showModal();

  if (season && staffelEintrag && serienFolgenAnzeigen(serienEintrag, staffelEintrag, season, heading || `Staffel ${season}`)) return;

  const suffix = season ? `?season=${encodeURIComponent(season)}` : '';
  try {
    const values = normalizeArray(await api(`/api/episodes/${encodeURIComponent(seriesId)}${suffix}`));
    $('episodes').innerHTML = '';

    if (season && values.length === 1 && looksLikeSeason(values[0]) && String(seasonOf(values[0])) === String(season)) {
      if (serienFolgenAnzeigen(serienEintrag, values[0], season, heading || `Staffel ${season}`)) return;
      if (staffelEintrag && serienFolgenAnzeigen(serienEintrag, staffelEintrag, season, heading || `Staffel ${season}`)) return;
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
          button.onclick = () => renderSeriesLevelNeu(seriesId, seasonId, `${heading || titleOf(serienEintrag) || 'Serie'} – ${titleOf(entry)}`, serienEintrag, entry);
        }
        $('episodes').append(button);
        continue;
      }

      const serienWert = serienFolgenNummer(entry);
      if (!serienWert) {
        const button = document.createElement('button');
        button.textContent = `${titleOf(entry)} – keine Episodennummer`;
        button.disabled = true;
        button.title = 'Das Portal hat für diesen Eintrag keine eindeutige Episodennummer geliefert.';
        $('episodes').append(button);
        continue;
      }

      const eintrag = {
        ...entry,
        type: 'series',
        category: serienEintrag.category || state.category,
        series_parent_id: cleanId(seriesId),
      };
      serienEpisodeZeile(
        eintrag,
        serienWert,
        titleOf(entry),
        `${titleOf(serienEintrag) || heading || 'Serie'} - ${titleOf(entry)}`,
      );
    }

    if (!values.length) $('episodes').textContent = 'Keine Staffeln oder Episoden gefunden.';
  } catch (error) {
    $('episodes').textContent = error.message;
  }
}

renderSeriesLevel = renderSeriesLevelNeu;
openSeries = async function (item) {
  const id = cleanId(item.movie_id || item.series_id || item.id);
  if (!id) return showMessage('Keine Serien-ID vorhanden.');
  state.currentSeriesItem = {
    ...item,
    type: 'series',
    category: item.category || state.category,
    series_parent_id: id,
  };
  await renderSeriesLevelNeu(id, null, titleOf(item), state.currentSeriesItem, null);
};
