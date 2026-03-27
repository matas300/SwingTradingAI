import { escapeHtml, formatPct, formatPrice, reliabilityTone, signalTone } from "../formatters.js";

export function renderSignals(state) {
  const rows = state.data?.signals || [];
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Signals</p>
          <h3>Latest structured plans</h3>
        </div>
      </div>
      ${
        rows.length
          ? `<div class="signal-table">
              <div class="table-row table-head">
                <span>Ticker</span>
                <span>Direction</span>
                <span>Entry zone</span>
                <span>Stop</span>
                <span>Confidence</span>
                <span>RR</span>
                <span>Reliability</span>
              </div>
              ${rows
                .map(
                  (row) => `
                    <button class="table-row table-button" data-action="open-ticker" data-ticker="${escapeHtml(row.ticker)}">
                      <span>${escapeHtml(row.ticker)}</span>
                      <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
                      <span>${formatPrice(row.entry_low)} - ${formatPrice(row.entry_high)}</span>
                      <span>${formatPrice(row.stop_loss)}</span>
                      <span>${formatPct(row.confidence_score, 0)}</span>
                      <span>${row.risk_reward ? row.risk_reward.toFixed(2) : "-"}</span>
                      <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label)}</span>
                    </button>
                  `,
                )
                .join("")}
            </div>`
          : `<div class="empty-state">Signals will appear after the first completed daily refresh.</div>`
      }
    </section>
  `;
}
