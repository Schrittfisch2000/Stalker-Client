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

function serienFolgenAnzeigen(serie, staffelEintrag, staffel, ueberschrift) {
  const folgen = serienFolgenwerte(staffelEintrag);
  if (!folgen.length) return false;

  const grundBefehl = commandOf(staffelEintrag) || commandOf(serie);
  $('seriesTitle').textContent = ueberschrift;
  $('episodes').innerHTML = '';

  for (const folge of folgen) {
    const nummer = String(folge).replace(/^episode\s*/i, '').trim();
    const eintrag = {
      ...serie,
      ...staffelEintrag,
      name: `Episode ${nummer}`,
      title: `Episode ${nummer}`,
      episode_name: `Episode ${nummer}`,
      cmd: grundBefehl,
      command: grundBefehl,
      series: nummer,
      series_number: nummer,
      episode_id: nummer,
      season_id: staffel,
      season_number: staffel,
    };
    const button = document.createElement('button');
    button.textContent = `Episode ${nummer}`;
    button.onclick = () => {
      $('seriesDialog').close();
      playItem(eintrag, nummer);
    };
    $('episodes').append(button);
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
      const button = document.createElement('button');
      button.textContent = titleOf(entry);
      if (looksLikeSeason(entry)) {
        const seasonId = seasonOf(entry);
        if (!seasonId) {
          button.disabled = true;
          button.title = 'Das Portal hat keine Staffelnummer geliefert.';
        } else {
          button.onclick = () => renderSeriesLevelNeu(seriesId, seasonId, `${heading || titleOf(serienEintrag) || 'Serie'} – ${titleOf(entry)}`, serienEintrag, entry);
        }
      } else {
        const seriesValue = entry.series || entry.series_number || entry.episode_id || null;
        button.onclick = () => {
          $('seriesDialog').close();
          playItem(entry, seriesValue);
        };
      }
      $('episodes').append(button);
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
  state.currentSeriesItem = item;
  await renderSeriesLevelNeu(id, null, titleOf(item), item, null);
};
