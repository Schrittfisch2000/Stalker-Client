(() => {
  const style = document.createElement('style');
  style.textContent = `
    .auth-overlay{position:fixed;inset:0;background:#090909;z-index:9999;display:grid;place-items:center;padding:24px}.auth-card{width:min(420px,100%);background:#171717;border:1px solid #333;border-radius:14px;padding:26px;color:#fff;box-shadow:0 24px 80px #000}.auth-card h2{margin:0 0 8px}.auth-card p{color:#aaa}.auth-card input,.auth-card select{width:100%;box-sizing:border-box;margin:7px 0;padding:12px;background:#0d0d0d;border:1px solid #444;color:#fff;border-radius:8px}.auth-card button,.user-admin button{padding:10px 14px;border:0;border-radius:8px;cursor:pointer}.auth-primary{background:#e50914;color:#fff;font-weight:700;width:100%;margin-top:10px}.auth-error{color:#ff6868;min-height:20px}.user-button{width:auto!important;min-width:0;height:2.5rem;padding:0 .85rem!important;border-radius:999px!important;background:#222!important;color:#fff!important;white-space:nowrap;flex:0 0 auto}.user-name-button{max-width:10rem;overflow:hidden;text-overflow:ellipsis}.logout-button{font-size:.86rem}.user-admin{width:min(760px,95vw);color:#fff;background:#151515;border:1px solid #333;border-radius:12px;padding:0}.user-admin::backdrop{background:#000b}.user-admin-inner{padding:22px}.user-head{display:flex;justify-content:space-between;align-items:center}.user-grid{display:grid;grid-template-columns:1fr 1fr 140px auto;gap:8px;align-items:center;margin:14px 0}.user-row{display:grid;grid-template-columns:1fr 120px 90px auto;gap:8px;align-items:center;padding:10px 0;border-top:1px solid #333}.user-row button{background:#333;color:#fff}.user-row .danger{background:#7c1118}.user-note{color:#aaa;font-size:.9rem}@media(max-width:1100px){.header-actions{flex-wrap:wrap;justify-content:flex-end}.header-actions input{order:1;flex:1 1 14rem}.status-badge{order:2}.user-name-button,.logout-button,#openSettings{order:3}}@media(max-width:700px){.user-grid,.user-row{grid-template-columns:1fr}.user-row{padding:14px 0}.user-name-button{max-width:7rem}.logout-button{font-size:0}.logout-button::after{content:'↪';font-size:1rem}.header-actions{gap:.4rem}.header-actions input{flex-basis:100%;width:100%!important}}
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
      const form = new FormData(event.currentTarget);
      const error = overlay.querySelector('.auth-error');
      error.textContent = '';
      try {
        await request(initialized ? '/api/auth/login' : '/api/auth/setup', { method: 'POST', body: JSON.stringify({ username: form.get('username'), password: form.get('password') }) });
        location.reload();
      } catch (exc) { error.textContent = exc.message; }
    };
  }

  async function openUsers(current) {
    let dialog = document.getElementById('userAdminDialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'userAdminDialog';
      dialog.className = 'user-admin';
      dialog.innerHTML = `<div class="user-admin-inner"><div class="user-head"><div><h2>Benutzerverwaltung</h2><div class="user-note"></div></div><button type="button" data-close>×</button></div><form class="user-grid"><input name="username" placeholder="Benutzername" minlength="3" required><input name="password" type="password" placeholder="Passwort (mind. 8 Zeichen)" minlength="8" required><select name="role"><option value="user">Benutzer</option><option value="admin">Administrator</option></select><button class="auth-primary" type="submit">Anlegen</button></form><div class="auth-error"></div><div data-users></div></div>`;
      document.body.append(dialog);
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      dialog.querySelector('form').onsubmit = async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await request('/api/users', { method: 'POST', body: JSON.stringify({ username: form.get('username'), password: form.get('password'), role: form.get('role') }) });
          event.currentTarget.reset();
          await renderUsers(dialog, current);
        } catch (exc) { dialog.querySelector('.auth-error').textContent = exc.message; }
      };
    }
    dialog.querySelector('.user-note').textContent = `Angemeldet als ${current.username} (${current.role === 'admin' ? 'Administrator' : 'Benutzer'})`;
    await renderUsers(dialog, current);
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
    userButton.title = status.user.role === 'admin' ? 'Benutzerverwaltung' : 'Angemeldeter Benutzer';
    if (status.user.role === 'admin') userButton.onclick = () => openUsers(status.user);
    actions.insertBefore(userButton, actions.lastElementChild);

    const logout = document.createElement('button');
    logout.className = 'icon-button user-button logout-button';
    logout.textContent = 'Abmelden';
    logout.title = 'Abmelden';
    logout.onclick = async () => { await request('/api/auth/logout', { method: 'POST' }); location.reload(); };
    actions.insertBefore(logout, actions.lastElementChild);
  }

  document.addEventListener('DOMContentLoaded', init);
})();