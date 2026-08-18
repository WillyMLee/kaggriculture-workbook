"""Serve the Fieldbook with an exact human-vs-agent Kaggriculture arena.

The server binds to localhost, steps the vendored official environment, and
persists human decisions as transition-complete offline-RL episodes.  It never
mutates the frozen opponent during a match or writes across sessions.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import secrets
import shutil
import sys
import tempfile
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggriculture_env import ENV_NAME, load_environment  # noqa: E402
from scripts.run_training_arena import feature_snapshot, summarize_action  # noqa: E402
from scripts.validate_artifact import load_artifact_agent  # noqa: E402


UNIT_OPS = {
    "NORTH", "SOUTH", "EAST", "WEST", "PASS", "DROP", "PICKUP", "PLACE",
    "PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG", "BUILD_COOP",
    "BUILD_PASTURE", "FEED", "COLLECT_FERTILIZER", "CARE",
}
MARKET_OPS = {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}
ITEM_UNIT_OPS = {"PICKUP", "PLACE"}
QUANTITY_UNIT_OPS = {"PICKUP", "PLACE"}
MARKET_QUANTITY_OPS = {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"}
INTENTS = {"lean", "dense", "land", "town", "repair", "close", "explore", "routine"}


def _plain(value):
    """Detach Kaggle Struct/list state into ordinary JSON-compatible values."""
    return json.loads(json.dumps(value))


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value, limit):
    return str(value or "").strip()[:limit]


def _normalize_unit_action(value):
    if not isinstance(value, list) or not value:
        return ["PASS"]
    op = str(value[0]).upper()
    if op not in UNIT_OPS:
        raise ValueError(f"Unknown unit action: {op}")
    if op == "PLANT":
        if len(value) < 2:
            raise ValueError("PLANT requires a crop")
        return [op, str(value[1]).upper()]
    if op in ITEM_UNIT_OPS:
        if len(value) < 2:
            raise ValueError(f"{op} requires an item")
        action = [op, str(value[1]).upper()]
        if op in QUANTITY_UNIT_OPS and len(value) >= 3:
            quantity = max(1, min(100, int(value[2])))
            action.append(quantity)
        return action
    return [op]


def _normalize_market_order(value):
    if not isinstance(value, list) or not value:
        raise ValueError("Each market order must be a non-empty list")
    op = str(value[0]).upper()
    if op not in MARKET_OPS:
        raise ValueError(f"Unknown market order: {op}")
    if op not in MARKET_QUANTITY_OPS:
        return [op]
    if len(value) < 3:
        raise ValueError(f"{op} requires an item and quantity")
    return [op, str(value[1]).upper(), max(1, min(1000, int(value[2])))]


def normalize_action(action, hand_count):
    if not isinstance(action, dict):
        raise ValueError("Action must be an object")
    raw_hands = action.get("hands") or []
    if not isinstance(raw_hands, list):
        raise ValueError("hands must be a list")
    hands = [_normalize_unit_action(value) for value in raw_hands[:hand_count]]
    hands.extend([["PASS"] for _ in range(hand_count - len(hands))])
    raw_market = action.get("market") or []
    if not isinstance(raw_market, list):
        raise ValueError("market must be a list")
    return {
        "farmer": _normalize_unit_action(action.get("farmer") or ["PASS"]),
        "hands": hands,
        "market": [_normalize_market_order(value) for value in raw_market[:10]],
    }


def normalize_feedback(feedback):
    if not isinstance(feedback, dict):
        return {}
    intent = _safe_text(feedback.get("intent"), 24).lower()
    if intent and intent not in INTENTS:
        intent = "explore"
    try:
        confidence = max(1, min(5, int(feedback.get("confidence", 3))))
    except (TypeError, ValueError):
        confidence = 3
    return {
        "intent": intent or "routine",
        "confidence": confidence,
        "rationale": _safe_text(feedback.get("rationale"), 500),
        "turning_point": bool(feedback.get("turning_point", False)),
    }


def _inventory_delta(before, after):
    keys = set(before or {}) | set(after or {})
    return {
        key: int((after or {}).get(key, 0)) - int((before or {}).get(key, 0))
        for key in sorted(keys)
        if int((after or {}).get(key, 0)) != int((before or {}).get(key, 0))
    }


def _call_agent(agent, observation):
    """Capture the frozen agent's daily trace instead of flooding the server console."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        action = agent(observation)
    trace = None
    for line in output.getvalue().splitlines():
        if line.startswith("KAGG_TRACE "):
            try:
                trace = json.loads(line[len("KAGG_TRACE "):])
            except json.JSONDecodeError:
                continue
    return action, trace


class ArenaManager:
    def __init__(self, artifact, output_dir):
        self.artifact = Path(artifact).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.kaggle, self.environment_module = load_environment()
        self.sessions = {}
        self.lock = threading.RLock()
        self.agent_root = Path(tempfile.mkdtemp(prefix="kaggriculture-human-arena-"))

    def close(self):
        shutil.rmtree(self.agent_root, ignore_errors=True)

    def _load_agent(self, session_id, role):
        destination = self.agent_root / session_id / role
        destination.mkdir(parents=True, exist_ok=True)
        return load_artifact_agent(self.artifact, destination)

    def new_session(self, seed, human_seat=0):
        human_seat = int(human_seat)
        if human_seat not in (0, 1):
            raise ValueError("human_seat must be 0 or 1")
        seed = int(seed)
        session_id = f"human-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        env = self.kaggle.make(ENV_NAME, configuration={"seed": seed}, debug=False)
        session = {
            "id": session_id,
            "seed": seed,
            "human_seat": human_seat,
            "agent_seat": 1 - human_seat,
            "created_at": _utc_now(),
            "env": env,
            "agent": self._load_agent(session_id, "opponent"),
            "coach": self._load_agent(session_id, "coach"),
            "records": [],
            "annotations": [],
            "saved": False,
            "opponent_last_action": None,
            "human_last_action": None,
        }
        self.sessions[session_id] = session
        self._prepare_actions(session)
        self._write_checkpoint(session, complete=False)
        return self.serialize(session)

    def get(self, session_id):
        try:
            return self.sessions[str(session_id)]
        except KeyError as error:
            raise KeyError("Unknown or expired arena session") from error

    def _observation(self, session, seat):
        return _plain(session["env"].state[seat]["observation"])

    def _prepare_actions(self, session):
        if session["env"].done:
            session["agent_action"] = None
            session["coach_action"] = None
            session["agent_trace"] = None
            session["coach_trace"] = None
            return
        agent_obs = self._observation(session, session["agent_seat"])
        coach_obs = self._observation(session, session["human_seat"])
        agent_action, agent_trace = _call_agent(session["agent"], agent_obs)
        coach_action, coach_trace = _call_agent(session["coach"], coach_obs)
        session["agent_action"] = normalize_action(
            agent_action, len(agent_obs["farms"][session["agent_seat"]].get("hands", []))
        )
        session["coach_action"] = normalize_action(
            coach_action, len(coach_obs["farms"][session["human_seat"]].get("hands", []))
        )
        session["agent_trace"] = agent_trace
        session["coach_trace"] = coach_trace

    def _rules(self, env):
        module = self.environment_module
        return {
            "crops": module.CROPS,
            "animals": module.ANIMALS,
            "products": module.PRODUCTS,
            "shops": module.SHOPS,
            "land_prices": module.LAND_PRICES,
            "turns_per_day": int(env.configuration.turnsPerDay),
            "episode_steps": int(env.configuration.episodeSteps),
            "shed_capacity": int(env.configuration.shedCapacity),
            "max_market_orders": int(env.configuration.maxMarketOrdersPerTurn),
        }

    def _insights(self, observation, seat):
        farm = observation["farms"][seat]
        private = observation.get("private") or {}
        shed = private.get("shed") or {}
        prices = (observation.get("market") or {}).get("prices") or {}
        animals = self.environment_module.ANIMALS
        product_value = sum(int(shed.get(item, 0)) * int(prices.get(item, 0)) for item in prices)
        animal_backlog = sum(int(shed.get(item, 0)) for item in animals)
        empty_pastures = 0
        empty_coops = 0
        productive_tiles = 0
        weeds = 0
        harvest_ready = 0
        for row in farm.get("tiles", []):
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                kind = tile.get("kind")
                if kind == "WEED":
                    weeds += 1
                if kind == "PLANT" or tile.get("animal"):
                    productive_tiles += 1
                if tile.get("yield_units", 0) > 0:
                    harvest_ready += 1
                if kind == "PASTURE" and not tile.get("animal"):
                    empty_pastures += 1
                if kind == "COOP" and not tile.get("animal"):
                    empty_coops += 1
        extra_land = max(0, len(farm.get("unlocked_quadrants", [])) - 1)
        next_land = (
            self.environment_module.LAND_PRICES[extra_land]
            if extra_land < len(self.environment_module.LAND_PRICES)
            else None
        )
        hires_today = int(farm.get("hires_today", 0))
        a, b = 1, 1
        for _ in range(hires_today):
            a, b = b, a + b
        shop_counts = Counter((observation.get("town") or {}).get("unlocked_shops") or [])
        town_demand = Counter()
        for shop, count in shop_counts.items():
            for item in self.environment_module.SHOPS.get(shop, []):
                town_demand[item] += count
        return {
            "shed_load": int(sum(int(value) for value in shed.values())),
            "inventory_market_value": int(product_value),
            "animal_backlog": animal_backlog,
            "empty_pastures": empty_pastures,
            "empty_coops": empty_coops,
            "productive_tiles": productive_tiles,
            "weeds": weeds,
            "harvest_ready": harvest_ready,
            "next_land_price": next_land,
            "next_hire_cost": a,
            "town_demand": dict(sorted(town_demand.items())),
        }

    def _turn_effect(self, before, after, seat):
        before_farm = before["farms"][seat]
        after_farm = after["farms"][seat]
        before_private = before.get("private") or {}
        after_private = after.get("private") or {}
        before_pos = [before_farm.get("farmer"), *(before_farm.get("hands") or [])]
        after_pos = [after_farm.get("farmer"), *(after_farm.get("hands") or [])]
        shed_delta = _inventory_delta(before_private.get("shed"), after_private.get("shed"))
        seed_delta = _inventory_delta(before_private.get("seeds"), after_private.get("seeds"))
        bank_delta = round(float(after_farm.get("money", 0)) - float(before_farm.get("money", 0)), 2)
        changed = bool(
            bank_delta or shed_delta or seed_delta or before_pos != after_pos
            or before_farm.get("tiles") != after_farm.get("tiles")
            or len(before_farm.get("hands", [])) != len(after_farm.get("hands", []))
        )
        return {
            "bank_delta": bank_delta,
            "shed_delta": shed_delta,
            "seed_delta": seed_delta,
            "units_moved": before_pos != after_pos,
            "visible_change": changed,
        }

    def step(self, session_id, action=None, use_coach=False, feedback=None):
        with self.lock:
            session = self.get(session_id)
            env = session["env"]
            if env.done:
                raise ValueError("This episode is already complete")
            human_seat = session["human_seat"]
            before = self._observation(session, human_seat)
            hand_count = len(before["farms"][human_seat].get("hands", []))
            coach_action = _plain(session["coach_action"])
            if use_coach:
                human_action = coach_action
            else:
                human_action = normalize_action(action or {}, hand_count)
            opponent_action = _plain(session["agent_action"])
            actions = [None, None]
            actions[human_seat] = human_action
            actions[session["agent_seat"]] = opponent_action
            env.step(actions)
            after = self._observation(session, human_seat)
            done = bool(env.done)
            human_bank = float(after["farms"][human_seat]["money"])
            opponent_bank = float(after["farms"][session["agent_seat"]]["money"])
            margin = human_bank - opponent_bank
            state = feature_snapshot(before)
            next_state = None if done else feature_snapshot(after)
            action_summary = summarize_action(human_action)
            coach_summary = summarize_action(coach_action)
            record = {
                "episode_id": session["id"],
                "decision_index": len(session["records"]),
                "arena_seed": "human-arena",
                "game_seed": session["seed"],
                "seat": human_seat,
                "style": "human",
                "style_family": "human-guided",
                "style_weight": 1.0,
                "base_game_priors": {},
                "state": state,
                "action": human_action,
                "action_summary": action_summary,
                "option_label": action_summary["branch"],
                "coach_action": coach_action,
                "coach_action_summary": coach_summary,
                "coach_disagreement": action_summary["branch"] != coach_summary["branch"],
                "used_coach": bool(use_coach),
                "human_feedback": normalize_feedback(feedback),
                "next_state": next_state,
                "done": done,
                "immediate_bank_delta": round(human_bank - float(before["farms"][human_seat]["money"]), 2),
                "current_margin": round(margin, 2),
                "terminal_candidate_reward": human_bank if done else None,
                "terminal_opponent_reward": opponent_bank if done else None,
                "terminal_margin": round(margin, 2) if done else None,
                "return_to_go": round(margin, 2) if done else None,
                "win": margin > 0 if done else None,
                "training_weight": round(min(4.0, 1.0 + abs(margin) / 20000.0), 4) if done else 1.0,
                "effect": self._turn_effect(before, after, human_seat),
            }
            session["records"].append(record)
            session["human_last_action"] = human_action
            session["opponent_last_action"] = opponent_action
            if record["human_feedback"].get("rationale") or record["human_feedback"].get("turning_point"):
                session["annotations"].append({
                    "step": int(before.get("step", 0)),
                    "day": int(before.get("day", 0)),
                    "hour": int(before.get("hour", 0)),
                    **record["human_feedback"],
                })
            self._prepare_actions(session)
            self._write_checkpoint(session, complete=done)
            return self.serialize(session)

    def autoplay_next_day(self, session_id, feedback=None):
        session = self.get(session_id)
        if session["env"].done:
            return self.serialize(session)
        start = self._observation(session, session["human_seat"])
        start_day = int(start.get("day", 0))
        turns = 0
        first_feedback = feedback
        while turns < 24 and not session["env"].done:
            self.step(session_id, use_coach=True, feedback=first_feedback)
            first_feedback = None
            turns += 1
            current = self._observation(session, session["human_seat"])
            if int(current.get("day", 0)) > start_day and int(current.get("hour", 0)) == 0:
                break
        response = self.serialize(session)
        response["autoplayed_turns"] = turns
        return response

    def annotate(self, session_id, feedback):
        with self.lock:
            session = self.get(session_id)
            observation = self._observation(session, session["human_seat"])
            annotation = {
                "step": int(observation.get("step", 0)),
                "day": int(observation.get("day", 0)),
                "hour": int(observation.get("hour", 0)),
                **normalize_feedback(feedback),
            }
            session["annotations"].append(annotation)
            self._write_checkpoint(session, complete=session["env"].done)
            return {"saved": True, "annotation": annotation, "count": len(session["annotations"])}

    def _episode_summary(self, session):
        observation = self._observation(session, session["human_seat"])
        human_seat = session["human_seat"]
        agent_seat = session["agent_seat"]
        human_bank = float(observation["farms"][human_seat]["money"])
        agent_bank = float(observation["farms"][agent_seat]["money"])
        margin = human_bank - agent_bank
        branch_counts = Counter(row["option_label"] for row in session["records"])
        coach_branches = Counter(row["coach_action_summary"]["branch"] for row in session["records"])
        disagreements = sum(row["coach_disagreement"] for row in session["records"])
        insights = self._insights(observation, human_seat)
        feedback = []
        if insights["animal_backlog"]:
            feedback.append(f"{insights['animal_backlog']} purchased animal(s) remain in the shed; reduce purchase-to-deployment lag.")
        if session["env"].done and insights["inventory_market_value"]:
            feedback.append(f"Approximately {insights['inventory_market_value']:,} coins of priced products remain unsold at the terminal state.")
        if insights["weeds"] >= 4:
            feedback.append(f"{insights['weeds']} weeds are occupying owned capacity.")
        if disagreements and margin > 0:
            feedback.append("Human deviations produced a positive current margin; prioritize these junctions for counterfactual replay.")
        elif disagreements and margin < 0:
            feedback.append("Review the first high-confidence deviation before adding it to the learned policy.")
        if not feedback:
            feedback.append("No simple execution warning fired; compare annotated junctions and terminal margin in offline replay.")
        return {
            "complete": bool(session["env"].done),
            "turns": len(session["records"]),
            "human_bank": round(human_bank, 2),
            "agent_bank": round(agent_bank, 2),
            "margin": round(margin, 2),
            "result": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
            "human_branch_counts": dict(branch_counts),
            "coach_branch_counts": dict(coach_branches),
            "coach_disagreements": disagreements,
            "manual_turns": sum(not row["used_coach"] for row in session["records"]),
            "annotations": len(session["annotations"]),
            "feedback": feedback,
        }

    def _training_rows(self, session):
        summary = self._episode_summary(session)
        margin = float(summary["margin"])
        human_bank = float(summary["human_bank"])
        agent_bank = float(summary["agent_bank"])
        rows = []
        for source in session["records"]:
            row = dict(source)
            row["terminal_candidate_reward"] = human_bank
            row["terminal_opponent_reward"] = agent_bank
            row["terminal_margin"] = margin
            row["return_to_go"] = margin
            row["win"] = margin > 0
            row["training_weight"] = round(min(5.0, 1.25 + abs(margin) / 15000.0 + (0.5 if row["coach_disagreement"] else 0.0)), 4)
            rows.append(row)
        return rows

    def _write_checkpoint(self, session, complete):
        summary = self._episode_summary(session)
        payload = {
            "schema_version": "human-arena-v1",
            "session_id": session["id"],
            "created_at": session["created_at"],
            "updated_at": _utc_now(),
            "artifact": self.artifact.name,
            "seed": session["seed"],
            "human_seat": session["human_seat"],
            "complete": bool(complete),
            "summary": summary,
            "annotations": session["annotations"],
            "records": session["records"],
        }
        destination = self.output_dir / f"{session['id']}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        if complete:
            rows = self._training_rows(session)
            trajectory = self.output_dir / f"{session['id']}.training.jsonl"
            trajectory_temp = trajectory.with_suffix(".jsonl.tmp")
            trajectory_temp.write_text(
                "".join(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            trajectory_temp.replace(trajectory)
        session["saved"] = True
        return destination

    def save(self, session_id):
        with self.lock:
            session = self.get(session_id)
            path = self._write_checkpoint(session, complete=session["env"].done)
            return {
                "saved": True,
                "complete": bool(session["env"].done),
                "path": str(path),
                "training_ready": bool(session["env"].done),
                "summary": self._episode_summary(session),
            }

    def serialize(self, session):
        observation = self._observation(session, session["human_seat"])
        human_seat = session["human_seat"]
        agent_seat = session["agent_seat"]
        human_bank = float(observation["farms"][human_seat]["money"])
        agent_bank = float(observation["farms"][agent_seat]["money"])
        recent = []
        for row in session["records"][-18:]:
            recent.append({
                "step": row["state"]["day"] * 24 + row["state"]["hour"],
                "day": row["state"]["day"],
                "hour": row["state"]["hour"],
                "branch": row["option_label"],
                "coach_branch": row["coach_action_summary"]["branch"],
                "used_coach": row["used_coach"],
                "disagreement": row["coach_disagreement"],
                "effect": row["effect"],
                "margin": row["current_margin"],
            })
        return {
            "session_id": session["id"],
            "seed": session["seed"],
            "human_seat": human_seat,
            "agent_seat": agent_seat,
            "artifact": self.artifact.name,
            "done": bool(session["env"].done),
            "status": [str(state["status"]) for state in session["env"].state],
            "observation": observation,
            "coach_suggestion": _plain(session.get("coach_action")),
            "coach_trace": _plain(session.get("coach_trace")),
            "opponent_last_action": _plain(session.get("opponent_last_action")),
            "human_last_action": _plain(session.get("human_last_action")),
            "bank": {
                "human": round(human_bank, 2),
                "agent": round(agent_bank, 2),
                "margin": round(human_bank - agent_bank, 2),
            },
            "insights": self._insights(observation, human_seat),
            "rules": self._rules(session["env"]),
            "recent_turns": recent,
            "annotations": session["annotations"][-20:],
            "summary": self._episode_summary(session),
        }


class HumanArenaHandler(SimpleHTTPRequestHandler):
    manager = None
    static_dir = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def _json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            length = min(2_000_000, int(self.headers.get("Content-Length", "0")))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/human-arena/health":
            return self._json(200, {
                "ok": True,
                "artifact": self.manager.artifact.name,
                "sessions": len(self.manager.sessions),
                "training_boundary": "Human episodes are saved for offline learning; the live opponent never updates during play.",
            })
        if parsed.path == "/api/human-arena/session":
            try:
                session_id = parse_qs(parsed.query).get("id", [""])[0]
                return self._json(200, self.manager.serialize(self.manager.get(session_id)))
            except KeyError as error:
                return self._json(404, {"error": str(error)})
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/human-arena/"):
            return self._json(404, {"error": "Unknown endpoint"})
        try:
            body = self._body()
            if parsed.path == "/api/human-arena/new":
                payload = self.manager.new_session(body.get("seed", 20260818), body.get("human_seat", 0))
            elif parsed.path == "/api/human-arena/step":
                payload = self.manager.step(
                    body.get("session_id"), body.get("action"), bool(body.get("use_coach", False)), body.get("feedback"),
                )
            elif parsed.path == "/api/human-arena/autoplay":
                payload = self.manager.autoplay_next_day(body.get("session_id"), body.get("feedback"))
            elif parsed.path == "/api/human-arena/annotate":
                payload = self.manager.annotate(body.get("session_id"), body.get("feedback"))
            elif parsed.path == "/api/human-arena/save":
                payload = self.manager.save(body.get("session_id"))
            else:
                return self._json(404, {"error": "Unknown endpoint"})
            return self._json(200, payload)
        except KeyError as error:
            return self._json(404, {"error": str(error)})
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            return self._json(400, {"error": str(error)})
        except Exception as error:  # pragma: no cover - defensive local server boundary
            return self._json(500, {"error": f"Arena error: {type(error).__name__}: {error}"})

    def log_message(self, format_string, *args):
        if self.path.startswith("/api/"):
            sys.stderr.write("human-arena " + (format_string % args) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=43128)
    parser.add_argument(
        "--artifact", type=Path,
        default=PROJECT_ROOT / "artifacts" / "kaggriculture-v1.1.0-alpha5.tar.gz",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "results" / "human_arena_sessions")
    parser.add_argument("--static-dir", type=Path, default=PROJECT_ROOT / "dist")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Human Arena must bind to a loopback host")
    manager = ArenaManager(args.artifact, args.output_dir)
    HumanArenaHandler.manager = manager
    HumanArenaHandler.static_dir = args.static_dir.resolve()
    server = ThreadingHTTPServer((args.host, args.port), HumanArenaHandler)
    print(f"Human Arena ready at http://{args.host}:{args.port}/index.html#human-arena", flush=True)
    print(f"Opponent: {manager.artifact.name}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()


if __name__ == "__main__":
    main()
