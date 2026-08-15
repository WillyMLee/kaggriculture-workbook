"""Focused regression checks for the v0.3 phase and closeout policy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import (
    _market_plan,
    _operations_attention,
    _opponent_attention,
    _phase_attention,
    _strategy_belief,
    agent,
)


def make_farm():
    return {
        "money": 0,
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": [0],
        "tiles": [[None for _ in range(10)] for _ in range(10)],
    }


def add_cows(farm, count, *, fed=False, fertilizer=False):
    for x in range(count):
        farm["tiles"][4][x] = {
            "kind": "PASTURE",
            "animal": "COW",
            "fed_today": fed,
            "cared_today": False,
            "fertilizer_available": fertilizer,
            "yield_units": 0,
        }


def test_phase_boundaries():
    expected = {
        0: ("early", None),
        11: ("early", None),
        12: ("middle", None),
        21: ("middle", None),
        22: ("late", "optimize"),
        27: ("late", "optimize"),
        28: ("late", "execute"),
        29: ("late", "execute"),
    }
    for day, result in expected.items():
        phase = _phase_attention({"day": day})
        assert (phase["phase"], phase["late_mode"]) == result


def test_closeout_keeps_labor_and_feed():
    farm = make_farm()
    add_cows(farm, 4)
    private = {"shed": {"WHEAT": 10}, "seeds": {}, "inventories": []}
    signal = {"recurring_crop": "STRAWBERRY"}

    day_28 = _market_plan({"day": 28, "hour": 0}, farm, private, signal, _phase_attention({"day": 28}))
    assert sum(order == ["HIRE"] for order in day_28) == 8
    assert ["SELL", "WHEAT", 2] in day_28

    day_29 = _market_plan({"day": 29, "hour": 0}, farm, private, signal, _phase_attention({"day": 29}))
    assert sum(order == ["HIRE"] for order in day_29) == 8
    assert ["SELL", "WHEAT", 6] in day_29

    for x in range(4):
        farm["tiles"][4][x]["fed_today"] = True
    day_29_after_feed = _market_plan(
        {"day": 29, "hour": 12}, farm, private, signal, _phase_attention({"day": 29})
    )
    assert ["SELL", "WHEAT", 10] in day_29_after_feed


def test_fertilizer_collection_enters_work_queue():
    farm = make_farm()
    add_cows(farm, 1, fertilizer=True)
    private = {"shed": {}, "seeds": {}}
    tasks = _operations_attention(
        {"day": 15},
        farm,
        private,
        {"recurring_crop": "STRAWBERRY"},
        _phase_attention({"day": 15}),
    )
    assert any(task[2] == ["COLLECT_FERTILIZER"] for task in tasks)


def test_execute_phase_does_not_fall_back_to_no_op():
    ours = make_farm()
    add_cows(ours, 3)
    opponent = make_farm()
    action = agent({
        "day": 28,
        "hour": 0,
        "player": 0,
        "farms": [ours, opponent],
        "private": {
            "shed": {"WHEAT": 24, "STRAWBERRY": 3, "MILK": 9, "FERTILIZER": 3},
            "seeds": {},
            "inventories": [{}],
        },
    })
    assert len(action["market"]) > 0
    assert sum(order == ["HIRE"] for order in action["market"]) == 8
    assert any(order[:2] == ["SELL", "MILK"] for order in action["market"])


def test_strategy_softmax_is_normalized_and_differentiates_crops():
    opponent = make_farm()
    for x in range(8):
        opponent["tiles"][0][x] = {
            "kind": "PLANT",
            "crop": "STRAWBERRY",
            "watered_today": False,
            "yield_units": 0,
        }
    probabilities = _strategy_belief(opponent, 14)
    assert abs(sum(probabilities.values()) - 1.0) < 1e-9
    assert max(probabilities, key=probabilities.get) == "strawberry-recurring"

    signal = _opponent_attention(
        {"day": 14, "player": 0, "farms": [make_farm(), opponent]},
        0,
    )
    assert signal["recurring_crop"] == "TOMATO"
    assert abs(sum(signal["attention_weights"].values()) - 1.0) < 0.001


def test_strategy_archetype_probes():
    cases = []
    melon = make_farm()
    strawberry = make_farm()
    tomato = make_farm()
    livestock = make_farm()
    expansion = make_farm()
    for index in range(10):
        melon["tiles"][0][index] = {"kind": "PLANT", "crop": "MELON"}
    for index in range(8):
        strawberry["tiles"][0][index] = {"kind": "PLANT", "crop": "STRAWBERRY"}
        tomato["tiles"][0][index] = {"kind": "PLANT", "crop": "TOMATO"}
    add_cows(livestock, 4)
    expansion["unlocked_quadrants"] = [0, 1, 2, 3]
    cases.extend([
        (melon, 6, "melon-rush"),
        (strawberry, 15, "strawberry-recurring"),
        (tomato, 15, "tomato-recurring"),
        (livestock, 15, "livestock-compound"),
        (expansion, 15, "land-expansion"),
        (make_farm(), 15, "mixed"),
    ])
    for farm, day, expected in cases:
        probabilities = _strategy_belief(farm, day)
        assert max(probabilities, key=probabilities.get) == expected


if __name__ == "__main__":
    test_phase_boundaries()
    test_closeout_keeps_labor_and_feed()
    test_fertilizer_collection_enters_work_queue()
    test_execute_phase_does_not_fall_back_to_no_op()
    test_strategy_softmax_is_normalized_and_differentiates_crops()
    test_strategy_archetype_probes()
    print("phase policy regressions: 6 passed")
