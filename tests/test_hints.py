from tempo.mentor.hints import build_hint_payload, eval_label
from tempo.mentor.motifs import Motif

MOTIFS = [
    Motif(name="hanging_piece", square=0, description="a"),
    Motif(name="fork", square=1, description="b"),
]


def test_eval_label_buckets():
    assert eval_label(None) is None
    assert eval_label(700) == "Completely winning"
    assert eval_label(150) == "Slightly better"
    assert eval_label(0) == "Roughly equal"
    assert eval_label(-1000) == "Losing badly"


def test_low_strength_shows_number_and_caps_motifs():
    # eval_cp always comes through — it drives the eval bar, which is
    # graphical/at-a-glance, not "a raw number" — only the tactics list
    # and plain-language label scale with strength.
    payload = build_hint_payload(MOTIFS, eval_cp=250, strength=0.1)
    assert payload.eval_cp == 250
    assert payload.eval_label == "Slightly better"
    assert len(payload.motifs) == 1


def test_mid_strength_shows_both():
    payload = build_hint_payload(MOTIFS, eval_cp=250, strength=0.5)
    assert payload.eval_cp == 250
    assert payload.eval_label == "Slightly better"
    assert len(payload.motifs) == 2


def test_high_strength_hides_label_only():
    payload = build_hint_payload(MOTIFS, eval_cp=250, strength=0.9)
    assert payload.eval_cp == 250
    assert payload.eval_label is None
    assert len(payload.motifs) == 2
