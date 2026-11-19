import { escapeHTML as e, select as $ } from './dom.js';
import { parseImport } from './core.js';

export function bindImportExport({ store, api, doc, mutate, toast }) {
  let pending;
  let generation = 0;
  function reset() {
    generation += 1;
    pending = null;
    $('#import-confirm', doc).disabled = true;
    $('#import-preview', doc).textContent = '';
  }
  async function preview() {
    reset();
    const ticket = generation;
    try {
      const parsed = parseImport($('#import-text', doc).value, [], store.state.limits);
      if (!parsed.words.length) {
        $('#import-preview', doc).textContent = parsed.errors.join('\n') || 'Không có từ hợp lệ.';
        return;
      }
      $('#import-preview', doc).textContent = 'Đang đối chiếu sổ từ…';
      const result = await api.previewImport(parsed.words);
      if (ticket !== generation) return;
      pending = parsed.words;
      $('#import-preview', doc).innerHTML =
        `<div class="import-summary"><strong>${result.added} từ mới</strong> · ${result.duplicates + parsed.duplicates} từ trùng · ${parsed.errors.length} dòng lỗi</div><p class="import-errors">${e(parsed.errors.slice(0, 12).join('\n'))}</p><div class="import-samples">${result.samples.map((word) => `<div>${e(word.kanji)} · ${e(word.reading)} — ${e(word.meaning)}</div>`).join('')}</div>`;
      $('#import-confirm', doc).disabled = result.added === 0;
      $('#import-confirm', doc).textContent = `Thêm ${result.added} từ mới →`;
    } catch (error) {
      if (ticket === generation) $('#import-preview', doc).textContent = error.message;
    }
  }
  $('#import-open', doc).addEventListener('click', () => {
    $('#import-text', doc).value = '';
    $('#import-file', doc).value = '';
    reset();
    $('#import-dialog', doc).showModal();
  });
  $('#import-text', doc).addEventListener('input', reset);
  $('#import-check', doc).addEventListener('click', preview);
  $('#import-file', doc).addEventListener('change', async (event) => {
    const file = event.target.files[0];
    reset();
    if (!file) return;
    if (file.size > store.state.limits.import_bytes) {
      $('#import-preview', doc).textContent = 'Tệp vượt quá giới hạn dung lượng.';
      return;
    }
    try {
      $('#import-text', doc).value = await file.text();
      await preview();
    } catch {
      $('#import-preview', doc).textContent = 'Không thể đọc tệp.';
    }
  });
  $('#import-local', doc).addEventListener('click', async () => {
    try {
      const old = JSON.parse(localStorage.getItem('n2-kotoba-v1') || 'null');
      if (!old?.words) {
        toast('Không có bản lưu cũ ở địa chỉ trình duyệt này.');
        return;
      }
      $('#import-text', doc).value = JSON.stringify(old.words);
      await preview();
    } catch {
      toast('Không đọc được bản lưu cũ. Hãy nhập tệp JSON đã xuất.');
    }
  });
  $('#import-confirm', doc).addEventListener('click', async () => {
    if (pending && (await mutate(() => api.importWords(pending)))) {
      reset();
      $('#import-dialog', doc).close();
      toast('Đã nhập các từ mới vào tài khoản.');
    }
  });
  $('#export', doc).addEventListener('click', async () => {
    try {
      const words = await api.exportWords();
      const blob = new Blob(
        [JSON.stringify({ words, attribution: store.state.catalogue }, null, 2)],
        { type: 'application/json;charset=utf-8' },
      );
      const url = URL.createObjectURL(blob);
      const anchor = doc.createElement('a');
      anchor.href = url;
      anchor.download = `kotoba-n2-${new Date().toISOString().slice(0, 10)}.json`;
      doc.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast('Đã xuất từ và ghi chú kèm nguồn dữ liệu.');
    } catch (error) {
      toast(error.message);
    }
  });
}
