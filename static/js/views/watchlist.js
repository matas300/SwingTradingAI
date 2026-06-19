import { compactList, escapeHtml, formatPct, formatPrice, reliabilityTone, signalTone } from "../formatters.js";

export function renderWatchlist(state) {
  const rows = [...(state.data?.study_watchlist || [])];
  const details = state.data?.tickers || {};
  const query = state.filters.query.trim().toLowerCase();
  const actionableOnly = state.filters.actionableOnly || state.settings.show_only_actionable;

  rows.sort((left, right) => (right.confidence_score || 0) - (left.confidence_score || 0));

  const filtered = rows.filter((row) => {
    if (actionableOnly && row.direction === "neutral") return false;
    if (!query) return true;
    return [row.ticker, row.direction, row.regime, row.reliability_label, row.strategy_name].some((value) =>
      String(value || "").toLowerCase().includes(query),
    );
  });

  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Study Watchlist</p>
          <h3>Observed tickers only</h3>
          <p class="help-text">This list has no committed capital. It is the research layer that feeds the signals.</p>
        </div>
      </div>
      <div class="toolbar">
        <label class="search-field">
          <span>Search</span>
          <input id="watchlist-query" type="search" aria-label="Filter tickers" placeholder="NVDA, long, high reliability" value="${escapeHtml(state.filters.query)}">
        </label>
        <label class="toggle-inline">
          <input id="actionable-only" type="checkbox" aria-label="Show actionable only" ${actionableOnly ? "checked" : ""}>
          <span>Actionable only</span>
        </label>
      </div>
      ${filtered.length ? `
        <div class="signal-table">
          <div class="table-row table-head watchlist-grid">
            <span>Ticker</span>
            <span>Direction</span>
            <span>Confidence</span>
            <span>Entry</span>
            <span>Trend</span>
            <span>Regime</span>
            <span>Warnings</span>
            <span>Reliability</span>
          </div>
          ${filtered.map((row) => {
            const signal = details[row.ticker]?.latest_prediction || details[row.ticker]?.latest_signal || null;
            const entryLow = signal?.entry_low ?? row.entry_low ?? null;
            const entryHigh = signal?.entry_high ?? row.entry_high ?? null;
            return `
            <button class="table-row table-button watchlist-grid" data-action="open-ticker" data-item="${escapeHtml(row.ticker)}">
              <span>${escapeHtml(row.ticker)}</span>
              <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
              <span>${formatPct(row.confidence_score, 0)}</span>
              <span>${formatPrice(entryLow)} - ${formatPrice(entryHigh)}</span>
              <span>${escapeHtml(row.trend || "-")}</span>
              <span>${escapeHtml(row.regime || "-")}</span>
              <span>${escapeHtml(compactList(row.warning_flags || [], 2))}</span>
              <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label || "-")}</span>
            </button>
            `;
          }).join("")}
        </div>
      ` : `<div class="empty-state">No study tickers match the current filters.</div>`}
    </section>
  `;
}
