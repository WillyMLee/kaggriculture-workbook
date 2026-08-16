"""Regression checks for v0.7 temporal inference on the real PQ_Marz loss."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents import balanced_tempo as agent  # noqa: E402


def main():
    fixture = PROJECT_ROOT / "results" / "kaggle_v0_6_1_pq_marz_regression.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    checkpoints = payload["episodes"][0]["checkpoints"]
    agent._EPISODE_MEMORY.clear()
    signals = {}
    for checkpoint in checkpoints:
        obs = checkpoint["observation"]
        signal = agent._opponent_attention(obs, int(obs["player"]))
        signals[int(checkpoint["day"])] = signal
        assert abs(sum(signal["probabilities"].values()) - 1.0) < 0.002
        assert "carrot-volume" in signal["probabilities"]
        assert "wheat-volume" in signal["probabilities"]

    day15 = signals[15]
    day21 = signals[21]
    assert signals[12]["animal_target"] == 5, signals[12]
    assert signals[12]["capital_mode"] == "compound", signals[12]
    assert day15["scale_gap"] >= 30, day15
    assert day15["asset_threat"] >= 0.60, day15
    assert day15["capital_mode"] == "compound", day15
    assert day21["animal_gap"] >= 20, day21
    assert day21["asset_threat"] >= 0.55, day21
    assert day21["archetype"] == "livestock-compound", day21
    day21_obs = next(row["observation"] for row in checkpoints if int(row["day"]) == 21)
    assert day21["own_terminal_value"] > day21_obs["farms"][1]["money"]

    # Day zero starts a new episode and must discard the previous posterior.
    agent._EPISODE_MEMORY[1]["history"].append({"sentinel": True})
    day0_obs = checkpoints[0]["observation"]
    agent._opponent_attention(day0_obs, int(day0_obs["player"]))
    assert not any(row.get("sentinel") for row in agent._EPISODE_MEMORY[1]["history"])

    compact = {
        day: {
            "archetype": signal["archetype"],
            "confidence": signal["confidence"],
            "threat": signal["asset_threat"],
            "scale_gap": signal["scale_gap"],
            "animal_gap": signal["animal_gap"],
            "capital": signal["capital_mode"],
        }
        for day, signal in signals.items()
    }
    print(json.dumps({"status": "passed", "signals": compact}, indent=2))


if __name__ == "__main__":
    main()
