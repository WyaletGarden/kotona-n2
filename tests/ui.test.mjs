import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { studyHTML } from '../frontend/src/study-view.js';
import { wordRows } from '../frontend/src/word-library.js';
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
      choice: 'ã‚',
      options: ['ã‚', 'ããŠã'],
    }),
    snapshot().stats,
  );
  assert.match(html, /ChÆ°a Ä‘Ãºng/);
  assert.match(html, /disabled/);
  assert.match(html, /Xem káº¿t quáº£/);
  const summary = studyHTML(
    session({ status: 'completed', index: 10, answered_count: 10, correct: 7, current_word: null }),
    snapshot().stats,
  );
  assert.match(summary, /hoÃ n thÃ nh phiÃªn há»c/);
  assert.match(summary, />7</);
});
test('manual review mark and mastery are separate in word rows', () => {
  const html = wordRows([{ ...word, marked_for_review: true, needs_review: true }], 2);
  assert.match(html, /ÄÃ¡nh dáº¥u Ã´n/);
  assert.doesNotMatch(html, /ÄÃ£ vá»¯ng/);
  assert.match(html, /Äá»c 0\/2/);
});
test('HTML has unique IDs, assets and selectors used by modules', () => {
  const html = readFileSync(new URL('../frontend/index.html', import.meta.url), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const m of html.matchAll(/(?:src|href)="\.\/([^"]+)"/g))
    assert.ok(existsSync(new URL('../frontend/src/' + m[1], import.meta.url)));
  for (const file of readdirSync(new URL('../frontend/src/', import.meta.url)).filter((n) =>
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
