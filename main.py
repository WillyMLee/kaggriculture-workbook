"""Kaggle submission entry point for the first interpretable baseline."""

from agents.balanced_tempo import agent as _balanced_tempo_agent


def agent(obs):
    """Return a valid action object even if the baseline encounters an unexpected state."""
    try:
        return _balanced_tempo_agent(obs)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}
