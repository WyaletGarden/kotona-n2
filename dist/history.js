import { escapeHTML as e, select as $ } from './dom.js';

export function bindHistory({ api, doc, mutate }) {
  let offset = 0;
  const limit = 20;
  let total = 0;
  let loading = false;
  let generation = 0;
  let failedOffset = 0;
  const content = $('#history-content', doc);
  const status = $('#history-status', doc);
  const retry = $('#history-retry', doc);
  const previous = $('#history-prev', doc);
  const next = $('#history-next', doc);
  const dialog = $('#history-dialog', doc);
  function updateControls() {
    previous.disabled = loading || offset === 0;
    next.disabled = loading || offset + limit >= total;
    content.setAttribute('aria-busy', String(loading));
  }
  const labels = {
    completed: 'Hoàn thành',
    in_progress: 'Đang học',
    paused: 'Tạm dừng',
    abandoned: 'Đã dừng',
    invalidated: 'Sổ từ đã thay đổi',
  };
  async function load(targetOffset) {
    const ticket = ++generation;
    loading = true;
    failedOffset = targetOffset;
    retry.hidden = true;
    status.textContent = 'Đang tải lịch sử…';
    updateControls();
    try {
      const page = await api.history(targetOffset, limit);
      if (ticket !== generation) return;
      offset = page.offset;
      total = page.total;
      content.innerHTML = page.items.length
        ? page.items
            .map(
              (session) =>
                `<div class="history-item"><div><strong>${session.mode === 'quiz' ? 'Trắc nghiệm' : 'Flashcard'} · ${session.quizType === 'reading' ? 'Cách đọc' : 'Nghĩa'}</strong><small>${labels[session.status]} · ${e(new Date(session.created_at).toLocaleString('vi-VN'))} · ${session.answered_count}/${session.total} từ</small>${['paused', 'in_progress'].includes(session.status) ? `<button class="button outline" data-resume="${e(session.id)}">Tiếp tục phiên này</button>` : ''}</div><span class="history-score">${session.correct} đúng</span></div>`,
            )
            .join('')
        : '<p class="dialog-description">Chưa có phiên học nào.</p>';
      status.textContent = '';
    } catch (error) {
      if (ticket !== generation) return;
      status.textContent = error.message;
      retry.hidden = false;
    } finally {
      if (ticket === generation) {
        loading = false;
        updateControls();
      }
    }
  }
  updateControls();
  $('#history-open', doc).addEventListener('click', () => {
    dialog.showModal();
    offset = total = 0;
    content.textContent = '';
    return load(0);
  });
  dialog.addEventListener('close', () => {
    // The browser queues this event; the dialog may already have reopened.
    if (dialog.open) return;
    generation += 1;
    loading = false;
  });
  previous.addEventListener('click', () => {
    if (!previous.disabled) return load(Math.max(0, offset - limit));
  });
  next.addEventListener('click', () => {
    if (!next.disabled) return load(offset + limit);
  });
  retry.addEventListener('click', () => {
    if (!loading) return load(failedOffset);
  });
  $('#history-content', doc).addEventListener('click', async (event) => {
    const button = event.target.closest('[data-resume]');
    if (button && (await mutate(() => api.resume(button.dataset.resume)))) dialog.close();
  });
}
