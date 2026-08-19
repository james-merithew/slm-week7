"""Build and freeze the allowed-forms set for the vocab ceiling.

Pipeline (fully deterministic):
  1. Read NGSL lemmas from data/ngsl_lemmas.txt (2,801 headwords).
  2. Add the NGSL supplemental basics (number words, months, days) as a
     documented deviation (2026-08-18 calibration, fix B3).
  3. Expand every lemma to all inflections via lemminflect (all open POS).
  4. Add transparent derivational forms of listed headwords via a curated
     affix set (2026-08-18 calibration, decision C3), then their inflections.
  5. Add British spelling variants (-ise / doubled-l suffix rules plus a
     curated -our / -re list).
  6. Add contraction components and the possessive clitic tokens.
  7. Add the small, documented mandated-vocabulary list (words the panel's
     fixed banner requires but NGSL lacks).
  8. Freeze to data/allowed_forms.txt and record SHA256 hashes in
     data/VERSION.json.

Run:  python -m src.checker.build_allowed
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from .wordforms import (
    CONTRACTION_COMPONENTS,
    CURATED_BRITISH,
    british_variants,
    expand_contractions,
    inflections_of,
)

DATA_DIR = Path(__file__).parent / "data"
LEMMAS_PATH = DATA_DIR / "ngsl_lemmas.txt"
ALLOWED_PATH = DATA_DIR / "allowed_forms.txt"
VERSION_PATH = DATA_DIR / "VERSION.json"
BANNER_PATH = DATA_DIR / "banner.txt"

# Words the spec's FIXED banner text requires but which are not NGSL word
# families. Documented deviation (see RULES.md): the panel mandates the exact
# banner string, so its vocabulary must be sayable.
MANDATED_EXTRA_WORDS = ["deadline", "deadlines"]

# NGSL supplemental basics (documented deviation; 2026-08-18 calibration,
# fix B3). The 2,801-lemma NGSL core omits vocabulary the NGSL project
# publishes as its supplemental word list: cardinal/ordinal number words,
# month names, and day-of-week names. "two" alone accounted for 12 false
# unearned_word flags on spec-prompted calibration turns. These are treated
# exactly like NGSL lemmas (inflection-expanded).
SUPPLEMENTAL_BASICS = [
    # cardinal number words
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "million", "billion",
    # ordinal number words
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "thirtieth", "fortieth", "fiftieth",
    "sixtieth", "seventieth", "eightieth", "ninetieth", "hundredth",
    "thousandth", "millionth",
    # month names
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    # day-of-week names
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
]

# Derivational affixes for transparent family members of LISTED headwords
# (2026-08-18 calibration, decision C3). Inflection-only expansion missed
# transparent derivations ("plainly", "separately", "denial"). Exact rules
# (documented in RULES.md / SOURCES.md; deliberately conservative):
#   -ly    only where lemminflect knows the headword as an ADJ:
#          base+"ly"; base ending in "y" -> y->i +"ly" (happy->happily);
#          base ending in "ic" -> +"ally" (basic->basically).
#          (No "-le"->"-y" rule: it would generate "multiply" from
#          "multiple", a true violation per the calibration labels.)
#   -al/-ial, -ment, -ation/-tion
#          only where lemminflect knows the headword as a VERB
#          (deverbal nominalizations): base+suffix; a base ending in "e"
#          also drops it before the suffix (arrive->arrival,
#          separate->separation, argue->argument); a base ending in "y"
#          takes y->i before "-al" (deny->denial).
# A candidate survives only if lemminflect's dictionary knows it (realness
# filter). Prefixed forms (un-), compounds (weekday), and non-listed lexemes
# (dodge, stub) are never generated: every affix is a suffix on a listed
# headword.
DERIVATIONAL_SUFFIX_NOTE = "-ly (ADJ headwords); -al/-ial/-ment/-ation/-tion (VERB headwords)"


def _lemminflect_known(word: str) -> bool:
    from lemminflect import getLemma

    return any(
        getLemma(word, upos=u, lemmatize_oov=False)
        for u in ("NOUN", "VERB", "ADJ", "ADV")
    )


def derivational_forms(lemmas: list[str]) -> set[str]:
    """Transparent derivational family members of listed headwords (C3)."""
    from lemminflect import getAllInflections

    listed = set(lemmas)
    out: set[str] = set()
    for lem in lemmas:
        cands: set[str] = set()
        if getAllInflections(lem, upos="ADJ"):
            if lem.endswith("y") and len(lem) > 2:
                cands.add(lem[:-1] + "ily")
            elif lem.endswith("ic"):
                cands.add(lem + "ally")
            else:
                cands.add(lem + "ly")
        if getAllInflections(lem, upos="VERB"):
            if lem.endswith("y"):
                cands.add(lem[:-1] + "ial")   # deny -> denial
            elif lem.endswith("e"):
                cands.add(lem[:-1] + "al")    # arrive -> arrival
                cands.add(lem[:-1] + "ial")
                cands.add(lem[:-1] + "ation")  # separate -> separation
                cands.add(lem[:-1] + "tion")
                cands.add(lem[:-1] + "ment")   # argue -> argument
            else:
                cands.add(lem + "al")
                cands.add(lem + "ial")
                cands.add(lem + "ation")       # confirm -> confirmation
                cands.add(lem + "tion")
            cands.add(lem + "ment")            # pay -> payment
        out |= {c for c in cands if c not in listed and _lemminflect_known(c)}
    return out

# Closed-class function words (spec: "function words/digits policy").
# NGSL headwords collapse pronoun families (e.g. "you" is a headword but
# "your"/"yours" are not), and lemminflect does not inflect pronouns, so the
# closed class is enumerated explicitly here. Documented in RULES.md.
FUNCTION_WORDS = [
    "an", "etc",
    "me", "my", "mine", "myself",
    "your", "yours", "yourself", "yourselves",
    "him", "his", "himself",
    "her", "hers", "herself",
    "its", "itself",
    "our", "ours", "ourselves",
    "them", "their", "theirs", "themselves",
    "these", "those",
    "whom", "whose",
    "oneself",
    "ok", "okay",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lemmas() -> list[str]:
    return [
        w.strip().lower()
        for w in LEMMAS_PATH.read_text(encoding="utf-8").splitlines()
        if w.strip()
    ]


def build_allowed_forms() -> set[str]:
    lemmas = load_lemmas()
    forms: set[str] = set()
    # NGSL supplemental basics (B3) are treated exactly like listed lemmas.
    expandable = lemmas + [w for w in SUPPLEMENTAL_BASICS if w not in lemmas]
    for lem in expandable:
        forms |= inflections_of(lem)
    # Transparent derivational family members of listed headwords (C3),
    # themselves inflection-expanded (denial -> denials).
    for der in sorted(derivational_forms(lemmas)):
        forms |= inflections_of(der)
    # British variants of every generated form (algorithmic rules).
    for f in list(forms):
        forms |= british_variants(f)
    # Curated British pairs, only when the American base is present.
    for base, variants in CURATED_BRITISH.items():
        if base in forms:
            forms.update(variants)
    forms.update(CONTRACTION_COMPONENTS)
    forms.update(MANDATED_EXTRA_WORDS)
    forms.update(FUNCTION_WORDS)
    return forms


def load_allowed() -> set[str]:
    """Load the frozen allowed set (build it first if missing)."""
    if not ALLOWED_PATH.exists():
        freeze()
    return set(ALLOWED_PATH.read_text(encoding="utf-8").split())


def verify_banner(allowed: set[str]) -> list[str]:
    """Return the banner words NOT covered by the allowed set (should be [])."""
    banner = BANNER_PATH.read_text(encoding="utf-8")
    text = expand_contractions(banner)
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text)
    return sorted({w.lower() for w in words} - allowed)


def freeze() -> dict:
    import lemminflect

    lemmas = load_lemmas()
    derived = sorted(derivational_forms(lemmas))
    forms = build_allowed_forms()
    ALLOWED_PATH.write_text(
        "\n".join(sorted(forms)) + "\n", encoding="utf-8", newline="\n"
    )
    unclean = verify_banner(forms)
    meta = {
        "spec": "Benefits Notices, Explained — checker spec v3",
        "checker_version": "1.1",
        "ngsl_lemma_count": len(lemmas),
        "allowed_form_count": len(forms),
        "ngsl_lemmas_sha256": _sha256(LEMMAS_PATH),
        "allowed_forms_sha256": _sha256(ALLOWED_PATH),
        "lemminflect_version": lemminflect.__version__,
        "mandated_extra_words": MANDATED_EXTRA_WORDS,
        "supplemental_basics_count": len(SUPPLEMENTAL_BASICS),
        "derivational_affix_rules": DERIVATIONAL_SUFFIX_NOTE,
        "derived_headword_count": len(derived),
        "banner_checker_clean": not unclean,
        "banner_uncovered_words": unclean,
    }
    VERSION_PATH.write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return meta


def main() -> int:
    meta = freeze()
    print(json.dumps(meta, indent=2))
    if not meta["banner_checker_clean"]:
        print("ERROR: banner is not checker-clean:", meta["banner_uncovered_words"],
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
