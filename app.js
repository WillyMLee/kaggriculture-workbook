(function () {
  "use strict";

  const KEYS = {
    checklist: "kaggriculture-fieldbook-checklist-v1",
    experiments: "kaggriculture-fieldbook-experiments-v1",
    submissions: "kaggriculture-fieldbook-submissions-v2",
    submissionGate: "kaggriculture-submission-gate-v2",
    roadmap: "kaggriculture-fieldbook-roadmap-v1",
    balancedNotes: "kaggriculture-balanced-notes-v1",
    agentArchive: "kaggriculture-agent-archive-v1",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function readStore(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  function writeStore(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // The workbook still works for the current page session if storage is unavailable.
    }
  }

  function makeId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  // Navigation
  const viewIds = ["brief", "mechanics", "tensions", "opponent", "balanced", "simulator", "attention", "architecture", "past-agents", "research-models", "human-arena", "submission", "submissions", "experiments", "roadmap"];

  function showView(viewId, updateHash = true) {
    const safeId = viewIds.includes(viewId) ? viewId : "brief";
    $$(".view").forEach((view) => {
      const active = view.id === safeId;
      view.hidden = !active;
      view.classList.toggle("is-active", active);
    });
    $$("[data-view-target]").forEach((button) => {
      const active = button.dataset.viewTarget === safeId;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-current", active ? "page" : "false");
    });
    if (updateHash) history.replaceState(null, "", `#${safeId}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  $$("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewTarget));
  });
  $$("[data-view-jump]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewJump));
  });
  window.addEventListener("hashchange", () => showView(location.hash.slice(1), false));
  showView(location.hash.slice(1), false);

  // Layperson architecture explainer
  const architectureLab = $("#architecture-lab");
  if (architectureLab) {
    const architectureScenarios = {
      capacity: {
        attention: { operations: 0.25, opponent: 0.75, horizon: 0.95 },
        options: { compact: 0.5, expand: 1.9, repair: 0.25, liquidate: -0.7 },
        factors: { capacity: "ceiling", service: "ready", capital: "funded", runway: "15 days", trajectory: "cash lead" },
        title: "A cash lead can still hide a capacity ceiling.",
        copy: "Day 15: our farm has cash but one plot; the opponent already operates three.",
        decision: "Expand is preferred, then permitted only if the full land + production + labor bundle passes every gate.",
      },
      balanced: {
        attention: { operations: 1.0, opponent: 0.3, horizon: 0.55 },
        options: { compact: 1.5, expand: 0.1, repair: 0.6, liquidate: -0.8 },
        factors: { capacity: "open", service: "steady", capital: "useful", runway: "22 days", trajectory: "ahead" },
        title: "The current plot still has productive room.",
        copy: "Early game: both farms are compact, work is current, and another plot would dilute the engine.",
        decision: "Compact wins because existing capacity can still compound without adding service debt.",
      },
      service: {
        attention: { operations: 2.0, opponent: 0.0, horizon: 0.5 },
        options: { compact: 0.2, expand: -0.9, repair: 2.1, liquidate: -0.6 },
        factors: { capacity: "unused", service: "overdue", capital: "protected", runway: "16 days", trajectory: "at risk" },
        title: "Urgent work interrupts the strategy plan.",
        copy: "Care, harvest, or weeds are behind. Growth pauses until the farm can reliably operate what it owns.",
        decision: "Repair wins. Mandatory work can veto every growth preference.",
      },
      terminal: {
        attention: { operations: 0.35, opponent: 0.1, horizon: 1.65 },
        options: { compact: -0.1, expand: -1.4, repair: 0.1, liquidate: 2.0 },
        factors: { capacity: "irrelevant", service: "finish only", capital: "convert", runway: "2 days", trajectory: "realize" },
        title: "Only value reachable before the finish counts.",
        copy: "Day 28: new growth cannot repay. Hands route inventory to town and stop speculative reinvestment.",
        decision: "Liquidate wins because terminal cash, not unfinished productive potential, decides the match.",
      },
    };
    const architectureSteps = [
      ["Observe", "Compress the visible farm, town, opponent, and remaining clock."],
      ["Protect", "Reserve work that becomes irreversible if delayed."],
      ["Focus", "Allocate attention across operations, opponent evidence, and the horizon."],
      ["Propose", "Turn safe strategy scores into a probability distribution over four capital branches."],
      ["Judge", "Reprice each branch through capacity, service, capital, runway, and trajectory."],
      ["Execute", "Commit one safe action; rejected land cannot pull its dependent purchases through."],
      ["Reobserve", "Read the new state and recompute instead of blindly finishing an old forecast."],
    ];
    let architectureScenario = "capacity";
    let architectureStep = 0;
    let architectureTimer = null;

    function softmaxPercentages(values) {
      const entries = Object.entries(values);
      const maximum = Math.max(...entries.map(([, value]) => value));
      const weights = entries.map(([key, value]) => [key, Math.exp(value - maximum)]);
      const total = weights.reduce((sum, [, value]) => sum + value, 0);
      const result = Object.fromEntries(weights.map(([key, value]) => [key, Math.round((value / total) * 100)]));
      const difference = 100 - Object.values(result).reduce((sum, value) => sum + value, 0);
      const largest = weights.sort((a, b) => b[1] - a[1])[0][0];
      result[largest] += difference;
      return result;
    }

    function renderProbabilityGroup(kind, values) {
      const percentages = softmaxPercentages(values);
      Object.entries(percentages).forEach(([name, value]) => {
        const bar = $(`[data-${kind}-bar="${name}"]`, architectureLab);
        const label = $(`[data-${kind}-value="${name}"]`, architectureLab);
        if (bar) bar.style.width = `${value}%`;
        if (label) label.textContent = `${value}%`;
        if (bar?.parentElement) {
          bar.parentElement.setAttribute("role", "progressbar");
          bar.parentElement.setAttribute("aria-label", `${name} ${value} percent`);
          bar.parentElement.setAttribute("aria-valuemin", "0");
          bar.parentElement.setAttribute("aria-valuemax", "100");
          bar.parentElement.setAttribute("aria-valuenow", String(value));
        }
      });
      return percentages;
    }

    function renderArchitecture() {
      const scenario = architectureScenarios[architectureScenario];
      const step = architectureSteps[architectureStep];
      const optionProbabilities = renderProbabilityGroup("attention", scenario.attention);
      renderProbabilityGroup("option", scenario.options);
      $$('[data-architecture-step]', architectureLab).forEach((item) => {
        const index = Number(item.dataset.architectureStep);
        item.classList.toggle("is-active", index === architectureStep);
        item.classList.toggle("is-complete", index < architectureStep);
      });
      Object.entries(scenario.factors).forEach(([name, value]) => {
        const target = $(`[data-factor="${name}"]`, architectureLab);
        if (target) target.textContent = value;
      });
      $("#architecture-step-label").textContent = `Step ${String(architectureStep + 1).padStart(2, "0")} · ${step[0]}`;
      $("#architecture-state-title").textContent = architectureStep === 0 ? scenario.title : step[0];
      $("#architecture-state-copy").textContent = architectureStep === 0 ? scenario.copy : step[1];
      $("#architecture-decision").textContent = scenario.decision;
      architectureLab.dataset.step = String(architectureStep);
      architectureLab.dataset.dominantAttention = Object.entries(optionProbabilities).sort((a, b) => b[1] - a[1])[0][0];
    }

    function stopArchitecturePlayback() {
      if (architectureTimer) window.clearInterval(architectureTimer);
      architectureTimer = null;
      $("#architecture-play").textContent = architectureStep === architectureSteps.length - 1 ? "Replay decision" : "Play decision";
    }

    function playArchitecture() {
      stopArchitecturePlayback();
      architectureStep = 0;
      renderArchitecture();
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        architectureStep = architectureSteps.length - 1;
        renderArchitecture();
        stopArchitecturePlayback();
        return;
      }
      $("#architecture-play").textContent = "Playing…";
      architectureTimer = window.setInterval(() => {
        architectureStep += 1;
        renderArchitecture();
        if (architectureStep >= architectureSteps.length - 1) stopArchitecturePlayback();
      }, 720);
    }

    $$('[data-architecture-scenario]', architectureLab).forEach((button) => {
      button.addEventListener("click", () => {
        stopArchitecturePlayback();
        architectureScenario = button.dataset.architectureScenario;
        architectureStep = 0;
        $$('[data-architecture-scenario]', architectureLab).forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        renderArchitecture();
      });
    });
    $("#architecture-play").addEventListener("click", playArchitecture);
    $("#architecture-next").addEventListener("click", () => {
      stopArchitecturePlayback();
      architectureStep = (architectureStep + 1) % architectureSteps.length;
      renderArchitecture();
    });
    renderArchitecture();
  }

  // Balanced Tempo notebook
  const notebookTabs = $$('[data-notebook-tab]');
  const notebookPanels = $$('[data-notebook-panel]');
  notebookTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const activeId = tab.dataset.notebookTab;
      notebookTabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
      });
      notebookPanels.forEach((panel) => {
        panel.hidden = panel.dataset.notebookPanel !== activeId;
      });
    });
  });

  const balancedNotes = $("#balanced-working-notes");
  if (balancedNotes) {
    balancedNotes.value = readStore(KEYS.balancedNotes, "");
    balancedNotes.addEventListener("input", () => {
      writeStore(KEYS.balancedNotes, balancedNotes.value);
      $("#balanced-notes-status").textContent = "Saved in this browser";
    });
    $$('[data-challenge-prompt]').forEach((button) => {
      button.addEventListener("click", () => {
        balancedNotes.value = button.dataset.challengePrompt;
        writeStore(KEYS.balancedNotes, balancedNotes.value);
        balancedNotes.focus();
      });
    });
  }

  // Best-run daily replay
  const replay = window.BALANCED_BEST_RUN;
  const replayBoard = $("#replay-board");
  if (replay && replayBoard) {
    let replayIndex = 0;
    let replayTimer = null;
    const replayRange = $("#replay-range");
    const replayPlay = $("#replay-play");

    function formatSigned(value) {
      if (value === 0) return "0";
      return `${value > 0 ? "+" : "−"}${Math.abs(value).toLocaleString()}`;
    }

    function setCondition(id, progress, value, text, state = "active") {
      const item = $(`#condition-${id}`);
      const track = item.querySelector(".condition-track");
      $(`#condition-${id}-bar`).style.width = `${Math.max(0, Math.min(100, progress))}%`;
      $(`#condition-${id}-text`).textContent = text;
      track.setAttribute("aria-valuenow", String(Math.round(value)));
      item.classList.toggle("is-met", state === "met");
      item.classList.toggle("is-inactive", state === "inactive");
    }

    function stopReplay() {
      if (replayTimer) window.clearInterval(replayTimer);
      replayTimer = null;
      replayPlay.textContent = replayIndex === replay.days.length - 1 ? "Replay" : "Play fast";
    }

    function renderReplay(index) {
      replayIndex = Math.max(0, Math.min(replay.days.length - 1, Number(index)));
      const day = replay.days[replayIndex];
      const workersByCell = new Map();
      day.workers.forEach((worker) => {
        const key = worker.y * 10 + worker.x;
        workersByCell.set(key, [...(workersByCell.get(key) || []), worker]);
      });

      replayBoard.innerHTML = day.cells.map((code, cellIndex) => {
        const workers = workersByCell.get(cellIndex) || [];
        const workerDots = workers.map((worker) => `<i class="replay-worker ${worker.kind}" aria-hidden="true"></i>`).join("");
        return `<span class="replay-cell cell-${escapeHtml(code)}">${workerDots}</span>`;
      }).join("");
      replayBoard.setAttribute("aria-label", `Farm state on day ${day.day}. ${day.phase}. Bank ${day.bank.toLocaleString()} coins.`);
      $("#replay-phase").textContent = day.phase;
      $("#replay-day").textContent = String(day.day).padStart(2, "0");
      $("#replay-bank").textContent = day.bank.toLocaleString();
      $("#replay-opponent").textContent = day.opponent_bank.toLocaleString();
      $("#replay-margin").textContent = formatSigned(day.margin);
      $("#replay-shed").textContent = day.shed_units.toLocaleString();
      const scoreTotal = day.bank + day.opponent_bank;
      const scoreShare = scoreTotal > 0 ? (day.bank / scoreTotal) * 100 : 50;
      const leadText = day.margin === 0
        ? "tied"
        : `${day.margin > 0 ? "ahead" : "behind"} by ${Math.abs(day.margin).toLocaleString()}`;
      $("#win-current-status").textContent = `Day ${String(day.day).padStart(2, "0")} · ${leadText}`;
      setCondition("score", scoreShare, scoreShare, `${day.bank.toLocaleString()} vs ${day.opponent_bank.toLocaleString()} · ${leadText}`, day.margin > 0 ? "met" : "active");

      const cows = Number(day.assets.cow || 0);
      const strawberries = Number(day.assets.strawberry || 0);
      setCondition("cows", (cows / 4) * 100, cows, `${cows} / 4`, cows >= 4 ? "met" : "active");
      setCondition("strawberries", (strawberries / 15) * 100, strawberries, `${strawberries} / 15`, strawberries >= 15 ? "met" : "active");

      const exitDue = day.day >= 27;
      const exitProgress = exitDue ? 100 - Math.min(100, day.shed_units) : 0;
      const exitText = exitDue ? `${day.shed_units} unit${day.shed_units === 1 ? "" : "s"} remain` : "Not due until day 27";
      setCondition("exit", exitProgress, exitProgress, exitText, exitDue ? (day.shed_units === 0 ? "met" : "active") : "inactive");
      $("#replay-reason-title").textContent = day.reasoning.title;
      $("#replay-reason-text").textContent = day.reasoning.text;
      const notableOps = Object.entries(day.actions.unit_ops)
        .filter(([operation]) => !["PASS", "NORTH", "SOUTH", "EAST", "WEST"].includes(operation))
        .slice(0, 5)
        .map(([operation, count]) => `${operation} ${count}`);
      $("#replay-actions").textContent = notableOps.length ? notableOps.join(" · ") : "Movement and positioning";
      $("#replay-change").textContent = day.change;
      replayRange.value = String(replayIndex);
      $$('[data-replay-select]').forEach((button) => {
        const active = Number(button.dataset.replaySelect) === replayIndex;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-current", active ? "true" : "false");
      });
    }

    $("#replay-day-body").innerHTML = replay.days.map((day) => `
      <tr>
        <td><button type="button" class="replay-day-select" data-replay-select="${day.day}">${String(day.day).padStart(2, "0")}</button></td>
        <td>${escapeHtml(day.phase)}</td>
        <td>${day.bank.toLocaleString()}</td>
        <td>${formatSigned(day.bank_delta)}</td>
        <td>${escapeHtml(day.change)}</td>
        <td>${escapeHtml(day.reasoning.title)}</td>
      </tr>`).join("");

    $$('[data-replay-select]').forEach((button) => {
      button.addEventListener("click", () => {
        stopReplay();
        renderReplay(button.dataset.replaySelect);
      });
    });
    replayRange.addEventListener("input", () => {
      stopReplay();
      renderReplay(replayRange.value);
    });
    $("#replay-previous").addEventListener("click", () => {
      stopReplay();
      renderReplay(replayIndex - 1);
    });
    $("#replay-next").addEventListener("click", () => {
      stopReplay();
      renderReplay(replayIndex + 1);
    });
    replayPlay.addEventListener("click", () => {
      if (replayTimer) {
        stopReplay();
        return;
      }
      if (replayIndex === replay.days.length - 1) renderReplay(0);
      replayPlay.textContent = "Pause";
      replayTimer = window.setInterval(() => {
        if (replayIndex >= replay.days.length - 1) {
          stopReplay();
          return;
        }
        renderReplay(replayIndex + 1);
      }, 350);
    });
    notebookTabs.filter((tab) => tab.dataset.notebookTab !== "replay").forEach((tab) => tab.addEventListener("click", stopReplay));
    renderReplay(0);
  }

  // Deadline countdown
  const deadline = new Date("2026-09-30T23:59:00Z");
  const diff = deadline.getTime() - Date.now();
  const deadlineDays = Math.max(0, Math.ceil(diff / 86400000));
  $("#deadline-days").textContent = String(deadlineDays);

  // Readiness checklist
  const checklistState = readStore(KEYS.checklist, {});
  const checklistInputs = $$("[data-check]");
  checklistInputs.forEach((input) => {
    input.checked = Boolean(checklistState[input.dataset.check]);
    input.addEventListener("change", () => {
      checklistState[input.dataset.check] = input.checked;
      writeStore(KEYS.checklist, checklistState);
      renderChecklistProgress();
    });
  });

  function renderChecklistProgress() {
    const completed = checklistInputs.filter((input) => input.checked).length;
    $("#checklist-progress").textContent = `${completed} / ${checklistInputs.length} ready`;
    $("#checklist-progress-bar").style.width = `${(completed / checklistInputs.length) * 100}%`;
  }
  renderChecklistProgress();

  // First-submission release gate
  const submissionGateState = readStore(KEYS.submissionGate, {
    contract: true,
    fallback: true,
    selfplay: true,
    coverage: true,
    liquidation: true,
    version: true,
  });
  const submissionGateInputs = $$('[data-submit-check]');
  submissionGateInputs.forEach((input) => {
    input.checked = Boolean(submissionGateState[input.dataset.submitCheck]);
    input.addEventListener("change", () => {
      submissionGateState[input.dataset.submitCheck] = input.checked;
      writeStore(KEYS.submissionGate, submissionGateState);
      renderSubmissionGate();
    });
  });

  function renderSubmissionGate() {
    const completed = submissionGateInputs.filter((input) => input.checked).length;
    $("#submission-progress").textContent = `${completed} / ${submissionGateInputs.length} ready`;
    $("#submission-progress-bar").style.width = `${(completed / submissionGateInputs.length) * 100}%`;
  }
  renderSubmissionGate();

  // Farm explainer
  const farmModes = {
    routing: {
      kicker: "Routing lens",
      title: "Cut empty movement",
      text: "Cluster work by place and deadline.",
      bullets: ["Route through the shed", "Reserve care loops", "Replan at harvest"],
      legend: [["Worker route", "#c49450"], ["Shed access", "#8d6240"]],
    },
    crops: {
      kicker: "Crop lens",
      title: "Stagger crop clocks",
      text: "Flatten watering and harvest spikes.",
      bullets: ["Offset planting", "Collect fertilizer value", "Stop late planting"],
      legend: [["Active crop", "#c49450"], ["Shed access", "#8d6240"]],
    },
    animals: {
      kicker: "Animal lens",
      title: "Protect the feed loop",
      text: "Animals convert wheat into recurring yield.",
      bullets: ["Hold wheat reserve", "Harvest before full", "Collect useful fertilizer"],
      legend: [["Animal structure", "#b88342"], ["Shed access", "#8d6240"]],
    },
    expansion: {
      kicker: "Expansion lens",
      title: "Buy only with payback",
      text: "Land needs labor and time to earn.",
      bullets: ["Count remaining turns", "Pair land with labor", "Passable is not usable"],
      legend: [["Unlocked", "#4a4130"], ["Locked quadrant", "rgba(231,225,213,.12)"]],
    },
  };

  const routeCells = new Set([44, 43, 42, 32, 22, 23, 24, 25, 26, 36, 46, 56, 55, 54]);
  const cropCells = new Set([11, 12, 13, 21, 22, 23, 31, 32, 33, 16, 17, 26, 27]);
  const animalCells = new Set([61, 62, 71, 72, 66, 67, 76, 77]);
  const shedCells = new Set([44, 45, 54, 55]);

  function renderFarm(mode) {
    const board = $("#farm-board");
    board.innerHTML = "";
    for (let i = 0; i < 100; i += 1) {
      const cell = document.createElement("span");
      cell.className = "farm-cell";
      if (shedCells.has(i)) cell.classList.add("shed");
      if (mode === "routing" && routeCells.has(i) && !shedCells.has(i)) cell.classList.add("route");
      if (mode === "crops" && cropCells.has(i)) cell.classList.add("crop");
      if (mode === "animals" && animalCells.has(i)) cell.classList.add("animal");
      if (mode === "expansion" && (i % 10 >= 5 || Math.floor(i / 10) >= 5) && !shedCells.has(i)) cell.classList.add("locked");
      board.appendChild(cell);
    }

    const data = farmModes[mode];
    $("#farm-insight").innerHTML = `
      <p class="eyebrow">${data.kicker}</p>
      <h3>${data.title}</h3>
      <p>${data.text}</p>
      <ul>${data.bullets.map((item) => `<li>${item}</li>`).join("")}</ul>`;
    $("#board-legend").innerHTML = data.legend.map(([label, color]) => `
      <span class="legend-item"><span class="legend-swatch" style="background:${color}"></span>${label}</span>`).join("");
  }

  $("#farm-focus").addEventListener("change", (event) => renderFarm(event.target.value));
  renderFarm("routing");

  // Production reference
  const production = [
    { type: "crop", asset: "Wheat", buy: "10 seed", price: "25", first: "2 days", cadence: "One harvest; max at day 4", care: "Water daily" },
    { type: "crop", asset: "Carrot", buy: "20 seed", price: "35", first: "2 days", cadence: "One harvest; max at day 3", care: "Water daily" },
    { type: "crop", asset: "Tomato", buy: "50 seed", price: "60", first: "8 days", cadence: "Daily ×4, then decays", care: "Water daily" },
    { type: "crop", asset: "Strawberry", buy: "100 seed", price: "120", first: "10 days", cadence: "Every 2 days ×4", care: "Water daily" },
    { type: "crop", asset: "Melon", buy: "80 seed", price: "250", first: "10 days", cadence: "One harvest", care: "Water daily" },
    { type: "animal", asset: "Goose → egg", buy: "300 animal", price: "50", first: "4 days", cadence: "Daily, indefinite", care: "Feed wheat daily" },
    { type: "animal", asset: "Cow → milk", buy: "400 animal", price: "160", first: "8 days", cadence: "Every 2 days", care: "Feed wheat daily" },
    { type: "animal", asset: "Sheep → wool", buy: "500 animal", price: "200", first: "6 days", cadence: "Every 3 days", care: "Feed wheat daily" },
  ];

  function renderProduction(filter = "all") {
    const rows = filter === "all" ? production : production.filter((item) => item.type === filter);
    $("#production-body").innerHTML = rows.map((item) => `
      <tr>
        <td><span class="asset-name"><span class="asset-dot ${item.type}"></span>${item.asset}</span></td>
        <td>${item.buy}</td><td>${item.price} coins</td><td>${item.first}</td><td>${item.cadence}</td><td>${item.care}</td>
      </tr>`).join("");
  }
  $$('[data-production-filter]').forEach((button) => {
    button.addEventListener("click", () => {
      $$('[data-production-filter]').forEach((item) => item.classList.toggle("is-active", item === button));
      renderProduction(button.dataset.productionFilter);
    });
  });
  renderProduction();

  // Kaggle submission tracker
  const firstLadderEntries = [
    {
      id: "submission-v0-2-0",
      version: "v0.2.0",
      date: "2026-08-15",
      status: "error",
      episodes: 0,
      rating: null,
      rank: null,
      change: "First multi-file Kaggle upload",
      notes: "Validation failed before play: the generic agents package name collided with Kaggle's installed module.",
    },
    {
      id: "submission-v0-2-1",
      version: "v0.2.1",
      date: "2026-08-15",
      status: "active",
      episodes: 4,
      rating: 459.2,
      rank: 3536,
      peakRank: 3536,
      change: "Single-file artifact; same three-attention policy",
      notes: "Reviewed ladder snapshot: 1 win, 3 losses. Repeated gaps were fixed labor, weak response to shared markets, and a day-27 liquidation bug.",
    },
    {
      id: "submission-v0-6-1",
      version: "v0.6.1",
      date: "2026-08-15",
      status: "active",
      episodes: 18,
      rating: 562.2,
      rank: null,
      peakRank: 2891,
      change: "Economics, strategy utility, and bounded global routing",
      notes: "18 external matches: 9 wins and 9 losses. PQ_Marz loss exposed a cash-only blind spot while the opponent compounded productive assets.",
    },
    {
      id: "submission-v0-8-4",
      version: "v0.8.4",
      date: "2026-08-16",
      status: "complete",
      episodes: 0,
      rating: 609.7,
      rank: null,
      change: "Fixed-engine recognition and commitment-safe attention",
      notes: "The current highest public score among the recent submitted family; retained as evidence that a leaner engine still has useful ceiling.",
    },
    {
      id: "submission-v0-9-1-i4",
      version: "v0.9.1-i4",
      date: "2026-08-17",
      status: "active",
      episodes: 4,
      rating: 605.2,
      rank: null,
      change: "Sunk-capital-aware livestock allocation and survival-first service queue",
      notes: "Current Kaggle score is 605.2. The reviewed BeyondAnalytics loss had a −14,332 engine gap by day 22, followed by stranded seed capital and late wheat churn.",
    },
    {
      id: "submission-v1-0-0-alpha9",
      version: "v1.0.0-alpha9",
      date: "2026-08-17T00:01:00",
      status: "active",
      episodes: 4,
      rating: 647.3,
      rank: null,
      peakRank: null,
      change: "Four-day scenario MPC at the capital junction",
      notes: "Reviewed live snapshot: public score 647.3. The newest four visible games finished 1–3; Alpha9 stayed on one plot with six animals in every replay and lost to both one-plot density and funded land compounding.",
    },
  ];
  let submissions = readStore(KEYS.submissions, firstLadderEntries);
  if (!Array.isArray(submissions)) submissions = [];
  submissions = submissions.map((item) => {
    if (item.id === "submission-v0-2-1") {
      return { ...item, rating: 459.2, rank: 3536, episodes: Math.max(item.episodes || 0, 4) };
    }
    const seeded = firstLadderEntries.find((entry) => entry.id === item.id);
    if (seeded) return { ...item, ...seeded };
    return item;
  });
  firstLadderEntries.forEach((seeded) => {
    if (!submissions.some((item) => item.id === seeded.id)) submissions.push(seeded);
  });
  writeStore(KEYS.submissions, submissions);
  const submissionDialog = $("#submission-dialog");
  const submissionForm = $("#submission-form");

  function openSubmissionDialog() {
    submissionForm.elements.date.value = new Date().toISOString().slice(0, 10);
    submissionDialog.showModal();
    setTimeout(() => submissionForm.elements.version.focus(), 0);
  }

  $("#open-submission-form").addEventListener("click", openSubmissionDialog);
  $$('[data-open-submission]').forEach((button) => button.addEventListener("click", openSubmissionDialog));
  $("#close-submission-dialog").addEventListener("click", () => submissionDialog.close());
  $("#cancel-submission").addEventListener("click", () => submissionDialog.close());

  submissionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(submissionForm);
    submissions.push({
      id: makeId("submission"),
      version: String(data.get("version")).trim(),
      date: String(data.get("date")),
      status: String(data.get("status")),
      episodes: Number(data.get("episodes") || 0),
      rating: data.get("rating") === "" ? null : Number(data.get("rating")),
      rank: data.get("rank") === "" ? null : Number(data.get("rank")),
      change: String(data.get("change")).trim(),
      notes: String(data.get("notes")).trim(),
    });
    writeStore(KEYS.submissions, submissions);
    submissionForm.reset();
    submissionDialog.close();
    renderSubmissions();
  });

  function renderSubmissionAnalysis(sorted) {
    const analysis = $("#submission-analysis");
    if (!sorted.length) {
      analysis.innerHTML = `
        <article><span>Signal</span><strong>No ladder data yet</strong><p>Submit the interpretable baseline, then log its first rating and rank.</p></article>
        <article><span>Confidence</span><strong>Unknown</strong><p>Early ratings move quickly; wait for more episodes before making a large rewrite.</p></article>
        <article><span>Next read</span><strong>Loss replays</strong><p>Classify the opponent opening and identify the first irreversible mistake.</p></article>`;
      return;
    }
    const latest = sorted.at(-1);
    const previous = sorted.length > 1 ? sorted.at(-2) : null;
    let signalTitle = "Baseline established";
    let signalText = "Use this version as the comparison point for the next single-mechanism change.";
    if (latest.status === "error") {
      signalTitle = "Validation failure";
      signalText = "Fix the runtime or action contract before interpreting strategy quality.";
    } else if (latest.id === "submission-v0-6-1" && latest.episodes < 10) {
      signalTitle = "Accepted, sample pending";
      signalText = "The current score is seeded by validation self-play; wait for external opponents before comparing strategy quality.";
    } else if (latest.rating != null && previous?.rating != null) {
      const delta = latest.rating - previous.rating;
      signalTitle = `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} rating`;
      signalText = delta >= 0
        ? "The latest version is moving upward; inspect whether the improvement holds across more episodes."
        : "The latest version is moving downward; classify losses before choosing which mechanism to change.";
    }
    const confidenceTitle = latest.episodes < 50 ? "Low sample" : latest.episodes < 200 ? "Developing" : "Useful signal";
    const confidenceText = latest.episodes < 50
      ? "Treat early ladder movement as noisy and avoid a broad rewrite."
      : latest.episodes < 200
        ? "Look for repeated opponent archetypes and recurring failure modes."
        : "The sample is large enough to prioritize stable patterns over isolated replays.";
    analysis.innerHTML = `
      <article><span>Signal</span><strong>${escapeHtml(signalTitle)}</strong><p>${escapeHtml(signalText)}</p></article>
      <article><span>Confidence</span><strong>${escapeHtml(confidenceTitle)}</strong><p>${escapeHtml(confidenceText)}</p></article>
      <article><span>Next read</span><strong>First divergence</strong><p>Find the earliest turn where the losing replay stopped matching the intended plan.</p></article>`;
  }

  function renderSubmissions() {
    const sorted = [...submissions].sort((a, b) => new Date(a.date) - new Date(b.date));
    const ratings = submissions.filter((item) => item.rating != null);
    const ranks = submissions.flatMap((item) => {
      const value = item.rank ?? item.peakRank;
      return value == null ? [] : [value];
    });
    const bestRating = ratings.length ? [...ratings].sort((a, b) => b.rating - a.rating)[0] : null;
    const bestRank = ranks.length ? Math.min(...ranks) : null;
    $("#submission-count").textContent = String(submissions.length);
    $("#submission-best-rating").textContent = bestRating ? bestRating.rating.toFixed(1) : "—";
    $("#submission-best-version").textContent = bestRating ? `from ${bestRating.version}` : "no data yet";
    $("#submission-best-rank").textContent = bestRank == null ? "—" : `#${bestRank.toLocaleString()}`;
    $("#submission-episodes").textContent = submissions.reduce((sum, item) => sum + item.episodes, 0).toLocaleString();
    $("#submission-body").innerHTML = [...sorted].reverse().map((item) => `
      <tr>
        <td><strong>${escapeHtml(item.version)}</strong><small>${escapeHtml(item.change)}</small></td>
        <td>${escapeHtml(item.date)}</td>
        <td><span class="submission-status ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
        <td>${item.rating == null ? "—" : item.rating.toFixed(1)}</td>
        <td>${item.rank == null ? "—" : `#${item.rank.toLocaleString()}`}</td>
        <td>${item.episodes.toLocaleString()}</td>
        <td>${escapeHtml(item.notes || "—")}</td>
        <td><button class="delete-button" type="button" aria-label="Delete ${escapeHtml(item.version)}" data-delete-submission="${item.id}">×</button></td>
      </tr>`).join("");
    const empty = submissions.length === 0;
    $("#submission-empty").hidden = !empty;
    $("#submission-table-wrap").hidden = empty;
    $$('[data-delete-submission]').forEach((button) => {
      button.addEventListener("click", () => {
        submissions = submissions.filter((item) => item.id !== button.dataset.deleteSubmission);
        writeStore(KEYS.submissions, submissions);
        renderSubmissions();
      });
    });
    renderSubmissionAnalysis(sorted);
  }

  // Frozen agent lineage
  const seededAgents = [
    {
      id: "agent-v0-2-1",
      version: "v0.2.1",
      date: "2026-08-15",
      status: "submitted",
      evidence: "Kaggle 1–3 reviewed · live score 459.2 · rank #3,536",
      model: "Fixed three-attention baseline; accepted single-file artifact.",
      limitation: "Fixed labor and crop responses; liquidation sold feed and stopped operating.",
    },
    {
      id: "agent-v0-3-0",
      version: "v0.3.0",
      date: "2026-08-15",
      status: "retired",
      evidence: "Local 19–1 · invalidated",
      model: "Phase gates, fertilizer collection, feed reserve, and target reservation.",
      limitation: "Days 28–29 silently fell back to PASS because closeout variables were undefined.",
    },
    {
      id: "agent-v0-3-1",
      version: "v0.3.1",
      date: "2026-08-15",
      status: "frozen",
      evidence: "Local 20–0 · +13,439 avg",
      model: "v0.3 phase policy with verified non-fallback final execution.",
      limitation: "Only tested against one frozen strategy family; not ready for Kaggle.",
    },
    {
      id: "agent-v0-4-0",
      version: "v0.4.0",
      date: "2026-08-15",
      status: "frozen",
      evidence: "Held-out 100–0 · worst margin +1,380",
      model: "Weighted strategy beliefs plus dynamic operations, opponent, and horizon attention.",
      limitation: "Ready against submitted v0.2.1; still one opponent family, so broader ladder generalization is unproven.",
    },
    {
      id: "agent-v0-5-1",
      version: "v0.5.1",
      date: "2026-08-15",
      status: "frozen",
      evidence: "v0.4: 19-1 | v0.2.1: 20-0",
      model: "Dense opponent archetypes, town-demand and crop ROI forecasts, mixed portfolio, capacity lookahead, and obstruction recovery.",
      limitation: "Hold: seed 5 seat 0 still loses to v0.4 by 2,719; requires 20 / 20 before promotion.",
    },
    {
      id: "agent-v0-6-0",
      version: "v0.6.0",
      date: "2026-08-15",
      status: "retired",
      evidence: "v0.5.1: 12-8 | average +324",
      model: "Reverse terminal-state planner with payoff reachability, feed and care cutoffs, travel slack, capacity checks, and demand-timed liquidation.",
      limitation: "Aggregate improvement only; eight losses and a -2,999 worst margin failed the 20 / 20 promotion rule.",
    },
    {
      id: "agent-v0-6-1",
      version: "v0.6.1",
      date: "2026-08-15",
      status: "submitted",
      evidence: "Kaggle 9–9 external · current score 562.2",
      model: "Marginal crop/livestock economics, expected-utility strategy grouping, profitable fertilizer use, and bounded global worker routing.",
      limitation: "PQ_Marz exposed a cash-only blind spot: the opponent built a 28-animal engine while our visible bank still led.",
    },
    {
      id: "agent-v0-7-0",
      version: "v0.7.0",
      date: "2026-08-16",
      status: "candidate",
      evidence: "v0.6.1: 7–7–6 · +104 avg · 12.8 KB artifact",
      model: "Within-match opponent memory, temporal Bayesian beliefs, productive-asset threat, asset-aware valuation, and sparse daily telemetry.",
      limitation: "Parity is not superiority; test more unfamiliar strategy families before submission. Naive second-quadrant expansion was rejected 0–4.",
    },
    {
      id: "agent-v0-7-1",
      version: "v0.7.1-i5",
      date: "2026-08-16",
      status: "frozen",
      evidence: "v0.7.0 exact gate: 20–0 · +5,685 avg · worst +380",
      model: "Dynamic wheat and labor reserves, sticky hand routes, bounded purchases, three-day opponent forecast, crop×livestock diagnostics, and terminal-aware resource pickup.",
      limitation: "Locally promoted over v0.7.0, but the mixed-conversion persona still wins both seats by 13,434; hold the Kaggle submission until that strategy family is understood.",
    },
    {
      id: "agent-v0-7-2",
      version: "v0.7.2",
      date: "2026-08-16",
      status: "candidate",
      evidence: "frontier arena: 1–7 | v0.7.1-i5: 0–2, −1,755 avg",
      model: "Replay-derived frontier cascade, land payback gates, mixed livestock targets, protected expansion crew, twelve-hand service cap, and trajectory milestone training signals.",
      limitation: "Experimental only: the high-cap branch approaches the frontier proxy but loses broadly to lean engines and never reaches 60k by day 24. Keep v0.7.1-i5 as control.",
    },
    {
      id: "agent-v0-8-0",
      version: "v0.8.0",
      date: "2026-08-16",
      status: "candidate",
      evidence: "matched arena: +749 avg lift | fixed control: 1–1, zero avg",
      model: "Promoted lean core plus a cached daily lean/selective/frontier selector, service and payback gates, hysteresis, and bounded dense-worker routing.",
      limitation: "Held: targeted arena remains 1–5, frontier response does not outperform the lean control, and the 767 ms worst action misses the 700 ms gate.",
    },
    {
      id: "agent-v0-8-1",
      version: "v0.8.1",
      date: "2026-08-16",
      status: "candidate",
      evidence: "matched v0.8.0 arena: +482 avg · 3 improved · 5 unchanged",
      model: "Lean v0.8 core plus a day-12 six-path crop×livestock ensemble, three-day vote stability, locked engine commitment, and animal-family service caps.",
      limitation: "Held: the paired arena still finishes 1–7, no run reaches the 60k milestone, and one combined suite hit the environment deadline before its isolated rerun completed normally.",
    },
    {
      id: "agent-v0-8-2",
      version: "v0.8.2",
      date: "2026-08-16",
      status: "candidate",
      evidence: "v0.8.0 exact gate: 4–10–6 · +440 avg · worst −1,265",
      model: "Operative operations/opponent/horizon attention, daily four-strategy softmax, corrected pre-hire service pressure, and stable day-12 engine-family commitment.",
      limitation: "Do not submit: it failed the required 20–0 gate. One +4,650 seed drives the positive average while ten episodes lose and six tie.",
    },
    {
      id: "agent-v0-8-3",
      version: "v0.8.3",
      date: "2026-08-16",
      status: "candidate",
      evidence: "v0.8.0 comparable gate: 4–2–14 · +495 avg · worst −1,215",
      model: "v0.8.2 attention and softmax plus commitment-safe crop memory that prevents temporary midgame votes from creating stranded seed inventory.",
      limitation: "More reliable than v0.8.2, but not submission-ready: fourteen ties and two losses still fail the required 20–0 gate.",
    },
    {
      id: "agent-v0-8-4",
      version: "v0.8.4",
      date: "2026-08-16",
      status: "submitted",
      evidence: "Kaggle live: 590.5 · rank 3,095 · visible recent record 3–2",
      model: "Public-state fixed-engine recognition, commitment-safe attention, and a sticky fifth-cow best response learned from crop and livestock counterfactuals.",
      limitation: "Live evaluation confirms volatility. A recent loss to Vignesh's early livestock engine ended 43,351–77,597; the delayed day-10 recognition is too late against immediate compounding.",
    },
    {
      id: "agent-v0-8-5",
      version: "v0.8.5",
      date: "2026-08-17",
      status: "candidate",
      evidence: "Sarthak proxy 2–0 · Vignesh proxy 0–2 · v0.8.4 control 2–4",
      model: "Animal-first compound opener: four cows, compact wheat/melon support, day-5 staged land, dynamic livestock scoring, and bounded worker routing.",
      limitation: "Held. It improves the Vignesh deficit by 3,053 and beats the Sarthak proxy, but averages −3,146 against exact v0.8.4 and still loses both Vignesh seats.",
    },
    {
      id: "agent-v0-9-0",
      version: "v0.9.0",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.7.1-i5: 20–0 · v0.8.4: 20–0 · +9,119 weakest-gate avg",
      model: "Top-ladder mixed opener, staged three-quadrant core, environment-driven cow/sheep tilt, market-cap-safe land execution, persistent late feed, and bounded routing.",
      limitation: "Locally promoted, not submitted. The narrowest control wins are +235 and +335, and public top-ladder evidence covers ten ranked-team perspectives rather than every strategy family.",
    },
    {
      id: "agent-v0-9-1",
      version: "v0.9.1-i4",
      date: "2026-08-17",
      status: "submitted",
      evidence: "Kaggle latest window: 3–1 · score 625.7 | Beyond loss −20,738",
      model: "v0.9 core plus sunk-capital-aware livestock allocation and a survival-first service queue that protects feed and care before routine watering.",
      limitation: "Beyond led by 14,332 on day 22 with a larger strawberry/sheep engine; terminal stranded seeds and late wheat churn widened the final loss. Core growth remains the primary gap.",
    },
    {
      id: "agent-v0-9-2-i1",
      version: "v0.9.2-i1",
      date: "2026-08-17",
      status: "candidate",
      evidence: "seed 2200: 2–0 · preregistered weighted arena: 12–0 · +24,466 avg",
      model: "Remembered recurring-density milestones, bounded additive town-schema restructuring, and an RL-ready weighted random-seed training harness.",
      limitation: "Keep frozen while the corrected all-style curriculum runs. The seed-2200 seat-1 margin remains only +64, and the first weighted draw covered five of eight styles.",
    },
    {
      id: "agent-v1-0-0-alpha3",
      version: "v1.0.0-alpha3",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.9 series: 14–6 · +13,772 avg · worst −8,666",
      model: "Proven mixed opener plus a daily compact/expand/repair/liquidate softmax over bundle funding, productive utilization, service slack, weeds, town support, opponent land, and horizon.",
      limitation: "Held. It sweeps v0.9.0 but goes 4–4 against submitted v0.9.1-i4 and 2–2 against v0.9.2-i1; seeds 2700 and 2703 require junction-trace calibration before submission.",
    },
    {
      id: "agent-v1-0-0-alpha4",
      version: "v1.0.0-alpha4",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.9.2-i1: 6–4 · +7,395 avg | mini arena: 8–0 · 0 failures",
      model: "Alpha3 junction controller plus terminal reachability for seed purchases, planting, inventory holds, and finish/convert/liquidate diagnostics.",
      limitation: "Held. It improves the exact Beyond seed by 137, but slightly trails alpha3 on their shared 2700–2701 panel and still loses both seats on seeds 2700 and 2703.",
    },
    {
      id: "agent-v1-0-0-alpha5",
      version: "v1.0.0-alpha5",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.9.2-i1: 10–0 · +7,830 avg · +2,075 worst | arena: 8–0",
      model: "Alpha4 plus a scored midgame expansion confirmation: 64% productive density or repeated town demand before another capital bundle can win.",
      limitation: "Local front runner, held for a fresh 20-game release gate. It ties alpha4 directly in 12 paired games and is not yet evidence of universal dominance.",
    },
    {
      id: "agent-v1-0-0-alpha6",
      version: "v1.0.0-alpha6",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.9.2 + Beyond: 10–0 · +7,830 avg | six-style arena: 12–0 · 360 rows",
      model: "Alpha5 plus a constant-time favorable/base/adverse option-value head for the daily compact, expand, repair, and liquidate junction.",
      limitation: "Held. Direct alpha5 evidence is neutral (1–1–2 at zero average); the decision-tree dataset is prepared but no learned scorer has been fitted or promoted.",
    },
    {
      id: "agent-v1-0-0-alpha7",
      version: "v1.0.0-alpha7",
      date: "2026-08-17",
      status: "candidate",
      evidence: "v0.9.2 + Beyond: 10–0 · +7,830 avg · +2,075 worst | arena: 12–0",
      model: "Alpha6 plus an asymmetric counterfactual-regret veto that can release a stale expansion commitment before service damage appears.",
      limitation: "Held. Fresh direct panels net to zero versus Alpha6 and Alpha5; the broader all-commitment break was rejected after losing the Beyond control.",
    },
    {
      id: "agent-v1-0-0-alpha9",
      version: "v1.0.0-alpha9",
      date: "2026-08-17",
      status: "submitted",
      evidence: "Kaggle snapshot: score 647.3 · newest visible games 1–3 | local release gate 20–0",
      model: "Four-day scenario MPC compares compact, expand, repair, and liquidate under funding, density, service, weed, and payback constraints.",
      limitation: "Latest losses show two capacity ceilings: a denser one-plot livestock engine and funded three-to-four-plot compounding can both overtake an apparent cash lead.",
    },
    {
      id: "agent-v1-1-0-alpha2",
      version: "v1.1.0-alpha2",
      date: "2026-08-17",
      status: "candidate",
      evidence: "Alpha9 short gate 8–0 · fresh gate 11–0–6 partial · observed-loss proxies 4–0 · 53 tests",
      model: "Interruptible engine options plus a constant-time auxiliary value head for capacity, service, capital, runway, and trajectory.",
      limitation: "Promising local candidate, not submitted. The fresh Alpha9 panel stopped at 17/20 with six ties, so it cannot satisfy the strict 20–0 promotion rule.",
    },
    {
      id: "agent-v1-1-0-alpha3-i2",
      version: "v1.1.0-alpha3-i2",
      date: "2026-08-17",
      status: "candidate",
      evidence: "Alpha9 16–4 · v0.9.2 8–0 · five-style arena 10–0 · 55 tests",
      model: "Alpha2 plus a parity-gated proactive saturation permit that releases a stale compact commitment only when density, funding, service, runway, value, and MPC agree.",
      limitation: "Held. The mean improves, but seeds 3302 and 3304 lose both seats; the current four-day MPC does not price enough downstream variance after early land.",
    },
    {
      id: "agent-v1-1-0-alpha4",
      version: "v1.1.0-alpha4",
      date: "2026-08-17",
      status: "candidate",
      evidence: "Alpha9 12–0–8 · eight-style arena 8–0 · 58 tests",
      model: "Alpha3's proactive saturation path is staged for one observation, with a cash reserve and distributional expected, lower-tail, adverse, and spread checks before expansion commits.",
      limitation: "Held. It removes Alpha3's four direct losses but leaves eight ties; the persona arena never triggers early expansion or a day-24 60k bank, so coverage is not yet representative.",
    },
    {
      id: "agent-v1-1-0-alpha5",
      version: "v1.1.0-alpha5",
      date: "2026-08-17",
      status: "candidate",
      evidence: "Alpha9 20–0 · Alpha4 8–2 · eight-style arena 8–0 · 62 tests",
      model: "Risk-adjusted mixture of lean liquidity, dense one-plot livestock, and staged land compounding, with a baseline confidence shield and path-specific farm geometry.",
      limitation: "Submission-qualified against Alpha9, locally held. Alpha4 still wins seed 3304 in both seats by 221 because Alpha5 buys livestock faster than it converts shed inventory into productive slots.",
    },
  ];
  let agentArchive = readStore(KEYS.agentArchive, seededAgents);
  if (!Array.isArray(agentArchive)) agentArchive = [...seededAgents];
  agentArchive = agentArchive.map((item) => {
    const seeded = seededAgents.find((candidate) => candidate.id === item.id);
    return seeded ? { ...item, ...seeded } : item;
  });
  seededAgents.forEach((seeded) => {
    if (!agentArchive.some((item) => item.id === seeded.id)) agentArchive.push(seeded);
  });
  writeStore(KEYS.agentArchive, agentArchive);
  const agentDialog = $("#agent-dialog");
  const agentForm = $("#agent-form");

  function openAgentDialog() {
    agentForm.elements.date.value = new Date().toISOString().slice(0, 10);
    agentDialog.showModal();
    setTimeout(() => agentForm.elements.version.focus(), 0);
  }

  $("#open-agent-form").addEventListener("click", openAgentDialog);
  $("#close-agent-dialog").addEventListener("click", () => agentDialog.close());
  $("#cancel-agent").addEventListener("click", () => agentDialog.close());
  agentForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(agentForm);
    agentArchive.push({
      id: makeId("agent"),
      version: String(data.get("version")).trim(),
      date: String(data.get("date")),
      status: String(data.get("status")),
      evidence: String(data.get("evidence")).trim(),
      model: String(data.get("model")).trim(),
      limitation: String(data.get("limitation")).trim(),
    });
    writeStore(KEYS.agentArchive, agentArchive);
    agentForm.reset();
    agentDialog.close();
    renderAgentArchive();
  });

  function renderAgentArchive() {
    $("#agent-lineage").innerHTML = [...agentArchive].reverse().map((item) => `
      <article data-status="${escapeHtml(item.status)}">
        <div class="agent-version"><span>${escapeHtml(item.status)}</span><strong>${escapeHtml(item.version)}</strong><small>${escapeHtml(item.date)}</small></div>
        <div><span>Core model</span><p>${escapeHtml(item.model)}</p></div>
        <div><span>Evidence</span><p>${escapeHtml(item.evidence)}</p></div>
        <div><span>Known limitation</span><p>${escapeHtml(item.limitation)}</p></div>
        <button class="delete-button" type="button" aria-label="Delete ${escapeHtml(item.version)}" data-delete-agent="${escapeHtml(item.id)}">×</button>
      </article>`).join("");
    $("#agent-lineage-empty").hidden = agentArchive.length > 0;
    $$('[data-delete-agent]').forEach((button) => {
      button.addEventListener("click", () => {
        agentArchive = agentArchive.filter((item) => item.id !== button.dataset.deleteAgent);
        writeStore(KEYS.agentArchive, agentArchive);
        renderAgentArchive();
      });
    });
  }

  // Experiments
  let experiments = readStore(KEYS.experiments, []);
  if (!Array.isArray(experiments)) experiments = [];

  const experimentDialog = $("#experiment-dialog");
  const experimentForm = $("#experiment-form");

  function openExperimentDialog() {
    $("#experiment-form-error").textContent = "";
    experimentDialog.showModal();
    setTimeout(() => experimentForm.elements.version.focus(), 0);
  }
  $("#open-experiment-form").addEventListener("click", openExperimentDialog);
  $$('[data-open-experiment]').forEach((button) => button.addEventListener("click", openExperimentDialog));
  const policyHypotheses = {
    balanced: "Balanced tempo: melon cash loop into cattle and strawberries, then early liquidation",
  };
  $$('[data-policy-test]').forEach((button) => {
    button.addEventListener("click", () => {
      const policy = button.dataset.policyTest;
      showView("experiments");
      openExperimentDialog();
      experimentForm.elements.hypothesis.value = policyHypotheses[policy] || "";
      experimentForm.elements.opponent.value = "starter";
    });
  });
  $("#close-experiment-dialog").addEventListener("click", () => experimentDialog.close());
  $("#cancel-experiment").addEventListener("click", () => experimentDialog.close());

  function winRate(item) {
    return item.games > 0 ? ((item.wins + item.ties * 0.5) / item.games) * 100 : 0;
  }

  experimentForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(experimentForm);
    const games = Number(data.get("games"));
    const wins = Number(data.get("wins"));
    const losses = Number(data.get("losses"));
    const ties = Number(data.get("ties"));
    if (wins + losses + ties !== games) {
      $("#experiment-form-error").textContent = "Wins + losses + ties must equal the number of episodes.";
      return;
    }
    experiments.push({
      id: makeId("exp"),
      createdAt: new Date().toISOString(),
      version: String(data.get("version")).trim(),
      opponent: String(data.get("opponent")).trim(),
      hypothesis: String(data.get("hypothesis")).trim(),
      games, wins, losses, ties,
      bank: data.get("bank") === "" ? null : Number(data.get("bank")),
      result: String(data.get("result")),
      notes: String(data.get("notes")).trim(),
    });
    writeStore(KEYS.experiments, experiments);
    experimentForm.reset();
    experimentForm.elements.games.value = 20;
    experimentForm.elements.wins.value = 0;
    experimentForm.elements.losses.value = 0;
    experimentForm.elements.ties.value = 0;
    experimentDialog.close();
    renderExperiments();
    renderRoadmap();
  });

  $("#experiment-sort").addEventListener("change", renderExperiments);

  function renderExperiments() {
    const sort = $("#experiment-sort").value;
    const sorted = [...experiments].sort((a, b) => {
      if (sort === "winrate") return winRate(b) - winRate(a);
      if (sort === "games") return b.games - a.games;
      return new Date(b.createdAt) - new Date(a.createdAt);
    });

    const totalGames = experiments.reduce((sum, item) => sum + item.games, 0);
    const best = experiments.length ? [...experiments].sort((a, b) => winRate(b) - winRate(a))[0] : null;
    const latest = experiments.length ? [...experiments].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))[0] : null;
    $("#stat-experiments").textContent = String(experiments.length);
    $("#stat-games").textContent = totalGames.toLocaleString();
    $("#stat-win-rate").textContent = best ? `${winRate(best).toFixed(1)}%` : "—";
    $("#stat-best-version").textContent = best ? `from ${best.version}` : "no data yet";
    $("#stat-bank").textContent = latest?.bank != null ? Math.round(latest.bank).toLocaleString() : "—";

    $("#experiment-list").innerHTML = sorted.map((item) => `
      <article class="experiment-entry">
        <span class="version-chip">${escapeHtml(item.version)}</span>
        <div class="entry-main">
          <h3>${escapeHtml(item.hypothesis)}</h3>
          <p>vs. ${escapeHtml(item.opponent)} · ${item.wins}W / ${item.losses}L / ${item.ties}T${item.notes ? ` · ${escapeHtml(item.notes)}` : ""}</p>
          <span class="result-badge ${escapeHtml(item.result)}">${escapeHtml(item.result)}</span>
        </div>
        <div class="entry-rate"><strong>${winRate(item).toFixed(1)}%</strong><span>outcome rate · ${item.games} episodes</span></div>
        <div class="entry-bank"><strong>${item.bank == null ? "—" : Math.round(item.bank).toLocaleString()}</strong><span>avg bank</span></div>
        <button class="delete-button" type="button" aria-label="Delete ${escapeHtml(item.version)}" data-delete-experiment="${item.id}">×</button>
      </article>`).join("");

    const empty = experiments.length === 0;
    $("#experiment-empty").hidden = !empty;
    $("#experiment-list").hidden = empty;
    $$('[data-delete-experiment]').forEach((button) => {
      button.addEventListener("click", () => {
        experiments = experiments.filter((item) => item.id !== button.dataset.deleteExperiment);
        writeStore(KEYS.experiments, experiments);
        renderExperiments();
      });
    });
    renderExperimentChart();
  }

  function renderExperimentChart() {
    const chart = $("#experiment-chart");
    const empty = $("#experiment-chart-empty");
    if (!experiments.length) {
      chart.hidden = true;
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    chart.hidden = false;
    const ordered = [...experiments].sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
    const w = 960, h = 310, left = 52, right = 25, top = 34, bottom = 52;
    const plotW = w - left - right, plotH = h - top - bottom;
    const x = (index) => left + (ordered.length === 1 ? plotW / 2 : (index / (ordered.length - 1)) * plotW);
    const y = (value) => top + plotH - (value / 100) * plotH;
    const points = ordered.map((item, index) => ({ x: x(index), y: y(winRate(item)), value: winRate(item), label: item.version }));
    const path = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const area = `${path} L${points.at(-1).x.toFixed(1)},${(top + plotH).toFixed(1)} L${points[0].x.toFixed(1)},${(top + plotH).toFixed(1)} Z`;
    const grid = [0, 25, 50, 75, 100].map((value) => `
      <line class="chart-gridline" x1="${left}" y1="${y(value)}" x2="${w-right}" y2="${y(value)}" />
      <text class="chart-label" x="${left-10}" y="${y(value)+4}" text-anchor="end">${value}%</text>`).join("");
    const marks = points.map((point, index) => `
      <circle class="chart-point" cx="${point.x}" cy="${point.y}" r="5"><title>${escapeHtml(point.label)}: ${point.value.toFixed(1)}%</title></circle>
      <text class="chart-value" x="${point.x}" y="${Math.max(18, point.y-13)}" text-anchor="middle">${point.value.toFixed(0)}%</text>
      <text class="chart-label" x="${point.x}" y="${h-22}" text-anchor="middle">${escapeHtml(point.label.slice(0, 12))}</text>`).join("");
    chart.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Outcome rate across ${ordered.length} recorded agent versions">
        <defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c49450" stop-opacity=".35"/><stop offset="1" stop-color="#c49450" stop-opacity="0"/></linearGradient></defs>
        ${grid}<path class="chart-area" d="${area}"/><path class="chart-path" d="${path}"/>${marks}
      </svg>`;
  }

  $("#export-experiments").addEventListener("click", () => {
    const payload = JSON.stringify({ exportedAt: new Date().toISOString(), competition: "kaggriculture", experiments }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `kaggriculture-experiments-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  // Roadmap
  const starterRoadmap = [
    { id: "v2-core-economy", title: "v2.0 opponent-light economy core", description: "v2d pairs an own-economy land gate with a selective recurring-density handoff. The first pressure shard improved both tested families; freeze those seeds and validate on a new holdout.", impact: 5, confidence: 4, effort: 3, status: "testing" },
    { id: "v2-staggered-close", title: "Stagger the late production cohort", description: "Replace expiring recurring crops around days 18–21 only when projected terminal value clears the labor, weed, harvest, and liquidation cost. The forced day-22 wheat wave was rejected.", impact: 5, confidence: 4, effort: 3, status: "planned" },
    { id: "v2-productive-slot", title: "v2.0 productive-slot scheduler", description: "The core mode now authorizes land from our own utilization, service slack, payback, and market conditions. Add day-15 density and weed gates before promotion.", impact: 5, confidence: 5, effort: 3, status: "testing" },
    { id: "v2-counterfactual-teacher", title: "v2.0 counterfactual search teacher", description: "The first 1,821-junction, 81-episode replay corpus is seed-split and prioritized. Exact 32–128 rollout labels are the next step; logged returns alone cannot promote a policy.", impact: 5, confidence: 4, effort: 4, status: "testing" },
    { id: "v2-human-arena", title: "Human reinforcement arena", description: "Play the exact environment against frozen Alpha5, annotate high-value deviations, and save transition-complete episodes for offline replay without mutating the live opponent.", impact: 4, confidence: 4, effort: 3, status: "testing" },
    { id: "v2-distilled-tree", title: "v2.0 distilled junction tree", description: "Export a shallow tree ensemble for option value, downside, deployment lag, and closing conversion behind the Alpha5 confidence shield.", impact: 5, confidence: 4, effort: 4, status: "planned" },
    { id: "v2-residual-model", title: "v2.0 residual value model", description: "Keep game rules explicit and learn only persistent four-day errors in cash, service debt, productive density, and terminal value.", impact: 4, confidence: 3, effort: 4, status: "planned" },
    { id: "v2-adversarial-league", title: "v2.0 adversarial league", description: "Run a capped holdout against Alpha4, Alpha5, Alpha9, and lean, dense, land-rush, town, weed, and closing specialists; persist every live loss as a regression cell.", impact: 5, confidence: 4, effort: 3, status: "planned" },
    { id: "v1-transition-data", title: "Transition-complete training data", description: "Record daily branch, planned labor, capital quantities, next state, terminal boundary, and outcome; guarantee every selected style appears before weighted repeats.", impact: 5, confidence: 5, effort: 2, status: "testing" },
    { id: "v092-town-restructure", title: "Bounded town-schema restructuring", description: "Fix seed 2200: remember the recurring milestone, open serviceable third land, add the favored engine, and liquidate declining products without discarding productive assets.", impact: 5, confidence: 5, effort: 2, status: "testing" },
    { id: "v093-capital-mpc", title: "Finite-horizon capital allocator", description: "Compare the next coin across land, livestock, crops, hands, feed, and liquidity using service-adjusted terminal value.", impact: 5, confidence: 4, effort: 5, status: "planned" },
    { id: "v094-dense-routing", title: "Prove productive density", description: "Add zone ownership, urgent min-cost matching, and completion telemetry before testing 24, 32, and 42 serviceable plots.", impact: 5, confidence: 4, effort: 4, status: "planned" },
    { id: "v095-learned-selector", title: "Offline learned branch scorer", description: "Train a compact tree ensemble on arena outcomes to rank simulator-approved branches, then export deterministic thresholds into the agent.", impact: 4, confidence: 3, effort: 5, status: "planned" },
    { id: "first-submission", title: "Ship interpretable v0.2", description: "Freeze the artifact, pass self-play, and enter the ladder.", impact: 5, confidence: 5, effort: 2, status: "testing" },
    { id: "liquidation", title: "Late-game liquidation", description: "Sell everything before turn 720.", impact: 5, confidence: 4, effort: 2, status: "testing" },
    { id: "opponent-model", title: "Opponent archetype classifier", description: "Infer commitments from visible farms and market signals.", impact: 5, confidence: 3, effort: 3, status: "testing" },
    { id: "lookahead", title: "Short-horizon simulator", description: "Compare baseline and counter-strategy branches over the next few days.", impact: 5, confidence: 2, effort: 5, status: "planned" },
    { id: "attention", title: "Attention controller", description: "Protect survival and exit work before adaptive responses.", impact: 5, confidence: 4, effort: 3, status: "testing" },
    { id: "loss-tags", title: "Loss replay taxonomy", description: "Tag opener, first divergence, execution failure, and terminal inventory.", impact: 4, confidence: 5, effort: 2, status: "planned" },
  ];
  let roadmap = readStore(KEYS.roadmap, starterRoadmap);
  if (!Array.isArray(roadmap)) roadmap = [...starterRoadmap];
  roadmap = roadmap.map((item) => {
    const starter = starterRoadmap.find((candidate) => candidate.id === item.id);
    if (!starter) return item;
    const foundationIds = new Set(["v2-productive-slot", "v2-counterfactual-teacher", "v2-human-arena"]);
    return { ...starter, status: foundationIds.has(item.id) ? starter.status : (item.status || starter.status) };
  });
  starterRoadmap.forEach((starter) => {
    if (!roadmap.some((item) => item.id === starter.id)) roadmap.push({ ...starter });
  });
  writeStore(KEYS.roadmap, roadmap);

  const roadmapDialog = $("#roadmap-dialog");
  const roadmapForm = $("#roadmap-form");
  $("#add-roadmap-item").addEventListener("click", () => roadmapDialog.showModal());
  $("#close-roadmap-dialog").addEventListener("click", () => roadmapDialog.close());
  $("#cancel-roadmap").addEventListener("click", () => roadmapDialog.close());
  roadmapForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(roadmapForm);
    roadmap.push({
      id: makeId("idea"),
      title: String(data.get("title")).trim(),
      description: String(data.get("description")).trim(),
      impact: Number(data.get("impact")),
      confidence: Number(data.get("confidence")),
      effort: Number(data.get("effort")),
      status: "planned",
    });
    writeStore(KEYS.roadmap, roadmap);
    roadmapForm.reset();
    roadmapForm.elements.impact.value = 3;
    roadmapForm.elements.confidence.value = 3;
    roadmapForm.elements.effort.value = 2;
    roadmapDialog.close();
    renderRoadmap();
  });

  function priority(item) {
    return (item.impact * item.confidence) / Math.max(1, item.effort);
  }

  function renderRoadmap() {
    const sorted = [...roadmap].sort((a, b) => {
      if (a.status === "done" && b.status !== "done") return 1;
      if (a.status !== "done" && b.status === "done") return -1;
      return priority(b) - priority(a);
    });
    $("#roadmap-list").innerHTML = sorted.map((item) => `
      <article class="roadmap-item" data-status="${escapeHtml(item.status)}">
        <div class="roadmap-score"><strong>${priority(item).toFixed(1)}</strong><small>priority</small></div>
        <div class="roadmap-copy"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description)}</p></div>
        <div class="score-trio"><span>Impact<strong>${item.impact}</strong></span><span>Conf.<strong>${item.confidence}</strong></span><span>Effort<strong>${item.effort}</strong></span></div>
        <select aria-label="Status for ${escapeHtml(item.title)}" data-roadmap-status="${item.id}">
          <option value="planned" ${item.status === "planned" ? "selected" : ""}>Planned</option>
          <option value="testing" ${item.status === "testing" ? "selected" : ""}>Testing</option>
          <option value="done" ${item.status === "done" ? "selected" : ""}>Done</option>
          <option value="parked" ${item.status === "parked" ? "selected" : ""}>Parked</option>
        </select>
        <button class="delete-button" type="button" aria-label="Delete ${escapeHtml(item.title)}" data-delete-roadmap="${item.id}">×</button>
      </article>`).join("");

    $$('[data-roadmap-status]').forEach((select) => {
      select.addEventListener("change", () => {
        const item = roadmap.find((candidate) => candidate.id === select.dataset.roadmapStatus);
        if (item) item.status = select.value;
        writeStore(KEYS.roadmap, roadmap);
        renderRoadmap();
      });
    });
    $$('[data-delete-roadmap]').forEach((button) => {
      button.addEventListener("click", () => {
        roadmap = roadmap.filter((item) => item.id !== button.dataset.deleteRoadmap);
        writeStore(KEYS.roadmap, roadmap);
        renderRoadmap();
      });
    });

    const candidate = sorted.find((item) => item.status === "testing") || sorted.find((item) => item.status === "planned");
    if (candidate) {
      $("#next-bet-title").textContent = candidate.title;
      $("#next-bet-description").textContent = candidate.description;
      $("#next-bet-score").textContent = priority(candidate).toFixed(1);
    } else {
      $("#next-bet-title").textContent = "Backlog cleared";
      $("#next-bet-description").textContent = "Add the next failure-driven hypothesis when your replays reveal it.";
      $("#next-bet-score").textContent = "✓";
    }
  }

  renderSubmissions();
  renderAgentArchive();
  renderExperiments();
  renderRoadmap();
})();
