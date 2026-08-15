"""Phase Tempo v0.4: phase control with probabilistic strategy attention."""

from __future__ import annotations

import math


CROPS = {
    "WHEAT": {"max_yield_day": 4, "ongoing": False},
    "TOMATO": {"max_yield_day": 11, "ongoing": True},
    "STRAWBERRY": {"max_yield_day": 10, "ongoing": True},
    "MELON": {"max_yield_day": 12, "ongoing": False},
}
PRODUCTS = ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SELLABLE_PRODUCTS = ("WHEAT",) + PRODUCTS
SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
PASTURE_CELLS = ((0, 4), (1, 4), (2, 4), (3, 4))
MELON_CELLS = ((0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1))
WHEAT_CELLS = ((0, 2), (1, 2), (2, 2), (3, 2), (4, 2))
STRAWBERRY_CELLS = MELON_CELLS + ((0, 3), (1, 3), (2, 3), (3, 3), (4, 3))
RECURRING_CELLS = STRAWBERRY_CELLS


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _nearest_shed(position):
    return min(SHED_ACCESS, key=lambda target: (_distance(position, target), target[1], target[0]))


def _step_toward(position, target):
    x, y = position
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _tile(farm, position):
    return farm["tiles"][position[1]][position[0]]


def _count_tiles(farm, predicate):
    return sum(1 for row in farm["tiles"] for tile in row if predicate(tile))


def _softmax(scores, temperature=1.0):
    """Turn comparable strategy or attention scores into stable probabilities."""
    scale = max(float(temperature), 0.05)
    peak = max(scores.values())
    weights = {key: math.exp((value - peak) / scale) for key, value in scores.items()}
    total = sum(weights.values()) or 1.0
    return {key: weight / total for key, weight in weights.items()}


def _strategy_belief(farm, day):
    """Score visible commitments without pretending hidden intent is certain."""
    crops = {
        crop: _count_tiles(
            farm,
            lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop,
        )
        for crop in ("TOMATO", "STRAWBERRY", "MELON")
    }
    animals = _count_tiles(farm, lambda tile: isinstance(tile, dict) and "animal" in tile)
    quadrants = len(farm.get("unlocked_quadrants", []))
    hands = len(farm.get("hands", []))
    crop_total = sum(crops.values())
    scores = {
        "melon-rush": -1.0 + 0.34 * crops["MELON"] + (0.45 if day <= 12 else -0.35),
        "strawberry-recurring": -1.0 + 0.42 * crops["STRAWBERRY"],
        "tomato-recurring": -1.0 + 0.42 * crops["TOMATO"],
        "livestock-compound": -1.0 + 0.72 * animals,
        "land-expansion": -1.0 + 1.35 * max(0, quadrants - 1) + 0.04 * hands,
        "mixed": 0.1 + 0.05 * crop_total + 0.18 * min(animals, 2),
    }
    return _softmax(scores, temperature=0.85)


def _attention_weights(obs, player, strategy_probabilities):
    """Allocate attention among operations, opponent inference, and horizon."""
    day = int(obs.get("day", 0))
    farm = obs.get("farms", [])[player]
    urgent_work = _count_tiles(
        farm,
        lambda tile: isinstance(tile, dict)
        and (
            (tile.get("kind") == "PLANT" and not tile.get("watered_today", False))
            or ("animal" in tile and not tile.get("fed_today", False))
            or int(tile.get("yield_units", 0)) > 0
        ),
    )
    probabilities = list(strategy_probabilities.values())
    entropy = -sum(value * math.log(max(value, 1e-12)) for value in probabilities)
    certainty = 1.0 - entropy / math.log(len(probabilities))
    opponent_window = 0.65 if day <= 11 else (1.0 if day <= 21 else 0.35)
    progress = day / 29.0
    scores = {
        "operations": 0.8 + 2.8 * min(1.0, urgent_work / 8.0),
        "opponent": 0.35 + 2.4 * certainty * opponent_window,
        "horizon": -0.3 + 3.2 * progress * progress + (1.4 if day >= 28 else 0.0),
    }
    return _softmax(scores, temperature=0.9)


def _opponent_attention(obs, player):
    """Maintain a probabilistic strategy belief and choose one bounded response."""
    opponents = [farm for index, farm in enumerate(obs.get("farms", [])) if index != player]
    if not opponents:
        return {
            "archetype": "unknown",
            "confidence": 0.0,
            "recurring_crop": "STRAWBERRY",
            "probabilities": {},
            "attention_weights": {"operations": 1.0, "opponent": 0.0, "horizon": 0.0},
        }

    opponent = opponents[0]
    probabilities = _strategy_belief(opponent, int(obs.get("day", 0)))
    attention = _attention_weights(obs, player, probabilities)
    archetype, confidence = max(probabilities.items(), key=lambda item: item[1])

    # Recurring crops are a portfolio decision. Switch only when the weighted
    # probability of strawberry crowding materially exceeds tomato crowding.
    strawberry_risk = probabilities["strawberry-recurring"] + 0.25 * probabilities["mixed"]
    tomato_risk = probabilities["tomato-recurring"] + 0.18 * probabilities["mixed"]
    recurring_crop = (
        "TOMATO"
        if strawberry_risk - tomato_risk >= 0.16 and attention["opponent"] >= 0.12
        else "STRAWBERRY"
    )
    return {
        "archetype": archetype,
        "confidence": round(confidence, 4),
        "recurring_crop": recurring_crop,
        "probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "attention_weights": {key: round(value, 4) for key, value in attention.items()},
    }


def _phase_attention(obs):
    """Name the strategic phase and gate only investments, never survival work."""
    day = int(obs.get("day", 0))
    if day <= 11:
        return {
            "phase": "early",
            "late_mode": None,
            "allow_animals": False,
            "allow_recurring": False,
        }
    if day <= 21:
        return {
            "phase": "middle",
            "late_mode": None,
            "allow_animals": day <= 20,
            "allow_recurring": day <= 18,
        }
    return {
        "phase": "late",
        "late_mode": "optimize" if day <= 27 else "execute",
        "allow_animals": False,
        "allow_recurring": False,
    }


def _market_plan(obs, farm, private, opponent_signal, phase):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    inventories = private.get("inventories", [])
    orders = []

    animals = _count_tiles(farm, lambda tile: isinstance(tile, dict) and tile.get("animal") == "COW")

    # Labor is operating capacity, not an investment. Keep it through the last
    # day so feeding and harvesting are not abandoned during liquidation.
    if hour == 0:
        hire_target = 6 if phase["phase"] == "early" else 8
        orders.extend([["HIRE"] for _ in range(hire_target)])

    # Convert completed output continuously. Wheat remains feed until late
    # execution, when only the amount above the remaining feed reserve is sold.
    for item in PRODUCTS:
        if shed.get(item, 0) > 0:
            orders.append(["SELL", item, shed[item]])
    if phase["late_mode"] == "execute":
        future_feed_days = max(0, 29 - day)
        unfed_today = _count_tiles(
            farm,
            lambda tile: isinstance(tile, dict)
            and tile.get("animal") == "COW"
            and not tile.get("fed_today", False),
        )
        feed_reserve = animals * future_feed_days + unfed_today
        wheat_to_sell = max(0, int(shed.get("WHEAT", 0)) - feed_reserve)
        if wheat_to_sell:
            orders.append(["SELL", "WHEAT", wheat_to_sell])

    planted = {
        crop: _count_tiles(farm, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in CROPS
    }
    desired = {"WHEAT": 5} if day <= 25 else {}
    if phase["phase"] == "early":
        desired["MELON"] = 10
    elif phase["allow_recurring"]:
        desired[opponent_signal["recurring_crop"]] = 15

    for crop, target in desired.items():
        shortfall = max(0, target - planted.get(crop, 0) - int(seeds.get(crop, 0)))
        if shortfall:
            orders.append(["BUY_SEED", crop, shortfall])

    empty_pastures = _count_tiles(
        farm, lambda tile: isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile
    )
    carried_cows = sum(int(inv.get("COW", 0)) for inv in inventories)
    if 12 <= day <= 20 and phase["allow_animals"]:
        cow_shortfall = max(0, 4 - animals - int(shed.get("COW", 0)) - carried_cows)
        if cow_shortfall:
            orders.append(["BUY_ANIMAL", "COW", cow_shortfall])
        feed_on_hand = int(shed.get("WHEAT", 0)) + sum(int(inv.get("WHEAT", 0)) for inv in inventories)
        feed_target = max(8, (animals + empty_pastures) * 3)
        if feed_on_hand < feed_target:
            orders.append(["BUY_PRODUCT", "WHEAT", feed_target - feed_on_hand])

    return orders[:10]


def _operations_attention(obs, farm, private, opponent_signal, phase):
    """Build the deadline-ordered work queue for farmer and hands."""
    day = int(obs.get("day", 0))
    shed = private.get("shed", {})
    tasks = []

    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            position = (x, y)
            if tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                age = day - int(tile.get("planted_day", day))
                ready = int(tile.get("yield_units", 0)) > 0 and (
                    CROPS.get(crop, {}).get("ongoing") or age >= CROPS.get(crop, {}).get("max_yield_day", 99)
                )
                if ready:
                    tasks.append((0, position, ["HARVEST"]))
                if not tile.get("watered_today", False):
                    tasks.append((1, position, ["WATER"]))
            if "animal" in tile:
                if not tile.get("fed_today", False):
                    tasks.append((2, position, ["FEED"]))
                if tile.get("fertilizer_available", False):
                    tasks.append((3, position, ["COLLECT_FERTILIZER"]))
                if not tile.get("cared_today", False):
                    tasks.append((4, position, ["CARE"]))
                if int(tile.get("yield_units", 0)) > 0:
                    tasks.append((0, position, ["HARVEST"]))

    if 12 <= day <= 20 and phase["allow_animals"]:
        for position in PASTURE_CELLS:
            if _tile(farm, position) is None:
                tasks.append((5, position, ["BUILD_PASTURE"]))

    crop_cells = []
    if phase["late_mode"] != "execute":
        crop_cells = [(position, "WHEAT") for position in WHEAT_CELLS] if day <= 25 else []
        crop_cells += [(position, "MELON") for position in MELON_CELLS] if phase["phase"] == "early" else [
            (position, opponent_signal["recurring_crop"]) for position in RECURRING_CELLS
        ] if phase["allow_recurring"] else []
    seeds = private.get("seeds", {})
    for position, crop in crop_cells:
        tile = _tile(farm, position)
        if tile is None and seeds.get(crop, 0) > 0:
            tasks.append((6, position, ["PLANT", crop]))

    # One worker can carry several feed units or one cow from the shed.
    animal_tiles = [
        (x, y)
        for y, row in enumerate(farm["tiles"])
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and "animal" in tile and not tile.get("fed_today", False)
    ]
    empty_pastures = [
        (x, y)
        for y, row in enumerate(farm["tiles"])
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile
    ]
    if animal_tiles and shed.get("WHEAT", 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((1, position, ["PICKUP", "WHEAT", min(len(animal_tiles), shed["WHEAT"])]))
    if day <= 20 and empty_pastures and shed.get("COW", 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((2, position, ["PICKUP", "COW", 1]))

    return tasks


def _policy(obs):
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    private = obs.get("private", {}) or {}
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    opponent_signal = _opponent_attention(obs, player)
    phase = _phase_attention(obs)
    positions = [tuple(farm["farmer"])] + [tuple(position) for position in farm.get("hands", [])]
    inventories = list(private.get("inventories", []))
    while len(inventories) < len(positions):
        inventories.append({})

    actions = [["PASS"] for _ in positions]
    available = set(range(len(positions)))
    tasks = _operations_attention(obs, farm, private, opponent_signal, phase)

    # Carried resources take precedence because they unlock care and placement.
    reserved_targets = set()
    for index, (position, inventory) in enumerate(zip(positions, inventories)):
        if index not in available:
            continue
        if inventory.get("COW", 0) > 0:
            targets = [
                (2, (x, y), ["PLACE", "COW"])
                for y, row in enumerate(farm["tiles"])
                for x, tile in enumerate(row)
                if isinstance(tile, dict)
                and tile.get("kind") == "PASTURE"
                and "animal" not in tile
                and (x, y) not in reserved_targets
            ]
            if targets:
                _, target, operation = min(targets, key=lambda task: (_distance(position, task[1]), task[1]))
                actions[index] = operation if position == target else _step_toward(position, target)
                available.discard(index)
                reserved_targets.add(target)
        elif inventory.get("WHEAT", 0) > 0:
            feed_targets = [
                task for task in tasks
                if task[2][0] == "FEED" and task[1] not in reserved_targets
            ]
            if feed_targets:
                _, target, operation = min(feed_targets, key=lambda task: (_distance(position, task[1]), task[1]))
                actions[index] = operation if position == target else _step_toward(position, target)
                available.discard(index)
                reserved_targets.add(target)

    # In the execution subphase, carried output returns to the shed after any
    # feed delivery has been reserved. This prevents the old day-27 starvation.
    if phase["late_mode"] == "execute":
        for index, (position, inventory) in enumerate(zip(positions, inventories)):
            if index not in available:
                continue
            has_output = any(int(inventory.get(item, 0)) > 0 for item in PRODUCTS)
            terminal_wheat = day == 29 and hour >= 20 and int(inventory.get("WHEAT", 0)) > 0
            if has_output or terminal_wheat:
                target = _nearest_shed(position)
                actions[index] = ["DROP"] if position == target else _step_toward(position, target)
                available.discard(index)

    # Assign remaining work greedily, preferring deadlines before travel distance.
    used_tasks = set()
    for index in sorted(available):
        position = positions[index]
        candidates = [
            (task_index, task)
            for task_index, task in enumerate(tasks)
            if task_index not in used_tasks
        ]
        if not candidates:
            continue
        task_index, (_, target, operation) = min(
            candidates,
            key=lambda item: (item[1][0], _distance(position, item[1][1]), item[1][1]),
        )
        actions[index] = operation if position == target else _step_toward(position, target)
        used_tasks.add(task_index)

    # Late in the day, idle carriers return output to the shed for sale.
    if int(obs.get("hour", 0)) >= 20:
        for index in available:
            inventory = inventories[index]
            if not inventory or inventory.get("WHEAT", 0) or inventory.get("COW", 0):
                continue
            target = _nearest_shed(positions[index])
            actions[index] = ["DROP"] if positions[index] == target else _step_toward(positions[index], target)

    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": _market_plan(obs, farm, private, opponent_signal, phase),
    }


def agent(obs):
    """Kaggle entry point with a valid no-op fallback for unexpected states."""
    try:
        return _policy(obs)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


balanced_tempo_agent = agent
