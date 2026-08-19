"""Deterministic compliance checker for "Benefits Notices, Explained" (spec v3).

Imports are lazy so that `python -m src.checker.check` and
`python -m src.checker.build_allowed` run without runpy re-import warnings.
"""

__all__ = [
    "ConversationState",
    "Verdict",
    "Violation",
    "absorb_user_turn",
    "check_reply",
    "reply_metrics",
    "conversation_series",
]

_CHECK = {"ConversationState", "Verdict", "Violation", "absorb_user_turn",
          "check_reply"}
_METRICS = {"reply_metrics", "conversation_series"}


def __getattr__(name):
    if name in _CHECK:
        from . import check

        return getattr(check, name)
    if name in _METRICS:
        from . import metrics

        return getattr(metrics, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
