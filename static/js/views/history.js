import { escapeHtml, formatDate, formatPct } from "../formatters.js";

export function renderHistory(state) {
  const rows = state.data?.history || [];
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">History</p>
          <h3>Outcome tape</h3>
        </div>
      </div>
      ${
        rows.length
          ? `<div class="signal-table">
              <div class="table-row table-head">
                <span>Date</span>
                <span>Ticker</span>
                <span>Direction</span>
                <span>Status</span>
                <span>Return</span>
                <span>Holding</span>
              </div>
              ${rows
                .map(
                  (row) => `
                    <div class="table-row">
                      <span>${escapeHtml(formatDate(row.session_date))}</span>
                      <span>${escapeHtml(row.ticker)}</span>
                      <span>${escapeHtml(row.direction)}</span>
                      <span>${escapeHtml(row.outcome_status)}</span>
                      <span>${formatPct(row.realized_return_pct, 1)}</span>
                      <span>${escapeHtml(`${row.holding_days}d`)}</span>
                    </div>
                  `,
                )
                .join("")}
            </div>`
          : `<div class="empty-state">No history rows are available yet.</div>`
      }
    </section>
  `;
}
