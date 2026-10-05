"""Backend half of the cross-language feedback wire contract (D9).

``contracts/feedback_wire.json`` is the single source of truth for the
backend -> Unity LSL vector. This module checks the Python encoder against it;
``unity/Assets/Tests/EditMode/FeedbackWireContractTests.cs`` checks the C#
decoder against the SAME golden cases. A change on one side only fails here or
there. Runs without pylsl: the encoder is a pure function.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mindx_hnf.api.sink import (
    FEEDBACK_CHANNELS,
    MODE_CODE,
    SESSION_MODE_CODE,
    SHARED_SUBJECT_INDEX,
    UNROUTABLE_SUBJECT_INDEX,
    encode_feedback,
)
from mindx_hnf.contracts import FeedbackMode, FeedbackSample, SessionMode

_SPEC_PATH = Path(__file__).resolve().parents[2] / "contracts" / "feedback_wire.json"
SPEC: dict[str, Any] = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))


def test_channel_layout_matches_spec():
    assert list(FEEDBACK_CHANNELS) == SPEC["channels"]


def test_codes_and_sentinels_match_spec():
    assert {m.value: c for m, c in MODE_CODE.items()} == {
        e["name"]: e["code"] for e in SPEC["modeCodes"]
    }
    assert {m.value: c for m, c in SESSION_MODE_CODE.items()} == {
        e["name"]: e["code"] for e in SPEC["sessionModeCodes"]
    }
    assert SHARED_SUBJECT_INDEX == SPEC["sharedSubjectIndex"]
    assert UNROUTABLE_SUBJECT_INDEX == SPEC["unroutableSubjectIndex"]


def test_every_enum_member_has_a_code():
    # A new FeedbackMode/SessionMode without a wire code would KeyError live.
    assert set(MODE_CODE) == set(FeedbackMode)
    assert set(SESSION_MODE_CODE) == set(SessionMode)


@pytest.mark.parametrize("case", SPEC["cases"], ids=lambda c: c["name"])
def test_encoder_reproduces_golden_vector(case):
    sample = FeedbackSample(
        t_lsl=case["tLsl"],
        level=case["level"],
        mode=FeedbackMode(case["mode"]),
        raw_ins=case["rawIns"],
        session_mode=SessionMode(case["sessionMode"]),
        subject=case["subject"] or None,
    )
    assert encode_feedback(sample, case["subjects"]) == pytest.approx(case["vector"])
