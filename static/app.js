import { createPositionEvent, loadDashboard, loadPosition, loadTicker, openPositionFromSignal, refreshDashboard, saveSettings, updateWatchlist } from "./js/api.js";
import { formatDateTime } from "./js/formatters.js";
import { navigate, parseRoute } from "./js/router.js";
import { closeModal, getState, openModal, setRoute, setState, subscribe, updateAdminToken, updateFilters, updateSettings } from "./js/store.js";
import { renderHistory } from "./js/views/history.js";
import { renderOverview } from "./js/views/overview.js";
import { renderPositionDetail } from "./js/views/position-detail.js";
import { renderPositions } from "./js/views/positions.js";
import { renderSettings } from "./js/views/settings.js";
import { renderSignals } from "./js/views/signals.js";
import { renderTickerDetail } from "./js/views/ticker-detail.js";
import { renderWatchlist } from "./js/views/watchlist.js";

const contentNode = document.getElementById("app-content");
const statusNode = document.getElementById("status-strip");
const refreshButton = document.getElementById("refresh-button");
const themeToggleButton = document.getElementById("theme-toggle");
const dialogNode = document.getElementById("app-dialog");

function applyTheme(state) {
  const theme = state.settings.theme || "system";
  const resolvedTheme =
    theme === "system"
      ? window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark"
      : theme;
  document.documentElement.dataset.theme = resolvedTheme;
  document.body.dataset.density = state.settings.density || "comfortable";
}

function getDashboard(state) {
  return state.data || {};
}

function capabilitiesFor(state) {
  return (
    state.data?.capabilities || {
      mode: state.source === "api" ? "local-api" : "static-snapshot",
      write: state.source === "api",
      refresh: state.source === "api",
      auth_mode: "none",
    }
  );
}

function canWrite(state) {
  const capabilities = capabilitiesFor(state);
  if (!capabilities.write) return false;
  return capabilities.auth_mode !== "admin-token" || Boolean(state.adminToken);
}

function canRefresh(state) {
  return Boolean(capabilitiesFor(state).refresh);
}

function getTickerDetail(state, ticker) {
  return getDashboard(state).tickers?.[ticker] || null;
}

function getPositionDetail(state, positionId) {
  return getDashboard(state).positions?.[positionId] || null;
}

function recommendationLabel(action) {
  if (!action) return "No action";
  return String(action).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function nextTargetPrice(position) {
  const targets = position?.current_adaptive_targets || position?.original_targets || [];
  return targets.find((target) => target.kind === "target_1")?.price ?? null;
}

function chartPointsFromSnapshots(snapshots) {
  return (snapshots || [])
    .map((snapshot) => Number(snapshot.close))
    .filter((value) => Number.isFinite(value));
}

function toDateTimeLocal(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (input) => String(input).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

function signalForTicker(state, ticker) {
  const detail = getTickerDetail(state, ticker);
  return detail?.latest_prediction || detail?.latest_signal || null;
}

function resolvePositionSnapshot(state, positionId) {
  return getPositionDetail(state, positionId)?.position || null;
}

function renderStatus(state) {
  const generatedAt = state.data?.generated_at ? formatDateTime(state.data.generated_at) : "Not loaded";
  const capabilities = capabilitiesFor(state);
  const authHint =
    capabilities.auth_mode === "admin-token" && !state.adminToken
      ? "Admin token required for writes."
      : capabilities.auth_mode === "admin-token"
      ? "Hosted admin writes enabled."
      : capabilities.write
      ? "Interactive mode enabled."
      : "Read-only deploy mode active.";
  statusNode.innerHTML = `
    <div>
      <strong>${state.source === "api" ? "Live API mode" : "Static snapshot mode"}</strong>
      <span>Last dataset: ${generatedAt}</span>
    </div>
    <div>
      <span>${state.notice || authHint}</span>
    </div>
  `;
  refreshButton.disabled = !canRefresh(state) || state.status === "loading";
}

function renderView(state) {
  if (state.status === "loading") {
    return `<div class="empty-state">Loading dashboard data...</div>`;
  }
  if (state.status === "error") {
    return `<div class="empty-state">${state.error}</div>`;
  }

  switch (state.route.view) {
    case "watchlist":
      return renderWatchlist(state);
    case "signals":
      return renderSignals(state);
    case "positions":
      return renderPositions(state);
    case "ticker":
      return renderTickerDetail(state, state.route.item || "");
    case "position":
      return renderPositionDetail(state, state.route.item || "");
    case "history":
      return renderHistory(state);
    case "settings":
      return renderSettings(state);
    case "overview":
    default:
      return renderOverview(state);
  }
}

function updateActiveNav(state) {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("is-active", link.dataset.nav === state.route.view);
  });
}

function renderDialog(state) {
  if (!dialogNode) return;
  if (!state.modal) {
    if (dialogNode.open) dialogNode.close();
    dialogNode.innerHTML = "";
    return;
  }

  const { type } = state.modal;
  if (type === "open-position") {
    const signal = state.modal.signal;
    const writable = canWrite(state);
    const hostedAuthMode = capabilitiesFor(state).auth_mode === "admin-token";
    dialogNode.innerHTML = `
      <form id="open-position-form" class="modal-card">
        <div class="modal-head">
          <div>
            <p class="eyebrow">Open position</p>
            <h3>${signal?.ticker ? `${signal.ticker} from signal` : "Open position"}</h3>
          </div>
          <button class="ghost-button" type="button" data-action="close-modal">Close</button>
        </div>
        <div class="modal-grid">
          <label><span>Ticker</span><input name="ticker" value="${signal?.ticker || ""}" readonly></label>
          <label><span>Side</span><input name="side" value="${signal?.direction || "long"}" readonly></label>
          <label><span>Strategy</span><input name="strategy_name" value="${signal?.strategy_name || signal?.strategy_id || "adaptive-swing-v2"}" readonly></label>
          <label><span>Signal ID</span><input name="signal_id" value="${signal?.signal_id || ""}" readonly></label>
          <label><span>Execution price</span><input name="execution_price" type="number" step="0.01" min="0" value="${signal?.entry_reference_price ?? signal?.entry_high ?? signal?.entry_low ?? ""}" required></label>
          <label><span>Quantity</span><input name="quantity" type="number" step="0.001" min="0" value="1" required></label>
          <label><span>Opened at</span><input name="executed_at" type="datetime-local" value="${toDateTimeLocal()}" required></label>
          <label><span>Fees</span><input name="fees" type="number" step="0.01" min="0" value="0"></label>
        </div>
        <label class="stacked-field">
          <span>Notes</span>
          <textarea name="notes" rows="4" placeholder="Why am I taking this trade?"></textarea>
        </label>
        <p class="help-text">The form is prefilled from the originating signal, but you can adjust execution details before saving.</p>
        ${
          writable
            ? ""
            : `<p class="help-text">${
                hostedAuthMode
                  ? "Saving is still protected. Add the admin token in Settings before submitting."
                  : "This deploy is currently read-only. You can review the setup here, but saving requires a writable API mode."
              }</p>`
        }
        <div class="modal-actions">
          <button class="secondary-button" type="button" data-action="close-modal">Cancel</button>
          <button class="primary-button" type="submit">Create position</button>
        </div>
      </form>
    `;
  } else if (type === "position-event") {
    const position = state.modal.position;
    const eventType = state.modal.eventType || "ADD";
    const quantityValue = eventType === "CLOSE" ? "" : (state.modal.quantity ?? 1);
    dialogNode.innerHTML = `
      <form id="position-event-form" class="modal-card">
        <div class="modal-head">
          <div>
            <p class="eyebrow">Position event</p>
            <h3>${position?.ticker || "Position"} - ${recommendationLabel(eventType)}</h3>
          </div>
          <button class="ghost-button" type="button" data-action="close-modal">Close</button>
        </div>
        <div class="modal-grid">
          <label><span>Event type</span>
            <select name="event_type">
              ${["ADD", "REDUCE", "CLOSE", "MANUAL_NOTE", "UPDATE_STOP", "UPDATE_TARGETS"].map((option) => `<option value="${option}" ${option === eventType ? "selected" : ""}>${option.replaceAll("_", " ")}</option>`).join("")}
            </select>
          </label>
          <label><span>Quantity</span><input name="quantity" type="number" step="0.001" min="0" value="${quantityValue}"></label>
          <label><span>Price</span><input name="price" type="number" step="0.01" min="0" value="${position?.mark_price ?? position?.average_entry_price ?? ""}"></label>
          <label><span>Fees</span><input name="fees" type="number" step="0.01" min="0" value="0"></label>
          <label><span>Executed at</span><input name="executed_at" type="datetime-local" value="${toDateTimeLocal()}" required></label>
        </div>
        <label class="stacked-field">
          <span>Notes</span>
          <textarea name="notes" rows="4" placeholder="Add context for this event"></textarea>
        </label>
        <p class="help-text">CLOSE can use the full remaining quantity automatically if you leave quantity blank.</p>
        <div class="modal-actions">
          <button class="secondary-button" type="button" data-action="close-modal">Cancel</button>
          <button class="primary-button" type="submit">Save event</button>
        </div>
      </form>
    `;
  } else {
    dialogNode.innerHTML = "";
  }

  if (!dialogNode.open) {
    dialogNode.showModal();
  }
}

function renderApp(state) {
  applyTheme(state);
  renderStatus(state);
  contentNode.innerHTML = renderView(state);
  updateActiveNav(state);
  renderDialog(state);
}

async function hydrateDashboard() {
  setState({ status: "loading", error: "" });
  try {
    const payload = await loadDashboard();
    setState({
      status: "ready",
      source: payload.source,
      data: {
        ...payload.data,
        tickers: payload.data?.tickers || {},
        positions: payload.data?.positions || {},
      },
      error: "",
      notice: payload.source === "api" ? "Live API connected." : "Using the exported static snapshot.",
    });
  } catch (error) {
    setState({
      status: "error",
      error: error instanceof Error ? error.message : "Unknown dashboard loading error.",
    });
  }
}

async function hydrateTickerDetail(route) {
  const ticker = route.item || "";
  if (route.view !== "ticker" || !ticker) return;
  if (getTickerDetail(getState(), ticker)?.latest_prediction || getTickerDetail(getState(), ticker)?.latest_signal) return;
  try {
    const detail = await loadTicker(ticker, getState().data);
    setState({
      data: {
        ...getState().data,
        tickers: {
          ...(getState().data?.tickers || {}),
          [ticker]: detail,
        },
      },
    });
  } catch (error) {
    setState({
      notice: error instanceof Error ? error.message : "Ticker detail unavailable.",
    });
  }
}

async function hydratePositionDetail(route) {
  const positionId = route.item || "";
  if (route.view !== "position" || !positionId) return;
  if (getPositionDetail(getState(), positionId)?.position) return;
  try {
    const detail = await loadPosition(positionId, getState().data);
    setState({
      data: {
        ...getState().data,
        positions: {
          ...(getState().data?.positions || {}),
          [positionId]: detail,
        },
      },
    });
  } catch (error) {
    setState({
      notice: error instanceof Error ? error.message : "Position detail unavailable.",
    });
  }
}

async function hydrateRouteData(route) {
  await hydrateTickerDetail(route);
  await hydratePositionDetail(route);
}

async function handleHashChange() {
  const route = parseRoute(window.location.hash || `#${getState().settings.default_view || "overview"}`);
  setRoute(route);
  await hydrateRouteData(route);
}

async function refreshAndHydrate(route = getState().route) {
  await hydrateDashboard();
  await hydrateRouteData(route);
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const item = target.dataset.item;

  if (action === "open-ticker" && item) {
    navigate("ticker", item);
  }
  if (action === "open-position" && item) {
    navigate("position", item);
  }
  if (action === "open-view" && item) {
    navigate(item);
  }
  if (action === "open-position-modal" && item) {
    const signal = signalForTicker(getState(), item) || getTickerDetail(getState(), item)?.latest_prediction || getTickerDetail(getState(), item)?.latest_signal || null;
    if (signal && signal.direction !== "neutral") {
      openModal({ type: "open-position", signal });
    } else {
      setState({ notice: "Only long or short signals can be converted into a real position." });
    }
  }
  if (action === "open-add" && item) {
    openModal({ type: "position-event", position: resolvePositionSnapshot(getState(), item), eventType: "ADD" });
  }
  if (action === "open-reduce" && item) {
    openModal({ type: "position-event", position: resolvePositionSnapshot(getState(), item), eventType: "REDUCE" });
  }
  if (action === "open-close" && item) {
    openModal({ type: "position-event", position: resolvePositionSnapshot(getState(), item), eventType: "CLOSE" });
  }
  if (action === "open-note" && item) {
    openModal({ type: "position-event", position: resolvePositionSnapshot(getState(), item), eventType: "MANUAL_NOTE" });
  }
  if (action === "close-modal") {
    closeModal();
  }
  if (action === "refresh-now") {
    if (getState().source !== "api") return;
    setState({ notice: "Running the daily refresh..." });
    try {
      await refreshAndHydrate(getState().route);
      setState({ notice: "Daily refresh completed." });
    } catch (error) {
      setState({ notice: error instanceof Error ? error.message : "Refresh failed." });
    }
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.id === "watchlist-query") {
    updateFilters({ query: target.value });
  }
  if (target.id === "actionable-only") {
    updateFilters({ actionableOnly: target.checked });
  }
  if (target.id === "positions-query") {
    updateFilters({ query: target.value });
  }
  if (target.id === "positions-side") {
    updateFilters({ side: target.value });
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;

  if (form.id === "settings-form") {
    event.preventDefault();
    const formData = new FormData(form);
    const adminToken = String(formData.get("admin_token") || "");
    const payload = {
      theme: String(formData.get("theme") || "system"),
      density: String(formData.get("density") || "comfortable"),
      default_view: String(formData.get("default_view") || "overview"),
      favorite_metric: String(formData.get("favorite_metric") || "confidence"),
      show_only_actionable: formData.get("show_only_actionable") === "on",
      risk_budget_pct: Number(formData.get("risk_budget_pct") || 0.01),
      max_add_fraction: Number(formData.get("max_add_fraction") || 0.25),
    };
    updateAdminToken(adminToken);
    updateSettings(payload);
    if (canWrite(getState())) {
      try {
        await saveSettings(payload);
        setState({ notice: capabilitiesFor(getState()).auth_mode === "admin-token" ? "Preferences saved with hosted admin mode." : "Preferences saved to the local API store." });
      } catch (_error) {
        setState({ notice: "Preferences saved locally only." });
      }
    } else {
      setState({ notice: "Preferences saved locally in this browser." });
    }
  }

  if (form.id === "watchlist-form") {
    event.preventDefault();
    if (!canWrite(getState())) return;
    const formData = new FormData(form);
    const tickers = String(formData.get("tickers") || "")
      .split(/[\s,;]+/)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
    try {
      await updateWatchlist({ tickers, daily_period: "2y" });
      setState({ notice: "Watchlist updated. Reloading dashboard..." });
      await refreshAndHydrate();
    } catch (error) {
      setState({ notice: error instanceof Error ? error.message : "Unable to update watchlist." });
    }
  }

  if (form.id === "open-position-form") {
    event.preventDefault();
    if (!canWrite(getState())) {
      setState({ notice: "Admin token required before creating a hosted position." });
      return;
    }
    const formData = new FormData(form);
    const payload = {
      signal_id: String(formData.get("signal_id") || ""),
      execution_price: Number(formData.get("execution_price") || 0),
      quantity: Number(formData.get("quantity") || 0),
      executed_at: String(formData.get("executed_at") || ""),
      fees: Number(formData.get("fees") || 0),
      notes: String(formData.get("notes") || ""),
    };
    try {
      const detail = await openPositionFromSignal(payload);
      const positionId = detail?.position?.position_id || detail?.position?.id || detail?.position_id || null;
      closeModal();
      setState({
        notice: "Position opened from the selected signal.",
        data: {
          ...getState().data,
          positions: {
            ...(getState().data?.positions || {}),
            ...(positionId ? { [positionId]: detail } : {}),
          },
        },
      });
      if (positionId) {
        navigate("position", positionId);
        await hydratePositionDetail({ view: "position", item: positionId });
      }
    } catch (error) {
      setState({ notice: error instanceof Error ? error.message : "Unable to open the position." });
    }
  }

  if (form.id === "position-event-form") {
    event.preventDefault();
    if (!canWrite(getState())) {
      setState({ notice: "Admin token required before writing position events." });
      return;
    }
    const formData = new FormData(form);
    const eventType = String(formData.get("event_type") || "ADD");
    const position = getState().modal?.position;
    const positionId = position?.position_id || position?.id || getState().route.item;
    if (!positionId) return;
    const payload = {
      event_type: eventType,
      quantity: Number(formData.get("quantity") || 0),
      price: formData.get("price") === "" ? null : Number(formData.get("price")),
      fees: Number(formData.get("fees") || 0),
      executed_at: String(formData.get("executed_at") || ""),
      notes: String(formData.get("notes") || ""),
      metadata: {},
    };
    try {
      const detail = await createPositionEvent(positionId, payload);
      closeModal();
      setState({
        notice: "Position event saved.",
        data: {
          ...getState().data,
          positions: {
            ...(getState().data?.positions || {}),
            [positionId]: detail,
          },
        },
      });
      navigate("position", positionId);
      await hydratePositionDetail({ view: "position", item: positionId });
    } catch (error) {
      setState({ notice: error instanceof Error ? error.message : "Unable to save the position event." });
    }
  }
});

refreshButton.addEventListener("click", async () => {
  if (!canRefresh(getState())) return;
  setState({ notice: "Running the daily refresh..." });
  try {
    await refreshAndHydrate();
    setState({ notice: "Daily refresh completed." });
  } catch (error) {
    setState({ notice: error instanceof Error ? error.message : "Refresh failed." });
  }
});

themeToggleButton.addEventListener("click", () => {
  const order = ["system", "dark", "light"];
  const current = getState().settings.theme || "system";
  const next = order[(order.indexOf(current) + 1) % order.length];
  updateSettings({ theme: next });
  setState({ notice: `Theme switched to ${next}.` });
});

dialogNode?.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeModal();
});

subscribe(renderApp);
window.addEventListener("hashchange", handleHashChange);

if (!window.location.hash) {
  navigate(getState().settings.default_view || "overview");
}

hydrateDashboard().then(handleHashChange);
