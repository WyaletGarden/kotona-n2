import { select as $, selectAll } from './dom.js';
import { validateWord } from './core.js';

export function bindWordEditor({ store, api, doc, mutate, toast }) {
  let pendingDelete;
  let openedRevision;
  function open(word = null) {
    openedRevision = store.state.revision;
    $('#word-form', doc).reset();
    $('#edit-id', doc).value = word?.id || '';
    $('#word-dialog-title', doc).textContent = word ? 'Chỉnh sửa từ vựng' : 'Thêm một từ mới';
    for (const field of ['kanji', 'reading', 'meaning', 'note'])
      $('#word-' + field, doc).value = word?.[field] || '';
    $('#word-error', doc).textContent = '';
    $('#word-dialog', doc).showModal();
    $('#word-kanji', doc).focus();
  }
  selectAll('.add-trigger', doc).forEach((button) =>
    button.addEventListener('click', () => open()),
  );
  $('#word-form', doc).addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = $('#edit-id', doc).value;
    if (id && openedRevision !== store.state.revision) {
      $('#word-error', doc).textContent =
        'Dữ liệu đã thay đổi ở phiên khác. Hãy đóng và mở lại biểu mẫu để đối chiếu trước khi sửa.';
      return;
    }
    const word = Object.fromEntries(
      ['kanji', 'reading', 'meaning', 'note'].map((field) => [
        field,
        $('#word-' + field, doc)
          .value.trim()
          .normalize('NFC'),
      ]),
    );
    const error = validateWord(word, store.state.limits);
    if (error) {
      $('#word-error', doc).textContent = error;
      return;
    }
    if (await mutate(() => (id ? api.editWord(id, word) : api.addWord(word)))) {
      $('#word-dialog', doc).close();
      toast(id ? 'Đã cập nhật từ vựng.' : 'Đã thêm từ mới.');
    }
  });
  $('#word-rows', doc).addEventListener('click', async (event) => {
    const button = event.target.closest('[data-word-action]');
    if (!button) return;
    const word = store.wordById(button.dataset.id);
    if (!word) return;
    if (button.dataset.wordAction === 'edit') open(word);
    else if (button.dataset.wordAction === 'toggle') {
      if (await mutate(() => api.review(word.id, !word.marked_for_review)))
        toast('Đã cập nhật dấu ôn. Mức ghi nhớ được giữ riêng.');
    } else {
      pendingDelete = { id: word.id, revision: store.state.revision };
      $('#delete-description', doc).textContent =
        `${word.kanji}（${word.reading}）sẽ được xóa. Lịch sử trả lời vẫn được giữ; phiên chưa hoàn thành có từ này sẽ dừng.`;
      $('#delete-dialog', doc).showModal();
    }
  });
  $('#delete-confirm', doc).addEventListener('click', async () => {
    if (pendingDelete && pendingDelete.revision !== store.state.revision) {
      toast('Sổ từ đã thay đổi. Hãy chọn lại từ cần xóa để xác nhận nội dung mới.');
      $('#delete-dialog', doc).close();
      pendingDelete = null;
      return;
    }
    if (pendingDelete && (await mutate(() => api.deleteWord(pendingDelete.id)))) {
      pendingDelete = null;
      $('#delete-dialog', doc).close();
      toast('Đã xóa từ khỏi sổ.');
    }
  });
  return { open };
}
