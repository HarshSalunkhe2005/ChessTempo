"""Phase 4: scale hint detail to the user's current skill estimate.

The project's stated design goal (see the root README) is hints "in human
terms... scaled to your current skill estimate," not a fixed eval-number-
and-tactics dump for everyone. A beginner gets a plain-language read on
the position and the single most concrete thing to watch for; a strong
player gets the full motif list and the raw centipawn number, since they
already know how to use it.
"""
from __future__ import annotations

from dataclasses import dataclass

from tempo.mentor.motifs import Motif

# Same 0-1 scale as DifficultyController.strength, but this is about how
# much detail to *show*, not how strong the bot plays.
_LOW_STRENGTH_CUTOFF = 0.35
_MID_STRENGTH_CUTOFF = 0.65

# (minimum eval_cp for this label, label), most favorable first — the
# first match wins. Centipawns, side-to-move's perspective.
_EVAL_LABELS = [
    (600, "Completely winning"),
    (300, "Much better"),
    (100, "Slightly better"),
    (-100, "Roughly equal"),
    (-300, "Slightly worse"),
    (-600, "Much worse"),
]


def eval_label(eval_cp: int | None) -> str | None:
    """A plain-language read on `eval_cp`, e.g. "Slightly better" instead
    of "+0.85"."""
    if eval_cp is None:
        return None
    for threshold, label in _EVAL_LABELS:
        if eval_cp >= threshold:
            return label
    return "Losing badly"


@dataclass
class HintPayload:
    motifs: list[Motif]
    eval_cp: int | None
    eval_label: str | None


def build_hint_payload(motifs: list[Motif], eval_cp: int | None, strength: float) -> HintPayload:
    """Scale what a hint shows based on `strength` (0-1, the difficulty
    controller's current estimate of this user's skill):

    - Low strength (beginner): plain-language eval only, capped to the
      single most concrete motif so it doesn't overwhelm.
    - Mid strength: plain-language eval *and* the raw number, all motifs.
    - High strength: just the raw number — players at this level don't
      need "Slightly better" spelled out — plus all motifs.
    """
    label = eval_label(eval_cp)

    if strength < _LOW_STRENGTH_CUTOFF:
        return HintPayload(motifs=motifs[:1], eval_cp=None, eval_label=label)
    if strength < _MID_STRENGTH_CUTOFF:
        return HintPayload(motifs=motifs, eval_cp=eval_cp, eval_label=label)
    return HintPayload(motifs=motifs, eval_cp=eval_cp, eval_label=None)
