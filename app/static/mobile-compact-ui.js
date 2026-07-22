(() => {
  const mobileQuery = window.matchMedia('(max-width: 600px)');
  const categories = document.getElementById('categories');
  const tabs = document.getElementById('tabs');
  if (!categories || !tabs) return;

  let select = null;
  let syncing = false;

  function activeMediaType() {
    return tabs.querySelector('button.active')?.dataset.type || 'itv';
  }

  function syncMediaType() {
    document.body.dataset.mediaType = activeMediaType();
  }

  function ensureSelect() {
    if (select && select.isConnected) return select;
    select = document.createElement('select');
    select.className = 'mobile-category-select';
    select.setAttribute('aria-label', 'Kategorie auswählen');
    select.addEventListener('change', () => {
      const buttons = [...categories.querySelectorAll('button')];
      const target = buttons[Number(select.value)];
      if (target) target.click();
    });
    categories.before(select);
    return select;
  }

  function syncCategories() {
    if (syncing) return;
    syncing = true;
    const target = ensureSelect();
    const buttons = [...categories.querySelectorAll('button')];
    target.textContent = '';

    if (!buttons.length) {
      const option = document.createElement('option');
      option.textContent = categories.textContent.trim() || 'Kategorien werden geladen …';
      option.value = '';
      target.append(option);
      target.disabled = true;
    } else {
      buttons.forEach((button, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = button.textContent.trim();
        option.selected = button.classList.contains('active');
        target.append(option);
      });
      target.disabled = false;
    }

    categories.classList.toggle('mobile-enhanced', mobileQuery.matches);
    target.hidden = !mobileQuery.matches;
    syncing = false;
  }

  const categoryObserver = new MutationObserver(syncCategories);
  categoryObserver.observe(categories, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });

  const tabObserver = new MutationObserver(syncMediaType);
  tabObserver.observe(tabs, { subtree: true, attributes: true, attributeFilter: ['class'] });

  mobileQuery.addEventListener?.('change', syncCategories);
  tabs.addEventListener('click', () => requestAnimationFrame(syncMediaType));

  syncMediaType();
  syncCategories();
})();
