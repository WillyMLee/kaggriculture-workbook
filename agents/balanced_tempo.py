"""Balanced Tempo v0: melon cash, then cattle and strawberries, with an early exit."""

from __future__ import annotations


CROPS = {
    "WHEAT": {"max_yield_day": 4, "ongoing": False},
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


def _market_plan(obs, farm, private):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    inventories = private.get("inventories", [])
    orders = []

    # Convert completed output into score continuously; wheat is operating inventory until the exit phase.
    for item in SELLABLE_PRODUCTS if day >= 27 else PRODUCTS:
        if shed.get(item, 0) > 0:
            orders.append(["SELL", item, shed[item]])

    # Hard terminal gate: stop all investment and turn reachable inventory into bank.
    if day >= 27:
        return orders[:10]

    if hour == 0:
        for _ in range(6):
            orders.append(["HIRE"])

    planted = {
        crop: _count_tiles(farm, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in CROPS
    }
    desired = {"WHEAT": 5}
    if day <= 12:
        desired["MELON"] = 10
    else:
        desired["STRAWBERRY"] = 15

    for crop, target in desired.items():
        shortfall = max(0, target - planted.get(crop, 0) - int(seeds.get(crop, 0)))
        if shortfall:
            orders.append(["BUY_SEED", crop, shortfall])

    animals = _count_tiles(farm, lambda tile: isinstance(tile, dict) and tile.get("animal") == "COW")
    empty_pastures = _count_tiles(
        farm, lambda tile: isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile
    )
    carried_cows = sum(int(inv.get("COW", 0)) for inv in inventories)
    if day >= 11:
        cow_shortfall = max(0, 4 - animals - int(shed.get("COW", 0)) - carried_cows)
        if cow_shortfall:
            orders.append(["BUY_ANIMAL", "COW", cow_shortfall])
        feed_on_hand = int(shed.get("WHEAT", 0)) + sum(int(inv.get("WHEAT", 0)) for inv in inventories)
        feed_target = max(8, (animals + empty_pastures) * 3)
        if feed_on_hand < feed_target:
            orders.append(["BUY_PRODUCT", "WHEAT", feed_target - feed_on_hand])

    # Add the first expansion only after the opening payout is available.
    if day >= 13 and len(farm.get("unlocked_quadrants", [])) == 1 and farm.get("money", 0) >= 2200:
        orders.append(["BUY_LAND"])

    return orders[:10]


def _tasks(obs, farm, private):
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
                if not tile.get("cared_today", False):
                    tasks.append((3, position, ["CARE"]))
                if int(tile.get("yield_units", 0)) > 0:
                    tasks.append((0, position, ["HARVEST"]))

    if 11 <= day < 27:
        for position in PASTURE_CELLS:
            if _tile(farm, position) is None:
                tasks.append((4, position, ["BUILD_PASTURE"]))

    crop_cells = []
    if day < 27:
        crop_cells = [(position, "WHEAT") for position in WHEAT_CELLS]
        crop_cells += [(position, "MELON") for position in MELON_CELLS] if day <= 12 else [
            (position, "STRAWBERRY") for position in STRAWBERRY_CELLS
        ]
    seeds = private.get("seeds", {})
    for position, crop in crop_cells:
        tile = _tile(farm, position)
        if tile is None and seeds.get(crop, 0) > 0:
            tasks.append((5, position, ["PLANT", crop]))

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
    if day < 27 and empty_pastures and shed.get("COW", 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((2, position, ["PICKUP", "COW", 1]))

    return tasks


def agent(obs):
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    private = obs.get("private", {}) or {}
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    positions = [tuple(farm["farmer"])] + [tuple(position) for position in farm.get("hands", [])]
    inventories = list(private.get("inventories", []))
    while len(inventories) < len(positions):
        inventories.append({})

    actions = [["PASS"] for _ in positions]
    available = set(range(len(positions)))
    tasks = _tasks(obs, farm, private)

    # Carried resources take precedence because they unlock care and placement.
    for index, (position, inventory) in enumerate(zip(positions, inventories)):
        if inventory.get("COW", 0) > 0:
            targets = [
                (2, (x, y), ["PLACE", "COW"])
                for y, row in enumerate(farm["tiles"])
                for x, tile in enumerate(row)
                if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile
            ]
            if targets:
                _, target, operation = min(targets, key=lambda task: (_distance(position, task[1]), task[1]))
                actions[index] = operation if position == target else _step_toward(position, target)
                available.discard(index)
        elif inventory.get("WHEAT", 0) > 0:
            feed_targets = [task for task in tasks if task[2][0] == "FEED"]
            if feed_targets:
                _, target, operation = min(feed_targets, key=lambda task: (_distance(position, task[1]), task[1]))
                actions[index] = operation if position == target else _step_toward(position, target)
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
        "market": _market_plan(obs, farm, private),
    }


balanced_tempo_agent = agent
