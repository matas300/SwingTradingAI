const DASHBOARD_ENDPOINTS = ["/api/dashboard", "/static/data/app-state.json", "/data/app-state.json"];

function hasDashboardContent(data) {
  if (!data || typeof data !== "object") return false;
  const study = Array.isArray(data.study_watchlist) ? data.study_watchlist.length : 0;
  const signals = Array.isArray(data.signals) ? data.signals.length : 0;
  const openPositions = Array.isArray(data.open_positions) ? data.open_positions.length : 0;
  const tickerCount = data.tickers && typeof data.tickers === "object" ? Object.keys(data.tickers).length : 0;
  const positionCount = data.positions && typeof data.positions === "object" ? Object.keys(data.positions).length : 0;
  return study > 0 || signals > 0 || openPositions > 0 || tickerCount > 0 || positionCount > 0;
}

function requestHeaders() {
  const headers = { "Content-Type": "application/json" };
  try {
    const token = window.localStorage.getItem("swing-ai-admin-token");
    if (token) {
      headers["X-Admin-Token"] = token;
    }
  } catch (_error) {
    // Ignore localStorage access issues.
  }
  return headers;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      ...requestHeaders(),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function loadDashboard() {
  for (const [index, endpoint] of DASHBOARD_ENDPOINTS.entries()) {
    try {
      const data = await requestJson(endpoint);
      const isLastEndpoint = index === DASHBOARD_ENDPOINTS.length - 1;
      if (!hasDashboardContent(data) && !isLastEndpoint) {
        continue;
      }
      return {
        source: endpoint.startsWith("/api/") ? "api" : "static",
        data,
      };
    } catch (_error) {
      // Try the next source.
    }
  }
  throw new Error("Unable to load dashboard data from API or static snapshot.");
}

export async function loadTicker(ticker, dashboard) {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!normalized) throw new Error("Missing ticker.");
  try {
    return await requestJson(`/api/tickers/${normalized}`);
  } catch (_error) {
    const cached = dashboard?.tickers?.[normalized];
    if (cached) return cached;
    throw new Error(`Ticker ${normalized} is not available in the current dataset.`);
  }
}

export async function loadPosition(positionId, dashboard) {
  if (!positionId) throw new Error("Missing position id.");
  try {
    return await requestJson(`/api/positions/${encodeURIComponent(positionId)}`);
  } catch (_error) {
    const cached = dashboard?.positions?.[positionId];
    if (cached) return cached;
    throw new Error("Position detail is not available in the current dataset.");
  }
}

export async function saveSettings(payload) {
  return requestJson("/api/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function refreshDashboard(payload = {}) {
  return requestJson("/api/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateWatchlist(payload) {
  return requestJson("/api/watchlist", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function openPositionFromSignal(payload) {
  return requestJson("/api/positions/from-signal", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createPositionEvent(positionId, payload) {
  return requestJson(`/api/positions/${encodeURIComponent(positionId)}/events`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
