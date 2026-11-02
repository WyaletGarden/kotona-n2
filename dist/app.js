import { api as defaultApi } from './api.js';
import { createStore, createController } from './state.js';
import { bindDialogs, createToast, select as $, selectAll } from './dom.js';
import { renderShell } from './study-view.js';
import { createLibrary } from './word-library.js';
import { bindWordEditor } from './word-editor.js';
import { bindImportExport } from './import-export.js';
import { bindHistory } from './history.js';
import { createRefreshPolicy } from './refresh-policy.js';

export async function startApp({
  api = defaultApi,
  doc = document,
  win = window,
  initialSnapshot,
} = {}) {
  const store = createStore();
  const toast = createToast(doc);
  let library;
  let statsTimer;
  let externalTimer;
  const refreshPolicy = createRefreshPolicy();

  function scheduleStatsRefresh() {
    win.clearTimeout(statsTimer);
    const expires = store.state.statsExpiresAt;
    if (expires == null) return;
    const remaining = Math.max(0, expires - Date.now());
    statsTimer = win.setTimeout(
      async function refreshDueStats() {
        if (controller.busy) {
          statsTimer = win.setTimeout(refreshDueStats, 500);
          return;
        }
        if (!(await refreshSnapshot())) {
          statsTimer = win.setTimeout(refreshDueStats, 15000);
        } else if (store.state.view === 'words' && store.library.status === 'review') {
          await library.load();
        }
      },
      Math.min(remaining, 2147483647),
    );
  }
  const controller = createController({
    store,
    api,
    changed() {
      refreshPolicy.synced();
      renderShell(store.state, doc);
      scheduleStatsRefresh();
    },
    error: (failure) => toast(failure.message),
    unauthorized: () => win.location.reload(),
    saving(status) {
      if (status === 'idle') {
        doc.body.classList.remove('is-saving');
        return;
      }
      doc.body.classList.toggle('is-saving', status === 'pending');
      $('#save-indicator', doc).textContent = {
        pending: 'Đang lưu…',
        saved: '✓ Đã lưu vào tài khoản của bạn',
        failed: '⚠ Thao tác chưa được lưu. Hãy thử lại.',
      }[status];
    },
  });
  controller.accept(initialSnapshot || (await api.load()));
  async function refreshSnapshot() {
    return controller.run(() => api.load());
  }
  library = createLibrary({ store, api, doc, toast, refreshSnapshot });
  async function mutate(operation) {
    const visible = new Set(store.library.items.map((word) => word.id));
    let delta;
    const ok = await controller.run(async () => (delta = await operation()));
    if (ok) {
      try {
        win.localStorage?.setItem('kotoba:changed', `${store.state.revision}:${Date.now()}`);
      } catch {
        /* Storage may be disabled. Focus refresh remains available. */
      }
    }
    if (ok && store.state.view === 'words') {
      const patchable =
        !store.library.query &&
        store.library.status === 'all' &&
        delta.updated_words?.length &&
        delta.updated_words.every((word) => visible.has(word.id)) &&
        !delta.deleted_ids?.length &&
        !delta.imported &&
        store.library.total === store.state.stats.total;
      if (patchable) library.render();
      else await library.load();
    }
    return ok;
  }
  const editor = bindWordEditor({ store, api, doc, mutate, toast });
  bindImportExport({ store, api, doc, mutate, toast });
  bindHistory({ api, doc, mutate });
  bindDialogs(doc);
  function start(mode, scope, view, restart = false, overrides = {}) {
    return mutate(() =>
      api.start({ ...store.state.settings, mode, scope, view, restart, ...overrides }),
    );
  }
  function navigate(view) {
    const s = store.state.session;
    if (view === 'words') return mutate(() => api.preferences({ ...store.state.settings, view }));
    const scope = view === 'review' ? 'wrong' : 'all';
    const mode = view === 'review' ? s?.mode || 'flash' : view;
    if (
      s &&
      s.mode === mode &&
      s.scope === scope &&
      s.quizType === store.state.settings.quizType &&
      s.index < s.total &&
      ['in_progress', 'paused'].includes(s.status)
    ) {
      return mutate(() => api.preferences({ ...store.state.settings, view }));
    }
    return start(mode, scope, view);
  }
  async function studyAction(action, index) {
    if (controller.busy) return;
    const s = store.state.session;
    if (action === 'add') return editor.open();
    if (action === 'all-words') return navigate('flash');
    if (action === 'review') return navigate('review');
    if (action === 'use-flash')
      return start('flash', s?.scope || 'all', store.state.view === 'review' ? 'review' : 'flash');
    if (action === 'restart')
      return start(
        s?.mode || 'flash',
        store.state.view === 'review' ? 'wrong' : 'all',
        store.state.view === 'quiz' ? 'quiz' : store.state.view === 'review' ? 'review' : 'flash',
        true,
      );
    if (!s || s.status !== 'in_progress' || !s.current_word) return;
    if (action === 'reveal' && s.mode === 'flash' && !s.revealed)
      return mutate(() => api.action(s, 'reveal'));
    if (['rate-correct', 'rate-wrong'].includes(action) && s.mode === 'flash' && s.revealed)
      return mutate(() => api.action(s, 'flash_answer', { correct: action === 'rate-correct' }));
    if (
      action === 'choose' &&
      s.mode === 'quiz' &&
      !s.answered &&
      s.options[Number(index)] !== undefined
    )
      return mutate(() => api.action(s, 'quiz_answer', { choice: s.options[Number(index)] }));
    if (action === 'next' && s.answered) return mutate(() => api.action(s, 'next'));
  }
  $('#navigation', doc).addEventListener('click', (event) => {
    const button = event.target.closest('[data-view]');
    if (button) navigate(button.dataset.view);
  });
  $('.shell .brand', doc).addEventListener('click', (event) => {
    event.preventDefault();
    navigate('flash');
  });
  $('#open-review', doc).addEventListener('click', () => navigate('review'));
  $('#flash-mode', doc).addEventListener('click', () =>
    start(
      'flash',
      store.state.view === 'review' ? 'wrong' : 'all',
      store.state.view === 'review' ? 'review' : 'flash',
    ),
  );
  $('#quiz-mode', doc).addEventListener('click', () =>
    start(
      'quiz',
      store.state.view === 'review' ? 'wrong' : 'all',
      store.state.view === 'review' ? 'review' : 'quiz',
    ),
  );
  $('#study-panel', doc).addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (button && !button.disabled) studyAction(button.dataset.action, button.dataset.index);
  });
  $('#new-session', doc).addEventListener('click', () => studyAction('restart'));
  $('#session-size', doc).addEventListener('change', (event) =>
    mutate(() =>
      api.preferences({
        ...store.state.settings,
        count: Number(event.target.value),
        view: store.state.view,
      }),
    ),
  );
  $('#quiz-type', doc).addEventListener('change', (event) => {
    const s = store.state.session;
    start(
      s?.mode || 'flash',
      store.state.view === 'review' ? 'wrong' : 'all',
      store.state.view === 'quiz' ? 'quiz' : store.state.view === 'review' ? 'review' : 'flash',
      false,
      { quizType: event.target.value },
    );
  });
  doc.addEventListener('keydown', (event) => {
    if (
      controller.busy ||
      event.ctrlKey ||
      event.metaKey ||
      event.altKey ||
      event.repeat ||
      selectAll('dialog', doc).some((d) => d.open) ||
      ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(event.target.tagName) ||
      store.state.view === 'words'
    )
      return;
    const s = store.state.session;
    if (!s?.current_word) return;
    if (s.mode === 'flash') {
      if (event.code === 'Space') {
        event.preventDefault();
        studyAction('reveal');
      } else if (s.revealed && ['1', '2'].includes(event.key))
        studyAction(event.key === '1' ? 'rate-wrong' : 'rate-correct');
    } else if (event.key === 'Enter') {
      event.preventDefault();
      studyAction('next');
    } else if (/^[1-4]$/.test(event.key)) {
      event.preventDefault();
      studyAction('choose', Number(event.key) - 1);
    }
  });
  win.addEventListener('focus', async () => {
    if (controller.busy || !refreshPolicy.needsRefresh(store.state.statsExpiresAt)) return;
    if ((await refreshSnapshot()) && store.state.view === 'words') await library.load();
  });
  win.addEventListener('storage', (event) => {
    if (event.key !== 'kotoba:changed') return;
    refreshPolicy.invalidate();
    if (doc.visibilityState !== 'visible') return;
    win.clearTimeout(externalTimer);
    externalTimer = win.setTimeout(async function refreshExternalChange() {
      if (controller.busy) {
        externalTimer = win.setTimeout(refreshExternalChange, 500);
        return;
      }
      if (await refreshSnapshot()) {
        if (store.state.view === 'words') await library.load();
      } else {
        refreshPolicy.invalidate();
      }
    }, 0);
  });
  if (store.state.view === 'words') await library.load();
  else if (
    !store.state.session ||
    (store.state.view === 'review' && !store.state.session.total && store.state.stats.review > 0)
  )
    await navigate(store.state.view);
  return { store, navigate, refresh: refreshSnapshot };
}
