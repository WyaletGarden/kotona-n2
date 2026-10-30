import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { normalize, parseImport, validateWord, wordKey } from '../dist/core.js';
import { limits, word } from './fixtures.mjs';

test('Vietnamese search normalization and NFC word identity', () => {
  assert.equal(normalize('ĐƯỜNG'), 'duong');
  assert.equal(wordKey({ kanji: ' 記憶 ', reading: 'きおく ' }), '記憶|きおく');
  assert.equal(validateWord(word, limits), '');
  assert.match(validateWord({ ...word, reading: 'kioku' }, limits), /hiragana/);
});
test('quoted CSV, multiline notes, TSV and header aliases', () => {
  const r = parseImport(
    '\ufeffkanji,hiragana,meaning,note\r\n記憶,きおく,"Trí nhớ, ký ức","Ví dụ\nHai dòng"',
    [],
    limits,
  );
  assert.equal(r.words[0].meaning, 'Trí nhớ, ký ức');
  assert.match(r.words[0].note, /\n/);
  for (const d of ['\t', '|', ';'])
    assert.equal(parseImport(`記憶${d}きおく${d}Trí nhớ`, [], limits).words.length, 1);
  assert.equal(
    parseImport('từ,cách đọc,nghĩa tiếng Việt\n記憶,きおく,Trí nhớ', [], limits).words.length,
    1,
  );
});
test('attributed JSON exports round trip and duplicates are reported', () => {
  const data = { words: [word, word], attribution: { license: 'CC BY-SA 4.0' } };
  const parsed = parseImport(JSON.stringify(data), [], limits);
  assert.equal(parsed.words.length, 1);
  assert.equal(parsed.duplicates, 1);
  assert.equal(parseImport(JSON.stringify(data), [word], limits).words.length, 0);
});
test('malformed input, invalid fields and UTF-8 byte limits', () => {
  assert.throws(() => parseImport('[broken', [], limits), /JSON/);
  assert.throws(() => parseImport('記憶,きおく,"unfinished', [], limits), /ngoặc kép/);
  assert.throws(() => parseImport('あ'.repeat(350000), [], limits), /giới hạn/);
  assert.equal(parseImport('[null,1]', [], limits).errors.length, 2);
  assert.equal(parseImport('記憶,,Trí nhớ', [], limits).errors.length, 1);
});
test('parameterized capacity and complete catalogue parsing', () => {
  assert.throws(
    () =>
      parseImport('記憶,きおく,Trí nhớ\n習慣,しゅうかん,Thói quen', [], {
        ...limits,
        max_words: 1,
      }),
    /tối đa 1/,
  );
  const catalogue = JSON.parse(
    readFileSync(new URL('../backend/seed.json', import.meta.url), 'utf8'),
  );
  assert.equal(parseImport(JSON.stringify(catalogue), [], limits).words.length, catalogue.length);
});
