import { actionTone, escapeHtml, formatDate, formatDateTime, formatPnl, formatPct, humanizeKey } from "../formatters.js";

export function renderHistory(state) {
  const signalHistory = state.data?.history?.signals || [];
  const positionRecommendations = state.data?.history?.position_recommendations || [];
  const positionEvents = state.data?.history?.position_events || [];

  return `
    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">History</p>
            <h3>Signal outcomes</h3>
          </div>
        </div>
        ${signalHistory.length ? `
          <div class="signal-table">
            <div class="table-row table-head history-grid">
              <span>Date</span>
              <span>Ticker</span>
              <span>Direction</span>
              <span>Status</span>
              <span>Return</span>
              <span>Holding</span>
            </div>
            ${signalHistory.map((row) => `
              <div class="table-row history-grid">
                <span>${escapeHtml(formatDate(row.session_date))}</span>
                <span>${escapeHtml(row.ticker)}</span>
                <span>${escapeHtml(row.direction)}</span>
                <span>${escapeHtml(row.outcome_status)}</span>
                <span>${formatPct(row.realized_return_pct, 1)}</span>
                <span>${escapeHtml(`${row.holding_days}d`)}</span>
              </div>
            `).join("")}
          </div>
        ` : `<div class="empty-state">No signal history rows are available yet.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">History</p>
            <h3>Position recommendations</h3>
          </div>
        </div>
        ${positionRecommendations.length ? `
          <div class="signal-table">
            <div class="table-row table-head history-grid">
              <span>Position</span>
              <span>Action</span>
              <span>Confidence</span>
              <span>Effective</span>
              <span>Suggested size</span>
              <span>Rationale</span>
            </div>
            ${positionRecommendations.map((row) => `
              <div class="table-row history-grid">
                <span>${escapeHtml(row.position_id)}</span>
                <span class="badge tone-${actionTone(row.action)}">${escapeHtml(humanizeKey(row.action))}</span>
                <span>${formatPct(row.confidence, 0)}</span>
                <span>${escapeHtml(formatDateTime(row.effective_at))}</span>
                <span>${escapeHtml(row.suggested_size_action || "hold")}</span>
                <span>${escapeHtml(row.rationale || "")}</span>
              </div>
            `).join("")}
          </div>
        ` : `<div class="empty-state">No recommendation history rows are available yet.</div>`}
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">History</p>
            <h3>Trade events</h3>
          </div>
        </div>
        ${positionEvents.length ? `
          <div class="signal-table">
            <div class="table-row table-head history-grid">
              <span>Position</span>
              <span>Event</span>
              <span>Quantity</span>
              <span>Price</span>
              <span>Executed at</span>
              <span>Notes</span>
            </div>
            ${positionEvents.map((row) => `
              <div class="table-row history-grid">
                <span>${escapeHtml(row.position_id)}</span>
                <span>${escapeHtml(row.event_type)}</span>
                <span>${escapeHtml(String(row.quantity ?? "-"))}</span>
                <span>${escapeHtml(String(row.price ?? "-"))}</span>
                <span>${escapeHtml(formatDateTime(row.executed_at))}</span>
                <span>${escapeHtml(row.notes || "")}</span>
              </div>
            `).join("")}
          </div>
        ` : `<div class="empty-state">No position event rows are available yet.</div>`}
      </article>
    </section>
  `;
}
