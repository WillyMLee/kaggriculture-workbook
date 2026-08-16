"""Focused regressions for phase, economics, routing, and closeout policy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.balanced_tempo import (
    _EPISODE_MEMORY,
    _animal_portfolio_model,
    _assign_tasks,
    _demand_forecast,
    _dynamic_wheat_plan,
    _engine_combo_model,
    _fertilizer_targets,
    _labor_plan,
    _market_plan,
    _operations_attention,
    _opponent_attention,
    _phase_attention,
    _portfolio_model,
    _reverse_terminal_plan,
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
    expected_hires = _labor_plan({"day": 28}, farm, _phase_attention({"day": 28}))["target"]
    assert sum(order == ["HIRE"] for order in day_28) == expected_hires
    assert ["SELL", "WHEAT", 2] in day_28

    day_29 = _market_plan({"day": 29, "hour": 0}, farm, private, signal, _phase_attention({"day": 29}))
    expected_hires = _labor_plan({"day": 29}, farm, _phase_attention({"day": 29}))["target"]
    assert sum(order == ["HIRE"] for order in day_29) == expected_hires
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
    assert sum(order == ["HIRE"] for order in action["market"]) >= 7
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
    probabilities = _strategy_belief({"day": 14}, opponent, 14)
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
        probabilities = _strategy_belief({"day": day}, farm, day)
        assert max(probabilities, key=probabilities.get) == expected


def test_dense_predictor_uses_town_demand_and_diversifies():
    ours = make_farm()
    opponent = make_farm()
    obs = {
        "day": 12,
        "player": 0,
        "farms": [ours, opponent],
        "market": {"prices": {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}},
        "town": {"unlocked_shops": ["SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]},
    }
    forecast = _demand_forecast(obs)
    assert forecast["STRAWBERRY"]["visible_demand"] > forecast["TOMATO"]["visible_demand"]
    portfolio = _portfolio_model(obs, ours, opponent, _phase_attention(obs))
    assert portfolio["recurring_crop"] in ("TOMATO", "STRAWBERRY")
    signal = _opponent_attention(obs, 0)
    assert sum(signal["recurring_targets"].values()) == 15
    assert set(signal["recurring_targets"]) == {"TOMATO", "STRAWBERRY"}


def test_dense_predictor_protects_shed_capacity():
    farm = make_farm()
    for x in range(10):
        farm["tiles"][0][x] = {
            "kind": "PLANT",
            "crop": "MELON",
            "planted_day": 0,
            "watered_today": True,
            "yield_units": 6,
        }
    private = {"shed": {"WHEAT": 40}, "seeds": {}, "inventories": [{}]}
    signal = {"cash_crop": "MELON", "recurring_crop": "STRAWBERRY", "recurring_targets": {"STRAWBERRY": 8, "TOMATO": 7}}
    orders = _market_plan({"day": 12, "hour": 0}, farm, private, signal, _phase_attention({"day": 12}))
    assert any(order[:2] == ["SELL", "WHEAT"] for order in orders)


def test_dense_predictor_clears_planned_weeds():
    farm = make_farm()
    farm["tiles"][4][0] = {"kind": "WEED"}
    private = {"shed": {}, "seeds": {}}
    signal = {"cash_crop": "MELON", "recurring_crop": "STRAWBERRY", "recurring_targets": {"STRAWBERRY": 8, "TOMATO": 7}}
    tasks = _operations_attention({"day": 15}, farm, private, signal, _phase_attention({"day": 15}))
    assert any(target == (0, 4) and action == ["DIG"] for _, target, action in tasks)


def test_reverse_terminal_plan_removes_stranded_work():
    farm = make_farm()
    farm["tiles"][4][0] = {
        "kind": "PASTURE",
        "animal": "COW",
        "placed_day": 19,
        "fed_today": False,
        "cared_today": False,
        "fertilizer_available": False,
        "yield_units": 0,
    }
    farm["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "STRAWBERRY",
        "planted_day": 19,
        "watered_today": False,
        "yield_units": 0,
    }
    private = {"shed": {"WHEAT": 10}, "seeds": {}, "inventories": [{}]}
    day_28 = _reverse_terminal_plan({"day": 28, "hour": 0, "market": {}}, farm, private)
    assert (0, 4) in day_28["feed_positions"]
    assert (0, 4) not in day_28["care_positions"]
    assert (0, 0) in day_28["water_positions"]

    day_29_obs = {"day": 29, "hour": 0, "market": {"prices": {"WHEAT": 25}}}
    day_29 = _reverse_terminal_plan(day_29_obs, farm, private)
    assert day_29["feed_units_remaining"] == 0
    assert not day_29["feed_positions"]
    assert not day_29["care_positions"]
    assert not day_29["water_positions"]
    signal = {"cash_crop": "MELON", "recurring_crop": "STRAWBERRY", "recurring_targets": {"STRAWBERRY": 8, "TOMATO": 7}}
    orders = _market_plan(day_29_obs, farm, private, signal, _phase_attention(day_29_obs), day_29)
    assert ["SELL", "WHEAT", 10] in orders
    tasks = _operations_attention(day_29_obs, farm, private, signal, _phase_attention(day_29_obs), day_29)
    assert not any(action[0] in ("FEED", "CARE", "WATER") for _, _, action in tasks)


def test_reverse_terminal_plan_times_scarce_market_sales():
    farm = make_farm()
    opponent = make_farm()
    private = {"shed": {"MILK": 8, "STRAWBERRY": 6}, "seeds": {}, "inventories": [{}]}
    obs = {
        "day": 24,
        "hour": 0,
        "player": 0,
        "farms": [farm, opponent],
        "market": {"prices": {"MILK": 180, "STRAWBERRY": 140}},
        "town": {"unlocked_shops": ["SMOOTHIE_SHOP"]},
    }
    plan = _reverse_terminal_plan(obs, farm, private)
    assert {"MILK", "STRAWBERRY"}.issubset(plan["hold_items"])
    obs["day"] = 28
    assert not _reverse_terminal_plan(obs, farm, private)["hold_items"]


def test_marginal_economics_prices_livestock_and_fertilizer():
    farm = make_farm()
    opponent = make_farm()
    obs = {
        "day": 12,
        "market": {"prices": {"WHEAT": 25, "EGG": 50, "MILK": 220, "WOOL": 200, "FERTILIZER": 100}},
        "town": {"unlocked_shops": ["SMOOTHIE_SHOP"]},
    }
    model = _animal_portfolio_model(obs, farm, opponent, _strategy_belief(obs, opponent, 12))
    assert model["animal"] == "COW"
    assert model["details"]["COW"]["net"] > model["details"]["GOOSE"]["net"]
    farm["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "TOMATO",
        "planted_day": 12,
        "watered_today": False,
        "fertilized_until_day": -1,
        "yield_units": 0,
    }
    obs.update({"day": 20, "market": {"prices": {"TOMATO": 60, "FERTILIZER": 100}}})
    assert any(target[1] == (0, 0) for target in _fertilizer_targets(obs, farm))


def test_expected_utility_counters_concentrated_recurring_supply():
    _EPISODE_MEMORY.clear()
    farm = make_farm()
    opponent = make_farm()
    for x in range(10):
        opponent["tiles"][0][x] = {
            "kind": "PLANT",
            "crop": "STRAWBERRY",
            "watered_today": True,
            "yield_units": 0,
        }
    signal = _opponent_attention({
        "day": 12,
        "player": 0,
        "farms": [farm, opponent],
        "market": {"prices": {}},
        "town": {"unlocked_shops": []},
    }, 0)
    assert signal["recurring_crop"] == "TOMATO"
    assert signal["probabilities"]["strawberry-recurring"] > 0.6
    assert set(signal["strategy_utilities"]) == {"cash-engine", "recurring-engine", "livestock-engine"}


def test_deadline_router_assigns_workers_globally():
    positions = [(0, 0), (9, 9)]
    tasks = [(0, (9, 8), ["HARVEST"]), (0, (0, 1), ["HARVEST"])]
    assignment = dict(_assign_tasks(positions, {0, 1}, tasks, 20))
    assert assignment == {0: 1, 1: 0}
    crowded = [(priority % 7, (priority % 10, (priority // 10) % 10), ["WATER"]) for priority in range(2000)]
    bounded = _assign_tasks([(index, 0) for index in range(9)], set(range(9)), crowded, 12)
    assert len(bounded) == 9


def test_high_threat_fifth_animal_has_a_real_slot():
    farm = make_farm()
    signal = {
        "recurring_crop": "STRAWBERRY",
        "recurring_targets": {"STRAWBERRY": 9, "TOMATO": 6},
        "animal": "COW",
        "animal_target": 5,
    }
    private = {"shed": {}, "seeds": {"STRAWBERRY": 9, "TOMATO": 6}, "inventories": [{}]}
    tasks = _operations_attention(
        {"day": 14, "hour": 0}, farm, private, signal, _phase_attention({"day": 14})
    )
    builds = [task for task in tasks if task[2][0] == "BUILD_PASTURE"]
    assert len(builds) == 5
    assert any(task[1] == (4, 3) for task in builds)
    assert not any(task[1] == (4, 3) and task[2][0] == "PLANT" for task in tasks)


def test_wheat_is_a_dynamic_reserve_not_a_fixed_commitment():
    farm = make_farm()
    private = {"shed": {}, "inventories": []}
    base = _dynamic_wheat_plan({"day": 8, "market": {"prices": {"WHEAT": 25}}}, farm, private)
    add_cows(farm, 4)
    feed = _dynamic_wheat_plan({"day": 8, "market": {"prices": {"WHEAT": 25}}}, farm, private)
    scarce = _dynamic_wheat_plan({"day": 8, "market": {"prices": {"WHEAT": 32}}}, farm, private)
    assert base["tile_target"] == 3
    assert feed["feed_reserve"] == 12
    assert scarce["tile_target"] > feed["tile_target"]


def test_opponent_prediction_breaks_on_material_deviation():
    _EPISODE_MEMORY.clear()
    ours = make_farm()
    opponent = make_farm()
    _opponent_attention({"day": 9, "player": 0, "farms": [ours, opponent]}, 0)
    for x in range(8):
        opponent["tiles"][0][x] = {"kind": "PLANT", "crop": "MELON", "yield_units": 0}
    signal = _opponent_attention({"day": 10, "player": 0, "farms": [ours, opponent]}, 0)
    assert signal["prediction_break"] is True
    assert signal["prediction_error"] >= 8


def test_engine_combo_is_available_without_forcing_a_switch():
    _EPISODE_MEMORY.clear()
    ours = make_farm()
    ours["money"] = 3000
    opponent = make_farm()
    add_cows(opponent, 2, fed=True)
    obs = {
        "day": 3,
        "hour": 0,
        "player": 0,
        "farms": [ours, opponent],
        "market": {"prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }
    signal = _opponent_attention(obs, 0)
    assert len(signal["engine_combo"]["scores"]) == 6
    action = agent(obs)
    assert not any(order[0] == "BUY_ANIMAL" for order in action["market"])


if __name__ == "__main__":
    test_phase_boundaries()
    test_closeout_keeps_labor_and_feed()
    test_fertilizer_collection_enters_work_queue()
    test_execute_phase_does_not_fall_back_to_no_op()
    test_strategy_softmax_is_normalized_and_differentiates_crops()
    test_strategy_archetype_probes()
    test_dense_predictor_uses_town_demand_and_diversifies()
    test_dense_predictor_protects_shed_capacity()
    test_dense_predictor_clears_planned_weeds()
    test_reverse_terminal_plan_removes_stranded_work()
    test_reverse_terminal_plan_times_scarce_market_sales()
    test_marginal_economics_prices_livestock_and_fertilizer()
    test_expected_utility_counters_concentrated_recurring_supply()
    test_deadline_router_assigns_workers_globally()
    test_high_threat_fifth_animal_has_a_real_slot()
    test_wheat_is_a_dynamic_reserve_not_a_fixed_commitment()
    test_opponent_prediction_breaks_on_material_deviation()
    test_engine_combo_is_available_without_forcing_a_switch()
    print("phase policy regressions: 18 passed")
