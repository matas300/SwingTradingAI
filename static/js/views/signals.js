import { compactList, escapeHtml, formatDateTime, formatPct, formatPrice, humanizeKey, reliabilityTone, signalTone } from "../formatters.js";

export function renderSignals(state) {
  const rows = state.data?.signals || [];
  const capabilities = state.data?.capabilities || {};
  const canWrite = Boolean(capabilities.write && (capabilities.auth_mode !== "admin-token" || state.adminToken));
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Signals</p>
          <h3>Structured setups ready for review</h3>
          <p class="help-text">Open a real position from here only when you actually follow the setup.</p>
        </div>
      </div>
      ${rows.length ? `
        <div class="signal-table">
          <div class="table-row table-head signal-grid">
            <span>Ticker</span>
            <span>Direction</span>
            <span>Entry zone</span>
            <span>Stop</span>
            <span>Confidence</span>
            <span>RR</span>
            <span>Strategy</span>
            <span>Action</span>
          </div>
          ${rows.map((row) => `
            <div class="table-row signal-grid">
              <button class="table-button inline-button" data-action="open-ticker" data-item="${escapeHtml(row.ticker)}">${escapeHtml(row.ticker)}</button>
              <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
              <span>${formatPrice(row.entry_low)} - ${formatPrice(row.entry_high)}</span>
              <span>${formatPrice(row.stop_loss)}</span>
              <span>${formatPct(row.confidence_score, 0)}</span>
              <span>${row.risk_reward ? row.risk_reward.toFixed(2) : "-"}</span>
              <span>${escapeHtml(row.strategy_name || row.setup_name || "adaptive-swing-v2")}</span>
              <div class="table-actions">
                <button class="ghost-button" data-action="open-ticker" data-item="${escapeHtml(row.ticker)}">Inspect</button>
                <button class="secondary-button" data-action="open-position-modal" data-item="${escapeHtml(row.ticker)}" ${canWrite && row.direction !== "neutral" ? "" : "disabled"}>Open position</button>
              </div>
            </div>
            <div class="subtle-row">
              <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label)}</span>
              <span>${escapeHtml(compactList(row.warning_flags || [], 3))}</span>
              <span>${escapeHtml(formatDateTime(row.generated_at || row.updated_at || state.data?.generated_at))}</span>
              <span>${escapeHtml(humanizeKey(row.setup_quality || "balanced"))}</span>
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty-state">Signals will appear after the first completed daily refresh.</div>`}
    </section>
  `;
}
