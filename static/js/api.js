const DASHBOARD_ENDPOINTS = ["/api/dashboard", "/static/data/app-state.json", "/data/app-state.json"];

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function loadDashboard() {
  for (const endpoint of DASHBOARD_ENDPOINTS) {
    try {
      const data = await requestJson(endpoint);
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
  if (!normalized) {
    throw new Error("Missing ticker");
  }
  try {
    return await requestJson(`/api/tickers/${normalized}`);
  } catch (_error) {
    const cached = dashboard?.tickers?.[normalized];
    if (cached) return cached;
    throw new Error(`Ticker ${normalized} is not available in the current snapshot.`);
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
