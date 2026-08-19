"""Offline tests for the datagen pipeline (no API calls anywhere)."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.datagen import teacher as teacher_mod
from src.datagen.notices import (
    GENRES, ID_PREFIX, check_disjoint, generate_notices,
    load_eval_notice_texts, validate_notice)
from src.datagen.students import (
    BAIT_INTENTS, FIRST_TURN_PREFIX, DialogScript, plan_dialogs)
from src.datagen.run_datagen import dialog_record
from src.datagen.teacher import metadata_for_turn, repair_prompt


def _rng(seed=3):
    return random.Random(seed)


# --------------------------------------------------------------------------
# notices.py
# --------------------------------------------------------------------------


def test_notice_metadata_correct_by_construction():
    notices = generate_notices(60, _rng())
    assert len(notices) == 60
    for n in notices:
        validate_notice(n)  # raises on any inconsistency
        assert n.notice_id.startswith(ID_PREFIX)
        dl = n.metadata["operative_deadline"]
        if dl is not None:
            assert dl in n.notice_text  # verbatim substring
        for a in n.metadata["amounts"]:
            assert a in n.notice_text
        assert isinstance(n.metadata["adverse_action"], bool)
        # fake-PII conventions
        assert "00-TRAIN-" in n.notice_text
        assert "555-" in n.notice_text


def test_all_genres_reachable():
    notices = generate_notices(120, _rng(11))
    seen = {n.genre for n in notices}
    assert seen == set(GENRES)


def test_adverse_action_flags_match_genre():
    notices = generate_notices(80, _rng(5))
    for n in notices:
        if n.genre in ("denial", "termination", "reduction",
                       "multi_program", "missing_element"):
            assert n.metadata["adverse_action"] is True
        if n.genre in ("approval", "verification", "recert_form"):
            assert n.metadata["adverse_action"] is False


def test_dates_in_2026_2027():
    notices = generate_notices(40, _rng(9))
    for n in notices:
        assert ("2026" in n.notice_text) or ("2027" in n.notice_text)
        assert "2025" not in n.notice_text


def test_determinism_same_seed_same_plan():
    a = plan_dialogs(12, seed=42)
    b = plan_dialogs(12, seed=42)
    assert [s.dialog_id for s in a] == [s.dialog_id for s in b]
    assert [s.notice.notice_text for s in a] == [s.notice.notice_text for s in b]
    assert [[t.text for t in s.turns] for s in a] == \
        [[t.text for t in s.turns] for s in b]


# --------------------------------------------------------------------------
# disjointness
# --------------------------------------------------------------------------


def test_generated_disjoint_from_eval():
    notices = generate_notices(80, _rng(7))
    assert check_disjoint(notices) == []


def test_disjointness_check_catches_planted_duplicate():
    notices = generate_notices(5, _rng(1))
    planted = {notices[2].notice_text}
    clashes = check_disjoint(notices, eval_texts=planted)
    assert clashes == [notices[2].notice_id]


def test_eval_set_loads():
    texts = load_eval_notice_texts()
    assert len(texts) >= 30
    assert all(isinstance(t, str) and t for t in texts)


# --------------------------------------------------------------------------
# students.py
# --------------------------------------------------------------------------


def test_first_turn_format_and_followup_count():
    scripts = plan_dialogs(20, seed=8)
    assert len(scripts) == 20
    assert len({s.dialog_id for s in scripts}) == 20
    for s in scripts:
        assert s.turns[0].intent == "open"
        assert s.turns[0].text == FIRST_TURN_PREFIX + s.notice.notice_text
        assert 1 <= len(s.turns) - 1 <= 3


def test_bait_coverage_near_30pct():
    n = 40
    scripts = plan_dialogs(n, seed=13)
    frac = sum(1 for s in scripts if s.has_bait()) / n
    assert 0.20 <= frac <= 0.45


def test_contrast_pair_tagging_consistent():
    scripts = plan_dialogs(40, seed=21)
    groups = {}
    for s in scripts:
        if s.contrast_group:
            groups.setdefault(s.contrast_group, []).append(s)
    assert groups, "expected at least one contrast pair"
    # 15-20% of dialogs are contrast material (pair rounding tolerated)
    n_contrast = sum(len(v) for v in groups.values())
    assert 0.10 <= n_contrast / 40 <= 0.25
    for gid, pair in groups.items():
        assert len(pair) == 2
        roles = {s.contrast_role for s in pair}
        assert roles == {"term_used", "term_absent"}
        terms = {s.contrast_term for s in pair}
        assert len(terms) == 1
        term = terms.pop().lower()
        used = next(s for s in pair if s.contrast_role == "term_used")
        absent = next(s for s in pair if s.contrast_role == "term_absent")
        # twins share the notice, and the term is in it
        assert used.notice.notice_text == absent.notice.notice_text
        assert term in used.notice.notice_text.lower()
        # term appears in a follow-up of the used twin only
        assert any(term in t.text.lower() for t in used.turns[1:])
        assert not any(term in t.text.lower() for t in absent.turns[1:])


# --------------------------------------------------------------------------
# teacher.py helpers (no API)
# --------------------------------------------------------------------------


def test_metadata_threading_policy():
    n = generate_notices(1, _rng(2), genres=["reduction"])[0]
    t0 = metadata_for_turn(n, 0, "open")
    assert t0["operative_deadline"] == n.metadata["operative_deadline"]
    assert t0["adverse_action"] is True
    t1 = metadata_for_turn(n, 1, "vocab")
    assert "operative_deadline" not in t1
    t2 = metadata_for_turn(n, 2, "deadline_collapse")
    assert t2["operative_deadline"] == n.metadata["operative_deadline"]


def test_repair_prompt_lists_violations():
    viols = [
        {"rule": "unearned_word", "detail": "allotment",
         "message": "'allotment' is not in the allowed set and was not earned."},
        {"rule": "missing_banner", "detail": "Important: ...",
         "message": "Adverse-action notice: first reply must contain the fixed banner."},
    ]
    msg = repair_prompt(viols)
    assert "Your reply broke these rules" in msg
    assert "unearned_word" in msg and "missing_banner" in msg
    assert "fully compliant" in msg


def test_system_prompt_contains_spec_fewshot_and_single_line_banner():
    sp = teacher_mod.build_system_prompt()
    assert "You never give advice" in sp  # spec present
    assert "Worked examples" in sp       # few-shot present
    banner = (ROOT / "src" / "checker" / "data" / "banner.txt").read_text(
        encoding="utf-8").strip()
    assert "\n" not in banner
    assert banner in sp                  # single-line banner verbatim


def test_teacher_client_is_lazy():
    # Constructing a Teacher must not require an API key / network.
    t = teacher_mod.Teacher()
    assert t._client is None


# --------------------------------------------------------------------------
# serialization round-trip
# --------------------------------------------------------------------------


def test_chat_format_roundtrip(tmp_path):
    scripts = plan_dialogs(6, seed=4)
    s = next(sc for sc in scripts if sc.contrast_group) if any(
        sc.contrast_group for sc in scripts) else scripts[0]
    res = teacher_mod.DialogResult(script=s, accepted=True, repairs=1)
    msgs = []
    for i, turn in enumerate(s.turns):
        msgs.append({"role": "user", "content": turn.text})
        msgs.append({"role": "assistant", "content": f"reply {i}"})
    res.messages = msgs
    rec = dialog_record(res, system_prompt="SPEC")
    line = json.dumps(rec, ensure_ascii=False)
    back = json.loads(line)
    assert back == rec
    assert back["messages"][0] == {"role": "system", "content": "SPEC"}
    assert back["messages"][1]["role"] == "user"
    assert back["messages"][1]["content"].startswith(FIRST_TURN_PREFIX)
    roles = [m["role"] for m in back["messages"][1:]]
    assert roles == ["user", "assistant"] * len(s.turns)
    assert back["id"] == s.dialog_id
    assert back["notice_id"] == s.notice.notice_id
    assert back["provenance"]["repairs"] == 1
    assert back["provenance"]["teacher"] == teacher_mod.TEACHER_MODEL
    if s.contrast_group:
        assert back["contrast_group"] == s.contrast_group
        assert back["contrast_role"] in ("term_used", "term_absent")


def test_train_id_namespace():
    scripts = plan_dialogs(10, seed=17)
    for s in scripts:
        assert s.dialog_id.startswith("train-")
        assert s.notice.notice_id.startswith("train-")
