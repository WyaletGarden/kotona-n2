export const limits = {
  max_words: 2000,
  page_size: 50,
  max_page_size: 100,
  import_bytes: 1000000,
  kanji_length: 80,
  reading_length: 120,
  meaning_length: 300,
  note_length: 600,
  password_min: 10,
  password_max: 128,
  mastered_streak: 2,
};
export const word = {
  id: '98d815b8-d890-44eb-b4f2-bd8337e0a1ff',
  kanji: '記憶',
  reading: 'きおく',
  meaning: 'Trí nhớ',
  note: '',
  marked_for_review: false,
  seen: 0,
  correct: 0,
  known: false,
  needs_review: false,
  progress: {
    reading: { seen: 0, correct: 0, streak: 0 },
    meaning: { seen: 0, correct: 0, streak: 0 },
  },
};
export function snapshot(revision = 0) {
  return {
    version: 2,
    revision,
    view: 'flash',
    settings: { count: 10, quizType: 'reading' },
    stats: { total: 1617, known: 0, review: 0, new: 1617 },
    session: null,
    limits,
    catalogue: { count: 1617 },
  };
}
export function session(values = {}) {
  return {
    id: '3b013ddc-4480-4604-a403-e50ae559b630',
    mode: 'flash',
    scope: 'all',
    quizType: 'reading',
    status: 'in_progress',
    index: 0,
    total: 10,
    correct: 0,
    answered_count: 0,
    answered: false,
    current_result: null,
    revealed: false,
    choice: null,
    options: [],
    current_word: structuredClone(word),
    ...values,
  };
}
