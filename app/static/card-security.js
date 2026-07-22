(() => {
  const allowedImageProtocols = new Set(['http:', 'https:']);

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
    image.src = url.href;
    image.alt = '';
    image.loading = 'lazy';
    image.referrerPolicy = 'no-referrer';
    image.addEventListener('error', () => image.replaceWith(placeholderNode()), { once: true });
    return image;
  }

  createCard = function createSecureCard(item) {
    const card = document.createElement('article');
    card.className = 'card';
    card.append(imageNode(imageOf(item)));

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
})();
