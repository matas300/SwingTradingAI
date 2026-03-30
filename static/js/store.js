const listeners = new Set();

function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_error) {
    return fallback;
  }
}

function readText(key, fallback = "") {
  try {
    return window.localStorage.getItem(key) || fallback;
  } catch (_error) {
    return fallback;
  }
}

const state = {
  status: "loading",
  error: "",
  source: "static",
  data: null,
  route: { view: "overview", item: null },
  notice: "",
  modal: null,
  adminToken: readText("swing-ai-admin-token", ""),
  settings: readJson("swing-ai-settings", {
    theme: "system",
    density: "comfortable",
    default_view: "overview",
    favorite_metric: "confidence",
    show_only_actionable: false,
    risk_budget_pct: 0.01,
    max_add_fraction: 0.25,
  }),
  favorites: readJson("swing-ai-favorites", []),
  filters: {
    query: "",
    actionableOnly: false,
    side: "all",
  },
};

function persist() {
  window.localStorage.setItem("swing-ai-settings", JSON.stringify(state.settings));
  window.localStorage.setItem("swing-ai-favorites", JSON.stringify(state.favorites));
  if (state.adminToken) {
    window.localStorage.setItem("swing-ai-admin-token", state.adminToken);
  } else {
    window.localStorage.removeItem("swing-ai-admin-token");
  }
}

function notify() {
  persist();
  listeners.forEach((listener) => listener(state));
}

export function getState() {
  return state;
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setState(partial) {
  Object.assign(state, partial);
  notify();
}

export function setRoute(route) {
  state.route = route;
  notify();
}

export function updateSettings(partial) {
  state.settings = { ...state.settings, ...partial };
  notify();
}

export function updateAdminToken(value) {
  state.adminToken = String(value || "").trim();
  notify();
}

export function updateFilters(partial) {
  state.filters = { ...state.filters, ...partial };
  notify();
}

export function toggleFavorite(ticker) {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!normalized) return;
  if (state.favorites.includes(normalized)) {
    state.favorites = state.favorites.filter((item) => item !== normalized);
  } else {
    state.favorites = [...state.favorites, normalized];
  }
  notify();
}

export function openModal(modal) {
  state.modal = modal;
  notify();
}

export function closeModal() {
  state.modal = null;
  notify();
}
