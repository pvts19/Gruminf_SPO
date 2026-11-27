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
    location.href = 'login.html';
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

// куда вернуть пользователя после входа: берём ?next= из адреса,
// но только если это наша страница (чтобы нельзя было увести на чужой сайт)
function getNext() {
  const next = new URLSearchParams(location.search).get('next');
  if (next && /^[a-z]+\.html(\?[\w=&%-]*)?$/.test(next)) return next;
  return null;
}

// проверка входа и меню сверху
// onlyAdmin - страница только для админа, isPublic - страницу можно смотреть без входа
function initPage(onlyAdmin, isPublic) {
  const user = getUser();
  const current = location.pathname.split('/').pop() || 'index.html';
  if (!user && !isPublic) {
    location.href = 'login.html?next=' + encodeURIComponent(current + location.search);
    return null;
  }
  if (user && onlyAdmin && user.role !== 'admin') {
    location.href = 'index.html';
    return null;
  }

  let pages;
  if (!user) {
    pages = [['index.html', 'Услуги']];
  } else if (user.role === 'admin') {
    pages = [['admin.html', 'Записи'], ['services.html', 'Услуги']];
  } else {
    pages = [['index.html', 'Услуги'], ['pets.html', 'Мои питомцы'], ['my.html', 'Мои записи']];
  }
  // подсвечиваем ссылку на текущую страницу
  let links = '';
  for (const p of pages) {
    links += '<a class="link' + (p[0] === current ? ' active' : '') + '" href="' + p[0] + '">' + p[1] + '</a>';
  }
  let right;
  if (user) {
    right = '<span class="user">' + esc(user.name) + '</span><button class="small" onclick="logout()">Выйти</button>';
  } else {
    right = '<span class="user"></span><a href="login.html"><button class="small primary">Войти</button></a>';
  }
  document.getElementById('menu').innerHTML =
    '<a class="logo" href="' + pages[0][0] + '">🐾 Пушистик</a>' + links + right;
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
