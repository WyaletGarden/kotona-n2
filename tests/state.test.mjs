import test from 'node:test';
import assert from 'node:assert/strict';
import { createStore, createController } from '../dist/state.js';
import { APIError, createApi } from '../dist/api.js';
import { snapshot, word } from './fixtures.mjs';

test('render failures never turn a confirmed save into a failed write', async () => {
  const store = createStore();
  store.applySnapshot(snapshot());
  const messages = [];
  const statuses = [];
  const runner = createController({
    store,
    api: { acceptRevision() {} },
    changed() {
      throw Error('render');
    },
    error: (failure) => messages.push(failure.message),
    saving: (status) => statuses.push(status),
  });
  assert.equal(await runner.run(async () => snapshot(1)), true);
  assert.equal(store.state.revision, 1);
  assert.ok(statuses.includes('saved'));
  assert.match(messages[0], /đã được xác nhận/);
});

test('compact changes preserve metadata and reject stale pages', () => {
  const store = createStore();
  store.applySnapshot(snapshot());
  store.applyPage({ revision: 0, total: 1617, offset: 0, items: [word] });
  store.applySnapshot({
    ...snapshot(1),
    limits: undefined,
    catalogue: undefined,
    updated_words: [{ ...word, meaning: 'Ký ức' }],
  });
  assert.equal(store.library.items[0].meaning, 'Ký ức');
  assert.equal(store.state.limits.max_words, 2000);
  assert.equal(store.state.catalogue.count, 1617);
  assert.equal(store.applyPage({ revision: 0, items: [], offset: 0, total: 0 }), false);
  assert.equal(store.applySnapshot(snapshot(0)), false);
});
test('failed writes preserve confirmed state and concurrent input is blocked', async () => {
  const store = createStore();
  store.applySnapshot(snapshot());
  let finish,
    calls = 0;
  const runner = createController({ store, api: { acceptRevision() {} }, error() {} });
  const first = runner.run(() => {
    calls++;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  assert.equal(
    await runner.run(() => {
      calls++;
      return snapshot(2);
    }),
    false,
  );
  finish(snapshot(1));
  assert.equal(await first, true);
  assert.equal(calls, 1);
  assert.equal(await runner.run(() => Promise.reject(new APIError('offline'))), false);
  assert.equal(store.state.revision, 1);
});
test('conflicts resync selectively without replaying writes', async () => {
  const store = createStore();
  store.applySnapshot(snapshot());
  let loads = 0,
    writes = 0;
  const api = {
    acceptRevision() {},
    load: async () => {
      loads++;
      return snapshot(3);
    },
  };
  const runner = createController({ store, api, error() {} });
  await runner.run(async () => {
    writes++;
    throw new APIError('duplicate', 409, 'duplicate_word');
  });
  assert.equal(loads, 0);
  await runner.run(async () => {
    writes++;
    throw new APIError('stale', 409, 'revision_conflict');
  });
  assert.equal(loads, 1);
  assert.equal(writes, 2);
  assert.equal(store.state.revision, 3);
});
test('HTTP client sends CSRF, revision and typed study action', async () => {
  const calls = [];
  const client = createApi(async (path, options) => {
    calls.push({ path, options });
    return new Response(JSON.stringify(path.endsWith('/me') ? { csrf: 'test-csrf' } : {}), {
      status: 200,
    });
  });
  await client.request('/auth/me');
  client.acceptRevision(7);
  await client.action({ id: word.id, index: 2 }, 'quiz_answer', { choice: 'きおく' });
  assert.equal(calls[1].options.credentials, 'same-origin');
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'test-csrf');
  assert.equal(calls[1].options.headers['X-Revision'], '7');
  assert.equal(JSON.parse(calls[1].options.body).action, 'quiz_answer');
  await client.words({ query: 'a&b', status: 'review', offset: 50, limit: 50 });
  assert.equal(new URL('https://example.com' + calls[2].path).searchParams.get('q'), 'a&b');
});
test('network, validation and malformed responses remain actionable', async () => {
  await assert.rejects(
    createApi(async () => {
      throw Error('offline');
    }).load(),
    (error) => error.code === 'network_error',
  );
  await assert.rejects(
    createApi(
      async () =>
        new Response(JSON.stringify({ detail: [{ loc: ['body', 'reading'], msg: 'invalid' }] }), {
          status: 422,
        }),
    ).load(),
    /reading: invalid/,
  );
  await assert.rejects(
    createApi(async () => new Response('broken', { status: 200 })).load(),
    (error) => error.code === 'invalid_response',
  );
});
