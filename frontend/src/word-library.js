import { escapeHTML as e, select as $ } from './dom.js';

export function wordRows(items, masteredStreak) {
  return items
    .map((word) => {
      const label = word.marked_for_review
        ? 'Đánh dấu ôn'
        : word.needs_review
          ? 'Cần ôn'
          : word.known
            ? 'Đã vững'
            : word.seen
              ? 'Đang học'
              : 'Chưa học';
      return `<tr><td><span lang="ja" class="table-kanji">${e(word.kanji)}</span></td><td lang="ja" class="table-reading">${e(word.reading)}</td><td class="table-meaning">${e(word.meaning)}<small class="skill-caption">Chuỗi đúng · Đọc ${word.progress.reading.streak}/${masteredStreak} · Nghĩa ${word.progress.meaning.streak}/${masteredStreak}</small></td><td><span class="word-status ${word.known ? 'known' : word.needs_review ? 'wrong' : ''}">${label}</span><button class="icon-button" data-word-action="toggle" data-id="${e(word.id)}" aria-label="${word.marked_for_review ? 'Bỏ đánh dấu ôn' : 'Đánh dấu để ôn'} ${e(word.kanji)}">${word.marked_for_review ? '★' : '☆'}</button></td><td><div class="row-actions"><button class="icon-button" data-word-action="edit" data-id="${e(word.id)}" aria-label="Sửa ${e(word.kanji)}">✎</button><button class="icon-button" data-word-action="delete" data-id="${e(word.id)}" aria-label="Xóa ${e(word.kanji)}">×</button></div></td></tr>`;
    })
    .join('');
}

export function createLibrary({ store, api, doc, toast, refreshSnapshot }) {
  const library = store.library;
  let generation = 0;
  let abort;
  let searchTimer;
  function render() {
    $('#word-rows', doc).innerHTML = wordRows(library.items, store.state.limits.mastered_streak);
    $('#word-empty', doc).hidden = library.items.length > 0 || library.loading;
    $('#word-count', doc).textContent = library.loading
      ? 'Đang tải…'
      : `${library.total ? library.offset + 1 : 0}–${Math.min(library.offset + library.items.length, library.total)} / ${library.total} từ`;
    $('#word-prev', doc).disabled = library.loading || library.offset === 0;
    $('#word-next', doc).disabled =
      library.loading || library.offset + store.state.limits.page_size >= library.total;
    $('#word-table', doc).setAttribute('aria-busy', String(library.loading));
  }
  async function load(retried = false) {
    const ticket = ++generation;
    abort?.abort();
    abort = new AbortController();
    library.loading = true;
    render();
    try {
      const page = await api.words(
        { ...library, limit: store.state.limits.page_size },
        abort.signal,
      );
      if (ticket !== generation) return;
      if (!store.applyPage(page)) {
        if (!retried && (await refreshSnapshot())) return load(true);
        throw Error('Sổ từ vừa thay đổi. Hãy tải lại danh sách.');
      }
      if (page.offset > 0 && !page.items.length) {
        library.offset = Math.max(0, Math.floor((page.total - 1) / page.limit) * page.limit);
        return load(true);
      }
    } catch (error) {
      if (error.name !== 'AbortError' && ticket === generation) toast(error.message);
    } finally {
      if (ticket === generation) {
        library.loading = false;
        render();
      }
    }
  }
  $('#search', doc).addEventListener('input', (event) => {
    library.query = event.target.value;
    library.offset = 0;
    ++generation;
    abort?.abort();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(), 250);
  });
  $('#word-filter', doc).addEventListener('change', (event) => {
    library.status = event.target.value;
    library.offset = 0;
    load();
  });
  $('#word-prev', doc).addEventListener('click', () => {
    library.offset = Math.max(0, library.offset - store.state.limits.page_size);
    load();
  });
  $('#word-next', doc).addEventListener('click', () => {
    library.offset += store.state.limits.page_size;
    load();
  });
  return { load, render };
}
