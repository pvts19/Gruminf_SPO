// общие функции для всех страниц

async function api(method, url, body) {
  const headers = {};
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = 'Bearer ' + token;
  if (body) headers['Content-Type'] = 'application/json';

  let res;
  try {
    res = await fetch('/api' + url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch (e) {
    throw new Error('Нет связи с сервером');
  }

  if (res.status === 401 && url !== '/auth/login') {
    localStorage.clear();
    location.href = 'index.html';
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = 'Ошибка ' + res.status;
    if (data && typeof data.detail === 'string') msg = data.detail;
    // ошибки валидации приходят списком
    if (data && Array.isArray(data.detail)) msg = 'Проверьте поля: ' + data.detail.map(d => d.loc[d.loc.length - 1]).join(', ');
    throw new Error(msg);
  }
  return data;
}

function getUser() {
  return JSON.parse(localStorage.getItem('user') || 'null');
}

// проверка входа и меню сверху
function initPage(onlyAdmin) {
  const user = getUser();
  if (!user) {
    location.href = 'index.html';
    return null;
  }
  if (onlyAdmin && user.role !== 'admin') {
    location.href = 'pets.html';
    return null;
  }

  let pages;
  if (user.role === 'admin') {
    pages = [['admin.html', 'Записи'], ['services.html', 'Услуги']];
  } else {
    pages = [['pets.html', 'Мои питомцы'], ['book.html', 'Записаться'], ['my.html', 'Мои записи']];
  }
  // подсвечиваем ссылку на текущую страницу
  const current = location.pathname.split('/').pop();
  let links = '';
  for (const p of pages) {
    links += '<a class="link' + (p[0] === current ? ' active' : '') + '" href="' + p[0] + '">' + p[1] + '</a>';
  }
  document.getElementById('menu').innerHTML =
    '<a class="logo" href="' + pages[0][0] + '">🐾 Пушистик</a>' + links +
    '<span class="user">' + esc(user.name) + '</span><button class="small" onclick="logout()">Выйти</button>';
  return user;
}

function statusBadge(status) {
  return '<span class="badge ' + status + '">' + STATUS[status] + '</span>';
}

function emptyBlock(html) {
  return '<div class="empty">' + html + '</div>';
}

async function logout() {
  try { await api('POST', '/auth/logout'); } catch (e) {}
  localStorage.clear();
  location.href = 'index.html';
}

function showMsg(id, text, isError) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = isError ? 'msg error' : 'msg ok';
}

// чтобы имена питомцев и т.п. не ломали html
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('ru-RU') + ' ' + iso.slice(11, 16);
}

const STATUS = { booked: 'Записан', done: 'Выполнено', cancelled: 'Отменено' };
