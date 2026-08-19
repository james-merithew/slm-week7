"""Dataset loading, thinking-mode stripping, deterministic subsampling, and
assistant-only loss masking.

THINKING MODE IS OFF END-TO-END (project research-record requirement):
  1. Any <think>...</think> block found in dataset messages is STRIPPED here,
     and we hard-fail if a stray unmatched tag survives.
  2. enable_thinking=False is passed to every apply_chat_template call. Hybrid
     Qwen3 checkpoints honor it; the -2507 Instruct template has no thinking
     branch and ignores the kwarg (harmless).

ASSISTANT-ONLY LOSS MASKING:
  The Unsloth path (train.py) uses unsloth.chat_templates.train_on_responses_only
  with the QWEN3 marker strings. This module implements the SAME masking for the
  PEFT fallback path (train_peft.py) using character offsets: everything outside
  <|im_start|>assistant\n ... <|im_end|> spans gets label -100. The <|im_end|>
  terminator IS trained on (the model must learn to stop).

  Verify with:  python src/train/train_peft.py --config ... --verify-masking
  (the "decode one masked batch" protocol rule).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# Marker strings that delimit trainable assistant responses in the rendered
# chat template. QWEN3 markers are the ones Unsloth's train_on_responses_only
# is given in train.py — keep these two places in sync.
MARKERS = {
    "qwen": {
        "instruction_part": "<|im_start|>user\n",
        "response_part": "<|im_start|>assistant\n",
        "end_part": "<|im_end|>",
    },
    "llama": {
        "instruction_part": "<|start_header_id|>user<|end_header_id|>\n\n",
        "response_part": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        "end_part": "<|eot_id|>",
    },
}


def markers_for(model_id: str) -> dict[str, str]:
    mid = model_id.lower()
    if "qwen" in mid:
        return MARKERS["qwen"]
    if "llama" in mid:
        return MARKERS["llama"]
    # Default to Qwen (project primary); fail loudly later if markers not found.
    return MARKERS["qwen"]


# ---------------------------------------------------------------------------
# Loading / thinking-strip / subsample
# ---------------------------------------------------------------------------

def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks; thinking mode is OFF for this project."""
    out = THINK_BLOCK_RE.sub("", text)
    if "<think>" in out or "</think>" in out:
        raise ValueError(
            "Unmatched <think> tag survived stripping — fix the dataset row: "
            f"{out[:200]!r}")
    return out.strip()


def load_conversations(path: str | Path) -> list[list[dict[str, str]]]:
    """Load chat-format JSONL: each line {'messages': [{role, content}, ...]}."""
    convs: list[list[dict[str, str]]] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            msgs = row.get("messages")
            if not msgs:
                raise ValueError(f"{path}:{lineno}: no 'messages' key")
            cleaned = []
            for m in msgs:
                if m["role"] not in ("system", "user", "assistant"):
                    raise ValueError(f"{path}:{lineno}: bad role {m['role']!r}")
                cleaned.append({"role": m["role"],
                                "content": strip_thinking(str(m["content"]))})
            if not any(m["role"] == "assistant" for m in cleaned):
                raise ValueError(f"{path}:{lineno}: conversation has no assistant turn")
            convs.append(cleaned)
    return convs


def subsample(convs: list, n: int | None, seed: int, shuffle: bool = True) -> list:
    """Deterministic subsample: shuffle full list with RNG(seed), take first n.

    Nested-subset property for the data-efficiency sweep: for a fixed seed,
    N=75 ⊂ N=150 ⊂ N=300 ⊂ N=600 ⊂ N=1200.
    """
    rows = list(convs)
    if shuffle:
        random.Random(seed).shuffle(rows)
    if n is None:
        return rows
    if n > len(rows):
        raise ValueError(f"Requested n={n} but dataset has only {len(rows)} rows")
    return rows[:n]


# ---------------------------------------------------------------------------
# Chat template + assistant-only masking (PEFT fallback path)
# ---------------------------------------------------------------------------

def render_conversation(tokenizer, messages: list[dict[str, str]]) -> str:
    """Render full conversation text with thinking disabled."""
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=False,   # REQUIRED: thinking OFF end-to-end
    )


def assistant_char_spans(text: str, marks: dict[str, str]) -> list[tuple[int, int]]:
    """Char ranges [start, end) of trainable content: response body + end token."""
    spans = []
    resp, end = marks["response_part"], marks["end_part"]
    pos = 0
    while True:
        i = text.find(resp, pos)
        if i == -1:
            break
        start = i + len(resp)
        j = text.find(end, start)
        stop = (j + len(end)) if j != -1 else len(text)
        spans.append((start, stop))
        pos = stop
    return spans


def tokenize_with_masking(tokenizer, messages: list[dict[str, str]],
                          max_seq_len: int, marks: dict[str, str]) -> dict[str, list[int]]:
    """Tokenize one conversation; labels are -100 outside assistant responses."""
    text = render_conversation(tokenizer, messages)
    spans = assistant_char_spans(text, marks)
    if not spans:
        raise ValueError(
            f"No assistant response markers ({marks['response_part']!r}) found in "
            f"rendered text — wrong marker set for this model? Text head: {text[:200]!r}")
    enc = tokenizer(text, add_special_tokens=False, truncation=True,
                    max_length=max_seq_len, return_offsets_mapping=True)
    labels = []
    for tok_id, (a, b) in zip(enc["input_ids"], enc["offset_mapping"]):
        in_response = any(a >= s and b <= e for s, e in spans) and b > a
        labels.append(tok_id if in_response else -100)
    return {"input_ids": enc["input_ids"],
            "attention_mask": enc["attention_mask"],
            "labels": labels}


def build_tokenized_dataset(tokenizer, convs: list, max_seq_len: int, model_id: str):
    """Return a datasets.Dataset of pre-masked features."""
    from datasets import Dataset
    marks = markers_for(model_id)
    feats = [tokenize_with_masking(tokenizer, c, max_seq_len, marks) for c in convs]
    dropped = sum(1 for f in feats if all(l == -100 for l in f["labels"]))
    if dropped:
        print(f"[data] WARNING: {dropped} conversations have zero trainable tokens "
              f"(assistant turns truncated past max_seq_len={max_seq_len})")
    return Dataset.from_list(feats)


class PadCollator:
    """Right-pad input_ids/attention_mask with pad token, labels with -100."""

    def __init__(self, tokenizer):
        self.pad_id = tokenizer.pad_token_id
        if self.pad_id is None:
            self.pad_id = tokenizer.eos_token_id

    def __call__(self, features: list[dict[str, Any]]):
        import torch
        width = max(len(f["input_ids"]) for f in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for f in features:
            pad = width - len(f["input_ids"])
            batch["input_ids"].append(list(f["input_ids"]) + [self.pad_id] * pad)
            batch["attention_mask"].append(list(f["attention_mask"]) + [0] * pad)
            batch["labels"].append(list(f["labels"]) + [-100] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}


# ---------------------------------------------------------------------------
# Masking verification ("decode one masked batch" protocol rule)
# ---------------------------------------------------------------------------

def print_masked_batch(tokenizer, batch) -> None:
    """Decode one collated batch showing exactly which tokens carry loss.

    Everything shown as ····[MASKED]···· contributes NO gradient; only the
    text between ▶▶▶ and ◀◀◀ is trained on. User/system turns MUST all be
    inside [MASKED] regions.
    """
    input_ids = batch["input_ids"]
    labels = batch["labels"]
    for row in range(min(2, input_ids.shape[0])):
        ids = input_ids[row].tolist()
        labs = labels[row].tolist()
        pieces, cur_ids, cur_state = [], [], None  # state: True=trained, False=masked
        for tok, lab in zip(ids, labs):
            state = lab != -100
            if state != cur_state and cur_ids:
                pieces.append((cur_state, tokenizer.decode(cur_ids)))
                cur_ids = []
            cur_state = state
            cur_ids.append(tok)
        if cur_ids:
            pieces.append((cur_state, tokenizer.decode(cur_ids)))
        print(f"\n=== masked-batch row {row} "
              f"({sum(1 for l in labs if l != -100)}/{len(labs)} tokens trained) ===")
        for trained, text in pieces:
            if trained:
                print(f"▶▶▶TRAINED▶▶▶{text}◀◀◀")
            else:
                print(f"····[MASKED]···· {text!r}")
    print("\n[verify-masking] Check: every user/system turn above must appear "
          "under [MASKED]; only assistant replies (+ their end-of-turn token) "
          "under TRAINED. No <think> CONTENT anywhere: an EMPTY "
          "'<think>\\n\\n</think>' scaffold in the last assistant turn is "
          "expected on hybrid Qwen3 checkpoints (that is exactly how "
          "enable_thinking=False renders); the Qwen3-*-Instruct-2507 target "
          "template emits no think tags at all.")
