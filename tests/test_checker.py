"""Tests for the deterministic compliance checker (spec v3).

Every rule has a passing case and a failing case, plus an end-to-end
compliant reply over a small synthetic notice.
"""
import json
from pathlib import Path

import pytest

from src.checker import (
    ConversationState,
    absorb_user_turn,
    check_reply,
    conversation_series,
    reply_metrics,
)
from src.checker.build_allowed import ALLOWED_PATH, VERSION_PATH, _sha256

NOTICE = """State Benefits Office
Notice of Change for Maria Lopez
Date: 08/01/2026
Your monthly food benefit will change from $250 to $180 on 09/01/2026.
You must send proof of your income by 08/25/2026 if you do not agree.
If you want a hearing, you must ask for one by 08/25/2026.
Call 1-800-555-0199 with questions. Case number: 12345678.
"""

BANNER = (
    "Important: letters like this often have a much shorter deadline if you "
    "want to keep your benefits while you ask for a hearing. Look for it in "
    "the letter, and ask a free legal aid office if you are not sure."
)


def make_state(first_reply=False):
    state = ConversationState(first_reply=first_reply)
    absorb_user_turn(state, "Can you explain this letter I got?")
    return state


def rules_of(verdict):
    return [v.rule for v in verdict.violations]


# ---------------------------------------------------------------- rule a


def test_vocab_ceiling_pass():
    v = check_reply("Your food benefit will change soon.", NOTICE, make_state())
    assert v.passed


def test_vocab_ceiling_fail():
    v = check_reply("The stipulations herein necessitate remittance.",
                    NOTICE, make_state())
    assert set(rules_of(v)) == {"unearned_word"}
    assert {x.detail for x in v.violations} == {
        "stipulations", "herein", "necessitate", "remittance"}


def test_think_blocks_stripped():
    v = check_reply(
        "<think>utilize sophisticated verbiage</think>Your benefit will change.",
        NOTICE, make_state())
    assert v.passed


def test_contractions_expanded():
    v = check_reply("You don't have to agree, and it won't change if you're right.",
                    NOTICE, make_state())
    assert v.passed


def test_hyphenated_parts_checked():
    ok = check_reply("This is a well-known kind of letter.", NOTICE, make_state())
    assert ok.passed
    bad = check_reply("This is a quasi-testamentary letter.", NOTICE, make_state())
    assert "unearned_word" in rules_of(bad)


# ---------------------------------------------------------------- rule b


def test_student_word_allowance_pass():
    state = make_state()
    absorb_user_turn(state, "What about my copay?")
    v = check_reply("Your copays stay the same.", NOTICE, state)  # lemma family
    assert v.passed


def test_student_word_allowance_fail():
    v = check_reply("Your copay stays the same.", NOTICE, make_state())
    assert rules_of(v) == ["unearned_word"]
    assert v.violations[0].detail == "copay"


# ---------------------------------------------------------------- rule c


def test_taught_term_unlock_and_persist():
    state = make_state()
    v1 = check_reply("You may ask for a recertification — that is, a check "
                     "that you still need this help. The recertification is free.",
                     NOTICE, state)
    assert v1.passed
    assert v1.new_taught_terms == ["recertification"]
    assert "recertification" in state.taught_terms
    # Persists to later replies, lemma-matched.
    v2 = check_reply("Your recertifications happen every year.", NOTICE, state)
    assert v2.passed


def test_gloss_not_plain_voids_unlock():
    v = check_reply("You may face a garnishment — that is, a legal levy on "
                    "your remuneration.", NOTICE, make_state())
    assert "gloss_not_plain" in rules_of(v)
    assert v.new_taught_terms == []


def test_too_many_new_terms():
    v = check_reply(
        "This is a copay — that is, a small part you pay. "
        "This is a premium, which means the money you pay each month. "
        "This is an addendum, which means an extra page added at the end.",
        NOTICE, make_state())
    assert "too_many_new_terms" in rules_of(v)
    assert len(v.new_taught_terms) == 2


def test_first_use_must_be_glossed():
    v = check_reply("The subrogation starts soon. Subrogation — that is, one "
                    "office asking another to pay it back.", NOTICE, make_state())
    assert "unearned_word" in rules_of(v)
    assert v.new_taught_terms == []


def test_this_is_called_form():
    v = check_reply("You can ask for more time to send papers. "
                    "This is called an extension.", NOTICE, make_state())
    assert v.passed
    assert v.new_taught_terms == ["extension"]


def test_multiword_term_unlocks_as_exact_unit():
    state = make_state()
    v1 = check_reply("You may get a copay waiver, which means a paper that "
                     "says you do not have to pay your small share.",
                     NOTICE, state)
    assert v1.passed
    assert v1.new_taught_terms == ["copay waiver"]
    # Exact unit is allowed later...
    v2 = check_reply("Ask about the copay waiver soon.", NOTICE, state)
    assert v2.passed
    # ...but the pieces alone are not earned by the phrase unlock.
    v3 = check_reply("Ask about the waiver soon.", NOTICE, state)
    assert "unearned_word" in rules_of(v3)


# ---------------------------------------------------------------- rule d


def test_proper_noun_verbatim_pass():
    v = check_reply("Maria Lopez got this letter about her food benefit.",
                    NOTICE, make_state())
    assert v.passed


def test_proper_noun_not_in_source_fail():
    v = check_reply("Bob told me about this.", NOTICE, make_state())
    assert rules_of(v) == ["unearned_word"]
    assert v.violations[0].detail == "bob"


# ---------------------------------------------------------------- rule e


def test_quote_exact_substring_pass():
    v = check_reply('The letter says "you must ask for one by 08/25/2026" '
                    "and that is the one date you must not miss, so keep it "
                    "in mind as the days go by this month.",
                    NOTICE, make_state())
    assert v.passed


def test_fabricated_quote():
    v = check_reply('The letter says "you must pay us back now" and that is '
                    "the main point of it, so read the whole page with care "
                    "before you do anything else at all.",
                    NOTICE, make_state())
    assert "fabricated_quote" in rules_of(v)


def test_quoted_span_exempt_from_vocab():
    # "proof" appears only inside the quote; quoted spans are vocab-exempt.
    v = check_reply('It says "You must send proof of your income by '
                    '08/25/2026" and you must do that by 08/25/2026, which '
                    "is soon, so please read it with care and act on time.",
                    NOTICE, make_state())
    assert v.passed


def test_over_quoting():
    v = check_reply('The letter says "You must send proof of your income by '
                    '08/25/2026 if you do not agree." OK.',
                    NOTICE, make_state())
    assert "over_quoting" in rules_of(v)


def test_blockquote_lines():
    ok = check_reply(
        "The letter says:\n> If you want a hearing, you must ask for one by "
        "08/25/2026.\nThat is the main point, and this line makes the reply "
        "long enough to stay well under the quote cap for sure.",
        NOTICE, make_state())
    assert ok.passed
    bad = check_reply(
        "The letter says:\n> You owe us money right now.\nThat is the main "
        "point of it all, and this line makes the reply long enough to stay "
        "well under the quote cap for sure.",
        NOTICE, make_state())
    assert "fabricated_quote" in rules_of(bad)


# ---------------------------------------------------------------- rule f


def test_anchor_exact_pass():
    v = check_reply("Your benefit will change from $250 to $180 on 09/01/2026.",
                    NOTICE, make_state())
    assert v.passed


def test_paraphrased_anchor():
    v = check_reply("Your benefit will drop to $180.00 next month.",
                    NOTICE, make_state())
    assert "paraphrased_anchor" in rules_of(v)
    assert v.violations[0].detail == "$180.00"


def test_operative_deadline_present():
    v = check_reply("You must send proof of your income by 08/25/2026.",
                    NOTICE, make_state(), {"operative_deadline": "08/25/2026"})
    assert v.passed


def test_missing_operative_deadline():
    v = check_reply("Your benefit changes on 09/01/2026.", NOTICE,
                    make_state(), {"operative_deadline": "08/25/2026"})
    assert "missing_operative_deadline" in rules_of(v)


# ---------------------------------------------------------------- rule g


def test_modal_preserved_pass():
    v = check_reply("You must send proof of your income by 08/25/2026.",
                    NOTICE, make_state())
    assert v.passed
    assert v.advisory_flags == []


def test_softened_modal_is_advisory_only():
    # C1 (calibration): softened_modal NEVER fails strict pass; it reports
    # as an advisory flag (measured 5% precision in the 2026-08-18 audit).
    v = check_reply("You can send proof of your income by 08/25/2026 if you "
                    "like.", NOTICE, make_state())
    assert v.passed
    assert "softened_modal" not in rules_of(v)
    assert [a.rule for a in v.advisory_flags] == ["softened_modal"]
    m = reply_metrics(v)
    assert m["strict_pass"] is True
    assert m["advisory"] == 1
    assert m["advisory_by_rule"] == {"softened_modal": 1}


# ---------------------------------------------------------------- rule h


def test_advice_tripwire_fail():
    v = check_reply("You should ask for a hearing right away.",
                    NOTICE, make_state())
    assert "advice_given" in rules_of(v)


def test_advice_tripwire_pass():
    v = check_reply("The letter says you can ask for a hearing.",
                    NOTICE, make_state())
    assert v.passed


# ---------------------------------------------------------------- rule i


def test_scaffold_missing_on_first_reply():
    v = check_reply("Here is the letter, made simple.", NOTICE,
                    make_state(first_reply=True))
    assert "missing_scaffold" in rules_of(v)


def test_scaffold_present_on_first_reply():
    v = check_reply(
        "What this letter says: your food benefit will change on 09/01/2026.\n"
        "What it asks you to do: you must send proof of your income by "
        "08/25/2026.\nBy when: you must send it by 08/25/2026.",
        NOTICE, make_state(first_reply=True))
    assert v.passed


def test_scaffold_not_required_after_first_reply():
    v = check_reply("Here is more about the letter.", NOTICE, make_state())
    assert v.passed


# ---------------------------------------------------------------- rule j


def test_banner_missing_on_adverse_action():
    v = check_reply(
        "What this letter says: your food benefit will change on 09/01/2026.\n"
        "What it asks you to do: you must send proof of your income by "
        "08/25/2026.\nBy when: you must send it by 08/25/2026.",
        NOTICE, make_state(first_reply=True), {"adverse_action": True})
    assert "missing_banner" in rules_of(v)


def test_banner_present_on_adverse_action():
    v = check_reply(
        "What this letter says: your food benefit will change on 09/01/2026.\n"
        "What it asks you to do: you must send proof of your income by "
        "08/25/2026.\nBy when: you must send it by 08/25/2026.\n" + BANNER,
        NOTICE, make_state(first_reply=True), {"adverse_action": True})
    assert v.passed


# ------------------------------------------- v1.1 calibration regressions
# Each test below is lifted from a false positive (or false negative) in
# evidence/2026-08-18/calibration/REPORT.md.


def test_blockquoted_wrapped_verbatim_quote_passes():
    # B1: '> "verbatim letter line"' — the wrapping quote pair is
    # punctuation, not content; v1.0 compared content INCLUDING the marks.
    v = check_reply(
        'The letter says:\n'
        '> "If you want a hearing, you must ask for one by 08/25/2026."\n'
        "That is the main point, and this line makes the reply long enough "
        "to stay well under the quote cap for sure, with room to spare.",
        NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_quote_ratio_single_counts_blockquoted_quotes():
    # B1b: v1.0 counted '> "..."' spans in both the inline pass and the
    # blockquote pass, doubling quoted_chars.
    inner = "If you want a hearing, you must ask for one by 08/25/2026."
    reply = (f'The letter says:\n> "{inner}"\nThat is the one date that '
             "matters here, so mark it down somewhere you will see it "
             "again before the month ends.")
    v = check_reply(reply, NOTICE, make_state())
    single = len(inner) / len(reply)
    assert single < 0.40 < 2 * single  # double-counting would breach the cap
    assert v.quoted_ratio == pytest.approx(single, abs=0.01)
    assert "over_quoting" not in rules_of(v)
    assert v.passed


def test_trailing_punctuation_inside_quote_passes():
    # C2: US-style comma/period inside the closing quote is normalized away
    # (one trailing comma or period only).
    v = check_reply('The letter says "if you do not agree," so you can act '
                    "on it or not, and either way you know where you stand.",
                    NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_single_word_quote_case_insensitive():
    # C2: a single-word mention quote may be capitalized where the letter
    # prints lowercase ("Gross" vs "gross" in the calibration).
    v = check_reply('The word "Hearing" in the letter means a meeting where '
                    "you tell your side of the case.", NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_fabricated_quote_still_fails_after_normalization():
    # The C2 normalization must not open a hole for invented quotes.
    v = check_reply('The letter says "you must wire the money today," and '
                    "that is the main point of the whole page, so read it "
                    "all with care before you act on any of it.",
                    NOTICE, make_state())
    assert "fabricated_quote" in rules_of(v)


def test_gloss_with_possessive_clitic_passes():
    # B2: rule c's gloss-cleanliness pass must tokenize like the main pass —
    # "worker's" checks "worker", not the clitic-attached surface form.
    v = check_reply("You may face garnishment — that is, money taken out of "
                    "a worker's pay before the worker gets it.",
                    NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]
    assert v.new_taught_terms == ["garnishment"]


def test_number_month_day_words_earned():
    # B3: NGSL supplemental basics (number words, months, days) are in the
    # frozen allowed list; "two" alone caused 12 calibration false flags.
    v = check_reply("You have two or three weeks from the first Monday in "
                    "January to send the papers.", NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_user_introduced_anchor_exempt():
    # B5: an anchor the USER introduced (here a hypothetical date not in the
    # notice) may be echoed by the reply without a paraphrased_anchor flag.
    state = make_state()
    absorb_user_turn(state, "What happens if I ask on November 5 instead?")
    v = check_reply("November 5 is after the date in the letter, so the "
                    "letter's date still controls what happens to you.",
                    NOTICE, state)
    assert "paraphrased_anchor" not in rules_of(v)
    assert v.passed, [x.to_dict() for x in v.violations]


def test_truncated_anchor_fails_set_membership():
    # B4 (FN side): "$536" when the letter prints "$536.00" must FAIL —
    # v1.0's raw substring containment accepted any truncation.
    notice = NOTICE + "You must pay back $536.00 to the state office.\n"
    v = check_reply("The letter says you must pay back $536 to the state "
                    "office soon.", notice, make_state())
    assert "paraphrased_anchor" in rules_of(v)
    assert "$536" in {x.detail for x in v.violations}
    # A notice pasted into a user turn must NOT re-open the hole via the
    # user-anchor channel: the user "said" $536.00, not $536.
    state = make_state()
    absorb_user_turn(state, "Here is the letter:\n" + notice)
    v2 = check_reply("The letter says you must pay back $536 to the state "
                     "office soon.", notice, state)
    assert "paraphrased_anchor" in rules_of(v2)


def test_amount_regex_ends_on_digit():
    # B4: "$250," must extract "$250" (no trailing-comma captures).
    from src.checker.check import ANCHOR_RES
    assert ANCHOR_RES["amount"].search("You get $250, each month.").group(0) \
        == "$250"
    v = check_reply("Your benefit is $250, and that will change soon.",
                    NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_derivational_family_members_earned():
    # C3: transparent derivations of listed headwords (plain+ly, deny+al,
    # separate+ly) are earned via the curated affix expansion.
    v = check_reply("The letter is a denial, plainly put, and the two "
                    "offices work separately.", NOTICE, make_state())
    assert v.passed, [x.to_dict() for x in v.violations]


def test_non_transparent_forms_still_unearned():
    # C3 boundary (true violations per the calibration labels): compounds,
    # semantically shifted un- forms, and non-listed lexemes stay flagged.
    v = check_reply("The stub is undone and you cannot dodge it on a "
                    "weekday.", NOTICE, make_state())
    assert set(rules_of(v)) == {"unearned_word"}
    assert {x.detail for x in v.violations} == {
        "stub", "undone", "dodge", "weekday"}


# ---------------------------------------------------------------- end-to-end


def test_end_to_end_compliant_first_reply():
    state = ConversationState()
    absorb_user_turn(state, "Can you explain this letter I got about my food help?")
    reply = (
        "What this letter says: your monthly food benefit will change from "
        "$250 to $180 on 09/01/2026.\n"
        "What it asks you to do: you must send proof of your income by "
        "08/25/2026 if you do not agree. You can also ask for a hearing — "
        "that is, a meeting where you tell your side and someone new looks "
        "at the case.\n"
        "By when: you must send proof of your income by 08/25/2026, and if "
        "you want a hearing, you must ask for one by 08/25/2026.\n"
        + BANNER + "\n"
        'The letter also says "Call 1-800-555-0199 with questions."'
    )
    v = check_reply(reply, NOTICE, state,
                    {"adverse_action": True, "operative_deadline": "08/25/2026"})
    assert v.passed, [x.to_dict() for x in v.violations]
    assert state.first_reply is False
    # Second turn keeps working with the mutated state.
    v2 = check_reply("A hearing is free, and you keep your benefit while you wait "
                     "if you ask by 08/25/2026 and it is required that you do.",
                     NOTICE, state)
    assert v2.passed, [x.to_dict() for x in v2.violations]


# ---------------------------------------------------------------- metrics


def test_reply_metrics():
    v = check_reply("The stipulations herein necessitate remittance.",
                    NOTICE, make_state())
    m = reply_metrics(v)
    assert m["violations"] == 4
    assert m["by_rule"] == {"unearned_word": 4}
    assert m["advisory"] == 0
    assert m["advisory_by_rule"] == {}
    assert m["strict_pass"] is False
    assert m["violations_per_100_words"] == pytest.approx(
        100.0 * 4 / v.word_count, abs=0.01)


def test_conversation_series():
    s1 = make_state()
    v1 = check_reply("Your food benefit will change soon.", NOTICE, s1)
    v2 = check_reply("You should ask for a hearing.", NOTICE, s1)
    series = conversation_series([v1, v2])
    assert len(series["turns"]) == 2
    assert series["strict_pass"] is False
    assert series["by_rule"] == {"advice_given": 1}


# ---------------------------------------------------------------- frozen set


def test_allowed_set_frozen_and_hash_matches():
    meta = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    assert meta["allowed_forms_sha256"] == _sha256(ALLOWED_PATH)
    assert meta["banner_checker_clean"] is True
    assert meta["ngsl_lemma_count"] == 2801


def test_determinism_same_input_same_verdict():
    def run():
        state = make_state()
        v = check_reply("You may face a garnishment — that is, a legal levy "
                        "on your remuneration.", NOTICE, state)
        return json.dumps(v.to_dict(), sort_keys=True)
    assert run() == run()
