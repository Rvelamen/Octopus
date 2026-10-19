"""v17 grouped discovery: prompt constraint and dispatch test for the v16 window-number fix."""

import json

import pytest
from test_book_numbered_discovery import input_data

from backend.services.book_world.discovery_grouped import assemble_grouped
from backend.services.book_world.discovery_models import DiscoveryConfig
from backend.services.book_world.discovery_numbered import prepare_numbered
from backend.services.book_world.discovery_v17 import (
    GROUPED_V17_PROMPT,
    GROUPED_V17_VERSION,
    assemble_grouped_v17,
)


def test_v17_prompt_states_segment_index_constraint_explicitly():
    """v17 must add an explicit s = segment-index constraint; without it, the model
    in v16 used the window number (unit_key) as the segment index, which the
    validator correctly rejected as 'Scene 6 uses an unoffered segment'."""
    assert "s是本窗口中0起始的片段编号" in GROUPED_V17_PROMPT
    assert "[0, N)" in GROUPED_V17_PROMPT
    assert "unit_key" in GROUPED_V17_PROMPT or "窗口号" in GROUPED_V17_PROMPT
    assert "scene编号" in GROUPED_V17_PROMPT


def test_v17_version_is_distinct_from_v16():
    assert GROUPED_V17_VERSION == "character-discovery-v17"
    assert GROUPED_V17_VERSION != "character-discovery-v16"


def test_v17_config_accepts_prompt_version():
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version=GROUPED_V17_VERSION
    )
    assert config.prompt_version == "character-discovery-v17"


def test_v17_reuses_v16_validator_and_catches_out_of_range_segment():
    """v17 keeps assemble_grouped as the validator. The prompt change reduces the
    chance the model emits invalid s, but if the model still emits a window number
    as a segment index, the validator must still reject it."""
    data = input_data()
    numbered = prepare_numbered(data)
    bad_reply = {
        "scenes": [{"s": [0]}, {"s": [1]}, {"s": [0, 1]}, {"s": [0, 1]}, {"s": [0, 1]}, {"s": [0, 1]}, {"s": [50]}],
        "people": [],
    }
    with pytest.raises(ValueError, match="unoffered segment"):
        assemble_grouped_v17(json.dumps(bad_reply, ensure_ascii=False), numbered)
    with pytest.raises(ValueError, match="unoffered segment"):
        assemble_grouped(json.dumps(bad_reply, ensure_ascii=False), numbered)


def test_v17_assembles_valid_reply_identical_to_v16():
    """A well-formed reply must pass the v17 validator the same way as v16, since
    the schema and validator are unchanged."""
    valid_reply = {
        "scenes": [{"s": [0]}, {"s": [1]}],
        "people": [
            {
                "identity": "uncertain",
                "appearances": [
                    {"scene": 0, "n": "人物甲", "e": 0, "at": "active"},
                    {"scene": 1, "n": "人物甲", "e": 1, "at": "silent"},
                ],
            },
        ],
    }
    data = input_data()
    numbered = prepare_numbered(data)
    v17 = assemble_grouped_v17(json.dumps(valid_reply, ensure_ascii=False), numbered)
    v16 = assemble_grouped(json.dumps(valid_reply, ensure_ascii=False), numbered)
    assert v17 == v16
