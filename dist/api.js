export class APIError extends Error {
  constructor(message, status = 0, code = 'network_error') {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function createApi(fetcher = (...args) => globalThis.fetch(...args)) {
  let csrf = '';
  let revision = 0;
  async function request(path, { method = 'GET', body, signal } = {}) {
    let response;
    try {
      response = await fetcher(`/api${path}`, {
        method,
        signal,
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf,
          'X-Revision': String(revision),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new APIError('Không kết nối được máy chủ. Thao tác chưa được lưu; hãy thử lại.');
    }
    if (response.status === 204) return null;
    let data;
    try {
      data = await response.json();
    } catch {
      throw new APIError(
        'Phản hồi máy chủ không hợp lệ. Hãy tải lại trang.',
        response.status,
        'invalid_response',
      );
    }
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((e) => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('\n')
        : data.detail;
      throw new APIError(
        detail || 'Chưa xử lý được yêu cầu.',
        response.status,
        data.code || 'request_failed',
      );
    }
    if (data?.csrf) csrf = data.csrf;
    return data;
  }
  const write = (path, method, body) => request(path, { method, body });
  return {
    request,
    acceptRevision(value) {
      revision = value;
    },
    load: () => request('/workspace'),
    catalogue: () => request('/catalogue'),
    preferences: (body) => write('/preferences', 'PUT', body),
    start: (body) => write('/study/sessions', 'POST', body),
    resume: (id) => write(`/study/sessions/${encodeURIComponent(id)}/resume`, 'POST'),
    action: (session, action, values = {}) =>
      write('/study/actions', 'POST', {
        session_id: session.id,
        index: session.index,
        action,
        ...values,
      }),
    words: ({ query = '', status = 'all', offset = 0, limit }, signal) =>
      request(`/words?${new URLSearchParams({ q: query, status, offset, limit })}`, { signal }),
    addWord: (body) => write('/words', 'POST', body),
    editWord: (id, body) => write(`/words/${encodeURIComponent(id)}`, 'PUT', body),
    deleteWord: (id) => write(`/words/${encodeURIComponent(id)}`, 'DELETE'),
    review: (id, marked) =>
      write(`/words/${encodeURIComponent(id)}/review`, 'PATCH', { marked_for_review: marked }),
    previewImport: (words) => write('/words/import/preview', 'POST', { words }),
    importWords: (words) => write('/words/import', 'POST', { words }),
    exportWords: () => request('/words/export'),
    history: (offset = 0, limit = 20) =>
      request(`/study/history?${new URLSearchParams({ offset, limit })}`),
  };
}

export const api = createApi();
