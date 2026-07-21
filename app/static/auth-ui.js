(() => {
  const style = document.createElement('style');
  style.textContent = `
    .auth-overlay{position:fixed;inset:0;background:#090909;z-index:9999;display:grid;place-items:center;padding:24px}.auth-card{width:min(420px,100%);background:#171717;border:1px solid #333;border-radius:14px;padding:26px;color:#fff;box-shadow:0 24px 80px #000}.auth-card h2{margin:0 0 8px}.auth-card p{color:#aaa}.auth-card input,.auth-card select{width:100%;box-sizing:border-box;margin:7px 0;padding:12px;background:#0d0d0d;border:1px solid #444;color:#fff;border-radius:8px}.auth-card button,.user-admin button{padding:10px 14px;border:0;border-radius:8px;cursor:pointer}.auth-primary{background:#e50914;color:#fff;font-weight:700;margin-top:10px}.auth-card .auth-primary{width:100%}.auth-error{color:#ff6868;min-height:20px}.auth-success{color:#46d369;min-height:20px}.user-button{width:auto!important;min-width:0;height:2.5rem;padding:0 .85rem!important;border-radius:999px!important;background:#222!important;color:#fff!important;white-space:nowrap;flex:0 0 auto}.user-name-button{max-width:10rem;overflow:hidden;text-overflow:ellipsis}.logout-button{font-size:.86rem}.user-admin{width:min(820px,95vw);color:#fff;background:#151515;border:1px solid #333;border-radius:12px;padding:0}.user-admin::backdrop{background:#000b}.user-admin-inner{padding:22px}.user-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.admin-tabs{display:flex;gap:8px;margin:18px 0 8px}.admin-tabs button{background:#292929;color:#ddd}.admin-tabs button.active{background:#e50914;color:#fff}.admin-panel[hidden]{display:none}.user-grid{display:grid;grid-template-columns:1fr 1fr 140px auto;gap:8px;align-items:center;margin:14px 0}.user-row{display:grid;grid-template-columns:1fr 120px 90px auto;gap:8px;align-items:center;padding:10px 0;border-top:1px solid #333}.user-row button{background:#333;color:#fff}.user-row .danger{background:#7c1118}.user-note{color:#aaa;font-size:.9rem}.portal-form{display:grid;gap:12px;margin-top:16px}.portal-form label{display:grid;gap:6px;color:#ddd}.portal-form input{width:100%;box-sizing:border-box;padding:12px;background:#0d0d0d;border:1px solid #444;color:#fff;border-radius:8px}.portal-actions{display:flex;gap:10px;flex-wrap:wrap}.portal-actions button{background:#333;color:#fff}.portal-actions .auth-primary{background:#e50914}.close-admin{background:#292929!important;color:#fff!important;font-size:1.1rem}@media(max-width:1100px){.header-actions{flex-wrap:wrap;justify-content:flex-end}.header-actions input{order:1;flex:1 1 14rem}.status-badge{order:2}.user-name-button,.logout-button,#openSettings{order:3}}@media(max-width:700px){.user-grid,.user-row{grid-template-columns:1fr}.user-row{padding:14px 0}.user-name-button{max-width:7rem}.logout-button{font-size:0}.logout-button::after{content:'↪';font-size:1rem}.header-actions{gap:.4rem}.header-actions input{flex-basis:100%;width:100%!important}}
  `;
  document.head.append(style);

  async function request(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
    return data;
  }

  function showLogin(initialized) {
    const overlay = document.createElement('div');
    overlay.className = 'auth-overlay';
    overlay.innerHTML = `<form class="auth-card"><h2>${initialized ? 'Anmelden' : 'Administrator einrichten'}</h2><p>${initialized ? 'Melde dich an, um den Stalker Client zu verwenden.' : 'Erstelle das erste Administratorkonto.'}</p><input name="username" autocomplete="username" placeholder="Benutzername" required minlength="3"><input name="password" type="password" autocomplete="${initialized ? 'current-password' : 'new-password'}" placeholder="Passwort" required minlength="8"><div class="auth-error"></div><button class="auth-primary" type="submit">${initialized ? 'Anmelden' : 'Einrichten'}</button></form>`;
    document.body.append(overlay);
    overlay.querySelector('form').onsubmit = async (event) => {
      event.preventDefault();
      const formElement = event.currentTarget;
      const form = new FormData(formElement);
      const error = overlay.querySelector('.auth-error');
      error.textContent = '';
      try {
        await request(initialized ? '/api/auth/login' : '/api/auth/setup', { method: 'POST', body: JSON.stringify({ username: form.get('username'), password: form.get('password') }) });
        location.reload();
      } catch (exc) { error.textContent = exc.message; }
    };
  }

  function switchPanel(dialog, name) {
    dialog.querySelectorAll('.admin-tabs button').forEach((button) => button.classList.toggle('active', button.dataset.panel === name));
    dialog.querySelectorAll('.admin-panel').forEach((panel) => { panel.hidden = panel.dataset.panel !== name; });
  }

  async function loadPortalForm(dialog) {
    const error = dialog.querySelector('[data-portal-error]');
    const success = dialog.querySelector('[data-portal-success]');
    error.textContent = '';
    success.textContent = '';
    try {
      const config = await request('/api/config');
      dialog.querySelector('[name="portal_url"]').value = config.portal_url || '';
      dialog.querySelector('[name="portal_mac"]').value = config.portal_mac || '';
    } catch (exc) { error.textContent = exc.message; }
  }

  async function openAdmin(current, initialPanel = 'users') {
    let dialog = document.getElementById('userAdminDialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'userAdminDialog';
      dialog.className = 'user-admin';
      dialog.innerHTML = `<div class="user-admin-inner"><div class="user-head"><div><h2>Administration</h2><div class="user-note"></div></div><button class="close-admin" type="button" data-close>×</button></div><div class="admin-tabs"><button type="button" data-panel="users">Benutzer</button><button type="button" data-panel="portal">Portal</button></div><section class="admin-panel" data-panel="users"><form class="user-grid" data-user-form><input name="username" placeholder="Benutzername" minlength="3" required><input name="password" type="password" placeholder="Passwort (mind. 8 Zeichen)" minlength="8" required><select name="role"><option value="user">Benutzer</option><option value="admin">Administrator</option></select><button class="auth-primary" type="submit">Anlegen</button></form><div class="auth-error" data-user-error></div><div data-users></div></section><section class="admin-panel" data-panel="portal" hidden><form class="portal-form" data-portal-form><label>Portal-URL<input name="portal_url" type="url" required placeholder="http://portal.example/stalker_portal/c/"></label><label>MAC-Adresse<input name="portal_mac" required pattern="[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}" placeholder="00:1A:79:00:00:00"></label><div class="portal-actions"><button class="auth-primary" type="submit">Portal speichern</button><button type="button" data-test-portal>Verbindung testen</button></div><div class="auth-error" data-portal-error></div><div class="auth-success" data-portal-success></div></form></section></div>`;
      document.body.append(dialog);
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      dialog.querySelectorAll('.admin-tabs button').forEach((button) => { button.onclick = () => switchPanel(dialog, button.dataset.panel); });

      dialog.querySelector('[data-user-form]').onsubmit = async (event) => {
        event.preventDefault();
        const formElement = event.currentTarget;
        const form = new FormData(formElement);
        const error = dialog.querySelector('[data-user-error]');
        error.textContent = '';
        try {
          await request('/api/users', { method: 'POST', body: JSON.stringify({ username: form.get('username'), password: form.get('password'), role: form.get('role') }) });
          formElement.reset();
          await renderUsers(dialog, current);
        } catch (exc) { error.textContent = exc.message; }
      };

      dialog.querySelector('[data-portal-form]').onsubmit = async (event) => {
        event.preventDefault();
        const formElement = event.currentTarget;
        const form = new FormData(formElement);
        const error = dialog.querySelector('[data-portal-error]');
        const success = dialog.querySelector('[data-portal-success]');
        error.textContent = '';
        success.textContent = '';
        try {
          await request('/api/config', { method: 'PUT', body: JSON.stringify({ portal_url: form.get('portal_url'), portal_mac: form.get('portal_mac') }) });
          success.textContent = 'Portal wurde gespeichert.';
          location.reload();
        } catch (exc) { error.textContent = exc.message; }
      };

      dialog.querySelector('[data-test-portal]').onclick = async () => {
        const error = dialog.querySelector('[data-portal-error]');
        const success = dialog.querySelector('[data-portal-success]');
        error.textContent = '';
        success.textContent = 'Verbindung wird geprüft …';
        try {
          await request('/api/status');
          success.textContent = 'Portalverbindung erfolgreich.';
        } catch (exc) {
          success.textContent = '';
          error.textContent = exc.message;
        }
      };
    }
    dialog.querySelector('.user-note').textContent = `Angemeldet als ${current.username} (${current.role === 'admin' ? 'Administrator' : 'Benutzer'})`;
    await renderUsers(dialog, current);
    await loadPortalForm(dialog);
    switchPanel(dialog, initialPanel);
    dialog.showModal();
  }

  async function renderUsers(dialog, current) {
    const users = await request('/api/users');
    const container = dialog.querySelector('[data-users]');
    container.innerHTML = '';
    for (const user of users) {
      const row = document.createElement('div');
      row.className = 'user-row';
      row.innerHTML = `<strong></strong><select><option value="user">Benutzer</option><option value="admin">Administrator</option></select><label><input type="checkbox"> aktiv</label><div><button data-save>Speichern</button> <button class="danger" data-delete>Löschen</button></div>`;
      row.querySelector('strong').textContent = user.username;
      row.querySelector('select').value = user.role;
      row.querySelector('input').checked = user.active;
      row.querySelector('[data-save]').onclick = async () => {
        await request(`/api/users/${encodeURIComponent(user.username)}`, { method: 'PUT', body: JSON.stringify({ role: row.querySelector('select').value, active: row.querySelector('input').checked }) });
        await renderUsers(dialog, current);
      };
      row.querySelector('[data-delete]').disabled = user.username === current.username;
      row.querySelector('[data-delete]').onclick = async () => {
        if (!confirm(`Benutzer ${user.username} wirklich löschen?`)) return;
        await request(`/api/users/${encodeURIComponent(user.username)}`, { method: 'DELETE' });
        await renderUsers(dialog, current);
      };
      container.append(row);
    }
  }

  async function init() {
    let status;
    try { status = await request('/api/auth/status'); } catch (_) { return; }
    if (!status.authenticated) return showLogin(status.initialized);

    const actions = document.querySelector('.header-actions');
    if (!actions) return;
    const userButton = document.createElement('button');
    userButton.className = 'icon-button user-button user-name-button';
    userButton.textContent = status.user.username;
    userButton.title = status.user.role === 'admin' ? 'Administration öffnen' : 'Angemeldeter Benutzer';
    if (status.user.role === 'admin') userButton.onclick = () => openAdmin(status.user, 'users');
    actions.insertBefore(userButton, actions.lastElementChild);

    const logout = document.createElement('button');
    logout.className = 'icon-button user-button logout-button';
    logout.textContent = 'Abmelden';
    logout.title = 'Abmelden';
    logout.onclick = async () => { await request('/api/auth/logout', { method: 'POST' }); location.reload(); };
    actions.insertBefore(logout, actions.lastElementChild);

    if (status.user.role === 'admin') {
      const settingsButton = document.getElementById('openSettings');
      if (settingsButton) {
        settingsButton.title = 'Portalverwaltung';
        settingsButton.onclick = (event) => { event.preventDefault(); event.stopImmediatePropagation(); openAdmin(status.user, 'portal'); };
      }
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();