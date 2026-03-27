import { escapeHtml, formatPct, reliabilityTone, signalTone } from "../formatters.js";

export function renderWatchlist(state) {
  const rows = [...(state.data?.watchlist || [])];
  const query = state.filters.query.trim().toLowerCase();
  const actionableOnly = state.filters.actionableOnly || state.settings.show_only_actionable;

  rows.sort((left, right) => {
    const leftPinned = state.favorites.includes(left.ticker) ? 0 : 1;
    const rightPinned = state.favorites.includes(right.ticker) ? 0 : 1;
    return leftPinned - rightPinned || (right.confidence_score || 0) - (left.confidence_score || 0);
  });

  const filtered = rows.filter((row) => {
    if (actionableOnly && row.direction === "neutral") return false;
    if (!query) return true;
    return [row.ticker, row.direction, row.regime, row.reliability_label].some((value) =>
      String(value || "").toLowerCase().includes(query),
    );
  });

  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Watchlist</p>
          <h3>Tracked universe</h3>
        </div>
      </div>
      <div class="toolbar">
        <label class="search-field">
          <span>Search</span>
          <input id="watchlist-query" type="search" placeholder="NVDA, long, high reliability" value="${escapeHtml(state.filters.query)}">
        </label>
        <label class="toggle-inline">
          <input id="actionable-only" type="checkbox" ${actionableOnly ? "checked" : ""}>
          <span>Actionable only</span>
        </label>
      </div>
      ${
        filtered.length
          ? `<div class="signal-table">
              <div class="table-row table-head">
                <span>Ticker</span>
                <span>Direction</span>
                <span>Confidence</span>
                <span>Trend</span>
                <span>Regime</span>
                <span>Reliability</span>
                <span>Favorite</span>
              </div>
              ${filtered
                .map(
                  (row) => `
                    <div class="table-row">
                      <button class="table-button inline-button" data-action="open-ticker" data-ticker="${escapeHtml(row.ticker)}">${escapeHtml(row.ticker)}</button>
                      <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
                      <span>${formatPct(row.confidence_score, 0)}</span>
                      <span>${escapeHtml(row.trend || "-")}</span>
                      <span>${escapeHtml(row.regime || "-")}</span>
                      <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label || "-")}</span>
                      <button class="ghost-button" data-action="favorite" data-ticker="${escapeHtml(row.ticker)}">${state.favorites.includes(row.ticker) ? "Pinned" : "Pin"}</button>
                    </div>
                  `,
                )
                .join("")}
            </div>`
          : `<div class="empty-state">No tickers match the current filters.</div>`
      }
    </section>
  `;
}
