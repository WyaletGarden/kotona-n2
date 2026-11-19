import test from 'node:test';
import assert from 'node:assert/strict';
import { bindHistory } from '../frontend/src/history.js';

function setup() {
  const elements = Object.fromEntries(
    ['content', 'status', 'retry', 'prev', 'next', 'open', 'dialog'].map((name) => [
      `#history-${name}`,
      {
        handlers: {},
        attributes: {},
        disabled: false,
        hidden: false,
        innerHTML: '',
        textContent: '',
        addEventListener(type, handler) {
          this.handlers[type] = handler;
        },
        setAttribute(name, value) {
          this.attributes[name] = value;
        },
        showModal() {
          this.open = true;
        },
        close() {
          this.open = false;
          this.handlers.close();
        },
      },
    ]),
  );
  const requests = [];
  bindHistory({
    doc: { querySelector: (selector) => elements[selector] },
    api: {
      history(offset, limit) {
        return new Promise((resolve, reject) => requests.push({ offset, limit, resolve, reject }));
      },
    },
    mutate() {},
  });
  const get = (name) => elements[`#history-${name}`];
  return { get, requests, click: (name) => get(name).handlers.click() };
}

function page(offset, label = `page-${offset}`) {
  return {
    offset,
    limit: 20,
    total: 60,
    items: [
      {
        id: label,
        mode: 'flash',
        quizType: 'reading',
        status: 'completed',
        created_at: '2026-11-11T00:00:00Z',
        answered_count: 10,
        total: 10,
        correct: label,
      },
    ],
  };
}

test('history locks pagination while loading and advances from the confirmed page', async () => {
  const { get, requests, click } = setup();
  const opened = click('open');
  assert.equal(get('next').disabled, true);
  click('next');
  assert.equal(requests.length, 1);
  requests[0].resolve(page(0));
  await opened;
  const next = click('next');
  click('next');
  assert.equal(requests.length, 2);
  assert.equal(requests[1].offset, 20);
  assert.match(get('content').innerHTML, /page-0/);
  assert.equal(get('content').attributes['aria-busy'], 'true');
  requests[1].resolve(page(20));
  await next;
  assert.match(get('content').innerHTML, /page-20/);
  assert.equal(get('prev').disabled, false);
  assert.equal(get('next').disabled, false);
});

test('history ignores a late response or failure after closing and reopening', async () => {
  for (const fails of [false, true]) {
    const { get, requests, click } = setup();
    const stale = click('open');
    get('dialog').close();
    const current = click('open');
    requests[1].resolve(page(0, 'current-page'));
    await current;
    if (fails) requests[0].reject(Error('stale error'));
    else requests[0].resolve(page(40, 'stale-page'));
    await stale;
    assert.match(get('content').innerHTML, /current-page/);
    assert.equal(get('next').disabled, false);
    assert.equal(get('status').textContent, '');
    assert.equal(get('retry').hidden, true);
  }
});

test('a history network error preserves the confirmed page and retries the failed destination', async () => {
  const { get, requests, click } = setup();
  const opened = click('open');
  requests[0].resolve(page(0));
  await opened;
  const failed = click('next');
  requests[1].reject(Error('offline'));
  await failed;
  assert.match(get('content').innerHTML, /page-0/);
  assert.equal(get('status').textContent, 'offline');
  assert.equal(get('retry').hidden, false);
  assert.equal(get('prev').disabled, true);
  const retry = click('retry');
  assert.equal(requests[2].offset, 20);
  requests[2].resolve(page(20));
  await retry;
  assert.match(get('content').innerHTML, /page-20/);
  assert.equal(get('retry').hidden, true);
});

test('a queued close event cannot invalidate a newly reopened history dialog', async () => {
  const { get, requests, click } = setup();
  const stale = click('open');
  get('dialog').open = false;
  const current = click('open');
  get('dialog').handlers.close();
  requests[1].resolve(page(0, 'reopened-page'));
  await current;
  requests[0].resolve(page(40, 'old-page'));
  await stale;
  assert.match(get('content').innerHTML, /reopened-page/);
  assert.equal(get('content').attributes['aria-busy'], 'false');
  assert.equal(get('next').disabled, false);
});
