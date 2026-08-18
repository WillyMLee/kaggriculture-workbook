(() => {
  "use strict";

  const API = "/api/strategy-lab";
  const STORAGE_KEY = "kaggriculture-strategy-dojo-session";
  const $ = (id) => document.getElementById(id);
  const money = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const state = { session: null, token: "", selected: "", busy: false };

  async function request(path, payload) {
    const response = await fetch(`${API}${path}`, {
      method: payload === undefined ? "GET" : "POST",
      headers: payload === undefined ? undefined : { "content-type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `Strategy lab request failed (${response.status})`);
    return body;
  }

  function setBusy(next, message = "Working…") {
    state.busy = next;
    ["dojo-start", "dojo-feedback-submit"].forEach((id) => { if ($(id)) $(id).disabled = next; });
    if ($("dojo-play")) $("dojo-play").disabled = next || Boolean(state.session?.done);
    if (message && $("dojo-status")) $("dojo-status").textContent = message;
  }

  function phaseLabel(phase) {
    return { early: "Early · option value", middle: "Middle · engine commit", late: "Late · conversion", close: "Close · liquidation" }[phase] || phase;
  }

  function saveResume() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: state.session.session_id, token: state.token }));
  }

  function metric(id, value) {
    if ($(id)) $(id).textContent = value;
  }

  function renderPhases() {
    document.querySelectorAll("[data-dojo-phase]").forEach((node) => {
      const phases = ["early", "middle", "late", "close"];
      const current = phases.indexOf(state.session.phase);
      const index = phases.indexOf(node.dataset.dojoPhase);
      node.dataset.state = index === current ? "current" : index < current ? "done" : "next";
    });
  }

  function renderOptions() {
    const root = $("dojo-options");
    root.replaceChildren();
    state.session.options.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "dojo-option";
      button.dataset.action = item.action;
      button.dataset.state = !item.available ? "disabled" : state.selected === item.action ? "selected" : "idle";
      button.disabled = !item.available || state.session.done;
      const score = item.value <= -90 ? "blocked" : `${item.value >= 0 ? "+" : ""}${item.value.toFixed(1)} utility`;
      button.innerHTML = `<span>${item.action}</span><strong>${item.label}</strong><p>${item.detail}</p><small>${item.cost ? `${money.format(item.cost)} coins` : "no capital"} · ${score}</small>`;
      button.addEventListener("click", () => {
        state.selected = item.action;
        renderOptions();
        metric("dojo-selection", `${item.label} selected`);
      });
      root.append(button);
    });
  }

  function renderFarm(prefix, farm) {
    metric(`${prefix}-bank`, money.format(farm.bank));
    metric(`${prefix}-value`, money.format(farm.value));
    metric(`${prefix}-plots`, farm.plots);
    metric(`${prefix}-crops`, farm.crops);
    metric(`${prefix}-animals`, farm.animals);
    metric(`${prefix}-hands`, farm.hands);
    metric(`${prefix}-service`, `${Math.round(farm.service * 100)}%`);
    metric(`${prefix}-inventory`, money.format(farm.inventory));
    const bar = $(`${prefix}-service-bar`);
    if (bar) bar.style.width = `${Math.round(farm.service * 100)}%`;
  }

  function renderLog() {
    const root = $("dojo-log");
    root.replaceChildren();
    if (!state.session.history.length) {
      const empty = document.createElement("li");
      empty.innerHTML = "<span>Day 00</span><p>Your phase choices will appear here.</p>";
      root.append(empty);
      return;
    }
    [...state.session.history].reverse().forEach((entry) => {
      const row = document.createElement("li");
      row.innerHTML = `<span>D${String(entry.day).padStart(2, "0")} · ${entry.phase}</span><strong>${entry.action} / rival ${entry.rival_action}</strong><p>${entry.note}</p><em>${entry.margin >= 0 ? "+" : ""}${money.format(entry.margin)}</em>`;
      root.append(row);
    });
  }

  function renderResult() {
    const root = $("dojo-result");
    root.hidden = !state.session.done;
    if (!state.session.done) return;
    metric("dojo-result-verdict", state.session.result.verdict.toUpperCase());
    metric("dojo-result-score", `${money.format(state.session.result.human)} vs ${money.format(state.session.result.opponent)}`);
    metric("dojo-result-margin", `${state.session.result.margin >= 0 ? "+" : ""}${money.format(state.session.result.margin)}`);
  }

  function render() {
    const session = state.session;
    $("dojo-workspace").hidden = false;
    metric("dojo-session-label", `session ${session.session_id.slice(0, 8)} · ${session.version}`);
    metric("dojo-day", session.done ? "30 / 30" : `${String(session.day).padStart(2, "0")} / 29`);
    metric("dojo-phase", phaseLabel(session.phase));
    metric("dojo-margin", `${session.margin >= 0 ? "+" : ""}${money.format(session.margin)}`);
    metric("dojo-market", `crops ${session.market.crop.toFixed(2)}× · livestock ${session.market.animal.toFixed(2)}×`);
    metric("dojo-weather", session.market.weather);
    metric("dojo-opponent-style", `${session.opponent_style} benchmark`);
    metric("dojo-coach-action", session.coach.action.replaceAll("_", " "));
    metric("dojo-coach-score", `${session.coach.value >= 0 ? "+" : ""}${session.coach.value.toFixed(1)} utility`);
    renderFarm("dojo-human", session.human);
    renderFarm("dojo-opponent", session.opponent);
    renderPhases();
    if (!state.selected || !session.options.some((option) => option.action === state.selected && option.available)) state.selected = session.coach.action;
    renderOptions();
    renderLog();
    renderResult();
    $("dojo-play").disabled = session.done || state.busy;
    metric("dojo-status", session.done ? "Season complete. Add the lesson you want preserved." : "Every move and rationale saves automatically.");
  }

  async function health() {
    const indicator = $("dojo-server-state");
    try {
      const result = await request("/health");
      indicator.dataset.state = "ready";
      indicator.querySelector("strong").textContent = "Hosted dojo online";
      indicator.querySelector("small").textContent = `${result.version} · anonymous feedback saved`;
    } catch (_) {
      indicator.dataset.state = "offline";
      indicator.querySelector("strong").textContent = "Hosted dojo unavailable";
      indicator.querySelector("small").textContent = "The exact local arena remains available below.";
    }
  }

  async function resume() {
    let saved;
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch (_) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    if (!saved?.id || !saved?.token) return;
    try {
      const session = await request(`/session?id=${encodeURIComponent(saved.id)}&token=${encodeURIComponent(saved.token)}`);
      state.session = session;
      state.token = saved.token;
      render();
    } catch (_) {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function bind() {
    $("dojo-start").addEventListener("click", async () => {
      setBusy(true, "Creating a seeded strategy field…");
      $("dojo-launch-error").textContent = "";
      try {
        const session = await request("/new", {
          seed: Number($("dojo-seed").value),
          opponent_style: $("dojo-opponent").value,
        });
        state.token = session.token;
        delete session.token;
        state.session = session;
        state.selected = session.coach.action;
        saveResume();
        render();
        $("dojo-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        $("dojo-launch-error").textContent = error.message;
      } finally {
        setBusy(false, "Ready.");
      }
    });

    $("dojo-use-coach").addEventListener("click", () => {
      if (!state.session) return;
      state.selected = state.session.coach.action;
      renderOptions();
      metric("dojo-selection", `Coach line: ${state.selected}`);
    });

    $("dojo-play").addEventListener("click", async () => {
      if (!state.session || !state.selected || state.busy) return;
      setBusy(true, `Playing ${state.selected}…`);
      try {
        state.session = await request("/step", {
          session_id: state.session.session_id,
          token: state.token,
          action: state.selected,
          rationale: $("dojo-rationale").value,
          confidence: Number($("dojo-confidence").value),
          turning_point: $("dojo-turning-point").checked,
        });
        $("dojo-rationale").value = "";
        $("dojo-turning-point").checked = false;
        state.selected = state.session.coach.action;
        saveResume();
        render();
      } catch (error) {
        metric("dojo-status", error.message);
      } finally {
        setBusy(false, "");
      }
    });

    $("dojo-feedback-submit").addEventListener("click", async () => {
      if (!state.session || state.busy) return;
      setBusy(true, "Saving your lesson…");
      try {
        await request("/feedback", {
          session_id: state.session.session_id,
          token: state.token,
          category: $("dojo-feedback-category").value,
          note: $("dojo-feedback-note").value,
          rating: Number($("dojo-feedback-rating").value),
        });
        $("dojo-feedback-note").value = "";
        metric("dojo-feedback-status", "Saved to the Fieldbook training archive.");
      } catch (error) {
        metric("dojo-feedback-status", error.message);
      } finally {
        setBusy(false, "");
      }
    });
  }

  if ($("dojo-start")) {
    bind();
    health();
    resume();
  }
})();
