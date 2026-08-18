(() => {
  "use strict";

  const API = "/api/human-arena";
  const $ = (id) => document.getElementById(id);
  const money = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const PRODUCT_ITEMS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"];
  const CROP_ITEMS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"];
  const ANIMAL_ITEMS = ["GOOSE", "COW", "SHEEP"];
  const UNIT_OPS = ["PASS", "NORTH", "SOUTH", "EAST", "WEST", "DIG", "PLANT", "WATER", "HARVEST", "FERTILIZE", "BUILD_COOP", "BUILD_PASTURE", "FEED", "CARE", "COLLECT_FERTILIZER", "PICKUP", "PLACE", "DROP"];
  const MARKET_OPS = ["BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"];
  const state = { session: null, farmer: ["PASS"], hands: [], market: [], busy: false };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function option(value, label = value) {
    const node = document.createElement("option");
    node.value = value;
    node.textContent = label.replaceAll("_", " ").toLowerCase();
    return node;
  }

  async function request(path, payload) {
    const response = await fetch(`${API}${path}`, {
      method: payload === undefined ? "GET" : "POST",
      headers: payload === undefined ? undefined : { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `Arena request failed (${response.status})`);
    return body;
  }

  function setBusy(next, message = "Working…") {
    state.busy = next;
    ["arena-start", "arena-play-turn", "arena-play-coach", "arena-next-day", "arena-save"].forEach((id) => {
      if ($(id)) $(id).disabled = next;
    });
    if (next && $("arena-action-status")) $("arena-action-status").textContent = message;
  }

  function feedback() {
    return {
      intent: $("arena-intent").value,
      confidence: Number($("arena-confidence").value),
      rationale: $("arena-rationale").value.trim(),
      turning_point: $("arena-turning-point").checked,
    };
  }

  function resetFeedback() {
    $("arena-rationale").value = "";
    $("arena-turning-point").checked = false;
  }

  function itemsForUnit(op) {
    if (op === "PLANT") return CROP_ITEMS;
    if (op === "PICKUP" || op === "PLACE") return [...PRODUCT_ITEMS, ...ANIMAL_ITEMS];
    return [];
  }

  function normalizedUnit(op, item, quantity) {
    if (op === "PLANT") return [op, item || "WHEAT"];
    if (op === "PICKUP" || op === "PLACE") return [op, item || "WHEAT", Math.max(1, Number(quantity) || 1)];
    return [op];
  }

  function createUnitRow(label, position, action, onChange) {
    const row = el("div", "arena-unit-row");
    const identity = el("div", "arena-unit-identity");
    identity.append(el("strong", "", label), el("small", "", position ? `[${position[0]}, ${position[1]}]` : "not hired"));
    const operation = el("select", "arena-operation");
    UNIT_OPS.forEach((name) => operation.append(option(name)));
    operation.value = action?.[0] || "PASS";
    const item = el("select", "arena-item");
    const quantity = el("input", "arena-quantity");
    quantity.type = "number";
    quantity.min = "1";
    quantity.max = "100";
    quantity.value = action?.[2] || 1;
    const refresh = () => {
      const values = itemsForUnit(operation.value);
      const previous = action?.[1];
      item.replaceChildren(...values.map((name) => option(name)));
      if (previous && values.includes(previous)) item.value = previous;
      item.hidden = values.length === 0;
      quantity.hidden = !["PICKUP", "PLACE"].includes(operation.value);
      onChange(normalizedUnit(operation.value, item.value, quantity.value));
      updatePreview();
    };
    operation.addEventListener("change", refresh);
    item.addEventListener("change", refresh);
    quantity.addEventListener("input", refresh);
    row.append(identity, operation, item, quantity);
    refresh();
    return row;
  }

  function marketItems(op) {
    if (op === "BUY_SEED") return CROP_ITEMS;
    if (op === "BUY_ANIMAL") return ANIMAL_ITEMS;
    if (op === "BUY_PRODUCT" || op === "SELL") return PRODUCT_ITEMS;
    return [];
  }

  function normalizedMarket(op, item, quantity) {
    if (op === "HIRE" || op === "BUY_LAND") return [op];
    return [op, item || marketItems(op)[0], Math.max(1, Number(quantity) || 1)];
  }

  function renderMarketOrders() {
    const host = $("arena-market-orders");
    host.replaceChildren();
    if (!state.market.length) host.append(el("p", "arena-empty", "No queued orders."));
    state.market.forEach((action, index) => {
      const row = el("div", "arena-market-row");
      const operation = el("select", "arena-operation");
      MARKET_OPS.forEach((name) => operation.append(option(name)));
      operation.value = action[0];
      const item = el("select", "arena-item");
      const quantity = el("input", "arena-quantity");
      quantity.type = "number";
      quantity.min = "1";
      quantity.max = "1000";
      quantity.value = action[2] || 1;
      const remove = el("button", "arena-remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove order ${index + 1}`);
      const refresh = () => {
        const values = marketItems(operation.value);
        const previous = state.market[index]?.[1];
        item.replaceChildren(...values.map((name) => option(name)));
        if (previous && values.includes(previous)) item.value = previous;
        item.hidden = values.length === 0;
        quantity.hidden = values.length === 0;
        state.market[index] = normalizedMarket(operation.value, item.value, quantity.value);
        updatePreview();
      };
      operation.addEventListener("change", refresh);
      item.addEventListener("change", refresh);
      quantity.addEventListener("input", refresh);
      remove.addEventListener("click", () => {
        state.market.splice(index, 1);
        renderMarketOrders();
        updatePreview();
      });
      row.append(operation, item, quantity, remove);
      host.append(row);
      refresh();
    });
  }

  function currentAction() {
    return { farmer: state.farmer, hands: state.hands, market: state.market };
  }

  function shortAction(action) {
    if (!action) return "—";
    const parts = [`farmer ${action.farmer?.join(" ") || "PASS"}`];
    const activeHands = (action.hands || []).map((value, index) => `${index + 1}:${value.join(" ")}`).filter((value) => !value.endsWith(":PASS"));
    if (activeHands.length) parts.push(`hands ${activeHands.join(" · ")}`);
    if (action.market?.length) parts.push(`market ${action.market.map((value) => value.join(" ")).join(" · ")}`);
    return parts.join(" | ");
  }

  function updatePreview() {
    $("arena-action-preview").textContent = shortAction(currentAction());
  }

  function setAction(action) {
    const hands = state.session?.observation?.farms?.[state.session.human_seat]?.hands || [];
    state.farmer = [...(action?.farmer || ["PASS"])];
    state.hands = hands.map((_, index) => [...(action?.hands?.[index] || ["PASS"])]);
    state.market = (action?.market || []).map((value) => [...value]);
    renderActionEditor();
  }

  function renderActionEditor() {
    if (!state.session) return;
    const farm = state.session.observation.farms[state.session.human_seat];
    const host = $("arena-unit-actions");
    host.replaceChildren();
    host.append(createUnitRow("Farmer", farm.farmer, state.farmer, (value) => { state.farmer = value; }));
    farm.hands.forEach((position, index) => {
      host.append(createUnitRow(`Hand ${index + 1}`, position, state.hands[index] || ["PASS"], (value) => { state.hands[index] = value; }));
    });
    renderMarketOrders();
    updatePreview();
  }

  function tileKind(tile) {
    if (!tile) return "empty";
    return String(tile.animal || tile.crop || tile.kind || "soil").toLowerCase();
  }

  function tileGlyph(tile) {
    if (!tile) return "";
    const glyphs = { WHEAT: "W", CARROT: "C", TOMATO: "T", STRAWBERRY: "S", MELON: "M", GOOSE: "G", COW: "C", SHEEP: "S", WEED: "×", COOP: "c", PASTURE: "p", SOIL: "·" };
    return glyphs[tile.animal || tile.crop || tile.kind] || "·";
  }

  function tileDetail(tile, row, column, occupants) {
    const bits = [`row ${row + 1} · column ${column + 1}`];
    if (!tile) bits.push("empty ground");
    else Object.entries(tile).forEach(([key, value]) => {
      if (value !== null && value !== false && value !== "" && !(Array.isArray(value) && !value.length)) bits.push(`${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`);
    });
    if (occupants.length) bits.push(`units: ${occupants.join(", ")}`);
    return bits.join(" · ");
  }

  function renderBoard(id, farm, label) {
    const host = $(id);
    host.replaceChildren();
    const units = new Map();
    const addUnit = (position, name) => {
      if (!Array.isArray(position)) return;
      const key = `${position[0]}:${position[1]}`;
      units.set(key, [...(units.get(key) || []), name]);
    };
    addUnit(farm.farmer, "farmer");
    farm.hands.forEach((position, index) => addUnit(position, `hand ${index + 1}`));
    (farm.tiles || []).forEach((row, rowIndex) => (row || []).forEach((tile, columnIndex) => {
      const cell = el("button", `arena-cell arena-cell--${tileKind(tile)}`);
      cell.type = "button";
      cell.setAttribute("role", "gridcell");
      const occupants = units.get(`${rowIndex}:${columnIndex}`) || [];
      if (occupants.length) cell.dataset.unit = String(occupants.length);
      cell.textContent = tileGlyph(tile);
      cell.title = tileDetail(tile, rowIndex, columnIndex, occupants);
      cell.addEventListener("click", () => {
        $("arena-tile-title").textContent = `${label} · ${rowIndex + 1}, ${columnIndex + 1}`;
        $("arena-tile-detail").textContent = tileDetail(tile, rowIndex, columnIndex, occupants);
      });
      host.append(cell);
    }));
  }

  function renderCoach() {
    const trace = state.session.coach_trace || {};
    const macro = trace.macro || {};
    const regime = macro.regime || {};
    const attention = trace.attention || {};
    $("arena-coach-branch").querySelector("strong").textContent = macro.branch || regime.choice || trace.capital || "hold";
    $("arena-coach-action").textContent = shortAction(state.session.coach_suggestion);
    [["operations", attention.operations], ["opponent", attention.opponent], ["horizon", attention.horizon]].forEach(([name, raw]) => {
      const value = Math.max(0, Math.min(1, Number(raw) || 0));
      $(`arena-attention-${name}`).style.width = `${value * 100}%`;
      $(`arena-attention-${name}-value`).textContent = `${Math.round(value * 100)}%`;
    });
  }

  function renderInsights() {
    const data = state.session.insights;
    const entries = [
      ["Productive", `${data.productive_tiles} tiles`, "planted or occupied"],
      ["Shed dwell", `${data.animal_backlog} animals`, data.animal_backlog ? "deployment debt" : "clear"],
      ["Inventory", `${money.format(data.inventory_market_value)} coins`, "at current market"],
      ["Open structures", `${data.empty_pastures} pasture · ${data.empty_coops} coop`, "ready slots"],
      ["Weeds", String(data.weeds), data.weeds >= 4 ? "capacity warning" : "controlled"],
      ["Next land", data.next_land_price == null ? "all open" : money.format(data.next_land_price), "capital threshold"],
    ];
    $("arena-insight-strip").replaceChildren(...entries.map(([key, value, note]) => {
      const node = el("div");
      node.append(el("span", "", key), el("strong", "", value), el("small", "", note));
      return node;
    }));
  }

  function renderMarket() {
    const obs = state.session.observation;
    const prices = obs.market?.prices || {};
    const inventory = obs.private?.shed || {};
    const seeds = obs.private?.seeds || {};
    const demand = state.session.insights.town_demand || {};
    const items = [...new Set([...Object.keys(prices), ...Object.keys(inventory), ...Object.keys(seeds)])];
    $("arena-market-table").replaceChildren(...items.map((name) => {
      const row = document.createElement("tr");
      [name.replaceAll("_", " "), money.format(prices[name] || 0), inventory[name] || 0, seeds[name] || 0, demand[name] || 0].forEach((value) => row.append(el("td", "", String(value))));
      return row;
    }));
  }

  function renderRules() {
    const rules = state.session.rules;
    const host = $("arena-rule-reference");
    host.replaceChildren();
    Object.entries(rules.crops).forEach(([name, values]) => {
      const node = el("div");
      node.append(el("span", "", name), el("strong", "", `${values.seed} seed · yield d${values.first_yield_day}${values.ongoing ? ` / every ${values.interval}` : ""}`));
      host.append(node);
    });
    Object.entries(rules.animals).forEach(([name, values]) => {
      const node = el("div");
      node.append(el("span", "", name), el("strong", "", `${values.cost} · ${values.structure.toLowerCase()} · ${values.product.toLowerCase()} d${values.first_yield_day}`));
      host.append(node);
    });
  }

  function renderLog() {
    const rows = [...state.session.recent_turns].reverse();
    const host = $("arena-turn-log");
    host.replaceChildren();
    if (!rows.length) host.append(el("li", "arena-empty", "No turns played."));
    rows.forEach((row) => {
      const item = el("li", row.used_coach ? "" : "is-manual");
      const head = el("div");
      head.append(el("span", "", `D${row.day} · ${String(row.hour).padStart(2, "0")}:00`), el("strong", "", row.branch));
      const effect = row.effect || {};
      item.append(head, el("p", "", `${row.disagreement ? `coach: ${row.coach_branch} · ` : ""}bank ${effect.bank_delta >= 0 ? "+" : ""}${money.format(effect.bank_delta || 0)} · margin ${money.format(row.margin || 0)}`));
      host.append(item);
    });
  }

  function renderResult() {
    const summary = state.session.summary;
    const section = $("arena-result");
    section.hidden = !summary.complete;
    if (!summary.complete) return;
    const verdict = $("arena-result-verdict");
    verdict.textContent = summary.result.toUpperCase();
    verdict.dataset.state = summary.result === "win" ? "pass" : "hold";
    const stats = [
      ["Final bank", money.format(summary.human_bank)],
      ["Alpha5", money.format(summary.agent_bank)],
      ["Margin", `${summary.margin >= 0 ? "+" : ""}${money.format(summary.margin)}`],
      ["Manual choices", String(summary.manual_turns)],
      ["Disagreements", String(summary.coach_disagreements)],
    ];
    $("arena-result-stats").replaceChildren(...stats.map(([name, value]) => {
      const node = el("div");
      node.append(el("span", "", name), el("strong", "", value));
      return node;
    }));
    $("arena-result-feedback").replaceChildren(...summary.feedback.map((text) => {
      const node = el("li");
      node.append(el("span", "", "NOTE"), el("div", "", text));
      return node;
    }));
  }

  function renderSession(resetEditor = false) {
    const session = state.session;
    if (!session) return;
    const obs = session.observation;
    const humanFarm = obs.farms[session.human_seat];
    const agentFarm = obs.farms[session.agent_seat];
    $("arena-workspace").hidden = false;
    $("arena-session-label").textContent = `${session.session_id} · seed ${session.seed}`;
    $("arena-clock").textContent = `Day ${obs.day} · ${String(obs.hour).padStart(2, "0")}:00`;
    $("arena-turn").textContent = `turn ${obs.step} / ${session.rules.episode_steps}`;
    $("arena-human-bank").textContent = money.format(session.bank.human);
    $("arena-agent-bank").textContent = money.format(session.bank.agent);
    $("arena-margin").textContent = `${session.bank.margin >= 0 ? "+" : ""}${money.format(session.bank.margin)}`;
    $("arena-margin-note").textContent = session.bank.margin > 0 ? "ahead" : session.bank.margin < 0 ? "behind" : "level";
    const shops = obs.town?.unlocked_shops || [];
    $("arena-shop-count").textContent = `${shops.length} shop${shops.length === 1 ? "" : "s"}`;
    $("arena-town-summary").textContent = shops.length ? [...new Set(shops)].join(" · ").replaceAll("_", " ").toLowerCase() : "no demand yet";
    $("arena-human-land").textContent = (humanFarm.unlocked_quadrants || []).join(" · ") || "NW";
    $("arena-agent-land").textContent = (agentFarm.unlocked_quadrants || []).join(" · ") || "NW";
    renderBoard("arena-human-board", humanFarm, "Your farm");
    renderBoard("arena-agent-board", agentFarm, "Alpha5");
    renderCoach();
    renderInsights();
    renderMarket();
    renderRules();
    renderLog();
    renderResult();
    if (resetEditor) setAction({ farmer: ["PASS"], hands: humanFarm.hands.map(() => ["PASS"]), market: [] });
    $("arena-play-turn").disabled = session.done;
    $("arena-play-coach").disabled = session.done;
    $("arena-next-day").disabled = session.done;
    $("arena-action-status").textContent = session.done ? "Episode complete. Save the training file." : "Ready.";
  }

  async function runAction(path, payload, label) {
    if (!state.session || state.busy) return;
    setBusy(true, label);
    try {
      state.session = await request(path, { session_id: state.session.session_id, ...payload });
      renderSession(true);
      resetFeedback();
    } catch (error) {
      $("arena-action-status").textContent = error.message;
    } finally {
      setBusy(false);
    }
  }

  async function checkHealth() {
    const indicator = $("arena-server-state");
    if (!indicator) return;
    try {
      const health = await request("/health");
      if (!health.ok || !health.artifact) throw new Error("Exact arena server is not running.");
      indicator.dataset.state = "ready";
      indicator.querySelector("strong").textContent = "Exact engine ready";
      indicator.querySelector("small").textContent = `${health.artifact} · offline learning only`;
    } catch (_) {
      indicator.dataset.state = "offline";
      indicator.querySelector("strong").textContent = "Open the arena server";
      indicator.querySelector("small").textContent = "Run scripts/human_arena_server.py on port 43128";
    }
  }

  function bind() {
    $("arena-start").addEventListener("click", async () => {
      setBusy(true, "Creating exact episode…");
      $("arena-launch-error").textContent = "";
      try {
        state.session = await request("/new", { seed: Number($("arena-seed").value), human_seat: Number($("arena-seat").value) });
        renderSession(true);
      } catch (error) {
        $("arena-launch-error").textContent = error.message;
      } finally {
        setBusy(false);
      }
    });
    document.querySelectorAll("[data-arena-move]").forEach((button) => button.addEventListener("click", () => {
      state.farmer = [button.dataset.arenaMove];
      renderActionEditor();
    }));
    $("arena-add-market").addEventListener("click", () => {
      if (state.market.length < 10) state.market.push(["BUY_SEED", "WHEAT", 1]);
      renderMarketOrders();
    });
    $("arena-copy-coach").addEventListener("click", () => setAction(state.session?.coach_suggestion));
    $("arena-play-turn").addEventListener("click", () => runAction("/step", { action: currentAction(), feedback: feedback() }, "Stepping exact environment…"));
    $("arena-play-coach").addEventListener("click", () => runAction("/step", { use_coach: true, feedback: feedback() }, "Using coach for one turn…"));
    $("arena-next-day").addEventListener("click", () => runAction("/autoplay", { feedback: feedback() }, "Routing routine work to tomorrow…"));
    $("arena-save").addEventListener("click", async () => {
      if (!state.session || state.busy) return;
      setBusy(true, "Saving checkpoint…");
      try {
        const saved = await request("/save", { session_id: state.session.session_id });
        $("arena-action-status").textContent = saved.training_ready ? "Training JSONL saved." : "Checkpoint saved; finish the season for a training JSONL.";
      } catch (error) {
        $("arena-action-status").textContent = error.message;
      } finally {
        setBusy(false);
      }
    });
  }

  if ($("human-arena")) {
    bind();
    checkHealth();
  }
})();
