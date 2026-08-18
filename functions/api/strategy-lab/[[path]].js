const VERSION = "v2.0-dojo-1";
const STYLES = ["lean", "dense", "land", "mixed"];
const ACTIONS = ["lean", "crops", "livestock", "expand", "crew", "stabilize", "convert", "liquidate"];

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const round = (value) => Math.round(value);
const phaseFor = (day) => day <= 8 ? "early" : day <= 20 ? "middle" : day <= 27 ? "late" : "close";

function noise(seed, day, salt = 0) {
  let value = (seed ^ Math.imul(day + 1, 0x9e3779b1) ^ Math.imul(salt + 7, 0x85ebca6b)) >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d);
  value ^= value >>> 15;
  value = Math.imul(value, 0x846ca68b);
  value ^= value >>> 16;
  return (value >>> 0) / 4294967295;
}

function publicMarket(seed, day) {
  const crop = 0.78 + noise(seed, day, 2) * 0.58;
  const animal = 0.8 + noise(seed, day, 4) * 0.54;
  const weather = noise(seed, day, 6) < 0.16 ? "weed pressure" : noise(seed, day, 7) > 0.82 ? "clear routes" : "normal";
  return { crop: Number(crop.toFixed(2)), animal: Number(animal.toFixed(2)), weather };
}

function farmValue(farm, market = { crop: 1, animal: 1 }) {
  return round(farm.bank + farm.inventory * (0.9 + Math.max(market.crop, market.animal) * 0.18) + farm.plots * 1150 + farm.crops * 145 + farm.animals * 540 + farm.hands * 260);
}

function baseFarm() {
  return { bank: 3000, plots: 1, capacity: 16, crops: 6, animals: 2, hands: 4, weeds: 1, inventory: 0, missed: 0, earned: 0, invested: 0 };
}

function service(farm) {
  const demand = 1.4 + farm.plots * 0.8 + farm.crops * 0.2 + farm.animals * 0.95 + farm.weeds * 0.55;
  const supply = farm.hands * 1.8;
  return { demand, supply, ratio: clamp(supply / demand, 0.34, 1) };
}

function settleProduction(farm, market, seed, day, salt) {
  const before = { ...farm };
  const load = service(farm);
  const weatherPenalty = market.weather === "weed pressure" ? 0.84 : 1;
  const routeBonus = market.weather === "clear routes" ? 1.08 : 1;
  const cropGross = farm.crops * 43 * market.crop * load.ratio * weatherPenalty * routeBonus;
  const animalGross = farm.animals * 76 * market.animal * load.ratio * routeBonus;
  const gross = cropGross + animalGross;
  const stored = gross * (day >= 21 ? 0.42 : 0.27);
  const cash = gross - stored;
  farm.bank += round(cash);
  farm.inventory += round(stored);
  farm.earned += round(gross);
  if (load.ratio < 0.72) farm.missed += round((1 - load.ratio) * 10);
  const weedRoll = noise(seed, day, salt);
  farm.weeds = clamp(farm.weeds + (weedRoll < 0.24 ? 2 : weedRoll < 0.58 ? 1 : 0) - (load.ratio > 0.9 ? 1 : 0), 0, 12);
  return { before, gross: round(gross), service: load };
}

function costFor(action, farm) {
  return {
    lean: 0,
    crops: 480 + Math.max(0, farm.crops - 12) * 18,
    livestock: 920 + farm.animals * 35,
    expand: 2650 + Math.max(0, farm.plots - 1) * 850,
    crew: 780 + Math.max(0, farm.hands - 4) * 120,
    stabilize: 180 + farm.weeds * 25,
    convert: 0,
    liquidate: 0,
  }[action];
}

function applyAction(farm, action, market, day) {
  const cost = costFor(action, farm);
  if (cost > farm.bank && !["lean", "convert", "liquidate"].includes(action)) return { ok: false, cost, note: "Not enough liquid cash for this package." };
  let note = "";
  if (action === "lean") {
    const quick = 170 + round(90 * market.crop);
    farm.bank += quick;
    farm.weeds = Math.max(0, farm.weeds - 1);
    note = `Protected option value and recovered ${quick} coins.`;
  } else if (action === "crops") {
    const room = Math.max(0, farm.capacity - farm.crops - farm.animals * 2);
    if (room < 2) return { ok: false, cost, note: "The current plot is saturated; expand, sell, or rebalance first." };
    const added = Math.min(5, room);
    farm.bank -= cost; farm.invested += cost; farm.crops += added;
    note = `Added ${added} productive crop slots.`;
  } else if (action === "livestock") {
    const room = Math.max(0, farm.capacity - farm.crops - farm.animals * 2);
    if (room < 2) return { ok: false, cost, note: "No serviceable animal slot remains on this footprint." };
    const added = room >= 4 && farm.bank >= cost * 1.75 ? 2 : 1;
    const spend = added === 2 ? round(cost * 1.75) : cost;
    farm.bank -= spend; farm.invested += spend; farm.animals += added;
    note = `Placed ${added} recurring livestock unit${added === 1 ? "" : "s"}.`;
  } else if (action === "expand") {
    farm.bank -= cost; farm.invested += cost; farm.plots += 1; farm.capacity += 18;
    note = "Unlocked one plot; the new capacity still needs labor and productive assets.";
  } else if (action === "crew") {
    farm.bank -= cost; farm.invested += cost; farm.hands += 1;
    note = "Added one work hand and raised daily service capacity.";
  } else if (action === "stabilize") {
    farm.bank -= cost; farm.invested += cost; farm.weeds = Math.max(0, farm.weeds - 4); farm.missed = Math.max(0, farm.missed - 2);
    note = "Cleared pressure and protected already-funded production.";
  } else if (action === "convert") {
    const sold = round(farm.inventory * (0.86 + Math.max(market.crop, market.animal) * 0.22));
    farm.bank += sold; farm.inventory = 0;
    note = `Converted stored output into ${sold} coins.`;
  } else if (action === "liquidate") {
    const inventory = round(farm.inventory * (0.92 + Math.max(market.crop, market.animal) * 0.24));
    const salvageUnits = day >= 27 ? Math.max(0, Math.floor((farm.crops + farm.animals) * 0.14)) : 0;
    const salvage = salvageUnits * 180;
    farm.bank += inventory + salvage; farm.inventory = 0;
    if (salvageUnits) farm.crops = Math.max(0, farm.crops - salvageUnits);
    note = `Closed reachable inventory and assets for ${inventory + salvage} coins.`;
  }
  return { ok: true, cost, note };
}

function utility(action, farm, market, day) {
  const phase = phaseFor(day);
  const load = service(farm);
  const runway = 30 - day;
  const room = farm.capacity - farm.crops - farm.animals * 2;
  if ((action === "crops" || action === "livestock") && room < 2) return -99;
  if (action === "convert" && farm.inventory < 1) return -12;
  const payback = {
    lean: 5 + (farm.bank < 1200 ? 8 : 0) + farm.weeds,
    crops: market.crop * runway * 0.72 + room * 0.2 - (phase === "close" ? 15 : 0),
    livestock: market.animal * runway * 0.9 + (farm.crops >= farm.animals * 2 ? 4 : -4) - (phase === "late" ? 3 : phase === "close" ? 18 : 0),
    expand: room < 5 ? runway * 0.72 + farm.bank / 1800 : -5,
    crew: load.ratio < 0.8 ? (1 - load.ratio) * 26 : -2,
    stabilize: farm.weeds * 2.6 + (load.ratio < 0.7 ? 4 : 0),
    convert: farm.inventory / 260 + (Math.max(market.crop, market.animal) > 1.18 ? 5 : 0) + (phase === "late" ? 4 : 0),
    liquidate: phase === "close" ? 30 + farm.inventory / 180 : phase === "late" ? 3 + farm.inventory / 500 : -20,
  }[action];
  const unaffordable = costFor(action, farm) > farm.bank && !["lean", "convert", "liquidate"].includes(action);
  return unaffordable ? -99 : Number(payback.toFixed(1));
}

function coachFor(farm, market, day) {
  return ACTIONS.map((action) => ({ action, value: utility(action, farm, market, day) }))
    .sort((a, b) => b.value - a.value)[0];
}

function opponentAction(style, farm, market, day) {
  const phase = phaseFor(day);
  const load = service(farm);
  const room = farm.capacity - farm.crops - farm.animals * 2;
  if (phase === "close") return farm.inventory > 0 ? "liquidate" : "lean";
  if (farm.weeds >= 7 || load.ratio < 0.57) return "stabilize";
  if (load.ratio < 0.76 && farm.bank >= costFor("crew", farm)) return "crew";
  if (phase === "late" && farm.inventory > 750) return "convert";
  if (style === "land" && day >= 5 && room < 7 && farm.bank >= costFor("expand", farm)) return "expand";
  if (style === "dense" && room >= 2 && farm.bank >= costFor("livestock", farm)) return "livestock";
  if (style === "lean" && (farm.bank < 2200 || day % 3 === 0)) return "lean";
  if (style === "mixed") {
    if (room < 5 && farm.bank >= costFor("expand", farm) && day < 19) return "expand";
    if (market.animal > market.crop && room >= 2) return "livestock";
    if (room >= 2) return "crops";
  }
  const best = coachFor(farm, market, day).action;
  return best;
}

function actionOptions(farm, market, day) {
  const labels = {
    lean: ["Protect liquidity", "Keep the next choice reversible."],
    crops: ["Compound crops", "Buy a short recurring crop cohort."],
    livestock: ["Add livestock", "Fund recurring output and its service load."],
    expand: ["Unlock a plot", "Buy capacity now; productivity follows later."],
    crew: ["Hire a work hand", "Raise service throughput before adding density."],
    stabilize: ["Repair operations", "Clear weeds and protect funded assets."],
    convert: ["Sell inventory", "Realize stored output at today's demand."],
    liquidate: ["Close the book", "Convert reachable terminal value into bank."],
  };
  return ACTIONS.map((action) => {
    const cost = costFor(action, farm);
    const value = utility(action, farm, market, day);
    return { action, label: labels[action][0], detail: labels[action][1], cost, value, available: value > -90 };
  });
}

function summarize(state) {
  const market = state.market;
  const humanLoad = service(state.human);
  const rivalLoad = service(state.opponent);
  const coach = coachFor(state.human, market, state.day);
  return {
    session_id: state.id,
    version: VERSION,
    seed: state.seed,
    day: state.day,
    phase: phaseFor(state.day),
    market,
    opponent_style: state.opponentStyle,
    human: { ...state.human, service: Number(humanLoad.ratio.toFixed(2)), value: farmValue(state.human, market) },
    opponent: { ...state.opponent, service: Number(rivalLoad.ratio.toFixed(2)), value: farmValue(state.opponent, market) },
    margin: farmValue(state.human, market) - farmValue(state.opponent, market),
    coach,
    options: actionOptions(state.human, market, state.day),
    history: state.history.slice(-10),
    done: state.done,
    result: state.result || null,
  };
}

function initialState(id, seed, requestedStyle) {
  const opponentStyle = requestedStyle === "adaptive" ? STYLES[Math.floor(noise(seed, 0, 19) * STYLES.length)] : requestedStyle;
  const state = { id, seed, opponentStyle, day: 0, human: baseFarm(), opponent: baseFarm(), market: publicMarket(seed, 0), history: [], done: false, result: null };
  return state;
}

function stepState(state, action) {
  if (state.done) throw new Error("This season is already complete.");
  const day = state.day;
  const market = state.market;
  settleProduction(state.human, market, state.seed, day, 30);
  settleProduction(state.opponent, market, state.seed, day, 60);
  const rivalAction = opponentAction(state.opponentStyle, state.opponent, market, day);
  const humanResult = applyAction(state.human, action, market, day);
  if (!humanResult.ok) throw new Error(humanResult.note);
  let rivalResult = applyAction(state.opponent, rivalAction, market, day);
  if (!rivalResult.ok) rivalResult = applyAction(state.opponent, "lean", market, day);
  state.history.push({ day, phase: phaseFor(day), action, rival_action: rivalAction, note: humanResult.note, margin: farmValue(state.human, market) - farmValue(state.opponent, market) });
  state.day += 1;
  if (state.day >= 30) {
    applyAction(state.human, "liquidate", market, 29);
    applyAction(state.opponent, "liquidate", market, 29);
    const human = round(state.human.bank);
    const opponent = round(state.opponent.bank);
    state.done = true;
    state.result = { human, opponent, margin: human - opponent, verdict: human > opponent ? "ahead" : human < opponent ? "behind" : "level" };
  } else {
    state.market = publicMarket(state.seed, state.day);
  }
  return { state, rivalAction };
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((part) => part.toString(16).padStart(2, "0")).join("");
}

async function body(request) {
  const raw = await request.text();
  if (raw.length > 12000) throw new Error("Request is too large.");
  try { return raw ? JSON.parse(raw) : {}; } catch { throw new Error("Invalid JSON request."); }
}

function cleanText(value, limit) {
  return String(value || "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, limit);
}

async function loadSession(env, id, token) {
  if (!id || !token) return null;
  const row = await env.DB.prepare("SELECT * FROM strategy_sessions WHERE id = ? AND token_hash = ?").bind(id, await sha256(token)).first();
  return row ? { row, state: JSON.parse(row.state_json) } : null;
}

export async function onRequest(context) {
  const { request, env } = context;
  const rawPath = context.params.path;
  const path = Array.isArray(rawPath) ? rawPath.join("/") : String(rawPath || "");
  const method = request.method.toUpperCase();
  try {
    if (method === "GET" && (path === "" || path === "health")) {
      await env.DB.prepare("SELECT 1 AS ok").first();
      return json({ ok: true, mode: "hosted strategy proxy", version: VERSION, persistence: "D1" });
    }
    if (method === "GET" && path === "session") {
      const url = new URL(request.url);
      const loaded = await loadSession(env, url.searchParams.get("id"), url.searchParams.get("token"));
      return loaded ? json(summarize(loaded.state)) : json({ error: "Session not found." }, 404);
    }
    if (method !== "POST") return json({ error: "Method not allowed." }, 405);
    const payload = await body(request);
    if (path === "new") {
      const seed = clamp(Math.trunc(Number(payload.seed) || Date.now()), 1, 2000000000);
      const style = ["adaptive", ...STYLES].includes(payload.opponent_style) ? payload.opponent_style : "adaptive";
      const id = crypto.randomUUID();
      const token = `${crypto.randomUUID()}-${crypto.randomUUID()}`;
      const state = initialState(id, seed, style);
      const now = new Date().toISOString();
      await env.DB.prepare("INSERT INTO strategy_sessions (id, token_hash, seed, opponent_style, version, state_json, complete, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)")
        .bind(id, await sha256(token), seed, state.opponentStyle, VERSION, JSON.stringify(state), now, now).run();
      return json({ ...summarize(state), token }, 201);
    }
    if (path === "step") {
      const loaded = await loadSession(env, cleanText(payload.session_id, 80), cleanText(payload.token, 160));
      if (!loaded) return json({ error: "Session not found." }, 404);
      const action = cleanText(payload.action, 30);
      if (!ACTIONS.includes(action)) return json({ error: "Choose a valid strategy action." }, 400);
      const before = summarize(loaded.state);
      const coachAction = before.coach.action;
      const day = loaded.state.day;
      const phase = phaseFor(day);
      const { state } = stepState(loaded.state, action);
      const after = summarize(state);
      const rationale = cleanText(payload.rationale, 500);
      const confidence = clamp(Math.trunc(Number(payload.confidence) || 3), 1, 5);
      const turningPoint = payload.turning_point ? 1 : 0;
      const now = new Date().toISOString();
      await env.DB.batch([
        env.DB.prepare("UPDATE strategy_sessions SET state_json = ?, complete = ?, updated_at = ? WHERE id = ?").bind(JSON.stringify(state), state.done ? 1 : 0, now, state.id),
        env.DB.prepare("INSERT INTO strategy_decisions (session_id, day, phase, action, coach_action, rationale, confidence, turning_point, state_before, state_after, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
          .bind(state.id, day, phase, action, coachAction, rationale, confidence, turningPoint, JSON.stringify(before), JSON.stringify(after), now),
      ]);
      return json(after);
    }
    if (path === "feedback") {
      const loaded = await loadSession(env, cleanText(payload.session_id, 80), cleanText(payload.token, 160));
      if (!loaded) return json({ error: "Session not found." }, 404);
      const category = ["strategy", "rules", "interface", "surprise", "bug"].includes(payload.category) ? payload.category : "strategy";
      const note = cleanText(payload.note, 1200);
      if (note.length < 3) return json({ error: "Add a short feedback note first." }, 400);
      const rating = clamp(Math.trunc(Number(payload.rating) || 3), 1, 5);
      await env.DB.prepare("INSERT INTO strategy_feedback (session_id, day, category, note, rating, created_at) VALUES (?, ?, ?, ?, ?, ?)")
        .bind(loaded.state.id, loaded.state.day, category, note, rating, new Date().toISOString()).run();
      return json({ ok: true, saved: true, session_id: loaded.state.id });
    }
    return json({ error: "Unknown strategy-lab route." }, 404);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "Strategy lab failed." }, 400);
  }
}
