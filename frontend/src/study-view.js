import { escapeHTML as e, select as $, selectAll } from './dom.js';
import { createRoot } from 'react-dom/client';
import { createElement } from 'react';
import { StudyPanel } from './study-panel.js';

const studyRoots = new WeakMap();

export function studyHTML(session, stats) {
  if (!session || ['invalidated', 'abandoned'].includes(session.status)) {
    return '<div class="empty-state"><h2>Sáºµn sÃ ng cho má»™t phiÃªn há»c</h2><p>Chá»n kiá»ƒu luyá»‡n táº­p rá»“i báº¯t Ä‘áº§u phiÃªn má»›i.</p><button class="button primary" data-action="restart">Báº¯t Ä‘áº§u phiÃªn há»c â†’</button></div>';
  }
  const s = session;
  if (!s.total) {
    return `<div class="empty-state"><span class="big-check">âœ“</span><h2>${s.scope === 'wrong' ? 'ChÆ°a cÃ³ tá»« nÃ o Ä‘áº¿n lÆ°á»£t Ã´n' : 'Sá»• tá»« Ä‘ang chá» báº¡n'}</h2><p>${s.scope === 'wrong' ? 'Danh sÃ¡ch gá»“m tá»« báº¡n Ä‘Ã¡nh dáº¥u vÃ  tá»« cáº§n Ã´n cá»§a ká»¹ nÄƒng Ä‘Ã£ chá»n.' : 'ThÃªm tá»« hoáº·c nháº­p danh sÃ¡ch Ä‘á»ƒ báº¯t Ä‘áº§u.'}</p><button class="button primary" data-action="${s.scope === 'wrong' ? 'all-words' : 'add'}">${s.scope === 'wrong' ? 'Há»c táº¥t cáº£ tá»« â†’' : 'ThÃªm tá»« má»›i'}</button></div>`;
  }
  if (s.status === 'completed' || s.index >= s.total) {
    return `<div class="summary"><span class="big-check">âœ³</span><span class="eyebrow">Má»–I PHIÃŠN LÃ€ Má»˜T BÆ¯á»šC TIáº¾N</span><h2>Báº¡n Ä‘Ã£ hoÃ n thÃ nh phiÃªn há»c!</h2><p>Káº¿t quáº£ cá»§a ká»¹ nÄƒng ${s.quizType === 'reading' ? 'cÃ¡ch Ä‘á»c' : 'nghÄ©a tiáº¿ng Viá»‡t'} Ä‘Ã£ Ä‘Æ°á»£c lÆ°u.</p><div class="summary-score"><div><strong>${s.total}</strong><span>tá»« Ä‘Ã£ luyá»‡n</span></div><div><strong>${s.correct}</strong><span>Ä‘Ãºng</span></div><div><strong>${s.answered_count - s.correct}</strong><span>chÆ°a Ä‘Ãºng</span></div></div><div class="summary-buttons"><button class="button primary" data-action="restart">Há»c phiÃªn má»›i â†’</button>${stats.review ? '<button class="button outline" data-action="review">Ã”n láº¡i â†’</button>' : ''}</div></div>`;
  }
  const word = s.current_word;
  if (!word) return '';
  const top = `<div class="study-topline"><span class="card-number">Tá»ª ${s.index + 1} / ${s.total}</span><span class="card-level">${s.quizType === 'reading' ? 'CÃCH Äá»ŒC' : 'NGHÄ¨A TIáº¾NG VIá»†T'}</span></div>`;
  const kanji = `<span lang="ja" class="kanji ${word.kanji.length > 5 ? 'long' : ''}">${e(word.kanji)}</span>`;
  if (s.mode === 'flash') {
    return (
      top +
      `<button class="flash-card" data-action="reveal" aria-label="Láº­t tháº» xem Ä‘Ã¡p Ã¡n"><span class="card-prompt">${s.revealed ? 'Äá»I CHIáº¾U Vá»šI ÄIá»€U Báº N NHá»š' : s.quizType === 'reading' ? 'Báº N Äá»ŒC Tá»ª NÃ€Y THáº¾ NÃ€O?' : 'Báº N NHá»š NGHÄ¨A Cá»¦A Tá»ª NÃ€Y KHÃ”NG?'}</span>${kanji}${s.revealed ? `<span class="reading" lang="ja">${e(word.reading)}</span><span class="meaning">${e(word.meaning)}</span>` : '<span class="card-hidden">â†» Cháº¡m Ä‘á»ƒ khÃ¡m phÃ¡ Ä‘Ã¡p Ã¡n</span>'}</button>` +
      (s.revealed
        ? `${word.note ? `<p class="note-line">${e(word.note)}</p>` : ''}<div class="rating-buttons"><button class="button soft-danger" data-action="rate-wrong">â†º ChÆ°a nhá»›</button><button class="button primary" data-action="rate-correct">âœ“ Nhá»› Ä‘Ãºng</button></div><div class="keyboard-hint">1: ChÆ°a nhá»› Â· 2: Nhá»› Ä‘Ãºng</div>`
        : '<button class="button reveal-button" data-action="reveal">â†» Láº­t tháº» xem Ä‘Ã¡p Ã¡n</button><div class="keyboard-hint">Nháº¥n Space Ä‘á»ƒ láº­t tháº»</div>')
    );
  }
  if (s.options.length < 2) {
    return (
      top +
      '<div class="empty-state"><h2>Cáº§n thÃªm lá»±a chá»n khÃ¡c nhau</h2><p>Tráº¯c nghiá»‡m cáº§n Ã­t nháº¥t hai cÃ¡ch Ä‘á»c hoáº·c nghÄ©a khÃ¡c nhau.</p><button class="button primary" data-action="use-flash">Há»c báº±ng flashcard â†’</button></div>'
    );
  }
  const correct = word[s.quizType];
  return (
    top +
    `<div class="quiz-word"><p class="card-prompt">${s.quizType === 'reading' ? 'CHá»ŒN CÃCH Äá»ŒC ÄÃšNG' : 'CHá»ŒN NGHÄ¨A ÄÃšNG'}</p>${kanji}</div><div class="quiz-options">${s.options.map((option, index) => `<button class="quiz-option ${s.answered ? (option === correct ? 'correct' : option === s.choice ? 'wrong' : '') : ''}" data-action="choose" data-index="${index}" ${s.answered ? 'disabled' : ''}><span class="option-letter">${index + 1}</span><span>${e(option)}</span></button>`).join('')}</div>` +
    (s.answered
      ? `<div class="feedback ${s.current_result ? '' : 'wrong'}"><strong>${s.current_result ? 'âœ“ ChÃ­nh xÃ¡c!' : 'â†º ChÆ°a Ä‘Ãºng. Tá»« nÃ y sáº½ Ä‘Æ°á»£c Ã´n láº¡i.'}</strong><p>${e(word.kanji)}ï¼ˆ${e(word.reading)}ï¼‰Â· ${e(word.meaning)}</p>${word.note ? `<p>${e(word.note)}</p>` : ''}</div><button class="button primary full" data-action="next">${s.index === s.total - 1 ? 'Xem káº¿t quáº£ phiÃªn há»c' : 'Tá»« tiáº¿p theo'} â†’</button>`
      : '<p class="quiz-note">Chá»n má»™t Ä‘Ã¡p Ã¡n Ä‘á»ƒ kiá»ƒm tra trÃ­ nhá»›.</p>')
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
    quiz: 'Tráº¯c nghiá»‡m',
    review: 'Ã”n láº¡i',
    words: 'Sá»• tá»« cá»§a báº¡n',
  };
  const titles = {
    flash: 'Ghi nhá»› tá»«. Má»Ÿ rá»™ng tháº¿ giá»›i.',
    quiz: 'Thá»­ trÃ­ nhá»›, thÃªm tá»± tin.',
    review: 'Gáº·p láº¡i, Ä‘á»ƒ nhá»› lÃ¢u hÆ¡n.',
    words: 'Nhá»¯ng tá»« Ä‘ang lá»›n lÃªn cÃ¹ng báº¡n.',
  };
  $('#page-title', doc).textContent = titles[view];
  $('#page-description', doc).textContent =
    view === 'words'
      ? 'TÃ¬m kiáº¿m, ghi chÃº vÃ  tá»• chá»©c sá»• tá»« theo cÃ¡ch cá»§a báº¡n.'
      : 'CÃ¡ch Ä‘á»c vÃ  nghÄ©a Ä‘Æ°á»£c theo dÃµi riÃªng. ÄÃ£ vá»¯ng khi Ä‘áº¡t Ä‘á»§ chuá»—i Ä‘Ãºng á»Ÿ cáº£ hai ká»¹ nÄƒng.';
  $('#breadcrumb', doc).textContent = names[view];
  $('#study-view', doc).hidden = view === 'words';
  $('#words-view', doc).hidden = view !== 'words';
  $('#session-size', doc).value = String(state.settings.count);
  $('#quiz-type', doc).value = state.settings.quizType;
  $('#quiz-setting', doc).hidden = false;
  if (view === 'words') return;
  const studyPanel = $('#study-panel', doc);
  let studyRoot = studyRoots.get(studyPanel);
  if (!studyRoot) {
    studyRoot = createRoot(studyPanel);
    studyRoots.set(studyPanel, studyRoot);
  }
  studyRoot.render(createElement(StudyPanel, { html: studyHTML(s, stats) }));
  $('#flash-mode', doc).classList.toggle('selected', s?.mode === 'flash');
  $('#quiz-mode', doc).classList.toggle('selected', s?.mode === 'quiz');
  const done = s?.answered_count || 0;
  const total = s?.total || 0;
  const percent = total ? Math.round((done / total) * 100) : 0;
  $('#progress-percent', doc).innerHTML = `${percent}<span>%</span>`;
  $('#progress-ring', doc).style.setProperty('--progress', `${percent}%`);
  $('#progress-count', doc).textContent = `${done} / ${total} tá»«`;
  $('#progress-bar', doc).style.width = `${percent}%`;
  $('#session-correct', doc).textContent = s?.correct || 0;
  $('#session-wrong', doc).textContent = done - (s?.correct || 0);
  $('#scope-caption', doc).textContent =
    `Äang luyá»‡n ${state.settings.quizType === 'reading' ? 'cÃ¡ch Ä‘á»c' : 'nghÄ©a tiáº¿ng Viá»‡t'}`;
}
