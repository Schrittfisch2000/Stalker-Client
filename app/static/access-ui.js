(() => {
  const originalFetch = window.fetch.bind(window);
  let access = null;

  const request = async (path, options = {}) => {
    const response = await originalFetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
    return data;
  };

  const accessPromise = request('/api/access/me').then((value) => { access = value; return value; }).catch(() => null);

  const categoryId = (item) => String(item?.id ?? item?.genre_id ?? item?.category_id ?? item?.tv_genre_id ?? '');
  const normalize = (value) => Array.isArray(value) ? value : (Array.isArray(value?.data) ? value.data : (Array.isArray(value?.js) ? value.js : []));

  window.fetch = async (input, options = {}) => {
    let url = typeof input === 'string' ? input : input.url;
    const method = String(options.method || 'GET').toUpperCase();
    const currentAccess = await accessPromise;

    const contentMatch = url.match(/^\/api\/content\/(itv|vod|series)(\?.*)?$/);
    if (contentMatch && currentAccess?.role !== 'admin') {
      const type = contentMatch[1];
      const allowed = currentAccess?.categories?.[type] || [];
      if (!allowed.includes('*')) {
        const parsed = new URL(url, location.origin);
        if (parsed.searchParams.get('category') === '*' && allowed.length) parsed.searchParams.set('category', allowed[0]);
        url = parsed.pathname + parsed.search;
        input = url;
      }
    }

    const response = await originalFetch(input, options);

    const categoriesMatch = url.match(/^\/api\/categories\/(itv|vod|series)/);
    if (categoriesMatch && response.ok && currentAccess?.role !== 'admin') {
      const type = categoriesMatch[1];
      const allowed = currentAccess?.categories?.[type] || [];
      if (!allowed.includes('*')) {
        const data = await response.clone().json();
        const filtered = normalize(data).filter((item) => allowed.includes(categoryId(item)));
        return new Response(JSON.stringify(filtered), { status: response.status, headers: { 'Content-Type': 'application/json' } });
      }
    }

    return response;
  };

  async function openAccessDialog(username) {
    let dialog = document.getElementById('accessDialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'accessDialog';
      dialog.className = 'access-dialog';
      dialog.innerHTML = '<div class="access-head"><div><h2>Kategorien freigeben</h2><p data-access-user></p></div><button type="button" data-close>×</button></div><div data-access-groups></div><div class="access-actions"><button type="button" data-all>Alle erlauben</button><button class="auth-primary" type="button" data-save>Speichern</button></div><div class="auth-error" data-error></div>';
      document.body.append(dialog);
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
    }
    dialog.dataset.username = username;
    dialog.querySelector('[data-access-user]').textContent = `Freigaben für ${username}`;
    dialog.querySelector('[data-error]').textContent = '';
    const [saved, itv, vod, series] = await Promise.all([
      request(`/api/users/${encodeURIComponent(username)}/access`),
      request('/api/categories/itv'), request('/api/categories/vod'), request('/api/categories/series')
    ]);
    const groups = dialog.querySelector('[data-access-groups]');
    groups.innerHTML = '';
    for (const [type, label, values] of [['itv', 'Live-TV', itv], ['vod', 'Filme', vod], ['series', 'Serien', series]]) {
      const section = document.createElement('section');
      section.className = 'access-group';
      section.innerHTML = `<h3>${label}</h3><label class="access-all"><input type="checkbox" data-type="${type}" value="*"> Alle Kategorien</label><div class="access-list"></div>`;
      const allowed = saved.categories?.[type] || [];
      section.querySelector('[value="*"]').checked = allowed.includes('*');
      const list = section.querySelector('.access-list');
      for (const category of normalize(values)) {
        const id = categoryId(category);
        if (!id) continue;
        const title = category.title || category.name || category.genre_name || category.category_name || `Kategorie ${id}`;
        const labelNode = document.createElement('label');
        labelNode.innerHTML = '<input type="checkbox"><span></span>';
        labelNode.querySelector('input').dataset.type = type;
        labelNode.querySelector('input').value = id;
        labelNode.querySelector('input').checked = allowed.includes(id);
        labelNode.querySelector('span').textContent = title;
        list.append(labelNode);
      }
      groups.append(section);
    }
    dialog.querySelector('[data-all]').onclick = () => dialog.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = input.value === '*'; });
    dialog.querySelector('[data-save]').onclick = async () => {
      const categories = { itv: [], vod: [], series: [] };
      dialog.querySelectorAll('input[type="checkbox"]:checked').forEach((input) => categories[input.dataset.type].push(input.value));
      try {
        await request(`/api/users/${encodeURIComponent(username)}/access`, { method: 'PUT', body: JSON.stringify({ categories }) });
        dialog.close();
      } catch (error) { dialog.querySelector('[data-error]').textContent = error.message; }
    };
    dialog.showModal();
  }

  function addAccessButtons() {
    document.querySelectorAll('.user-row').forEach((row) => {
      if (row.querySelector('[data-access]')) return;
      const username = row.querySelector('strong')?.textContent?.trim();
      const actions = row.lastElementChild;
      if (!username || !actions) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.access = '1';
      button.textContent = 'Freigaben';
      button.onclick = () => openAccessDialog(username);
      actions.prepend(button);
    });
  }

  const style = document.createElement('style');
  style.textContent = '.access-dialog{width:min(900px,95vw);color:#fff;background:#151515;border:1px solid #333;border-radius:12px;padding:22px}.access-head{display:flex;justify-content:space-between;gap:1rem}.access-head h2{margin:0}.access-head button{background:transparent;border:0;color:#fff;font-size:2rem}.access-group{margin:1rem 0;padding:1rem;background:#202020;border-radius:8px}.access-group h3{margin-top:0}.access-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.5rem;max-height:14rem;overflow:auto}.access-list label,.access-all{display:flex;gap:.45rem;align-items:center}.access-actions{display:flex;justify-content:flex-end;gap:.7rem}.access-actions button{padding:.7rem 1rem;border:0;border-radius:7px}';
  document.head.append(style);

  document.addEventListener('DOMContentLoaded', async () => {
    await accessPromise;
    const observer = new MutationObserver(addAccessButtons);
    observer.observe(document.body, { childList: true, subtree: true });
    addAccessButtons();
  });
})();
