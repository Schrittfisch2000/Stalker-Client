(() => {
  const request = async (path, options = {}) => {
    const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
    return data;
  };

  const style = document.createElement('style');
  style.textContent = `
    .portal-select{max-width:180px;padding:.65rem .8rem;border:1px solid #444;border-radius:999px;background:#202020;color:#fff}
    .portal-admin-list{display:grid;gap:12px;margin-top:16px}.portal-admin-row{display:grid;grid-template-columns:1.2fr 1.6fr 1fr auto;gap:10px;align-items:center;padding:12px;border:1px solid #333;border-radius:10px;background:#101010}.portal-admin-row input{width:100%;box-sizing:border-box;padding:10px;background:#080808;border:1px solid #444;color:#fff;border-radius:7px}.portal-admin-row .portal-row-actions{display:flex;gap:6px;flex-wrap:wrap}.portal-admin-row button{background:#333;color:#fff}.portal-admin-row button.danger{background:#7c1118}.portal-admin-row button.default{background:#176b32}.portal-create{display:grid;grid-template-columns:1fr 1.5fr 1fr auto;gap:10px;margin:14px 0}.portal-create input{padding:11px;background:#0d0d0d;border:1px solid #444;color:#fff;border-radius:8px}.portal-assignment{margin-top:18px;padding-top:16px;border-top:1px solid #333}.portal-assignment-grid{display:grid;gap:10px}.portal-assignment-row{display:grid;grid-template-columns:180px 1fr auto;gap:10px;align-items:center}.portal-checks{display:flex;gap:10px;flex-wrap:wrap}.portal-checks label{display:flex;gap:5px;align-items:center;background:#222;padding:7px 9px;border-radius:7px}.portal-blocked{padding:24px;border:1px solid #633;border-radius:12px;background:#261416;color:#fff}.portal-blocked strong{display:block;margin-bottom:8px;font-size:1.1rem}@media(max-width:850px){.portal-admin-row,.portal-create,.portal-assignment-row{grid-template-columns:1fr}.portal-select{max-width:130px}}
  `;
  document.head.append(style);

  function blockCatalogWithoutPortal() {
    const categories = document.getElementById('categories');
    const items = document.getElementById('items');
    const message = document.getElementById('message');
    const search = document.getElementById('search');
    const status = document.getElementById('status');
    if (categories) categories.innerHTML = '';
    if (items) items.innerHTML = '';
    if (search) { search.value = ''; search.disabled = true; }
    document.querySelectorAll('#tabs button').forEach((button) => { button.disabled = true; });
    if (status) {
      status.textContent = 'Kein Portal zugewiesen';
      status.className = 'status-badge error';
    }
    if (message) {
      message.hidden = false;
      message.classList.add('portal-blocked');
      message.innerHTML = '<strong>Kein Portal zugewiesen</strong>Diesem Benutzer wurde kein Portal zugewiesen. Bitte wende dich an einen Administrator.';
    }
  }

  async function addPortalSelector() {
    let auth;
    try { auth = await request('/api/auth/status'); } catch (_) { return; }
    if (!auth.authenticated) return;
    let data;
    try { data = await request('/api/portals'); } catch (_) { return; }
    if (!data.portals?.length) {
      if (auth.user?.role !== 'admin') blockCatalogWithoutPortal();
      return;
    }
    const actions = document.querySelector('.header-actions');
    if (!actions || document.getElementById('portalSelect')) return;
    const select = document.createElement('select');
    select.id = 'portalSelect';
    select.className = 'portal-select';
    select.title = 'Aktives Portal auswählen';
    for (const portal of data.portals) {
      const option = document.createElement('option');
      option.value = portal.id;
      option.textContent = portal.name;
      option.selected = portal.id === data.selected_portal_id;
      select.append(option);
    }
    select.onchange = async () => {
      select.disabled = true;
      try {
        await request('/api/portals/select', { method: 'POST', body: JSON.stringify({ portal_id: select.value }) });
        location.reload();
      } catch (error) {
        alert(error.message);
        select.disabled = false;
      }
    };
    actions.insertBefore(select, actions.firstElementChild);
  }

  async function renderPortalAdmin(dialog) {
    const panel = dialog.querySelector('[data-panel="portal"].admin-panel');
    if (!panel || panel.dataset.multiPortalReady === '1') return;
    panel.dataset.multiPortalReady = '1';
    panel.innerHTML = `
      <h3>Portale verwalten</h3>
      <p class="user-note">Mehrere Stalker-/MAG-Portale verwalten und Benutzern zuweisen.</p>
      <form class="portal-create" data-create-portal>
        <input name="name" placeholder="Portalname" required>
        <input name="portal_url" type="url" placeholder="http://portal.example/stalker_portal/c/" required>
        <input name="portal_mac" placeholder="00:1A:79:00:00:00" pattern="[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}" required>
        <button class="auth-primary" type="submit">Hinzufügen</button>
      </form>
      <div class="auth-error" data-portals-error></div>
      <div class="auth-success" data-portals-success></div>
      <div class="portal-admin-list" data-portals-list></div>
      <section class="portal-assignment"><h3>Benutzer-Zuweisungen</h3><div class="portal-assignment-grid" data-assignments></div></section>
    `;
    panel.querySelector('[data-create-portal]').onsubmit = async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const values = new FormData(form);
      try {
        await request('/api/portals', { method: 'POST', body: JSON.stringify({ name: values.get('name'), portal_url: values.get('portal_url'), portal_mac: values.get('portal_mac'), active: true }) });
        form.reset();
        await refreshPortalAdmin(panel);
      } catch (error) { panel.querySelector('[data-portals-error]').textContent = error.message; }
    };
    await refreshPortalAdmin(panel);
  }

  async function refreshPortalAdmin(panel) {
    const error = panel.querySelector('[data-portals-error]');
    const success = panel.querySelector('[data-portals-success]');
    error.textContent = '';
    success.textContent = '';
    try {
      const [portalData, users] = await Promise.all([request('/api/portals'), request('/api/users')]);
      const list = panel.querySelector('[data-portals-list]');
      list.innerHTML = '';
      for (const portal of portalData.portals) {
        const row = document.createElement('div');
        row.className = 'portal-admin-row';
        row.innerHTML = `<input data-name><input data-url><input data-mac><div class="portal-row-actions"><label><input type="checkbox" data-active> aktiv</label><button data-save>Speichern</button><button data-default>Standard</button><button class="danger" data-delete>Löschen</button></div>`;
        row.querySelector('[data-name]').value = portal.name;
        row.querySelector('[data-url]').value = portal.portal_url || '';
        row.querySelector('[data-mac]').value = portal.portal_mac || '';
        row.querySelector('[data-active]').checked = portal.active;
        const defaultButton = row.querySelector('[data-default]');
        if (portal.id === portalData.default_portal_id) { defaultButton.textContent = 'Standard ✓'; defaultButton.classList.add('default'); defaultButton.disabled = true; }
        row.querySelector('[data-save]').onclick = async () => {
          await request(`/api/portals/${encodeURIComponent(portal.id)}`, { method: 'PUT', body: JSON.stringify({ name: row.querySelector('[data-name]').value, portal_url: row.querySelector('[data-url]').value, portal_mac: row.querySelector('[data-mac]').value, active: row.querySelector('[data-active]').checked }) });
          success.textContent = 'Portal gespeichert.';
          await refreshPortalAdmin(panel);
        };
        defaultButton.onclick = async () => { await request(`/api/portals/${encodeURIComponent(portal.id)}/default`, { method: 'PUT' }); await refreshPortalAdmin(panel); };
        row.querySelector('[data-delete]').onclick = async () => {
          if (!confirm(`Portal „${portal.name}“ wirklich löschen?`)) return;
          await request(`/api/portals/${encodeURIComponent(portal.id)}`, { method: 'DELETE' });
          await refreshPortalAdmin(panel);
        };
        list.append(row);
      }
      if (!portalData.portals.length) list.textContent = 'Noch kein Portal vorhanden.';
      await renderAssignments(panel, users, portalData.portals);
    } catch (exception) { error.textContent = exception.message; }
  }

  async function renderAssignments(panel, users, portals) {
    const container = panel.querySelector('[data-assignments]');
    container.innerHTML = '';
    for (const user of users.filter((entry) => entry.role !== 'admin')) {
      const assignment = await request(`/api/users/${encodeURIComponent(user.username)}/portals`);
      const row = document.createElement('div');
      row.className = 'portal-assignment-row';
      row.innerHTML = '<strong></strong><div class="portal-checks"></div><button>Speichern</button>';
      row.querySelector('strong').textContent = user.username;
      const checks = row.querySelector('.portal-checks');
      for (const portal of portals) {
        const label = document.createElement('label');
        label.innerHTML = '<input type="checkbox"><span></span>';
        label.querySelector('input').value = portal.id;
        label.querySelector('input').checked = assignment.portal_ids.includes(portal.id);
        label.querySelector('span').textContent = portal.name;
        checks.append(label);
      }
      row.querySelector('button').onclick = async () => {
        const portalIds = [...checks.querySelectorAll('input:checked')].map((input) => input.value);
        await request(`/api/users/${encodeURIComponent(user.username)}/portals`, { method: 'PUT', body: JSON.stringify({ portal_ids: portalIds }) });
        panel.querySelector('[data-portals-success]').textContent = `Zuweisungen für ${user.username} gespeichert.`;
      };
      container.append(row);
    }
    if (!container.children.length) container.textContent = 'Keine normalen Benutzer vorhanden.';
  }

  const observer = new MutationObserver(() => {
    const dialog = document.getElementById('userAdminDialog');
    if (dialog) renderPortalAdmin(dialog).catch(() => {});
  });

  document.addEventListener('DOMContentLoaded', () => {
    addPortalSelector();
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();
