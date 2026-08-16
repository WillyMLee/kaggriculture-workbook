"""Adaptive Horizon v0.7.1: dynamic reserves and bounded opponent prediction."""

from __future__ import annotations

import json
import math


CROPS = {
    "WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON": {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
BASE_PRICES = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}
ANIMAL_ECONOMICS = {
    "GOOSE": {"cost": 300, "first_yield_day": 4, "interval": 1, "product": "EGG"},
    "COW": {"cost": 400, "first_yield_day": 8, "interval": 2, "product": "MILK"},
    "SHEEP": {"cost": 500, "first_yield_day": 6, "interval": 3, "product": "WOOL"},
}
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
ADAPTIVE_PASTURE_CELL = ((4, 3),)
MELON_CELLS = ((0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1))
WHEAT_CELLS = ((0, 2), (1, 2), (2, 2), (3, 2), (4, 2))
STRAWBERRY_CELLS = MELON_CELLS + ((0, 3), (1, 3), (2, 3), (3, 3), (4, 3))
RECURRING_CELLS = STRAWBERRY_CELLS
STRATEGY_SUPPLY = {
    "wheat-volume": {"WHEAT": 1.0},
    "carrot-volume": {"CARROT": 1.0},
    "melon-rush": {"MELON": 1.0},
    "strawberry-recurring": {"STRAWBERRY": 1.0},
    "tomato-recurring": {"TOMATO": 1.0},
    "livestock-compound": {"EGG": 0.25, "MILK": 0.45, "WOOL": 0.30},
    "goose-volume": {"EGG": 1.0},
    "cow-milk": {"MILK": 1.0},
    "sheep-premium": {"WOOL": 1.0},
    "labor-swarm": {},
    "land-expansion": {"MELON": 0.20, "STRAWBERRY": 0.25, "TOMATO": 0.20},
    "mixed": {"CARROT": 0.12, "MELON": 0.16, "TOMATO": 0.18, "STRAWBERRY": 0.18, "EGG": 0.12, "MILK": 0.14, "WOOL": 0.10},
}
STRATEGY_NAMES = tuple(STRATEGY_SUPPLY)
_EPISODE_MEMORY = {}


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


def _episode_memory(obs, player):
    """Return isolated, resettable RAM for one player in one episode."""
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    step = int(obs.get("step", day * 24 + hour))
    previous = _EPISODE_MEMORY.get(player)
    new_episode = previous is None or (
        day == 0 and hour == 0 and int(previous.get("last_seen_step", -1)) != step
    )
    if new_episode:
        _EPISODE_MEMORY[player] = {
            "last_belief_day": -1,
            "opponent_features": None,
            "probabilities": None,
            "asset_growth": 0.0,
            "bank_delta": 0.0,
            "history": [],
            "predicted_delta": None,
            "prediction_error": 0.0,
            "prediction_break": False,
            "route_day": -1,
            "routes": {},
            "trace_days": set(),
            "last_seen_step": step,
        }
    else:
        _EPISODE_MEMORY[player]["last_seen_step"] = step
    return _EPISODE_MEMORY[player]


def _farm_feature_snapshot(obs, farm):
    """Compress public commitments into a day-over-day opponent trace."""
    crops = {
        crop: _count_tiles(
            farm,
            lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop,
        )
        for crop in CROPS
    }
    animals = {
        animal: _count_tiles(
            farm,
            lambda tile, animal=animal: isinstance(tile, dict) and tile.get("animal") == animal,
        )
        for animal in ANIMAL_ECONOMICS
    }
    asset = _public_asset_value(obs, farm)
    return {
        "money": float(farm.get("money", 0)),
        "crops": crops,
        "animals": animals,
        "hands": len(farm.get("hands", [])),
        "quadrants": len(farm.get("unlocked_quadrants", [])),
        "productive_value": asset["productive_value"],
        "terminal_proxy": asset["terminal_proxy"],
    }


def _public_asset_value(obs, farm):
    """Estimate visible terminal value without pretending private inventory is known."""
    day = int(obs.get("day", 0))
    remaining_days = max(0, 29 - day)
    prices = (obs.get("market") or {}).get("prices", {})
    productive_value = 0.0
    crop_pipeline = 0.0
    livestock_pipeline = 0.0

    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT" and tile.get("crop") in CROPS:
                crop = tile["crop"]
                data = CROPS[crop]
                price = float(prices.get(crop, BASE_PRICES[crop]))
                age = max(0, day - int(tile.get("planted_day", day)))
                ready_units = max(0, int(tile.get("yield_units", 0)))
                value = ready_units * price
                if data["ongoing"]:
                    future_yields = 0
                    for future_age in range(age + 1, age + remaining_days + 1):
                        since_first = future_age - data["first_yield_day"]
                        if since_first < 0 or since_first % data["interval"]:
                            continue
                        if since_first // data["interval"] + 1 <= data["max_yield"]:
                            future_yields += 1
                    value += future_yields * 2.5 * price * 0.72
                elif ready_units == 0 and age <= data["max_yield_day"] and remaining_days >= data["max_yield_day"] - age:
                    maturity_discount = 0.82 if int(tile.get("fertilized_until_day", -1)) >= day else 0.68
                    value += data["max_yield"] * price * maturity_discount
                crop_pipeline += value
            if tile.get("animal") in ANIMAL_ECONOMICS:
                animal = tile["animal"]
                data = ANIMAL_ECONOMICS[animal]
                product = data["product"]
                product_price = float(prices.get(product, BASE_PRICES[product]))
                wheat_price = float(prices.get("WHEAT", BASE_PRICES["WHEAT"]))
                ready_units = max(0, int(tile.get("yield_units", 0)))
                placed = int(tile.get("placed_day", day))
                next_age = max(0, day + 1 - placed)
                future_ticks = 0
                for future_day in range(day + 1, 29):
                    age = future_day - placed
                    if age >= data["first_yield_day"] and (age - data["first_yield_day"]) % data["interval"] == 0:
                        future_ticks += 1
                future_units = future_ticks * (1 + data["interval"])
                feed_cost = max(0, 28 - day) * wheat_price
                value = ready_units * product_price + future_units * product_price * 0.68 - feed_cost * 0.55
                if next_age <= data["first_yield_day"] + remaining_days:
                    livestock_pipeline += max(0.0, value)

    productive_value = crop_pipeline + livestock_pipeline
    return {
        "bank": float(farm.get("money", 0)),
        "crop_pipeline": round(crop_pipeline, 2),
        "livestock_pipeline": round(livestock_pipeline, 2),
        "productive_value": round(productive_value, 2),
        "terminal_proxy": round(float(farm.get("money", 0)) + productive_value, 2),
    }


def _own_terminal_value(obs, farm, private):
    """Add liquid private inventory to the public productive-value estimate."""
    prices = (obs.get("market") or {}).get("prices", {})
    liquid = 0.0
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []
    for item in SELLABLE_PRODUCTS:
        units = int(shed.get(item, 0)) + sum(int(inventory.get(item, 0)) for inventory in inventories)
        liquid += units * float(prices.get(item, BASE_PRICES.get(item, 1)))
    public = _public_asset_value(obs, farm)
    return round(public["terminal_proxy"] + liquid, 2)


def _softmax(scores, temperature=1.0):
    """Turn comparable strategy or attention scores into stable probabilities."""
    scale = max(float(temperature), 0.05)
    peak = max(scores.values())
    weights = {key: math.exp((value - peak) / scale) for key, value in scores.items()}
    total = sum(weights.values()) or 1.0
    return {key: weight / total for key, weight in weights.items()}


def _strategy_belief(obs, farm, day, memory=None):
    """Update a Bayesian-style belief from commitments and day-over-day deltas."""
    crops = {
        crop: _count_tiles(
            farm,
            lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop,
        )
        for crop in CROPS
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
        "wheat-volume": -1.1 + 0.10 * min(crops["WHEAT"], 15),
        "carrot-volume": -1.1 + 0.18 * min(crops["CARROT"], 15),
        "melon-rush": -1.0 + 0.22 * min(crops["MELON"], 15) + (0.45 if day <= 12 else -0.35),
        "strawberry-recurring": -1.0 + 0.30 * min(crops["STRAWBERRY"], 12),
        "tomato-recurring": -1.0 + 0.30 * min(crops["TOMATO"], 12),
        "livestock-compound": -1.0 + 1.02 * animals,
        "goose-volume": -1.2 + 0.92 * animal_counts["GOOSE"],
        "cow-milk": -1.2 + 0.92 * animal_counts["COW"],
        "sheep-premium": -1.2 + 0.92 * animal_counts["SHEEP"],
        "labor-swarm": -1.1 + 0.13 * hands,
        "land-expansion": -1.0 + 1.35 * max(0, quadrants - 1) + 0.04 * hands,
        "mixed": 0.1 + 0.05 * crop_total + 0.18 * min(animals, 2),
    }
    if memory is None:
        return _softmax(scores, temperature=0.85)
    if memory.get("last_belief_day") == day and memory.get("probabilities"):
        return memory["probabilities"]

    current = _farm_feature_snapshot(obs, farm)
    previous = memory.get("opponent_features")
    prior = memory.get("probabilities")
    asset_growth = 0.0
    bank_delta = 0.0
    crop_delta = {crop: 0 for crop in CROPS}
    animal_delta = {animal: 0 for animal in ANIMAL_ECONOMICS}
    if previous:
        crop_delta = {
            crop: current["crops"][crop] - previous["crops"].get(crop, 0)
            for crop in CROPS
        }
        animal_delta = {
            animal: current["animals"][animal] - previous["animals"].get(animal, 0)
            for animal in ANIMAL_ECONOMICS
        }
        asset_growth = current["productive_value"] - previous.get("productive_value", 0.0)
        bank_delta = current["money"] - previous.get("money", 0.0)
        investment = max(0.0, -bank_delta) + max(0.0, asset_growth)
        scores["wheat-volume"] += 1.10 * math.tanh(max(0, crop_delta["WHEAT"]) / 7.0)
        scores["carrot-volume"] += 1.10 * math.tanh(max(0, crop_delta["CARROT"]) / 7.0)
        scores["melon-rush"] += 1.10 * math.tanh(max(0, crop_delta["MELON"]) / 7.0)
        scores["tomato-recurring"] += 1.10 * math.tanh(max(0, crop_delta["TOMATO"]) / 7.0)
        scores["strawberry-recurring"] += 1.10 * math.tanh(max(0, crop_delta["STRAWBERRY"]) / 7.0)
        new_animals = sum(max(0, value) for value in animal_delta.values())
        scores["livestock-compound"] += 1.25 * new_animals + 0.00012 * investment
        scores["goose-volume"] += 1.05 * max(0, animal_delta["GOOSE"])
        scores["cow-milk"] += 1.05 * max(0, animal_delta["COW"])
        scores["sheep-premium"] += 1.05 * max(0, animal_delta["SHEEP"])
        scores["labor-swarm"] += 0.28 * max(0, current["hands"] - previous.get("hands", 0))
        scores["land-expansion"] += 1.25 * max(0, current["quadrants"] - previous.get("quadrants", 0))
        scores["mixed"] += 0.00008 * investment

        # Predict only the next few visible commitments.  If the opponent
        # deviates materially, lower inertia immediately; otherwise retain the
        # incumbent response and avoid thrashing on a single observation.
        prior_prediction = memory.get("predicted_delta") or {}
        predicted_crops = prior_prediction.get("crops", {})
        predicted_animals = prior_prediction.get("animals", {})
        prediction_error = sum(
            abs(crop_delta[crop] - float(predicted_crops.get(crop, 0)))
            for crop in CROPS
        ) + sum(
            abs(animal_delta[animal] - float(predicted_animals.get(animal, 0)))
            for animal in ANIMAL_ECONOMICS
        )
        predicted_scale = 1.0 + sum(abs(float(value)) for value in predicted_crops.values()) + sum(
            abs(float(value)) for value in predicted_animals.values()
        )
        memory["prediction_error"] = round(prediction_error, 3)
        memory["prediction_break"] = prediction_error > max(4.0, 0.75 * predicted_scale)
    if prior:
        uniform = 1.0 / len(STRATEGY_NAMES)
        for strategy in scores:
            scores[strategy] += 0.35 * math.log(max(prior.get(strategy, uniform), 1e-6) / uniform)

    probabilities = _softmax(scores, temperature=0.9)
    memory["last_belief_day"] = day
    memory["opponent_features"] = current
    memory["probabilities"] = probabilities
    memory["asset_growth"] = round(asset_growth, 2)
    memory["bank_delta"] = round(bank_delta, 2)
    previous_prediction = memory.get("predicted_delta") or {}
    memory["predicted_delta"] = {
        "crops": {
            crop: round(0.7 * max(0, crop_delta[crop]) + 0.3 * float((previous_prediction.get("crops") or {}).get(crop, 0)), 2)
            for crop in CROPS
        },
        "animals": {
            animal: round(0.7 * max(0, animal_delta[animal]) + 0.3 * float((previous_prediction.get("animals") or {}).get(animal, 0)), 2)
            for animal in ANIMAL_ECONOMICS
        },
        "horizon_days": 3,
    }
    memory["history"].append({
        "day": day,
        "terminal_proxy": current["terminal_proxy"],
        "productive_value": current["productive_value"],
        "money": current["money"],
        "asset_growth": round(asset_growth, 2),
        "bank_delta": round(bank_delta, 2),
        "crop_delta": crop_delta,
        "animal_delta": animal_delta,
        "prediction_error": memory.get("prediction_error", 0.0),
        "prediction_break": memory.get("prediction_break", False),
    })
    memory["history"] = memory["history"][-8:]
    return probabilities


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


def _dynamic_wheat_plan(obs, farm, private):
    """Size wheat as feed, liquidity, and town demand—not a fixed opener."""
    day = int(obs.get("day", 0))
    remaining = max(0, 29 - day)
    animals = _count_tiles(farm, lambda tile: isinstance(tile, dict) and tile.get("animal"))
    wheat_tiles = _count_tiles(
        farm, lambda tile: isinstance(tile, dict) and tile.get("crop") == "WHEAT"
    )
    wheat_price = float((obs.get("market") or {}).get("prices", {}).get("WHEAT", BASE_PRICES["WHEAT"]))
    town = _demand_forecast(obs, horizon_days=min(4, remaining + 1))["WHEAT"]
    shed_wheat = int((private.get("shed") or {}).get("WHEAT", 0))
    carried_wheat = sum(int(inv.get("WHEAT", 0)) for inv in (private.get("inventories") or []))

    # Maintain only a rolling reserve because the market remains available.
    reserve_days = min(3, remaining + 1)
    feed_reserve = animals * reserve_days
    feed_gap = max(0, feed_reserve - shed_wheat - carried_wheat)
    town_support = min(3, int(town["visible_demand"] // 40))
    price_support = 2 if wheat_price >= BASE_PRICES["WHEAT"] * 1.12 else 0
    if animals:
        tile_target = min(len(WHEAT_CELLS), max(3, (animals + 1) // 2 + town_support + price_support))
    else:
        tile_target = min(len(WHEAT_CELLS), 3 + town_support + price_support)
    if day >= 24:
        tile_target = min(tile_target, max(0, remaining - 1))
    return {
        "tile_target": tile_target,
        "current_tiles": wheat_tiles,
        "feed_reserve": feed_reserve,
        "feed_gap": feed_gap,
        "price": wheat_price,
    }


def _labor_plan(obs, farm, phase):
    """Hire for today's work and travel footprint, not a fixed phase quota."""
    day = int(obs.get("day", 0))
    work_units = 0
    active_positions = []
    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT":
                active_positions.append((x, y))
                work_units += int(not tile.get("watered_today", False))
                work_units += int(int(tile.get("yield_units", 0)) > 0)
            if tile.get("animal"):
                active_positions.append((x, y))
                work_units += int(not tile.get("fed_today", False))
                work_units += int(not tile.get("cared_today", False))
                work_units += int(tile.get("fertilizer_available", False))
                work_units += int(int(tile.get("yield_units", 0)) > 0)
    if phase.get("allow_animals"):
        work_units += 4
    if phase.get("allow_recurring"):
        work_units += 6
    if active_positions:
        route_span = max(_distance(position, _nearest_shed(position)) for position in active_positions)
    else:
        route_span = 0
    target = 2 + int(math.ceil(work_units / 8.0)) + int(route_span >= 5)
    if day == 0:
        target = max(target, 5)
    if phase.get("late_mode") == "execute":
        target = max(target, 7)
    return {
        "target": max(2, min(10, target)),
        "work_units": work_units,
        "route_span": route_span,
    }


def _expected_supply_pressure(probabilities, product):
    """Expected opponent supply for a product across all live archetypes."""
    return sum(
        float(probability) * STRATEGY_SUPPLY.get(strategy, {}).get(product, 0.0)
        for strategy, probability in probabilities.items()
    )


def _portfolio_model(obs, farm, opponent, phase, probabilities=None):
    """Score crops in coins per constrained tile/labor day, not gross revenue."""
    day = int(obs.get("day", 0))
    remaining = max(0, 29 - day)
    probabilities = probabilities or {}
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
            harvests = min(data["max_yield"], 1 + production_days // data["interval"])
            units = harvests
            final_yield_day = data["first_yield_day"] + max(0, harvests - 1) * data["interval"]
            water_days = final_yield_day + 1
            tile_days = final_yield_day + 1
            harvest_actions = harvests
        else:
            window_start = (data["max_yield_day"] + 1) // 2
            units = min(data["max_yield"], 1 + data["max_yield_day"] - window_start + 1)
            water_days = data["max_yield_day"] + 1
            tile_days = data["max_yield_day"] + 1
            harvest_actions = 1
        signal = forecast[crop]
        revenue = units * signal["price"]
        labor = 1.0 + water_days + harvest_actions
        demand_boost = 1.0 + min(0.45, signal["visible_demand"] / 180.0)
        # Shared-market crowding matters, but it should not overpower our own
        # ROI, town demand, or switching cost.
        observed_crowding = 0.045 * opponent_crops[crop]
        belief_crowding = 0.08 * _expected_supply_pressure(probabilities, crop)
        switching_cost = 0.0
        own_other = _count_tiles(
            farm,
            lambda tile, crop=crop: isinstance(tile, dict)
            and tile.get("crop") in CROPS
            and tile.get("crop") != crop,
        )
        if own_other:
            switching_cost = min(18.0, own_other * 1.5)
        net_margin = revenue - data["seed"] - switching_cost
        constrained_days = tile_days + 0.65 * labor
        scores[crop] = (
            net_margin
            * demand_boost
            * signal["momentum"]
            / max(1.0, constrained_days)
            / (1.0 + observed_crowding + belief_crowding)
        )
    recurring = max(("TOMATO", "STRAWBERRY"), key=lambda crop: (scores[crop], crop))
    cash = max(("CARROT", "MELON"), key=lambda crop: (scores[crop], crop))
    return {"scores": scores, "recurring_crop": recurring, "cash_crop": cash, "forecast": forecast}


def _animal_portfolio_model(obs, farm, opponent, probabilities=None):
    """Estimate animal value after feed, care, collection, tile, and crowding costs."""
    day = int(obs.get("day", 0))
    probabilities = probabilities or {}
    prices = (obs.get("market") or {}).get("prices", {})
    forecast = _demand_forecast(obs, horizon_days=max(1, min(8, 29 - day)))
    opponent_animals = {
        animal: _count_tiles(opponent, lambda tile, animal=animal: isinstance(tile, dict) and tile.get("animal") == animal)
        for animal in ANIMAL_ECONOMICS
    }
    scores = {}
    details = {}
    for animal, data in ANIMAL_ECONOMICS.items():
        first_day = day + data["first_yield_day"]
        if first_day > 28:
            scores[animal] = -1e6
            details[animal] = {"net": -1e6, "units": 0, "payback_day": None}
            continue
        production_days = list(range(first_day, 29, data["interval"]))
        max_held = 4 if animal == "GOOSE" else 6
        first_units = min(max_held, 1 + data["first_yield_day"])
        units = first_units + max(0, len(production_days) - 1) * (1 + data["interval"])
        last_day = production_days[-1]
        feed_days = last_day - day + 1
        product = data["product"]
        product_price = float(prices.get(product, BASE_PRICES[product]))
        wheat_price = float(prices.get("WHEAT", BASE_PRICES["WHEAT"]))
        fertilizer_price = float(prices.get("FERTILIZER", BASE_PRICES["FERTILIZER"]))
        product_revenue = units * product_price
        # Fertilizer is valuable but collection competes with survival and harvest work.
        fertilizer_credit = max(0, feed_days - 1) * fertilizer_price * 0.55
        feed_cost = feed_days * wheat_price
        labor_actions = feed_days * 2 + len(production_days) + max(0, feed_days - 1) + 3
        labor_shadow = labor_actions * 3.0
        crowding = 1.0 + 0.035 * opponent_animals[animal] + 0.12 * _expected_supply_pressure(probabilities, product)
        demand_boost = 1.0 + min(0.35, forecast[product]["visible_demand"] / 240.0)
        net = ((product_revenue + fertilizer_credit) * demand_boost / crowding) - data["cost"] - feed_cost - labor_shadow
        tile_days = max(1, last_day - day + 1)
        scores[animal] = net / (tile_days + 0.45 * labor_actions)
        details[animal] = {
            "net": round(net, 2),
            "units": units,
            "feed_days": feed_days,
            "payback_day": first_day,
        }
    choice = max(ANIMAL_ECONOMICS, key=lambda animal: (scores[animal], animal))
    return {"scores": scores, "animal": choice, "details": details}


def _engine_combo_model(obs, farm, crop_model, animal_model):
    """Score crop×livestock engines with shared labor, feed, and town effects."""
    day = int(obs.get("day", 0))
    remaining = max(0, 29 - day)
    shops = (obs.get("town") or {}).get("unlocked_shops", [])
    prices = (obs.get("market") or {}).get("prices", {})
    wheat_price = float(prices.get("WHEAT", BASE_PRICES["WHEAT"]))
    existing_animals = {
        animal: _count_tiles(
            farm, lambda tile, animal=animal: isinstance(tile, dict) and tile.get("animal") == animal
        )
        for animal in ANIMAL_ECONOMICS
    }
    combinations = {}
    for crop in ("TOMATO", "STRAWBERRY"):
        for animal, animal_data in ANIMAL_ECONOMICS.items():
            product = animal_data["product"]
            crop_target = 15
            animal_target = 4
            shop_synergy = sum(
                1 for shop in shops if crop in SHOP_PRODUCTS.get(shop, ()) and product in SHOP_PRODUCTS.get(shop, ())
            )
            fertilizer_synergy = min(4, animal_target) * max(0.0, crop_model["scores"][crop]) * 0.18
            feed_burden = animal_target * min(8, remaining) * wheat_price * 0.10
            labor_burden = (crop_target + animal_target * 3) * 1.8
            incumbent_bonus = existing_animals[animal] * 12.0
            score = (
                crop_model["scores"][crop] * crop_target
                + animal_model["scores"][animal] * animal_target
                + shop_synergy * 90.0
                + fertilizer_synergy
                + incumbent_bonus
                - feed_burden
                - labor_burden
            )
            combinations[f"{crop}+{animal}"] = score
    choice, score = max(combinations.items(), key=lambda item: (item[1], item[0]))
    crop, animal = choice.split("+", 1)
    return {
        "choice": choice,
        "crop": crop,
        "animal": animal,
        "score": round(score, 2),
        "scores": {key: round(value, 2) for key, value in combinations.items()},
    }


def _attention_weights(obs, player, strategy_probabilities, asset_threat=0.0):
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
    if day <= 11:
        opponent_window = 0.65
    elif day <= 21:
        opponent_window = 1.0
    elif day <= 27:
        opponent_window = 0.75
    else:
        opponent_window = 0.20
    progress = day / 29.0
    scores = {
        "operations": 1.15 + 3.0 * min(1.0, urgent_work / 8.0),
        # Opponent inference is advisory.  The town, our deadlines, and our
        # productive state retain most of the decision budget.
        "opponent": 0.10 + 1.25 * certainty * opponent_window + 0.70 * float(asset_threat),
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
            "animal": "COW",
            "animal_target": 4,
            "crop_scores": {},
            "animal_scores": {},
            "strategy_utilities": {},
            "probabilities": {},
            "attention_weights": {"operations": 1.0, "opponent": 0.0, "horizon": 0.0},
            "asset_threat": 0.0,
            "asset_gap": 0.0,
            "own_terminal_value": 0.0,
            "opponent_terminal_proxy": 0.0,
            "asset_growth": 0.0,
            "capital_mode": "hold",
        }

    opponent = opponents[0]
    own_farm = obs.get("farms", [])[player]
    memory = _episode_memory(obs, player)
    probabilities = _strategy_belief(obs, opponent, int(obs.get("day", 0)), memory)
    own_terminal_value = _own_terminal_value(obs, own_farm, obs.get("private", {}) or {})
    own_value = _public_asset_value(obs, own_farm)
    opponent_value = _public_asset_value(obs, opponent)
    asset_gap = float(opponent_value["terminal_proxy"]) - own_terminal_value
    productive_gap = float(opponent_value["productive_value"]) - float(own_value["productive_value"])
    own_scale = _count_tiles(
        own_farm, lambda tile: isinstance(tile, dict) and (tile.get("crop") or tile.get("animal"))
    )
    opponent_scale = _count_tiles(
        opponent, lambda tile: isinstance(tile, dict) and (tile.get("crop") or tile.get("animal"))
    )
    scale_gap = opponent_scale - own_scale
    own_animals_total = _count_tiles(own_farm, lambda tile: isinstance(tile, dict) and tile.get("animal"))
    opponent_animals_total = _count_tiles(opponent, lambda tile: isinstance(tile, dict) and tile.get("animal"))
    animal_gap = opponent_animals_total - own_animals_total
    quadrant_gap = len(opponent.get("unlocked_quadrants", [])) - len(own_farm.get("unlocked_quadrants", []))
    asset_growth = float(memory.get("asset_growth", 0.0))
    investment = max(0.0, -float(memory.get("bank_delta", 0.0)))
    asset_threat = max(
        0.0,
        min(
            1.0,
            0.35
            + 0.12 * math.tanh(asset_gap / 6000.0)
            + 0.20 * math.tanh(productive_gap / 5000.0)
            + 0.30 * math.tanh(scale_gap / 12.0)
            + 0.20 * math.tanh(animal_gap / 6.0)
            + 0.10 * math.tanh(quadrant_gap)
            + 0.08 * math.tanh(asset_growth / 3500.0)
            + 0.05 * math.tanh(investment / 2500.0),
        ),
    )
    attention = _attention_weights(obs, player, probabilities, asset_threat)
    phase = _phase_attention(obs)
    portfolio = _portfolio_model(obs, own_farm, opponent, phase, probabilities)
    animal_portfolio = _animal_portfolio_model(obs, own_farm, opponent, probabilities)
    combo = _engine_combo_model(obs, own_farm, portfolio, animal_portfolio)
    own_crop_counts = {
        crop: _count_tiles(own_farm, lambda tile, crop=crop: isinstance(tile, dict) and tile.get("crop") == crop)
        for crop in ("CARROT", "MELON", "TOMATO", "STRAWBERRY")
    }
    archetype, confidence = max(probabilities.items(), key=lambda item: item[1])

    # Convert expected portfolio values into a stable mixed response. A strategy
    # family never owns the decision outright; its probability changes utility.
    recurring_crop = portfolio["recurring_crop"]
    incumbent_recurring = max(("TOMATO", "STRAWBERRY"), key=lambda crop: (own_crop_counts[crop], crop))
    prediction_break = bool(memory.get("prediction_break", False))
    if own_crop_counts[incumbent_recurring]:
        challenger = recurring_crop
        incumbent_score = portfolio["scores"][incumbent_recurring]
        challenger_score = portfolio["scores"][challenger]
        score_scale = max(1.0, abs(incumbent_score) + abs(challenger_score))
        switch_margin = (challenger_score - incumbent_score) / score_scale
        threshold = 0.16 if prediction_break else 0.30
        if challenger == incumbent_recurring or switch_margin < threshold:
            recurring_crop = incumbent_recurring
    cash_crop = portfolio["cash_crop"]
    incumbent_cash = max(("CARROT", "MELON"), key=lambda crop: (own_crop_counts[crop], crop))
    if own_crop_counts[incumbent_cash]:
        cash_margin = (
            portfolio["scores"][cash_crop] - portfolio["scores"][incumbent_cash]
        ) / max(1.0, abs(portfolio["scores"][cash_crop]) + abs(portfolio["scores"][incumbent_cash]))
        if cash_crop == incumbent_cash or cash_margin < (0.14 if prediction_break else 0.26):
            cash_crop = incumbent_cash
    secondary = "TOMATO" if recurring_crop == "STRAWBERRY" else "STRAWBERRY"
    primary_score = portfolio["scores"][recurring_crop]
    secondary_score = portfolio["scores"][secondary]
    scale = max(1.0, abs(primary_score) + abs(secondary_score))
    primary_share = 0.5 + 0.30 * math.tanh((primary_score - secondary_score) / scale * 4.0)
    primary_target = max(8, min(12, int(round(15 * primary_share))))
    own_animal_counts = {
        animal_name: _count_tiles(
            own_farm,
            lambda tile, animal_name=animal_name: isinstance(tile, dict) and tile.get("animal") == animal_name,
        )
        for animal_name in ANIMAL_ECONOMICS
    }
    animal = animal_portfolio["animal"]
    if sum(own_animal_counts.values()):
        animal = max(ANIMAL_ECONOMICS, key=lambda name: (own_animal_counts[name], name))
    animal_target = 4 if animal_portfolio["details"][animal]["net"] > 0 else 0
    if animal_target and int(obs.get("day", 0)) <= 18 and asset_threat >= 0.68:
        animal_target = 5
    capital_mode = (
        "compound"
        if int(obs.get("day", 0)) <= 18 and asset_threat >= 0.58 and asset_growth > 250
        else "hold"
    )
    strategy_utilities = {
        "cash-engine": portfolio["scores"][cash_crop] * 10,
        "recurring-engine": primary_score * primary_target + secondary_score * (15 - primary_target),
        "livestock-engine": animal_portfolio["scores"][animal] * animal_target,
    }
    return {
        "archetype": archetype,
        "confidence": round(confidence, 4),
        "recurring_crop": recurring_crop,
        "recurring_targets": {
            recurring_crop: primary_target,
            secondary: 15 - primary_target,
        },
        "cash_crop": cash_crop,
        "animal": animal,
        "animal_target": animal_target,
        "crop_scores": {key: round(value, 2) for key, value in portfolio["scores"].items()},
        "animal_scores": {key: round(value, 2) for key, value in animal_portfolio["scores"].items()},
        "engine_combo": combo,
        "strategy_utilities": {key: round(value, 2) for key, value in strategy_utilities.items()},
        "probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "attention_weights": {key: round(value, 4) for key, value in attention.items()},
        "asset_threat": round(asset_threat, 4),
        "asset_gap": round(asset_gap, 2),
        "productive_gap": round(productive_gap, 2),
        "scale_gap": scale_gap,
        "animal_gap": animal_gap,
        "own_terminal_value": round(own_terminal_value, 2),
        "opponent_terminal_proxy": round(float(opponent_value["terminal_proxy"]), 2),
        "asset_growth": round(asset_growth, 2),
        "capital_mode": capital_mode,
        "opponent_forecast": memory.get("predicted_delta") or {},
        "prediction_error": memory.get("prediction_error", 0.0),
        "prediction_break": prediction_break,
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


def _reverse_terminal_plan(obs, farm, private):
    """Work backward from a sold, empty terminal state to today's obligations."""
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    remaining_turns = max(0, (29 - day) * 24 + (24 - hour))
    feed_positions = set()
    care_positions = set()
    water_positions = set()
    last_cash_day = day
    feed_units_remaining = 0

    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            position = (x, y)
            if tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                data = CROPS.get(crop, {})
                planted = int(tile.get("planted_day", day))
                profitable_days = []
                if data.get("ongoing"):
                    for work_day in range(day, 29):
                        next_day = work_day + 1
                        since_first = next_day - planted - data["first_yield_day"]
                        if since_first < 0 or since_first % data["interval"]:
                            continue
                        if since_first // data["interval"] + 1 <= data["max_yield"]:
                            profitable_days.append(work_day)
                elif day - planted <= data.get("max_yield_day", -1):
                    maturity_day = planted + data.get("max_yield_day", 99)
                    if maturity_day <= 28:
                        profitable_days.append(maturity_day)
                if profitable_days:
                    water_positions.add(position)
                    last_cash_day = max(last_cash_day, max(profitable_days) + 1)
            if "animal" in tile:
                animal = tile.get("animal")
                data = ANIMAL_ECONOMICS.get(animal)
                if not data:
                    continue
                placed = int(tile.get("placed_day", day))
                production_days = []
                for work_day in range(day, 29):
                    next_day = work_day + 1
                    since_first = next_day - placed - data["first_yield_day"]
                    if since_first >= 0 and since_first % data["interval"] == 0:
                        production_days.append(work_day)
                if production_days:
                    last_production = max(production_days)
                    feed_positions.add(position)
                    feed_units_remaining += last_production - day + 1
                    last_cash_day = max(last_cash_day, last_production + 1)
                    if any(production_day > day for production_day in production_days):
                        care_positions.add(position)

    shed = private.get("shed", {})
    inventories = private.get("inventories", [])
    market_prices = (obs.get("market") or {}).get("prices", {})
    projected_liquidation = 0.0
    for item in SELLABLE_PRODUCTS:
        units = int(shed.get(item, 0)) + sum(int(inv.get(item, 0)) for inv in inventories)
        projected_liquidation += units * float(market_prices.get(item, BASE_PRICES.get(item, 1)))

    forecast = _demand_forecast(obs, horizon_days=max(1, min(7, 28 - day)))
    hold_items = {
        item
        for item in PRODUCTS
        if item != "FERTILIZER"
        and day < 28
        and forecast.get(item, {}).get("visible_demand", 0) >= 6
        and forecast.get(item, {}).get("momentum", 0) >= 0.9
    }

    return {
        "remaining_turns": remaining_turns,
        "feed_positions": feed_positions,
        "care_positions": care_positions,
        "water_positions": water_positions,
        "feed_units_remaining": feed_units_remaining,
        "last_cash_day": min(29, last_cash_day),
        "projected_liquidation": projected_liquidation,
        "hold_items": hold_items,
        "liquidation_urgent": day >= 28 or remaining_turns <= 36,
    }


def _fertilizer_targets(obs, farm):
    """Plants where one fertilizer can still return more than its sale value."""
    day = int(obs.get("day", 0))
    prices = (obs.get("market") or {}).get("prices", {})
    fertilizer_price = float(prices.get("FERTILIZER", BASE_PRICES["FERTILIZER"]))
    targets = []
    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                continue
            if int(tile.get("fertilized_until_day", -1)) >= day:
                continue
            crop = tile.get("crop")
            data = CROPS.get(crop)
            if not data or crop in ("WHEAT", "CARROT"):
                continue
            planted = int(tile.get("planted_day", day))
            age = day - planted
            bonus_units = 0
            if data["ongoing"]:
                production_days = []
                for future_day in range(day, min(29, day + 3)):
                    since_first = future_day + 1 - planted - data["first_yield_day"]
                    if since_first >= 0 and since_first % data["interval"] == 0:
                        if since_first // data["interval"] + 1 <= data["max_yield"]:
                            production_days.append(future_day)
                bonus_units = len(production_days)
            else:
                window_start = (data["max_yield_day"] + 1) // 2
                days_left = max(0, min(data["max_yield_day"], age + 2) - max(age, window_start) + 1)
                room = max(0, data["max_yield"] - int(tile.get("yield_units", 0)))
                bonus_units = min(days_left, room)
            incremental_value = bonus_units * float(prices.get(crop, BASE_PRICES[crop]))
            if bonus_units and incremental_value >= fertilizer_price * 1.15:
                targets.append((-(incremental_value - fertilizer_price), (x, y), ["FERTILIZE"]))
    return sorted(targets, key=lambda task: (task[0], task[1]))


def _market_plan(obs, farm, private, opponent_signal, phase, terminal=None):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    inventories = private.get("inventories", [])
    orders = []

    animals = _count_tiles(farm, lambda tile: isinstance(tile, dict) and "animal" in tile)
    fertilizer_targets = _fertilizer_targets(obs, farm)
    wheat_plan = _dynamic_wheat_plan(obs, farm, private)
    labor_plan = _labor_plan(obs, farm, phase)

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
        orders.extend([["HIRE"] for _ in range(labor_plan["target"])])

    # Convert completed output continuously. Wheat remains feed until late
    # execution, when only the amount above the remaining feed reserve is sold.
    for item in PRODUCTS:
        safe_to_hold = terminal and day >= 22 and day < 28 and shed_load + incoming_harvest < 92
        if safe_to_hold and item in terminal.get("hold_items", set()):
            continue
        reserve = min(len(fertilizer_targets), 4) if item == "FERTILIZER" else 0
        quantity = max(0, int(shed.get(item, 0)) - reserve)
        if quantity:
            orders.append(["SELL", item, quantity])
    if phase["late_mode"] == "execute" or (terminal and terminal["liquidation_urgent"]):
        if terminal:
            feed_reserve = int(terminal["feed_units_remaining"])
        else:
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
    desired = {"WHEAT": wheat_plan["tile_target"]} if wheat_plan["tile_target"] else {}
    if phase["phase"] == "early":
        desired[opponent_signal.get("cash_crop", "MELON")] = 10
    elif phase["allow_recurring"]:
        desired.update(opponent_signal.get("recurring_targets", {opponent_signal["recurring_crop"]: 15}))
        if int(opponent_signal.get("animal_target", 4)) > len(PASTURE_CELLS):
            secondary = "TOMATO" if opponent_signal["recurring_crop"] == "STRAWBERRY" else "STRAWBERRY"
            desired[secondary] = max(0, desired.get(secondary, 0) - 1)

    purchase_window = hour <= 2 or hour in (6, 12, 18)
    if purchase_window:
        seed_budget = max(0, int(farm.get("money", 0)) - 80)
        for crop, target in desired.items():
            shortfall = max(0, target - planted.get(crop, 0) - int(seeds.get(crop, 0)))
            affordable = seed_budget // CROPS[crop]["seed"]
            quantity = min(shortfall, affordable)
            if quantity:
                orders.append(["BUY_SEED", crop, quantity])
                seed_budget -= quantity * CROPS[crop]["seed"]

    animal_choice = opponent_signal.get("animal", "COW")
    structure = "COOP" if animal_choice == "GOOSE" else "PASTURE"
    selected_animals = _count_tiles(
        farm, lambda tile: isinstance(tile, dict) and tile.get("animal") == animal_choice
    )
    empty_structures = _count_tiles(
        farm, lambda tile: isinstance(tile, dict) and tile.get("kind") == structure and "animal" not in tile
    )
    carried_animals = sum(int(inv.get(animal_choice, 0)) for inv in inventories)
    if phase["allow_animals"]:
        target = int(opponent_signal.get("animal_target", 4))
        animal_shortfall = max(0, target - selected_animals - int(shed.get(animal_choice, 0)) - carried_animals)
        animal_cost = ANIMAL_ECONOMICS[animal_choice]["cost"]
        affordable_animals = max(0, int(farm.get("money", 0)) - 120) // animal_cost
        animal_quantity = min(animal_shortfall, affordable_animals) if purchase_window else 0
        if animal_quantity:
            orders.append(["BUY_ANIMAL", animal_choice, animal_quantity])
        feed_on_hand = int(shed.get("WHEAT", 0)) + sum(int(inv.get("WHEAT", 0)) for inv in inventories)
        feed_target = max(8, wheat_plan["feed_reserve"], (animals + empty_structures) * 2)
        wheat_price = max(1, int((obs.get("market") or {}).get("prices", {}).get("WHEAT", BASE_PRICES["WHEAT"])))
        affordable_feed = max(0, int(farm.get("money", 0)) - 80) // wheat_price
        feed_quantity = min(max(0, feed_target - feed_on_hand), affordable_feed) if purchase_window else 0
        if feed_quantity:
            orders.append(["BUY_PRODUCT", "WHEAT", feed_quantity])

    return orders[:10]


def _operations_attention(obs, farm, private, opponent_signal, phase, terminal=None):
    """Build the deadline-ordered work queue for farmer and hands."""
    day = int(obs.get("day", 0))
    shed = private.get("shed", {})
    tasks = []
    animal_choice = opponent_signal.get("animal", "COW")
    animal_structure = "COOP" if animal_choice == "GOOSE" else "PASTURE"
    fertilize_targets = _fertilizer_targets(obs, farm)

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
                terminal_water = not terminal or terminal["remaining_turns"] > 24 or position in terminal["water_positions"]
                if not tile.get("watered_today", False) and terminal_water:
                    tasks.append((1, position, ["WATER"]))
            if "animal" in tile:
                terminal_feed = not terminal or terminal["remaining_turns"] > 24 or position in terminal["feed_positions"]
                terminal_care = not terminal or terminal["remaining_turns"] > 24 or position in terminal["care_positions"]
                if not tile.get("fed_today", False) and terminal_feed:
                    tasks.append((2, position, ["FEED"]))
                if tile.get("fertilizer_available", False) and day <= 28:
                    tasks.append((3, position, ["COLLECT_FERTILIZER"]))
                if not tile.get("cared_today", False) and terminal_care:
                    tasks.append((4, position, ["CARE"]))
                if int(tile.get("yield_units", 0)) > 0:
                    tasks.append((0, position, ["HARVEST"]))

    if phase["allow_animals"]:
        pasture_cells = PASTURE_CELLS
        if int(opponent_signal.get("animal_target", 4)) > len(PASTURE_CELLS):
            pasture_cells += ADAPTIVE_PASTURE_CELL
        for position in pasture_cells:
            planned_tile = _tile(farm, position)
            if planned_tile is None:
                tasks.append((5, position, ["BUILD_COOP" if animal_structure == "COOP" else "BUILD_PASTURE"]))
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
                if not (
                    position in ADAPTIVE_PASTURE_CELL
                    and int(opponent_signal.get("animal_target", 4)) > len(PASTURE_CELLS)
                )
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
        and (
            not terminal
            or terminal["remaining_turns"] > 24
            or (x, y) in terminal["feed_positions"]
        )
    ]
    empty_pastures = [
        (x, y)
        for y, row in enumerate(farm["tiles"])
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and tile.get("kind") == animal_structure and "animal" not in tile
    ]
    if animal_tiles and shed.get("WHEAT", 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((1, position, ["PICKUP", "WHEAT", min(len(animal_tiles), shed["WHEAT"])]))
    if fertilize_targets and shed.get("FERTILIZER", 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((2, position, ["PICKUP", "FERTILIZER", 1]))
    if day <= 20 and empty_pastures and shed.get(animal_choice, 0) > 0:
        for position in SHED_ACCESS:
            tasks.append((0, position, ["PICKUP", animal_choice, 1]))

    return tasks


def _assign_tasks(positions, available, tasks, hour):
    """Globally assign today's work with priority, deadline, and travel costs."""
    workers = sorted(available)
    if not workers or not tasks:
        return []
    # Only today's best reachable work enters the combinatorial assignment.
    # The complete queue can grow with every plant, animal, pickup point, and
    # weed; bounding it prevents an unusual board from consuming the 1s action
    # budget while preserving several alternatives per worker.
    ranked_tasks = sorted(
        enumerate(tasks),
        key=lambda item: (
            item[1][0],
            min(_distance(positions[worker], item[1][1]) for worker in workers),
            item[1][1],
            item[0],
        ),
    )[: max(18, len(workers) * 3)]
    # Dynamic programming is tiny here: at most eight workers, so 2^8 states.
    # It avoids the old first-worker-first choice that stranded another worker
    # with a long route to an equally urgent task.
    dp = {0: (0, ())}
    for task_index, (priority, target, operation) in ranked_tasks:
        next_dp = dict(dp)
        for mask, (total_cost, assignments) in dp.items():
            for local_index, worker in enumerate(workers):
                bit = 1 << local_index
                if mask & bit:
                    continue
                distance = _distance(positions[worker], target)
                today_deadline = priority <= 4 or operation[0] in ("HARVEST", "WATER", "FEED", "CARE")
                lateness = max(0, distance + 1 - max(1, 24 - int(hour))) if today_deadline else 0
                cost = priority * 10000 + lateness * 1800 + distance * 50 + task_index
                new_mask = mask | bit
                candidate = (total_cost + cost, assignments + ((worker, task_index),))
                current = next_dp.get(new_mask)
                if current is None or candidate[0] < current[0]:
                    next_dp[new_mask] = candidate
        dp = next_dp
    _, best = min(
        dp.items(),
        key=lambda item: (-bin(item[0]).count("1"), item[1][0], item[0]),
    )
    return list(best[1])


def _emit_day_trace(obs, player, opponent_signal, phase, result):
    """Write one compact, replay-friendly decision record per game day."""
    if "remainingOverageTime" not in obs:
        return
    day = int(obs.get("day", 0))
    memory = _episode_memory(obs, player)
    if day in memory["trace_days"]:
        return
    memory["trace_days"].add(day)
    probabilities = opponent_signal.get("probabilities", {})
    top_beliefs = sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))[:3]
    payload = {
        "day": day,
        "phase": phase["phase"],
        "late": phase.get("late_mode"),
        "bank": int(obs.get("farms", [])[player].get("money", 0)),
        "own_value": opponent_signal.get("own_terminal_value", 0),
        "opp_value": opponent_signal.get("opponent_terminal_proxy", 0),
        "asset_gap": opponent_signal.get("asset_gap", 0),
        "productive_gap": opponent_signal.get("productive_gap", 0),
        "scale_gap": opponent_signal.get("scale_gap", 0),
        "animal_gap": opponent_signal.get("animal_gap", 0),
        "threat": opponent_signal.get("asset_threat", 0),
        "belief": top_beliefs,
        "prediction_error": opponent_signal.get("prediction_error", 0),
        "prediction_break": opponent_signal.get("prediction_break", False),
        "capital": opponent_signal.get("capital_mode", "hold"),
        "crop": [opponent_signal.get("cash_crop"), opponent_signal.get("recurring_crop")],
        "animal": [opponent_signal.get("animal"), opponent_signal.get("animal_target", 0)],
        "attention": opponent_signal.get("attention_weights", {}),
        "market_orders": len(result.get("market", [])),
    }
    print("KAGG_TRACE " + json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _policy(obs, persona=None):
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
    if persona:
        phase = dict(phase)
        recurring_start = int(persona.get("recurring_start", 5))
        phase["allow_animals"] = day <= int(persona.get("animal_end", 18))
        if recurring_start <= day <= int(persona.get("recurring_end", 18)):
            phase["phase"] = "middle"
            phase["allow_recurring"] = True
        opponent_signal = {
            **opponent_signal,
            "cash_crop": persona.get("cash_crop", "MELON"),
            "recurring_crop": persona.get("recurring_crop", "STRAWBERRY"),
            "recurring_targets": dict(persona.get("recurring_targets", {"STRAWBERRY": 12, "TOMATO": 3})),
            "animal": persona.get("animal", "COW"),
            "animal_target": int(persona.get("animal_target", 4)),
            "capital_mode": persona.get("capital_mode", "compound"),
        }
    memory = _episode_memory(obs, player)
    if int(memory.get("route_day", -1)) != day:
        memory["route_day"] = day
        memory["routes"] = {}
    terminal = _reverse_terminal_plan(obs, farm, private)
    positions = [tuple(farm["farmer"])] + [tuple(position) for position in farm.get("hands", [])]
    inventories = list(private.get("inventories", []))
    while len(inventories) < len(positions):
        inventories.append({})

    actions = [["PASS"] for _ in positions]
    available = set(range(len(positions)))
    tasks = _operations_attention(obs, farm, private, opponent_signal, phase, terminal)

    # Carried resources take precedence because they unlock care and placement.
    reserved_targets = set()
    for index, (position, inventory) in enumerate(zip(positions, inventories)):
        if index not in available:
            continue
        carried_animal = next((name for name in ANIMAL_ECONOMICS if inventory.get(name, 0) > 0), None)
        if carried_animal:
            structure = "COOP" if carried_animal == "GOOSE" else "PASTURE"
            targets = [
                (2, (x, y), ["PLACE", carried_animal])
                for y, row in enumerate(farm["tiles"])
                for x, tile in enumerate(row)
                if isinstance(tile, dict)
                and tile.get("kind") == structure
                and "animal" not in tile
                and (x, y) not in reserved_targets
            ]
            if targets:
                _, target, operation = min(targets, key=lambda task: (_distance(position, task[1]), task[1]))
                actions[index] = operation if position == target else _step_toward(position, target)
                available.discard(index)
                reserved_targets.add(target)
        elif inventory.get("FERTILIZER", 0) > 0:
            targets = [
                task for task in _fertilizer_targets(obs, farm)
                if task[1] not in reserved_targets
            ]
            if targets:
                _, target, operation = min(targets, key=lambda task: (task[0], _distance(position, task[1]), task[1]))
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
    if phase["late_mode"] == "execute" or terminal["liquidation_urgent"]:
        for index, (position, inventory) in enumerate(zip(positions, inventories)):
            if index not in available:
                continue
            has_output = any(int(inventory.get(item, 0)) > 0 for item in SELLABLE_PRODUCTS)
            route_cost = _distance(position, _nearest_shed(position)) + 1
            if has_output and terminal["remaining_turns"] <= route_cost + 24:
                target = _nearest_shed(position)
                actions[index] = ["DROP"] if position == target else _step_toward(position, target)
                available.discard(index)

    # Keep a worker on the same route while its target remains valid. Urgent
    # work can still preempt a route that is more than one priority tier lower.
    next_routes = {}
    task_lookup = {
        (tuple(target), tuple(operation)): (task_index, priority, target, operation)
        for task_index, (priority, target, operation) in enumerate(tasks)
    }
    minimum_priority = min((task[0] for task in tasks), default=99)
    for raw_index, route in (memory.get("routes") or {}).items():
        index = int(raw_index)
        if index not in available:
            continue
        key = (tuple(route.get("target", ())), tuple(route.get("operation", ())))
        matched = task_lookup.get(key)
        if not matched:
            continue
        _, priority, target, operation = matched
        if priority > minimum_priority + 1 or target in reserved_targets:
            continue
        actions[index] = operation if positions[index] == target else _step_toward(positions[index], target)
        available.discard(index)
        reserved_targets.add(target)
        if positions[index] != target:
            next_routes[index] = {"target": target, "operation": operation, "priority": priority}

    # Assign the remaining workers together so one locally cheap choice cannot
    # force another worker into a long, deadline-missing route.
    assignable_tasks = [task for task in tasks if task[1] not in reserved_targets]
    for index, task_index in _assign_tasks(positions, available, assignable_tasks, hour):
        priority, target, operation = assignable_tasks[task_index]
        actions[index] = operation if positions[index] == target else _step_toward(positions[index], target)
        available.discard(index)
        if positions[index] != target:
            next_routes[index] = {"target": target, "operation": operation, "priority": priority}
    memory["routes"] = next_routes

    # Late in the day, idle carriers return output to the shed for sale.
    if int(obs.get("hour", 0)) >= 20:
        for index in available:
            inventory = inventories[index]
            if not inventory or inventory.get("WHEAT", 0) or inventory.get("COW", 0):
                continue
            target = _nearest_shed(positions[index])
            actions[index] = ["DROP"] if positions[index] == target else _step_toward(positions[index], target)

    result = {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": _market_plan(obs, farm, private, opponent_signal, phase, terminal),
    }
    _emit_day_trace(obs, player, opponent_signal, phase, result)
    return result


def agent(obs):
    """Kaggle entry point with a valid no-op fallback for unexpected states."""
    try:
        return _policy(obs)
    except Exception as exc:
        print(
            "KAGG_ERROR "
            + json.dumps(
                {"type": type(exc).__name__, "message": str(exc)[:240]},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return {"farmer": ["PASS"], "hands": [], "market": []}


balanced_tempo_agent = agent
