// Pure input helpers. Study state and scoring are owned exclusively by the API.
export function normalize(value) {
  return String(value)
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}
export function wordKey(word) {
  return `${word.kanji.trim().normalize('NFC')}|${word.reading.trim().normalize('NFC')}`;
}
export function validateWord(word, limits) {
  if (!word || typeof word !== 'object') return 'Dữ liệu từ không hợp lệ.';
  if (
    !['kanji', 'reading', 'meaning'].every(
      (key) => typeof word[key] === 'string' && word[key].trim(),
    )
  )
    return 'Cần đủ từ, hiragana và nghĩa tiếng Việt.';
  for (const key of ['kanji', 'reading', 'meaning', 'note']) {
    if (String(word[key] || '').length > limits[`${key}_length`]) return `Nội dung ${key} quá dài.`;
  }
  if (!/^[\p{Script=Hiragana}ー・\s]+$/u.test(word.reading))
    return 'Cách đọc chỉ dùng hiragana (ví dụ: ちょうせん).';
  return '';
}
function parseDelimited(text, delimiter) {
  const rows = [];
  let row = [],
    cell = '',
    quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (quoted || cell === '') quoted = !quoted;
      else cell += c;
    } else if (!quoted && c === delimiter) {
      row.push(cell);
      cell = '';
    } else if (!quoted && (c === '\n' || c === '\r')) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell);
      if (row.some((v) => v.trim())) rows.push(row);
      row = [];
      cell = '';
    } else cell += c;
  }
  if (quoted) throw Error('Dấu ngoặc kép trong dữ liệu chưa được đóng.');
  row.push(cell);
  if (row.some((v) => v.trim())) rows.push(row);
  return rows;
}
export function parseImport(input, existing = [], limits) {
  const text = String(input)
    .replace(/^\uFEFF/, '')
    .trim();
  if (!text) return { words: [], errors: ['Chưa có dữ liệu để nhập.'], duplicates: 0 };
  if (new TextEncoder().encode(text).byteLength > limits.import_bytes)
    throw Error(`Dữ liệu vượt quá giới hạn ${limits.import_bytes} byte.`);
  let records;
  if (text.startsWith('[') || text.startsWith('{')) {
    let raw;
    try {
      raw = JSON.parse(text);
    } catch {
      throw Error('JSON không hợp lệ.');
    }
    records = Array.isArray(raw) ? raw : raw.words;
    if (!Array.isArray(records)) throw Error('JSON cần là mảng từ hoặc có thuộc tính words.');
    records = records.map((w) => {
      if (!w || typeof w !== 'object') return { kanji: '', reading: '', meaning: '', note: '' };
      return {
        kanji: String(w.kanji ?? w.word ?? ''),
        reading: String(w.reading ?? w.hiragana ?? ''),
        meaning: String(w.meaning ?? w.nghia ?? ''),
        note: String(w.note ?? ''),
      };
    });
  } else {
    const first = text.split(/\r?\n/)[0];
    const delimiters = ['\t', ',', ';', '|'];
    let inQuotes = false;
    const counts = Object.fromEntries(delimiters.map((d) => [d, 0]));
    for (let i = 0; i < first.length; i++) {
      if (first[i] === '\"') {
        if (inQuotes && first[i + 1] === '\"') {
          i++;
          continue;
        }
        inQuotes = !inQuotes;
      } else if (!inQuotes && delimiters.includes(first[i])) counts[first[i]]++;
    }
    const delim = delimiters.sort((a, b) => counts[b] - counts[a]).find((d) => counts[d] > 0);
    if (!delim) throw Error('Dùng dấu phẩy, tab, | hoặc ; để ngăn cách các cột.');
    let rows = parseDelimited(text, delim);
    const names = rows[0].map((v) => normalize(v.trim()).replace(/\s+/g, ''));
    const aliases = [
      ['kanji', 'word', 'tu', 'tuvung'],
      ['reading', 'hiragana', 'cachdoc'],
      ['meaning', 'nghia', 'nghiatiengviet'],
      ['note', 'ghichu', 'vidu'],
    ];
    const index = aliases.map((a) => names.findIndex((v) => a.includes(v)));
    const header = index.slice(0, 3).every((i) => i >= 0);
    if (header) rows = rows.slice(1);
    records = rows.map((r) => ({
      kanji: r[header ? index[0] : 0] || '',
      reading: r[header ? index[1] : 1] || '',
      meaning: r[header ? index[2] : 2] || '',
      note: r[header ? index[3] : 3] || '',
    }));
  }
  if (records.length > limits.max_words) throw Error(`Mỗi lần nhập tối đa ${limits.max_words} từ.`);
  const keys = new Set(existing.map(wordKey));
  const words = [],
    errors = [];
  let duplicates = 0;
  records.forEach((raw, i) => {
    const w = Object.fromEntries(
      Object.entries(raw).map(([k, v]) => [k, v.trim().normalize('NFC')]),
    );
    const err = validateWord(w, limits);
    if (err) {
      errors.push(`Dòng dữ liệu ${i + 1}: ${err}`);
      return;
    }
    const key = wordKey(w);
    if (keys.has(key)) {
      duplicates++;
      return;
    }
    keys.add(key);
    words.push(w);
  });
  if (existing.length + words.length > limits.max_words)
    throw Error(`Sổ từ tối đa ${limits.max_words} từ.`);
  return { words, errors, duplicates };
}
