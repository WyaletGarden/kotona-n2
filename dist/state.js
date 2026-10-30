export function createStore() {
  const state = {
    revision: -1,
    view: 'flash',
    settings: null,
    stats: null,
    session: null,
    limits: null,
    catalogue: null,
  };
  const library = { items: [], total: 0, offset: 0, query: '', status: 'all', loading: false };
  function applySnapshot(snapshot) {
    if (snapshot.revision < state.revision) return false;
    const { revision, view, settings, stats, session } = snapshot;
    Object.assign(state, { revision, view, settings, stats, session });
    if (snapshot.limits) state.limits = snapshot.limits;
    if (snapshot.catalogue) state.catalogue = snapshot.catalogue;
    if (snapshot.updated_words) {
      const updates = new Map(snapshot.updated_words.map((word) => [word.id, word]));
      library.items = library.items.map((word) => updates.get(word.id) || word);
    }
    if (snapshot.deleted_ids)
      library.items = library.items.filter((word) => !snapshot.deleted_ids.includes(word.id));
    return true;
  }
  function applyPage(page) {
    if (page.revision !== state.revision) return false;
    Object.assign(library, { items: page.items, total: page.total, offset: page.offset });
    return true;
  }
  function wordById(id) {
    return (
      library.items.find((word) => word.id === id) ||
      (state.session?.current_word?.id === id ? state.session.current_word : null)
    );
  }
  return { state, library, applySnapshot, applyPage, wordById };
}

export function createController({
  store,
  api,
  changed = () => {},
  saving = () => {},
  error = () => {},
  unauthorized = () => {},
}) {
  let busy = false;
  function accept(snapshot) {
    if (store.applySnapshot(snapshot)) {
      api.acceptRevision(store.state.revision);
      try {
        changed();
      } catch {
        error(
          new Error('Dữ liệu đã được xác nhận nhưng giao diện chưa cập nhật. Hãy tải lại trang.'),
        );
      }
    }
  }
  async function run(operation) {
    if (busy) return false;
    busy = true;
    saving('pending');
    try {
      accept(await operation());
      saving('saved');
      return true;
    } catch (failure) {
      if (failure.status === 401) unauthorized();
      else if (['revision_conflict', 'session_conflict'].includes(failure.code)) {
        try {
          accept(await api.load());
        } catch {
          /* Keep the previous confirmed state. */
        }
      }
      saving('failed');
      error(failure);
      return false;
    } finally {
      busy = false;
      saving('idle');
    }
  }
  return {
    run,
    accept,
    get busy() {
      return busy;
    },
  };
}
