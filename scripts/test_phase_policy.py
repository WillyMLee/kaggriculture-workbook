"""Focused regression checks for the v0.3 phase and closeout policy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import _market_plan, _operations_attention, _phase_attention


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


if __name__ == "__main__":
    test_phase_boundaries()
    test_closeout_keeps_labor_and_feed()
    test_fertilizer_collection_enters_work_queue()
    print("phase policy regressions: 3 passed")
