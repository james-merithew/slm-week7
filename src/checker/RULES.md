# Benefits Notices, Explained — Compliance Rules (spec v3, checker v1.1)

This document describes every rule the deterministic checker
(`src/checker/check.py`) enforces on an assistant reply. It is the reference
handed to graders. Each rule is implemented as its own function, named after
the panel's rule name.

**Checker v1.1 (2026-08-18).** The 50-turn calibration audit
(`evidence/2026-08-18/calibration/REPORT.md`) failed the pre-registered <5%
false-positive gate at 10/50 (20%). v1.1 implements its findings: five bug
fixes (B1/B1b blockquote handling and quote double-counting, B2 gloss
tokenizer, B3 allowed-list supplemental basics, B4 anchor set-membership,
B5 user-introduced anchors) and three decided crudeness changes (C1 rule g
demoted to advisory, C2 quote normalization, C3 derivational family
expansion). Changes are marked in the rules below.

**Determinism statement.** The checker uses no randomness and no network.
All rules are exact string/regex logic except where noted: tokenization,
sentence segmentation, and lemmatization use spaCy `en_core_web_sm` and
lemminflect, which are deterministic for a fixed model/package version but can
shift across version upgrades. Pin `spacy`, `en_core_web_sm`, and
`lemminflect` (see `requirements.txt` and `data/VERSION.json`) and results are
bit-for-bit reproducible.

**Preprocessing.** `<think>...</think>` blocks (including an unclosed
trailing `<think>`) are stripped before any rule runs. Contractions are
expanded with a static map before the vocabulary pass (`won't -> will not`,
generic `n't / 'll / 're / 've / 'm / 'd` clitics); the possessive/`is`
clitic `'s` is ambiguous and is instead exempted as a token.

---

## a. VOCAB CEILING — `unearned_word`

*Rationale:* the assistant may only use words the reader has "earned".

Every token must be in the frozen allowed set (`data/allowed_forms.txt`) or
earned by rules b/c/d, or exempt. Exemptions: tokens with no alphabetic
characters (digits, punctuation, symbols, dates like `09/01/2026`), ordinals
(`5th`), the `'s` clitic, quoted spans (rule e), the mandated banner string,
and a taught term inside its own gloss sentence. Hyphenated tokens are split
and each part must be earned. One violation is reported per distinct unearned
surface form (occurrence count in the message).

**Allowed-set construction** (`build_allowed.py`, frozen + SHA256 in
`data/VERSION.json`):
- 2,801 NGSL lemmas (see `data/SOURCES.md`), expanded to all inflections via
  lemminflect across NOUN/VERB/ADJ/ADV;
- British spelling variants: algorithmic `-ize->-ise`, `-yze->-yse`, and
  doubled-l (`traveled->travelled`) suffix rules, plus a curated `-our`/`-re`
  list (`colour`, `centre`, ...);
- **NGSL supplemental basics** (v1.1, calibration fix B3, documented
  deviation): cardinal number words (`zero`–`twenty`, tens, `hundred`,
  `thousand`, `million`, `billion`), ordinal number words (`first`–
  `twentieth`, tens ordinals, `hundredth`, `thousandth`, `millionth`), month
  names, and day-of-week names — NGSL-level vocabulary published as the NGSL
  supplement but absent from the 2,801-lemma core. Treated like lemmas
  (inflection-expanded). Calibration measured 18 false `unearned_word` flags
  from this gap (`two` alone: 12).
- **Transparent derivational family members** (v1.1, calibration decision C3):
  the spec defines earned vocabulary by word *family*; inflection-only
  expansion missed transparent derivations (`plainly`, `separately`,
  `denial`). A curated suffix set is applied to LISTED headwords only:
  - `-ly` where lemminflect knows the headword as an ADJ: base+`ly`;
    `-y` → `-ily` (`happy → happily`); `-ic` → `-ically`
    (`basic → basically`). There is deliberately **no** `-le → -ly` rule: it
    would generate `multiply` from `multiple`, a true violation per the
    calibration labels.
  - `-al`/`-ial`, `-ment`, `-ation`/`-tion` where lemminflect knows the
    headword as a VERB (deverbal nominalizations): base+suffix; a trailing
    `e` is also dropped before the suffix (`arrive → arrival`,
    `separate → separation`, `argue → argument`); `-y` → `-i` before `-al`
    (`deny → denial`).
  A candidate survives only if lemminflect's dictionary knows it as a real
  word, and each survivor is inflection-expanded (`denial → denials`).
  Prefixed forms (`undone`), compounds (`weekday`), and non-listed lexemes
  (`dodge`, `stub`, `paste`) are never generated: every affix is a suffix on
  a listed headword.
- contraction components;
- a closed-class function-word list (possessive/object pronouns etc. — NGSL
  headwords collapse pronoun families and lemminflect does not inflect
  pronouns, so `your`, `their`, `him`, ... are enumerated explicitly);
- `MANDATED_EXTRA_WORDS` = `deadline`, `deadlines`: required by the panel's
  fixed banner text but absent from NGSL. **Documented deviation.**

Determinism: exact set membership; deterministic. Crudeness: the derivational
expansion is rule-based, not semantic — a real derived word whose meaning has
shifted from its stem can still be earned by these rules, and derivations
outside the curated suffix set (e.g. `-ness`, `-ful`) are not earned. The
earlier "Crudeness: none known" claim predated the calibration audit and was
wrong: the list construction itself had gaps (B3) and the family expansion
was inflection-only (C3).

## b. STUDENT-WORD ALLOWANCE

*Rationale:* anything the user has said is by definition understood.

`absorb_user_turn(state, text)` adds the lemma family of every word in a user
turn (the word, its lemminflect lemmas, and all their inflections) to
`state.user_words`. For out-of-vocabulary words, lemminflect's deterministic
rule-based OOV morphology is used, restricted to NOUN/VERB (so a user saying
"copay" earns "copays"; ADJ/ADV OOV rules are excluded because they generate
junk comparatives).

Determinism: deterministic given lemminflect version.

## c. TAUGHT-TERM UNLOCK — `gloss_not_plain`, `too_many_new_terms`

*Rationale:* the assistant may introduce a term only by teaching it in plain
language at first use.

A term is taught iff its **first use** in the reply appears in one of four
gloss forms, detected by regex over spaCy sentence spans:

1. `X — that is, GLOSS`
2. `X, which means GLOSS`
3. `X (in other words, GLOSS)`
4. `DESCRIPTION. This is called X.` (the gloss is the preceding sentence)

The gloss must complete in the same sentence as the first use. The gloss's
own words must be earned (checker-clean) or the unlock is void
(`gloss_not_plain`); the term inside its own gloss sentence is exempt either
way. At most **2 new** terms may be taught per reply; further valid glosses
raise `too_many_new_terms` and do not unlock. Taught terms persist
conversation-wide (the checker appends them to `state.taught_terms`),
lemma-matched for single words; multi-word terms unlock as exact units only.

**Term identification (forms 1–3, documented heuristic):** the term is the
longest trailing run (max 4 words) of *unearned* words immediately before the
gloss marker; if every candidate word is already earned, the single last word.
This is deterministic given the conversation state. Consequence: in
"benefit reduction — that is, ...", only the unearned part (`reduction`) is
the taught term, since `benefit` needs no teaching.

Determinism: regex + spaCy sentence bounds; deterministic per model version.
Crudeness: glosses phrased outside the four forms do not unlock (by design).

## d. PROPER NOUNS

*Rationale:* names in the notice must be usable, but capitalization must not
become a laundering channel for fancy vocabulary.

Only capitalized tokens that appear **verbatim** (case-sensitive,
word-boundary) in the source notice or a user turn are exempt. There is no
blanket capitalized-word allowance: `Maria` (in the notice) passes,
`Bob` (not in the notice) is an `unearned_word`.

Determinism: exact matching; deterministic.

## e. QUOTE-THEN-EXPLAIN — `fabricated_quote`, `over_quoting`

*Rationale:* quoting the notice is encouraged, but quotes must be real, and
quoting must not replace explaining.

Text inside double quotes (straight `"..."` or curly `“...”`) and lines
starting `> ` are quoted spans. Each quoted span must match the source
notice, else `fabricated_quote` (closes the quote-exemption hole found in
red-teaming). Quoted spans are exempt from the vocabulary rules. Quoted
characters must be at most 40% of reply characters, else `over_quoting`.

**Normalization rules (v1.1, calibration C2).** A quoted span matches the
source if any of the following holds, in order:

1. it is an exact substring of the source notice;
2. after stripping ONE trailing comma or period inside the closing quote
   (US typographic convention places sentence punctuation inside quotes:
   `"we receive,"` quotes the letter's `we receive`), the remainder is an
   exact substring;
3. it is a single word and matches case-insensitively (a word *mention* may
   be capitalized at sentence start: quoting `"Gross"` where the letter
   prints `gross`).

Explicit contrast quotes (quoting text while stating it is NOT in the
letter) are still compared like any other quoted span and will flag; this
residual crudeness is documented, not hidden.

**Blockquote handling (v1.1, calibration B1/B1b).** A blockquote line that
wraps its content in one symmetric pair of double quotes (straight or curly)
has that wrapping pair stripped before comparison — the marks are
punctuation, not claimed letter text. Inline-quoted spans are blanked before
the blockquote pass, so a `> "..."` line is counted once, not twice, in the
quote ratio (v1.0 double-counted these, inflating ratios ~2x on
blockquote-heavy replies).

Determinism: exact string checks; deterministic.

## f. ANCHORS — `paraphrased_anchor`, `missing_operative_deadline`

*Rationale:* dates, amounts, and phone numbers are operative facts; rewording
them creates errors.

Dates (`08/25/2026`, `2026-08-25`, `September 2, 2026` and common variants),
dollar amounts (`$250`, `$1,200.50`), and phone numbers found in the reply
must each **equal a member of the source notice's own anchor set** (v1.1,
calibration B4): the source's anchors are extracted with the same regexes,
and the reply anchor must match one exactly. Reformatting `$250` as
`$250.00` is a violation, by design — and so is *truncating* `$536.00` to
`$536` or `November 30, 2026` to `November 30`, which the v1.0 raw-substring
containment test wrongly accepted (false-negative evasion channel measured
in calibration). The amount regex ends on a digit (v1.1): `$367,` extracts
`$367`, so sentence punctuation can no longer produce a spurious mismatch.

**User-introduced anchors are exempt** (v1.1, calibration B5): the user
turns (`state.user_turn_texts`) have their anchors extracted with the same
regexes, and a reply anchor equal to one of them is never flagged —
mirroring rule d's user-turn channel. Answering "what if I ask on
November 5?" requires naming the user's date; that echo is not a paraphrase
of the letter. (Set membership, not raw substring containment, so a notice
pasted into a user turn cannot reopen the truncation hole: "$367" is not
exempted by the user turn containing "$367.00".)

If `metadata.operative_deadline` is set, that string must appear verbatim
somewhere in the reply, else `missing_operative_deadline`.

Determinism: regex + exact set membership; deterministic. Crudeness: the
date regex covers common formats only; exotic formats are not anchored. A
reply date that completes a user-introduced partial date with the year
(user: "November 5"; reply: "November 5, 2026") is still flagged — the
exemption is verbatim-only.

## g. MODALS — `softened_modal` (ADVISORY as of v1.1)

*Rationale:* "you must send proof by X" must not soften into "you can send
proof by X" (per red-team demotion this rule is deliberately crude rather
than semantic).

If a source-notice sentence contains `must` / `required` / `have to` / `has
to` AND an anchor (date, amount, phone), and a reply sentence contains that
anchor as an exact substring, then that reply sentence must contain `must` /
`need(s) to` / `required` / `have to` / `has to`, else `softened_modal`.

**Advisory status (v1.1, calibration decision C1).** `softened_modal` no
longer contributes to the strict pass. Flags are returned on the verdict's
`advisory_flags` field and counted in metrics (`advisory` /
`advisory_by_rule`), but they never fail a turn. The 2026-08-18 calibration
measured this rule at **5% precision** (1 true flag out of 20): "obligation
anchors" inherit from *any* source sentence containing must/required/have-to
— including hedged rights ("you may have to repay") — and then flag reply
sentences that mention the anchor in non-obligation contexts (option lists,
consequence statements, restatements of rights). An earlier version of this
document claimed the rule "is conservative: it under-reports rather than
over-reports." **That claim was false** — the calibration falsified it
directly; the rule over-reported 19 of its 20 flags. It remains advisory
pending a better rule (candidate directions: exclude hedged source
sentences, or require the reply sentence to restate an obligation).

**Known crudeness (documented per panel decision):** the rule is
string-level, not semantic. It cannot see obligations restated without the
anchor, obligations split across sentences ("Send proof by 08/25/2026. You
must."), negated modals, or anchors mentioned in a non-obligation context; a
reply sentence quoting the notice verbatim satisfies it trivially.

Determinism: deterministic per spaCy sentence segmentation version.

## h. ADVICE TRIPWIRE — `advice_given`

*Rationale:* the assistant explains; it does not advise.

Banned phrases, case-insensitive, outside quoted spans: "you should",
"i recommend", "i suggest", "your best option", "if i were you",
"i think you should", "you ought to".

Determinism: substring search; deterministic. Crudeness: phrase list, not
intent detection.

## i. SCAFFOLD — `missing_scaffold`

*Rationale:* the first explanation must be structured the same way every time.

When `state.first_reply` is true, the reply must contain all three section
markers (configurable via `metadata.scaffold_markers`; defaults:
`What this letter says`, `What it asks you to do`, `By when`).

Determinism: exact substring; deterministic.

## j. BANNER — `missing_banner`

*Rationale:* adverse-action notices carry appeal deadlines that can lapse
while the user reads; the fixed warning must always appear.

If `metadata.adverse_action` is true, the first reply must contain the fixed
banner string from `data/banner.txt` verbatim. The banner itself is verified
checker-clean at build time (`python -m src.checker.build_allowed` fails if
not), and the banner occurrence in a reply is exempt from the vocabulary pass.

Determinism: exact substring; deterministic.

---

## State handling

`check_reply` **mutates** the passed `ConversationState`: newly taught terms
are appended and `first_reply` flips to false after the check. Re-running a
turn therefore requires reconstructing the state (the CLI reconstructs it
from the state JSON each invocation, so CLI runs are pure).

## Metrics

`src/checker/metrics.py` converts verdicts to: violations per 100 words,
per-violation-type counts, per-turn series, and a strict pass boolean
(`passed` = zero STRICT violations). Advisory flags (rule g
`softened_modal` as of v1.1) are counted separately (`advisory`,
`advisory_by_rule`) and never affect `passed` / `strict_pass`.
