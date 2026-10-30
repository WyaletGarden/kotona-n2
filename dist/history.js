import { escapeHTML as e, select as $ } from './dom.js';

export function bindHistory({ api, doc, mutate }) {
  let offset = 0;
  const limit = 20;
  const labels = {
    completed: 'Hoàn thành',
    in_progress: 'Đang học',
    paused: 'Tạm dừng',
    abandoned: 'Đã dừng',
    invalidated: 'Sổ từ đã thay đổi',
  };
  async function load() {
    $('#history-content', doc).textContent = 'Đang tải lịch sử…';
    try {
      const page = await api.history(offset, limit);
      $('#history-content', doc).innerHTML = page.items.length
        ? page.items
            .map(
              (session) =>
                `<div class="history-item"><div><strong>${session.mode === 'quiz' ? 'Trắc nghiệm' : 'Flashcard'} · ${session.quizType === 'reading' ? 'Cách đọc' : 'Nghĩa'}</strong><small>${labels[session.status]} · ${e(new Date(session.created_at).toLocaleString('vi-VN'))} · ${session.answered_count}/${session.total} từ</small>${['paused', 'in_progress'].includes(session.status) ? `<button class="button outline" data-resume="${e(session.id)}">Tiếp tục phiên này</button>` : ''}</div><span class="history-score">${session.correct} đúng</span></div>`,
            )
            .join('')
        : '<p class="dialog-description">Chưa có phiên học nào.</p>';
      $('#history-prev', doc).disabled = offset === 0;
      $('#history-next', doc).disabled = offset + limit >= page.total;
    } catch (error) {
      $('#history-content', doc).textContent = error.message;
    }
  }
  $('#history-open', doc).addEventListener('click', () => {
    offset = 0;
    $('#history-dialog', doc).showModal();
    load();
  });
  $('#history-prev', doc).addEventListener('click', () => {
    offset = Math.max(0, offset - limit);
    load();
  });
  $('#history-next', doc).addEventListener('click', () => {
    offset += limit;
    load();
  });
  $('#history-content', doc).addEventListener('click', async (event) => {
    const button = event.target.closest('[data-resume]');
    if (button && (await mutate(() => api.resume(button.dataset.resume))))
      $('#history-dialog', doc).close();
  });
}
