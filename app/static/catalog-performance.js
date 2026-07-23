(() => {
  const PAGE_SIZE = 72;
  const allowedImageProtocols = new Set(['http:', 'https:']);
  let catalogGeneration = 0;
  let catalogItems = [];
  let catalogOffset = 0;

  const imageObserver = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const image = entry.target;
          imageObserver.unobserve(image);
          const source = image.dataset.src;
          if (!source) continue;
          delete image.dataset.src;
          image.src = source;
        }
      }, { rootMargin: '700px 0px', threshold: 0.01 })
    : null;

  function placeholderNode() {
    const placeholder = document.createElement('div');
    placeholder.className = 'placeholder';
    placeholder.textContent = '▶';
    return placeholder;
  }

  function imageNode(value) {
    const source = String(value || '').trim();
    if (!source) return placeholderNode();

    let url;
    try {
      url = new URL(source, window.location.href);
    } catch (_) {
      return placeholderNode();
    }
    if (!allowedImageProtocols.has(url.protocol)) return placeholderNode();

    const image = document.createElement('img');
    image.alt = '';
    image.loading = 'lazy';
    image.decoding = 'async';
    image.referrerPolicy = 'no-referrer';
    image.dataset.src = url.href;
    image.addEventListener('error', () => {
      imageObserver?.unobserve(image);
      image.replaceWith(placeholderNode());
    }, { once: true });

    if (imageObserver) imageObserver.observe(image);
    else {
      image.src = url.href;
      delete image.dataset.src;
    }
    return image;
  }

  window.cancelDeferredCardImages = function cancelDeferredCardImages(container) {
    if (!imageObserver || !container) return;
    container.querySelectorAll('img[data-src]').forEach((image) => imageObserver.unobserve(image));
  };

  createCard = function createDeferredCatalogCard(item) {
    const card = document.createElement('article');
    card.className = 'card';
    card.append(imageNode(item.image_proxy || item.image || imageOf(item)));

    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('h3');
    title.textContent = titleOf(item);

    const description = document.createElement('p');
    description.textContent = String(item.description || item.plot || item.descr || item.year || '').slice(0, 180);

    body.append(title, description);
    card.append(body);
    card.onclick = () => state.type === 'series' ? openSeries(item) : playItem(item);
    return card;
  };

  function clearCatalog() {
    const container = $('items');
    window.cancelDeferredCardImages(container);
    container.replaceChildren();
  }

  function renderNextBatch(generation) {
    if (generation !== catalogGeneration) return;
    const container = $('items');
    container.querySelector('.catalog-load-more')?.remove();

    const end = Math.min(catalogOffset + PAGE_SIZE, catalogItems.length);
    const fragment = document.createDocumentFragment();
    for (let index = catalogOffset; index < end; index += 1) {
      fragment.append(createCard(catalogItems[index]));
    }
    catalogOffset = end;
    container.append(fragment);

    if (catalogOffset < catalogItems.length) {
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'catalog-load-more';
      more.textContent = `Mehr anzeigen (${catalogOffset} von ${catalogItems.length})`;
      more.onclick = () => {
        more.disabled = true;
        requestAnimationFrame(() => renderNextBatch(generation));
      };
      container.append(more);
    }
  }

  loadContent = async function loadContentBatched() {
    if (!state.configured) return showMessage('Bitte zuerst Portal-URL und MAC-Adresse eintragen.');
    if (state.contentController) state.contentController.abort();

    const controller = new AbortController();
    const generation = ++catalogGeneration;
    state.contentController = controller;
    catalogItems = [];
    catalogOffset = 0;
    showMessage('Lade Inhalte …');
    clearCatalog();

    const search = encodeURIComponent($('search').value.trim());
    try {
      const values = normalizeArray(await api(
        `/api/content/${state.type}?category=${encodeURIComponent(state.category)}&search=${search}`,
        { signal: controller.signal },
      ));
      if (state.contentController !== controller || generation !== catalogGeneration) return;

      state.items = values;
      catalogItems = values;
      catalogOffset = 0;
      if (!values.length) {
        showMessage('Keine Inhalte gefunden.');
        return;
      }

      showMessage('');
      renderNextBatch(generation);
    } catch (error) {
      if (error.name !== 'AbortError' && generation === catalogGeneration) showMessage(error.message);
    } finally {
      if (state.contentController === controller) state.contentController = null;
    }
  };

  const style = document.createElement('style');
  style.textContent = `
    .catalog-load-more{grid-column:1/-1;justify-self:center;min-width:15rem;margin:1rem 0 2rem;padding:.8rem 1.1rem;border:1px solid rgba(255,255,255,.2);border-radius:.65rem;background:rgba(255,255,255,.08);color:inherit;font-weight:700;cursor:pointer}
    .catalog-load-more:hover{background:rgba(255,255,255,.14)}
    .catalog-load-more:disabled{opacity:.55;cursor:wait}
  `;
  document.head.append(style);
})();