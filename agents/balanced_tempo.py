"""Dense Predictor v0.5: market-aware portfolio prediction and routed operations."""

from __future__ import annotations

import math


CROPS = {
    "WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON": {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
BASE_PRICES = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL", "WOOL"),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT", "CARROT"),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
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
    animal_counts = {
        animal: _count_tiles(farm, lambda tile, animal=animal: isinstance(tile, dict) and tile.get("animal") == animal)
        for animal in ("GOOSE", "COW", "SHEEP")
    }
    animals = sum(animal_counts.values())
    quadrants = len(farm.get("unlocked_quadrants", []))
    hands = len(farm.get("hands", []))
    crop_total = sum(crops.values())
    scores = {
        "melon-rush": -1.0 + 0.34 * crops["MELON"] + (0.45 if day <= 12 else -0.35),
        "strawberry-recurring": -1.0 + 0.42 * crops["STRAWBERRY"],
        "tomato-recurring": -1.0 + 0.42 * crops["TOMATO"],
        "livestock-compound": -1.0 + 1.02 * animals,
        "goose-volume": -1.2 + 0.92 * animal_counts["GOOSE"],
        "cow-milk": -1.2 + 0.92 * animal_counts["COW"],
        "sheep-premium": -1.2 + 0.92 * animal_counts["SHEEP"],
        "labor-swarm": -1.1 + 0.13 * hands,
        "land-expansion": -1.0 + 1.35 * max(0, quadrants - 1) + 0.04 * hands,
        "mixed": 0.1 + 0.05 * crop_total + 0.18 * min(animals, 2),
    }
    return _softmax(scores, temperature=0.85)


def _demand_forecast(obs, horizon_days=6):
    """Estimate visible town draw and translate price momentum into crop value."""
    shops = (obs.get("town") or {}).get("unlocked_shops", [])
    market = obs.get("market") or {}
    prices = market.get("prices") or {}
    demand = {item: float(horizon_days) for item in SELLABLE_PRODUCTS}
    for shop in shops:
        for item in SHOP_PRODUCTS.get(shop, ()):
            demand[item] = demand.get(item, 0.0) + 6.0 * horizon_days
    return {
        item: {
            "visible_demand": demand.get(item, 0.0),
            "price": float(prices.get(item, BASE_PRICES.get(item, 1))),
            "momentum": float(prices.get(item, BASE_PRICES.get(item, 1))) / max(1.0, BASE_PRICES.get(item, 1)),
        }
        for item in SELLABLE_PRODUCTS
    }


def _portfolio_model(obs, farm, opponent, phase):
    """Score every crop by time-to-cash, visible demand, price, and crowding."""
    day = int(obs.get("day", 0))
    remaining = max(0, 29 - day)
    forecast = _demand_forecast(obs, horizon_days=min(8, remaining + 1))
    opponent_crops = {
        crop: _count_tiles(opponent, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in CROPS
    }
    scores = {}
    for crop, data in CROPS.items():
        if remaining < data["first_yield_day"]:
            scores[crop] = -1e6
            continue
        if data["ongoing"]:
            production_days = remaining - data["first_yield_day"]
            units = min(data["max_yield"], 1 + production_days // data["interval"])
            water_days = data["first_yield_day"] + max(0, production_days)
        else:
            units = data["max_yield"]
            water_days = data["max_yield_day"]
        signal = forecast[crop]
        revenue = units * signal["price"]
        labor = 1.0 + water_days + (units if data["ongoing"] else 1.0)
        demand_boost = 1.0 + min(0.45, signal["visible_demand"] / 180.0)
        crowding = 1.0 + 0.035 * opponent_crops[crop]
        scores[crop] = ((revenue - data["seed"]) / labor) * demand_boost * signal["momentum"] / crowding
    recurring = max(("TOMATO", "STRAWBERRY"), key=lambda crop: (scores[crop], crop))
    cash = max(("CARROT", "MELON"), key=lambda crop: (scores[crop], crop))
    return {"scores": scores, "recurring_crop": recurring, "cash_crop": cash, "forecast": forecast}


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
            "recurring_targets": {"STRAWBERRY": 8, "TOMATO": 7},
            "cash_crop": "MELON",
            "crop_scores": {},
            "probabilities": {},
            "attention_weights": {"operations": 1.0, "opponent": 0.0, "horizon": 0.0},
        }

    opponent = opponents[0]
    probabilities = _strategy_belief(opponent, int(obs.get("day", 0)))
    attention = _attention_weights(obs, player, probabilities)
    own_farm = obs.get("farms", [])[player]
    phase = _phase_attention(obs)
    portfolio = _portfolio_model(obs, own_farm, opponent, phase)
    own_crop_counts = {
        crop: _count_tiles(own_farm, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in ("CARROT", "MELON", "TOMATO", "STRAWBERRY")
    }
    archetype, confidence = max(probabilities.items(), key=lambda item: item[1])

    # Recurring crops are a portfolio decision. Switch only when the weighted
    # probability of strawberry crowding materially exceeds tomato crowding.
    strawberry_risk = probabilities["strawberry-recurring"] + 0.25 * probabilities["mixed"]
    tomato_risk = probabilities["tomato-recurring"] + 0.18 * probabilities["mixed"]
    defensive_recurring = (
        "TOMATO"
        if strawberry_risk - tomato_risk >= 0.16 and attention["opponent"] >= 0.12
        else "STRAWBERRY"
    )
    recurring_crop = portfolio["recurring_crop"] if attention["opponent"] < 0.32 else defensive_recurring
    if own_crop_counts["TOMATO"] + own_crop_counts["STRAWBERRY"]:
        recurring_crop = max(("TOMATO", "STRAWBERRY"), key=lambda crop: (own_crop_counts[crop], crop))
    cash_crop = portfolio["cash_crop"]
    if own_crop_counts["CARROT"] + own_crop_counts["MELON"]:
        cash_crop = max(("CARROT", "MELON"), key=lambda crop: (own_crop_counts[crop], crop))
    return {
        "archetype": archetype,
        "confidence": round(confidence, 4),
        "recurring_crop": recurring_crop,
        "recurring_targets": {
            recurring_crop: 8,
            ("TOMATO" if recurring_crop == "STRAWBERRY" else "STRAWBERRY"): 7,
        },
        "cash_crop": cash_crop,
        "crop_scores": {key: round(value, 2) for key, value in portfolio["scores"].items()},
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

    # Shed overflow discards end-of-day output. Forecast harvest already visible
    # on mature crops and clear low-value wheat before it displaces melon or
    # recurring output. Keep a small feed reserve; more wheat can be bought once
    # animals are placed and the high-value harvest has cleared.
    incoming_harvest = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict) or int(tile.get("yield_units", 0)) <= 0:
                continue
            if tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                age = day - int(tile.get("planted_day", day))
                if CROPS.get(crop, {}).get("ongoing") or age >= CROPS.get(crop, {}).get("max_yield_day", 99):
                    incoming_harvest += int(tile.get("yield_units", 0))
            elif "animal" in tile:
                incoming_harvest += int(tile.get("yield_units", 0))
    shed_load = sum(int(value) for value in shed.values())
    capacity_pressure = max(0, shed_load + incoming_harvest + 4 - 100)
    feed_floor = max(4, animals * 2)
    pressure_wheat_sale = min(
        max(0, int(shed.get("WHEAT", 0)) - feed_floor),
        capacity_pressure,
    )
    if pressure_wheat_sale:
        orders.append(["SELL", "WHEAT", pressure_wheat_sale])

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
        wheat_to_sell = max(0, int(shed.get("WHEAT", 0)) - feed_reserve - pressure_wheat_sale)
        if wheat_to_sell:
            orders.append(["SELL", "WHEAT", wheat_to_sell])

    planted = {
        crop: _count_tiles(farm, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in CROPS
    }
    desired = {"WHEAT": 5} if day <= 25 else {}
    if phase["phase"] == "early":
        desired[opponent_signal.get("cash_crop", "MELON")] = 10
    elif phase["allow_recurring"]:
        desired.update(opponent_signal.get("recurring_targets", {opponent_signal["recurring_crop"]: 15}))

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
            planned_tile = _tile(farm, position)
            if planned_tile is None:
                tasks.append((5, position, ["BUILD_PASTURE"]))
            elif isinstance(planned_tile, dict) and planned_tile.get("kind") == "WEED":
                tasks.append((4, position, ["DIG"]))

    crop_cells = []
    if phase["late_mode"] != "execute":
        crop_cells = [(position, "WHEAT") for position in WHEAT_CELLS] if day <= 25 else []
        crop_cells += [(position, opponent_signal.get("cash_crop", "MELON")) for position in MELON_CELLS] if phase["phase"] == "early" else []
        if phase["allow_recurring"]:
            targets = opponent_signal.get("recurring_targets", {opponent_signal["recurring_crop"]: 15})
            primary = opponent_signal["recurring_crop"]
            secondary = "TOMATO" if primary == "STRAWBERRY" else "STRAWBERRY"
            crop_cells += [
                (position, primary if index < int(targets.get(primary, 8)) else secondary)
                for index, position in enumerate(RECURRING_CELLS)
            ]
    seeds = private.get("seeds", {})
    for position, crop in crop_cells:
        tile = _tile(farm, position)
        if tile is None and seeds.get(crop, 0) > 0:
            tasks.append((6, position, ["PLANT", crop]))
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            tasks.append((5, position, ["DIG"]))

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
            tasks.append((0, position, ["PICKUP", "COW", 1]))

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
    # Preserve the stable v0.4 dispatcher while the predictive layer is
    # evaluated independently. Routing is a separate promotion lever.
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
