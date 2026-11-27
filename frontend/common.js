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

  let links = '';
  if (user.role === 'admin') {
    links = '<a href="admin.html">Записи</a> <a href="services.html">Услуги</a>';
  } else {
    links = '<a href="pets.html">Мои питомцы</a> <a href="book.html">Записаться</a> <a href="my.html">Мои записи</a>';
  }
  document.getElementById('menu').innerHTML =
    '<b>Груминг-салон «Пушистик»</b> ' + links +
    ' <span class="right">' + esc(user.name) + ' <button onclick="logout()">Выйти</button></span>';
  return user;
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
