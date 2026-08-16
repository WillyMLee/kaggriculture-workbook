"""Local opponents inferred from public rank-100–200 replay commitments.

These are testing personas, not reconstructions of private competitor code.
They preserve the sampled decision-tree shape while varying the dominant
livestock and conversion emphasis to avoid training against one clone.
"""

from __future__ import annotations

from agents.balanced_tempo import _policy


STRAWBERRY_COW_FERTILIZER = {
    "cash_crop": "MELON",
    "recurring_start": 5,
    "recurring_end": 18,
    "recurring_crop": "STRAWBERRY",
    "recurring_targets": {"STRAWBERRY": 12, "TOMATO": 3},
    "animal": "COW",
    "animal_target": 4,
    "animal_end": 18,
    "capital_mode": "compound",
}

STRAWBERRY_SHEEP_VOLUME = {
    "cash_crop": "MELON",
    "recurring_start": 6,
    "recurring_end": 18,
    "recurring_crop": "STRAWBERRY",
    "recurring_targets": {"STRAWBERRY": 10, "TOMATO": 5},
    "animal": "SHEEP",
    "animal_target": 4,
    "animal_end": 17,
    "capital_mode": "compound",
}

STRAWBERRY_MIXED_CONVERSION = {
    "cash_crop": "MELON",
    "recurring_start": 5,
    "recurring_end": 17,
    "recurring_crop": "STRAWBERRY",
    "recurring_targets": {"STRAWBERRY": 9, "TOMATO": 6},
    "animal": "COW",
    "animal_target": 5,
    "animal_end": 16,
    "capital_mode": "hold",
}


def strawberry_cow_fertilizer(obs):
    return _policy(obs, STRAWBERRY_COW_FERTILIZER)


def strawberry_sheep_volume(obs):
    return _policy(obs, STRAWBERRY_SHEEP_VOLUME)


def strawberry_mixed_conversion(obs):
    return _policy(obs, STRAWBERRY_MIXED_CONVERSION)


PERSONAS = {
    "strawberry-cow-fertilizer": strawberry_cow_fertilizer,
    "strawberry-sheep-volume": strawberry_sheep_volume,
    "strawberry-mixed-conversion": strawberry_mixed_conversion,
}
