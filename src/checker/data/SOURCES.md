# Data sources

## ngsl_lemmas.txt

- **What:** The 2,801 headwords (lemmas) of the New General Service List
  (NGSL 1.01), by Charles Browne, Brent Culligan, and Joseph Phillips (2013).
- **License of the NGSL itself:** Creative Commons Attribution 3.0 (CC BY 3.0).
  Attribution: "New General Service List" by Browne, C., Culligan, B., and
  Phillips, J. — https://www.newgeneralservicelist.org/
- **Obtained from (machine-readable mirror):**
  https://github.com/lpmi-13/machine_readable_wordlists
  (file `General/NGSL/NGSL.json`, repo licensed CC0; the underlying NGSL word
  list remains CC BY and is attributed above). Downloaded 2026-08-18.
- **Processing:** the JSON stores three frequency bands (1000/2000/2801) as
  {headword: [family members]}. We extracted only the headword keys,
  lowercased, deduplicated, and sorted — 2,801 lemmas. The mirror's
  family-member arrays were NOT used; inflection expansion is done
  independently and reproducibly with lemminflect (see build_allowed.py).

## NGSL supplemental basics (checker v1.1, calibration fix B3)

The NGSL project publishes a supplemental word list alongside the 2,801-lemma
core: numbers, months, days, and similar closed-set basics. The core-only
build flagged "two"/"three"/"January" as violations (18 false flags in the
2026-08-18 calibration). `build_allowed.SUPPLEMENTAL_BASICS` (81 words)
enumerates them explicitly as a **documented deviation** from the raw
core-lemma list: cardinal number words (zero–twenty, tens, hundred, thousand,
million, billion), ordinal number words (first–twentieth, tens ordinals,
hundredth, thousandth, millionth), the 12 month names, and the 7 day-of-week
names. They are inflection-expanded exactly like NGSL lemmas.

## Derivational family expansion (checker v1.1, calibration decision C3)

The spec defines earned vocabulary by word *family*; the v1.0 build expanded
inflections only. v1.1 adds transparent derivational forms of LISTED
headwords via a curated suffix set (`build_allowed.derivational_forms`):

- `-ly` where lemminflect knows the headword as an ADJ (base+`ly`;
  `-y`→`-ily`; `-ic`→`-ically`; **no** `-le`→`-ly` rule, which would
  generate "multiply" from "multiple" — a true violation per the calibration
  labels);
- `-al`/`-ial`, `-ment`, `-ation`/`-tion` where lemminflect knows the
  headword as a VERB (trailing `e` also dropped before the suffix;
  `-y`→`-i` before `-al`, so deny→denial).

Candidates are kept only if lemminflect's dictionary knows them as real
words, then inflection-expanded. 412 derived headwords survive. Prefixed
forms (undone), compounds (weekday), and non-listed lexemes (dodge, stub,
paste) are never generated.

## allowed_forms.txt

Generated artifact — do not edit by hand. Rebuild with
`python -m src.checker.build_allowed`. Provenance, counts, and SHA256 hashes
are recorded in VERSION.json. Includes a small documented
`MANDATED_EXTRA_WORDS` list (currently: deadline, deadlines) required by the
panel's fixed banner text but absent from NGSL, plus the supplemental
basics and derivational expansions described above.

## banner.txt

Fixed banner string specified by the expert panel (spec v3, rule j).
Verified checker-clean at build time.
