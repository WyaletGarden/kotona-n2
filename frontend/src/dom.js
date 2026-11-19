export const select = (selector, root = document) => root.querySelector(selector);
export const selectAll = (selector, root = document) => [...root.querySelectorAll(selector)];
export const escapeHTML = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char],
  );

export function createToast(doc = document) {
  let timer;
  return (message) => {
    clearTimeout(timer);
    const toast = select('#toast', doc);
    toast.textContent = message;
    toast.classList.add('show');
    timer = setTimeout(() => toast.classList.remove('show'), 4200);
  };
}

export function bindDialogs(doc = document) {
  selectAll('.close-dialog', doc).forEach((button) =>
    button.addEventListener('click', () => button.closest('dialog').close()),
  );
  selectAll('dialog', doc).forEach((dialog) =>
    dialog.addEventListener('click', (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        dialog.close();
    }),
  );
}
