import { escapeHTML as e, select as $, selectAll } from './dom.js';

export function studyHTML(session, stats) {
  if (!session || ['invalidated', 'abandoned'].includes(session.status)) {
    return '<div class="empty-state"><h2>Sẵn sàng cho một phiên học</h2><p>Chọn kiểu luyện tập rồi bắt đầu phiên mới.</p><button class="button primary" data-action="restart">Bắt đầu phiên học →</button></div>';
  }
  const s = session;
  if (!s.total) {
    return `<div class="empty-state"><span class="big-check">✓</span><h2>${s.scope === 'wrong' ? 'Chưa có từ nào đến lượt ôn' : 'Sổ từ đang chờ bạn'}</h2><p>${s.scope === 'wrong' ? 'Danh sách gồm từ bạn đánh dấu và từ cần ôn của kỹ năng đã chọn.' : 'Thêm từ hoặc nhập danh sách để bắt đầu.'}</p><button class="button primary" data-action="${s.scope === 'wrong' ? 'all-words' : 'add'}">${s.scope === 'wrong' ? 'Học tất cả từ →' : 'Thêm từ mới'}</button></div>`;
  }
  if (s.status === 'completed' || s.index >= s.total) {
    return `<div class="summary"><span class="big-check">✳</span><span class="eyebrow">MỖI PHIÊN LÀ MỘT BƯỚC TIẾN</span><h2>Bạn đã hoàn thành phiên học!</h2><p>Kết quả của kỹ năng ${s.quizType === 'reading' ? 'cách đọc' : 'nghĩa tiếng Việt'} đã được lưu.</p><div class="summary-score"><div><strong>${s.total}</strong><span>từ đã luyện</span></div><div><strong>${s.correct}</strong><span>đúng</span></div><div><strong>${s.answered_count - s.correct}</strong><span>chưa đúng</span></div></div><div class="summary-buttons"><button class="button primary" data-action="restart">Học phiên mới →</button>${stats.review ? '<button class="button outline" data-action="review">Ôn lại →</button>' : ''}</div></div>`;
  }
  const word = s.current_word;
  if (!word) return '';
  const top = `<div class="study-topline"><span class="card-number">TỪ ${s.index + 1} / ${s.total}</span><span class="card-level">${s.quizType === 'reading' ? 'CÁCH ĐỌC' : 'NGHĨA TIẾNG VIỆT'}</span></div>`;
  const kanji = `<span lang="ja" class="kanji ${word.kanji.length > 5 ? 'long' : ''}">${e(word.kanji)}</span>`;
  if (s.mode === 'flash') {
    return (
      top +
      `<button class="flash-card" data-action="reveal" aria-label="Lật thẻ xem đáp án"><span class="card-prompt">${s.revealed ? 'ĐỐI CHIẾU VỚI ĐIỀU BẠN NHỚ' : s.quizType === 'reading' ? 'BẠN ĐỌC TỪ NÀY THẾ NÀO?' : 'BẠN NHỚ NGHĨA CỦA TỪ NÀY KHÔNG?'}</span>${kanji}${s.revealed ? `<span class="reading" lang="ja">${e(word.reading)}</span><span class="meaning">${e(word.meaning)}</span>` : '<span class="card-hidden">↻ Chạm để khám phá đáp án</span>'}</button>` +
      (s.revealed
        ? `${word.note ? `<p class="note-line">${e(word.note)}</p>` : ''}<div class="rating-buttons"><button class="button soft-danger" data-action="rate-wrong">↺ Chưa nhớ</button><button class="button primary" data-action="rate-correct">✓ Nhớ đúng</button></div><div class="keyboard-hint">1: Chưa nhớ · 2: Nhớ đúng</div>`
        : '<button class="button reveal-button" data-action="reveal">↻ Lật thẻ xem đáp án</button><div class="keyboard-hint">Nhấn Space để lật thẻ</div>')
    );
  }
  if (s.options.length < 2) {
    return (
      top +
      '<div class="empty-state"><h2>Cần thêm lựa chọn khác nhau</h2><p>Trắc nghiệm cần ít nhất hai cách đọc hoặc nghĩa khác nhau.</p><button class="button primary" data-action="use-flash">Học bằng flashcard →</button></div>'
    );
  }
  const correct = word[s.quizType];
  return (
    top +
    `<div class="quiz-word"><p class="card-prompt">${s.quizType === 'reading' ? 'CHỌN CÁCH ĐỌC ĐÚNG' : 'CHỌN NGHĨA ĐÚNG'}</p>${kanji}</div><div class="quiz-options">${s.options.map((option, index) => `<button class="quiz-option ${s.answered ? (option === correct ? 'correct' : option === s.choice ? 'wrong' : '') : ''}" data-action="choose" data-index="${index}" ${s.answered ? 'disabled' : ''}><span class="option-letter">${index + 1}</span><span>${e(option)}</span></button>`).join('')}</div>` +
    (s.answered
      ? `<div class="feedback ${s.current_result ? '' : 'wrong'}"><strong>${s.current_result ? '✓ Chính xác!' : '↺ Chưa đúng. Từ này sẽ được ôn lại.'}</strong><p>${e(word.kanji)}（${e(word.reading)}）· ${e(word.meaning)}</p>${word.note ? `<p>${e(word.note)}</p>` : ''}</div><button class="button primary full" data-action="next">${s.index === s.total - 1 ? 'Xem kết quả phiên học' : 'Từ tiếp theo'} →</button>`
      : '<p class="quiz-note">Chọn một đáp án để kiểm tra trí nhớ.</p>')
  );
}

export function renderShell(state, doc = document) {
  const { stats, session: s, view } = state;
  $('#stat-total', doc).textContent = stats.total;
  $('#stat-known', doc).textContent = stats.known;
  $('#stat-wrong', doc).textContent = stats.review;
  $('#nav-wrong', doc).textContent = stats.review;
  selectAll('[data-view]', doc).forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  const names = {
    flash: 'Flashcard',
    quiz: 'Trắc nghiệm',
    review: 'Ôn lại',
    words: 'Sổ từ của bạn',
  };
  const titles = {
    flash: 'Ghi nhớ từ. Mở rộng thế giới.',
    quiz: 'Thử trí nhớ, thêm tự tin.',
    review: 'Gặp lại, để nhớ lâu hơn.',
    words: 'Những từ đang lớn lên cùng bạn.',
  };
  $('#page-title', doc).textContent = titles[view];
  $('#page-description', doc).textContent =
    view === 'words'
      ? 'Tìm kiếm, ghi chú và tổ chức sổ từ theo cách của bạn.'
      : 'Cách đọc và nghĩa được theo dõi riêng. Đã vững khi đạt đủ chuỗi đúng ở cả hai kỹ năng.';
  $('#breadcrumb', doc).textContent = names[view];
  $('#study-view', doc).hidden = view === 'words';
  $('#words-view', doc).hidden = view !== 'words';
  $('#session-size', doc).value = String(state.settings.count);
  $('#quiz-type', doc).value = state.settings.quizType;
  $('#quiz-setting', doc).hidden = false;
  if (view === 'words') return;
  $('#study-panel', doc).innerHTML = studyHTML(s, stats);
  $('#flash-mode', doc).classList.toggle('selected', s?.mode === 'flash');
  $('#quiz-mode', doc).classList.toggle('selected', s?.mode === 'quiz');
  const done = s?.answered_count || 0;
  const total = s?.total || 0;
  const percent = total ? Math.round((done / total) * 100) : 0;
  $('#progress-percent', doc).innerHTML = `${percent}<span>%</span>`;
  $('#progress-ring', doc).style.setProperty('--progress', `${percent}%`);
  $('#progress-count', doc).textContent = `${done} / ${total} từ`;
  $('#progress-bar', doc).style.width = `${percent}%`;
  $('#session-correct', doc).textContent = s?.correct || 0;
  $('#session-wrong', doc).textContent = done - (s?.correct || 0);
  $('#scope-caption', doc).textContent =
    `Đang luyện ${state.settings.quizType === 'reading' ? 'cách đọc' : 'nghĩa tiếng Việt'}`;
}
