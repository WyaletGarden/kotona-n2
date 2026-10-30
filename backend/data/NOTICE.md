# Kotoba vocabulary catalogue — sources and changes

The added vocabulary and Vietnamese study glosses are a derivative dataset under
**Creative Commons Attribution-ShareAlike 4.0 International**:
https://creativecommons.org/licenses/by-sa/4.0/
The full license text is in `CC-BY-SA-4.0.txt`. This notice concerns the vocabulary
data; it does not impose a new license on the application source code.

## Source attribution

Contains data from **OpenJLPT** and its contributors:
https://github.com/evanclan/OpenJLPT

Snapshot commit: `0d1d3410bec90bd4098a7c72de820543cb4f707c`

Source file:
https://github.com/evanclan/OpenJLPT/blob/0d1d3410bec90bd4098a7c72de820543cb4f707c/data/json/vocab/n2.json

Upstream attributions:

- **Jonathan Waller's JLPT Resources**, level assignments and English glosses,
  CC BY: https://www.tanos.co.uk/jlpt/
- **Electronic Dictionary Research and Development Group (EDRDG)**, JMdict
  spellings, readings, dictionary IDs and verification, CC BY-SA 4.0:
  https://www.edrdg.org/jmdict/j_jmdict.html
  Used in conformance with https://www.edrdg.org/edrdg/licence.html
- **OpenJLPT contributors**, corrections and dataset assembly, CC BY-SA 4.0.

The complete upstream notice is retained in `OPENJLPT-NOTICE.md`. No Tatoeba
example sentences, KanjiVG images or KANJIDIC2 character details are copied into
the added Kotoba entries.

## Selection and adaptations

- The source has 1,778 N2 entries, of which 1,587 have a kanji-bearing written
  form. One written form per source entry is selected; spelling alternatives
  are not added just to increase the count.
- Six word/reading pairs already exist in Kotoba's 36 starter words. Those
  starter definitions and notes are retained. **1,581 new entries** are added,
  producing **1,617 total** catalogue entries.
- Some kana-only source headwords have a kanji alternative. These alternatives
  can be uncommon in modern writing; the displayed spelling follows the source.
- Katakana characters in readings are converted to hiragana to match Kotoba's
  input rules (for example, ローマじ → ろーまじ).
- Vietnamese glosses were adapted by AI using the Japanese entries and English
  glosses. A few inaccurate English senses were corrected during adaptation,
  including 工夫／くふう, 努める／つとめる and 統計／とうけい.
- Vietnamese definitions have not received an independent Japanese-teacher
  review. They are concise learning glosses rather than exhaustive dictionaries.
- Added notes are empty rather than manufactured examples. Existing starter
  examples are retained.

JLPT level assignments are community study classifications, not an official
JLPT vocabulary syllabus. See the upstream notice for details.

`catalogue.json` records source checksums, commit, transformations and counts.
`n2-source.json` retains the selected source IDs, spellings, readings and English
glosses; `n2-vi.tsv` maps those IDs to Vietnamese definitions. `starter.json`
preserves the original starter catalogue. Rebuild offline with:

```powershell
.\.venv\Scripts\python.exe scripts/build_n2_seed.py
```

Please preserve this attribution and distribute derivative vocabulary data
under CC BY-SA 4.0 when redistributing or exporting it.
