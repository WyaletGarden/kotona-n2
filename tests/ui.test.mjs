import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { studyHTML } from '../dist/study-view.js';
import { wordRows } from '../dist/word-library.js';
import { snapshot, session, word } from './fixtures.mjs';

test('flashcard hides answers before revealing and escapes user content', () => {
  assert.doesNotMatch(studyHTML(session(), snapshot().stats), /class="reading"/);
  const html = studyHTML(
    session({ revealed: true, current_word: { ...word, meaning: '<img src=x onerror=alert(1)>' } }),
    snapshot().stats,
  );
  assert.match(html, /class="reading"/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
});
test('quiz feedback reflects the server grade and locks scoring', () => {
  const html = studyHTML(
    session({
      mode: 'quiz',
      total: 1,
      answered: true,
      answered_count: 1,
      current_result: false,
      choice: 'あ',
      options: ['あ', 'きおく'],
    }),
    snapshot().stats,
  );
  assert.match(html, /Chưa đúng/);
  assert.match(html, /disabled/);
  assert.match(html, /Xem kết quả/);
  const summary = studyHTML(
    session({ status: 'completed', index: 10, answered_count: 10, correct: 7, current_word: null }),
    snapshot().stats,
  );
  assert.match(summary, /hoàn thành phiên học/);
  assert.match(summary, />7</);
});
test('manual review mark and mastery are separate in word rows', () => {
  const html = wordRows([{ ...word, marked_for_review: true, needs_review: true }], 2);
  assert.match(html, /Đánh dấu ôn/);
  assert.doesNotMatch(html, /Đã vững/);
  assert.match(html, /Đọc 0\/2/);
});
test('HTML has unique IDs, assets and selectors used by modules', () => {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const m of html.matchAll(/(?:src|href)="\.\/([^"]+)"/g))
    assert.ok(existsSync(new URL('../dist/' + m[1], import.meta.url)));
  for (const file of readdirSync(new URL('../dist/', import.meta.url)).filter((n) =>
    n.endsWith('.js'),
  )) {
    const src = readFileSync(new URL('../dist/' + file, import.meta.url), 'utf8');
    for (const m of src.matchAll(/\$\(['"]#([\w-]+)['"]\s*(?:,|\))/g))
      assert.ok(ids.includes(m[1]), `${file}: missing #${m[1]}`);
  }
  assert.ok(
    ids.includes('word-prev') &&
      ids.includes('word-next') &&
      ids.includes('history-prev') &&
      ids.includes('history-next'),
  );
});
