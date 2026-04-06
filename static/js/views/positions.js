import { actionTone, compactList, escapeHtml, formatDateTime, formatPnl, formatPct, formatPrice, humanizeKey, reliabilityTone, signalTone } from "../formatters.js";

function targetPrice(targets, kind) {
  if (!Array.isArray(targets)) return null;
  return targets.find((item) => item.kind === kind)?.price ?? null;
}

function rowActions(row) {
  return `
    <div class="table-actions">
      <button class="ghost-button" data-action="open-add" data-item="${escapeHtml(row.position_id)}">Add</button>
      <button class="ghost-button" data-action="open-reduce" data-item="${escapeHtml(row.position_id)}">Reduce</button>
      <button class="ghost-button" data-action="open-close" data-item="${escapeHtml(row.position_id)}">Close all</button>
      <button class="ghost-button" data-action="open-note" data-item="${escapeHtml(row.position_id)}">Edit notes</button>
      <button class="secondary-button" data-action="open-position" data-item="${escapeHtml(row.position_id)}">View detail</button>
    </div>
  `;
}

export function renderPositions(state) {
  const rows = [...(state.data?.open_positions || [])];
  const capabilities = state.data?.capabilities || {};
  const canWrite = Boolean(capabilities.write && (capabilities.auth_mode !== "admin-token" || state.adminToken));
  const query = state.filters.query.trim().toLowerCase();
  const side = state.filters.side || "all";

  const filtered = rows.filter((row) => {
    if (side !== "all" && String(row.side || "").toLowerCase() !== side) return false;
    if (!query) return true;
    return [
      row.ticker,
      row.side,
      row.strategy_name,
      row.status,
      row.last_recommendation,
      row.reliability_label,
    ].some((value) => String(value || "").toLowerCase().includes(query));
  });

  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Open Positions</p>
          <h3>Every real trade, with events and daily recommendations</h3>
          <p class="help-text">These rows are distinct from the study watchlist and only include positions the user actually opened.</p>
        </div>
      </div>
      <div class="toolbar">
        <label class="search-field">
          <span>Search</span>
          <input id="positions-query" type="search" aria-label="Filter positions" placeholder="ticker, strategy, action" value="${escapeHtml(state.filters.query)}">
        </label>
        <label class="search-field">
          <span>Side</span>
          <select id="positions-side" aria-label="Filter by side">
            <option value="all" ${side === "all" ? "selected" : ""}>All</option>
            <option value="long" ${side === "long" ? "selected" : ""}>Long</option>
            <option value="short" ${side === "short" ? "selected" : ""}>Short</option>
          </select>
        </label>
      </div>
      ${filtered.length ? `
        <div class="signal-table">
          <div class="table-row table-head positions-grid">
            <span>Ticker</span>
            <span>Side</span>
            <span>Strategy</span>
            <span>Status</span>
            <span>Qty</span>
            <span>Average entry</span>
            <span>Current price</span>
            <span>Realized</span>
            <span>Unrealized</span>
            <span>Total</span>
            <span>Recommendation</span>
            <span>Confidence</span>
            <span>Next target</span>
            <span>Stop</span>
            <span>Last update</span>
          </div>
          ${filtered.map((row) => `
            <div class="table-row positions-grid">
              <button class="table-button inline-button" data-action="open-position" data-item="${escapeHtml(row.position_id)}">${escapeHtml(row.ticker)}</button>
              <span class="badge tone-${signalTone(row.side)}">${escapeHtml(row.side)}</span>
              <span>${escapeHtml(row.strategy_name || row.strategy_id || "strategy")}</span>
              <span class="badge tone-${actionTone(row.last_recommendation)}">${escapeHtml(row.status || "open")}</span>
              <span>${formatPrice(row.current_quantity)}</span>
              <span>${formatPrice(row.average_entry_price)}</span>
              <span>${formatPrice(row.mark_price)}</span>
              <span>${formatPnl(row.realized_pnl)}</span>
              <span>${formatPnl(row.unrealized_pnl)}</span>
              <span>${formatPnl(row.total_pnl)}</span>
              <span class="badge tone-${actionTone(row.last_recommendation)}">${escapeHtml(humanizeKey(row.last_recommendation || "maintain"))}</span>
              <span>${formatPct(row.last_recommendation_confidence || 0, 0)}</span>
              <span>${formatPrice(targetPrice(row.current_adaptive_targets || [], "target_1"))}</span>
              <span>${formatPrice(row.current_stop)}</span>
              <span>${escapeHtml(formatDateTime(row.updated_at))}</span>
            </div>
            <div class="subtle-row">
              <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label || "unrated")}</span>
              <span>${escapeHtml(compactList(row.warning_flags || [], 3))}</span>
              ${canWrite ? rowActions(row) : `<span class="help-text">${escapeHtml(capabilities.auth_mode === "admin-token" ? "Insert the admin token in Settings to unlock hosted writes." : "Read-only deploy mode.")}</span>`}
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty-state">No open positions yet. Open a real trade from the Signals or Ticker detail view.</div>`}
    </section>
  `;
}
