import { loadDashboard, loadTicker, refreshDashboard, saveSettings, updateWatchlist } from "./js/api.js";
import { formatDateTime } from "./js/formatters.js";
import { navigate, parseRoute } from "./js/router.js";
import { getState, setRoute, setState, subscribe, toggleFavorite, updateFilters, updateSettings } from "./js/store.js";
import { renderHistory } from "./js/views/history.js";
import { renderOverview } from "./js/views/overview.js";
import { renderSettings } from "./js/views/settings.js";
import { renderSignals } from "./js/views/signals.js";
import { renderTickerDetail } from "./js/views/ticker-detail.js";
import { renderWatchlist } from "./js/views/watchlist.js";

const contentNode = document.getElementById("app-content");
const statusNode = document.getElementById("status-strip");
const refreshButton = document.getElementById("refresh-button");
const themeToggleButton = document.getElementById("theme-toggle");

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

function renderStatus(state) {
  const generatedAt = state.data?.generated_at ? formatDateTime(state.data.generated_at) : "Not loaded";
  statusNode.innerHTML = `
    <div>
      <strong>${state.source === "api" ? "Live API mode" : "Static snapshot mode"}</strong>
      <span>Last dataset: ${generatedAt}</span>
    </div>
    <div>
      <span>${state.notice || (state.source === "api" ? "Refresh can trigger the local pipeline." : "Read-only deploy mode active.")}</span>
    </div>
  `;
  refreshButton.disabled = state.source !== "api" || state.status === "loading";
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
    case "ticker":
      return renderTickerDetail(state);
    case "signals":
      return renderSignals(state);
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

function renderApp(state) {
  applyTheme(state);
  renderStatus(state);
  contentNode.innerHTML = renderView(state);
  updateActiveNav(state);
}

async function hydrateDashboard() {
  setState({ status: "loading", error: "" });
  try {
    const payload = await loadDashboard();
    setState({
      status: "ready",
      source: payload.source,
      data: payload.data,
      error: "",
      notice: payload.source === "api" ? "Local API connected." : "Using the last exported static snapshot.",
    });
  } catch (error) {
    setState({
      status: "error",
      error: error instanceof Error ? error.message : "Unknown dashboard loading error.",
    });
  }
}

async function hydrateTickerDetail(route) {
  if (route.view !== "ticker" || !route.ticker) return;
  if (getState().data?.tickers?.[route.ticker]) return;
  try {
    const detail = await loadTicker(route.ticker, getState().data);
    setState({
      data: {
        ...getState().data,
        tickers: {
          ...(getState().data?.tickers || {}),
          [route.ticker]: detail,
        },
      },
    });
  } catch (error) {
    setState({
      notice: error instanceof Error ? error.message : "Ticker detail unavailable.",
    });
  }
}

async function handleHashChange() {
  const route = parseRoute(window.location.hash || `#${getState().settings.default_view || "overview"}`);
  setRoute(route);
  await hydrateTickerDetail(route);
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const ticker = target.dataset.ticker;

  if (action === "open-ticker" && ticker) {
    navigate("ticker", ticker);
  }
  if (action === "favorite" && ticker) {
    toggleFavorite(ticker);
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (target.id === "watchlist-query") {
    updateFilters({ query: target.value });
  }
  if (target.id === "actionable-only") {
    updateFilters({ actionableOnly: target.checked });
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;

  if (form.id === "settings-form") {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      theme: String(formData.get("theme") || "system"),
      density: String(formData.get("density") || "comfortable"),
      default_view: String(formData.get("default_view") || "overview"),
      show_only_actionable: formData.get("show_only_actionable") === "on",
    };
    updateSettings(payload);
    if (getState().source === "api") {
      try {
        await saveSettings(payload);
        setState({ notice: "Preferences saved to the local API store." });
      } catch (_error) {
        setState({ notice: "Preferences saved locally only." });
      }
    } else {
      setState({ notice: "Preferences saved locally in this browser." });
    }
  }

  if (form.id === "watchlist-form") {
    event.preventDefault();
    if (getState().source !== "api") return;
    const formData = new FormData(form);
    const tickers = String(formData.get("tickers") || "")
      .split(/[\s,;]+/)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
    try {
      await updateWatchlist({ tickers, daily_period: "2y" });
      setState({ notice: "Watchlist updated. Reloading dashboard..." });
      await hydrateDashboard();
    } catch (error) {
      setState({ notice: error instanceof Error ? error.message : "Unable to update watchlist." });
    }
  }
});

refreshButton.addEventListener("click", async () => {
  if (getState().source !== "api") return;
  setState({ notice: "Running the local daily refresh..." });
  try {
    await refreshDashboard({});
    await hydrateDashboard();
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

subscribe(renderApp);
window.addEventListener("hashchange", handleHashChange);

if (!window.location.hash) {
  navigate(getState().settings.default_view || "overview");
}

hydrateDashboard().then(handleHashChange);
