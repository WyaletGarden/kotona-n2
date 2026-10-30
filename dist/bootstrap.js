import { api } from './api.js';
import { select as $, createToast } from './dom.js';

const form = $('#auth-form');
const error = $('#auth-error');
const submit = $('#auth-submit');
const startup = $('#startup-screen');
const toast = createToast();
let registering = false;

$('#startup-retry').addEventListener('click', () => location.reload());

$('#auth-toggle').addEventListener('click', () => {
  registering = !registering;
  $('#auth-name-row').hidden = !registering;
  $('#auth-name').required = registering;
  $('#auth-title').textContent = registering ? 'Tạo góc học của bạn' : 'Chào mừng trở lại';
  $('#auth-password').autocomplete = registering ? 'new-password' : 'current-password';
  submit.textContent = registering ? 'Tạo tài khoản →' : 'Đăng nhập →';
  $('#auth-toggle').textContent = registering
    ? 'Đã có tài khoản? Đăng nhập'
    : 'Chưa có tài khoản? Đăng ký';
  error.textContent = '';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  error.textContent = '';
  try {
    const body = { email: $('#auth-email').value.trim(), password: $('#auth-password').value };
    if (registering) body.name = $('#auth-name').value.trim();
    await api.request(`/auth/${registering ? 'register' : 'login'}`, { method: 'POST', body });
    location.reload();
  } catch (failure) {
    error.textContent = failure.message;
  } finally {
    submit.disabled = false;
  }
});

$('#logout').addEventListener('click', async () => {
  try {
    await api.request('/auth/logout', { method: 'POST' });
    location.reload();
  } catch (failure) {
    toast(failure.message);
  }
});

submit.disabled = true;
try {
  const catalogue = await api.catalogue();
  $('#auth-catalogue-count').textContent =
    `Tài khoản mới có sẵn ${catalogue.count.toLocaleString('vi-VN')} mục từ.`;
  $('#auth-password').minLength = catalogue.limits.password_min;
  $('#auth-password').maxLength = catalogue.limits.password_max;
  $('#password-hint').textContent = `Tối thiểu ${catalogue.limits.password_min} ký tự.`;
  for (const field of ['kanji', 'reading', 'meaning', 'note'])
    $('#word-' + field).maxLength = catalogue.limits[`${field}_length`];
  $('#import-limits').textContent =
    `Dán từ Excel / Google Sheets hoặc chọn CSV, TSV, TXT, JSON. Tối đa ${catalogue.limits.import_bytes.toLocaleString('vi-VN')} byte và ${catalogue.limits.max_words.toLocaleString('vi-VN')} từ.`;
  const identity = await api.request('/auth/me');
  $('#account-name').textContent = identity.user.name;
  $('#account-email').textContent = identity.user.email;
  const { startApp } = await import('./app.js');
  await startApp();
  $('.shell').hidden = false;
  startup.hidden = true;
} catch (failure) {
  if (failure.status === 401) {
    $('#auth-screen').hidden = false;
    startup.hidden = true;
  } else {
    $('#startup-message').textContent = failure.message;
    $('#startup-retry').hidden = false;
  }
} finally {
  submit.disabled = false;
}
