"""Shared word-form machinery for the compliance checker.

Everything in this module is pure-Python + lemminflect and fully
deterministic: same input -> same output, no network, no randomness.
"""
from __future__ import annotations

import re

from lemminflect import getAllInflections, getAllInflectionsOOV, getLemma

# Universal POS tags we expand across. lemminflect covers open-class words.
_UPOS = ("NOUN", "VERB", "ADJ", "ADV")
# POS used for deterministic OOV rule-based expansion (ADJ/ADV OOV rules
# generate junk comparatives, so they are excluded).
_OOV_UPOS = ("NOUN", "VERB")


def inflections_of(lemma: str) -> set[str]:
    """All inflected forms of *lemma* across NOUN/VERB/ADJ/ADV, lowercased,
    including the lemma itself. For out-of-dictionary lemmas, falls back to
    lemminflect's deterministic OOV morphology rules (NOUN/VERB only)."""
    lemma = lemma.lower()
    out = {lemma}
    for upos in _UPOS:
        for forms in getAllInflections(lemma, upos=upos).values():
            out.update(f.lower() for f in forms)
    if out == {lemma}:  # not in lemminflect's dictionary
        for upos in _OOV_UPOS:
            for forms in getAllInflectionsOOV(lemma, upos).values():
                out.update(f.lower() for f in forms)
    return out


def family(word: str) -> set[str]:
    """The earned "lemma family" of a surface word: the word itself, every
    lemma lemminflect maps it to, and every inflection of those lemmas.

    In-dictionary lemmatization is preferred; for out-of-vocabulary words the
    deterministic OOV rules are used (NOUN/VERB only) so that e.g. a user
    saying "copay" earns "copays" too (documented in RULES.md).
    """
    w = word.lower()
    out = {w}
    lemmas = {w}
    found = False
    for upos in _UPOS:
        got = getLemma(w, upos=upos, lemmatize_oov=False)
        if got:
            lemmas.update(g.lower() for g in got)
            found = True
    if not found:
        for upos in _OOV_UPOS:
            got = getLemma(w, upos=upos, lemmatize_oov=True)
            if got:
                lemmas.update(g.lower() for g in got)
    for lem in lemmas:
        out |= inflections_of(lem)
    return out


# --------------------------------------------------------------------------
# British spelling variants
# --------------------------------------------------------------------------

# Algorithmic suffix rules (safe, purely orthographic).
_SUFFIX_RULES = (
    ("izations", "isations"), ("ization", "isation"),
    ("izing", "ising"), ("izes", "ises"), ("ized", "ised"), ("ize", "ise"),
    ("izers", "isers"), ("izer", "iser"), ("izable", "isable"),
    ("yzing", "ysing"), ("yzes", "yses"), ("yzed", "ysed"), ("yze", "yse"),
)

# Single-l -> double-l before suffix (travel -> travelled etc.).
_ELL_RULES = (
    ("eled", "elled"), ("eling", "elling"),
    ("eler", "eller"), ("elers", "ellers"),
)

# Curated full-form pairs that no safe suffix rule can generate
# (-our, -re, and misc.). Key = American lemma that must already be in the
# allowed set for the variants to be added.
CURATED_BRITISH: dict[str, list[str]] = {
    "color": ["colour", "colours", "coloured", "colouring", "colourful"],
    "honor": ["honour", "honours", "honoured", "honouring"],
    "favor": ["favour", "favours", "favoured", "favouring"],
    "favorite": ["favourite", "favourites"],
    "labor": ["labour", "labours", "laboured", "labouring"],
    "neighbor": ["neighbour", "neighbours", "neighbouring",
                 "neighbourhood", "neighbourhoods"],
    "behavior": ["behaviour", "behaviours"],
    "humor": ["humour"],
    "flavor": ["flavour", "flavours"],
    "harbor": ["harbour", "harbours"],
    "center": ["centre", "centres", "centred", "centring"],
    "theater": ["theatre", "theatres"],
    "meter": ["metre", "metres"],
    "liter": ["litre", "litres"],
    "fiber": ["fibre", "fibres"],
    "gray": ["grey", "greys"],
    "practice": ["practise", "practises", "practised", "practising"],
    "license": ["licence", "licences"],
    "defense": ["defence", "defences"],
    "offense": ["offence", "offences"],
    "program": ["programme", "programmes"],
    "check": ["cheque", "cheques"],
    "tire": ["tyre", "tyres"],
    "age": ["ageing"],
    "judgment": ["judgement", "judgements"],
    "enroll": ["enrol", "enrolment"],
    "fulfill": ["fulfil", "fulfilment"],
}


def british_variants(form: str) -> set[str]:
    """British spellings derivable from *form* by safe suffix rules."""
    out: set[str] = set()
    for a, b in _SUFFIX_RULES:
        if form.endswith(a) and len(form) > len(a) + 1:
            out.add(form[: -len(a)] + b)
    for a, b in _ELL_RULES:
        if form.endswith(a) and len(form) > len(a) + 2:
            out.add(form[: -len(a)] + b)
    return out


# --------------------------------------------------------------------------
# Contractions (static map — applied to text BEFORE tokenization)
# --------------------------------------------------------------------------

_APOS = "['’]"
# Order matters: irregulars first, then generic clitic patterns.
_CONTRACTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(rf"\bwon{_APOS}t\b", re.I), "will not"),
    (re.compile(rf"\bcan{_APOS}t\b", re.I), "can not"),
    (re.compile(rf"\bshan{_APOS}t\b", re.I), "shall not"),
    (re.compile(rf"\bain{_APOS}t\b", re.I), "is not"),
    (re.compile(rf"\blet{_APOS}s\b", re.I), "let us"),
    (re.compile(rf"\bcannot\b", re.I), "can not"),
    (re.compile(rf"n{_APOS}t\b", re.I), " not"),
    (re.compile(rf"{_APOS}ll\b", re.I), " will"),
    (re.compile(rf"{_APOS}re\b", re.I), " are"),
    (re.compile(rf"{_APOS}ve\b", re.I), " have"),
    (re.compile(rf"{_APOS}m\b", re.I), " am"),
    (re.compile(rf"{_APOS}d\b", re.I), " would"),
]

# The words the generic patterns can introduce (contraction components) —
# added to the allowed set at build time so expansion never creates a
# violation by itself.
CONTRACTION_COMPONENTS = [
    "not", "will", "are", "have", "am", "would", "can", "shall", "us", "is",
    # possessive / is-clitic token left in place and exempted at check time:
    "'s", "’s",
]


def expand_contractions(text: str) -> str:
    """Expand common English contractions via the static map above.

    The possessive / "is" clitic ('s) is deliberately left alone (ambiguous);
    the checker exempts the 's token instead.
    """
    for pat, repl in _CONTRACTION_PATTERNS:
        text = pat.sub(repl, text)
    return text
