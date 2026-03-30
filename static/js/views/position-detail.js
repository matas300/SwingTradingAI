import { actionTone, compactList, escapeHtml, formatDate, formatDateTime, formatPnl, formatPct, formatPrice, humanizeKey, signalTone, buildSparklinePath } from "../formatters.js";

function extractTargets(targetSet) {
  if (!targetSet) return [];
  if (Array.isArray(targetSet)) return targetSet;
  const mapping = [
    ["stop_loss", targetSet.stop_loss],
    ["target_1", targetSet.target_1],
    ["target_2", targetSet.target_2],
    ["target_3", targetSet.target_3 ?? targetSet.optional_target_3],
    ["probabilistic_target", targetSet.probabilistic_target],
  ];
  return mapping
    .filter(([, price]) => price != null)
    .map(([kind, price]) => ({ kind, price }));
}

function eventLabel(event) {
  return humanizeKey(event.event_type || event.eventType || "-");
}

function chartValues(detail) {
  return (detail?.chart || []).map((row) => Number(row.close)).filter((value) => Number.isFinite(value));
}

export function renderPositionDetail(state, positionId) {
  const detail = state.data?.positions?.[positionId];
  const capabilities = state.data?.capabilities || {};
  const canWrite = Boolean(capabilities.write && (capabilities.auth_mode !== "admin-token" || state.adminToken));
  if (!positionId) return `<div class="empty-state">No position selected.</div>`;
  if (!detail) return `<div class="empty-state">Position ${escapeHtml(positionId)} is not cached yet. Open it from the positions view first.</div>`;

  const position = detail.position || {};
  const originSignal = detail.origin_signal || detail.signal_origin || null;
  const originalTargets = extractTargets(detail.original_targets);
  const adaptiveTargets = extractTargets(detail.adaptive_targets);
  const events = detail.events || [];
  const recommendations = detail.recommendations || [];
  const chartValuesList = chartValues(detail);
  const chartPath = buildSparklinePath(chartValuesList, 640, 180);

  return `
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Position Detail</p>
        <h2>${escapeHtml(position.ticker || positionId)}</h2>
        <p class="lede">This view keeps the original signal, the real trade events, and the adaptive recommendation chain in one place.</p>
      </div>
      <div class="hero-meta">
        <span class="pill tone-${signalTone(position.side)}">${escapeHtml(position.side || "-")}</span>
        <span class="pill tone-${actionTone(position.last_recommendation)}">${escapeHtml(humanizeKey(position.last_recommendation || "maintain"))}</span>
        <button class="secondary-button" data-action="open-add" data-item="${escapeHtml(position.position_id || positionId)}" ${canWrite ? "" : "disabled"}>Add</button>
        <button class="secondary-button" data-action="open-reduce" data-item="${escapeHtml(position.position_id || positionId)}" ${canWrite ? "" : "disabled"}>Reduce</button>
        <button class="secondary-button" data-action="open-close" data-item="${escapeHtml(position.position_id || positionId)}" ${canWrite ? "" : "disabled"}>Close all</button>
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi-card"><span>Average entry</span><strong>${formatPrice(position.average_entry_price)}</strong></article>
      <article class="kpi-card"><span>Current quantity</span><strong>${formatPrice(position.current_quantity)}</strong></article>
      <article class="kpi-card"><span>Total PnL</span><strong>${formatPnl(position.total_pnl)}</strong></article>
      <article class="kpi-card"><span>Recommendation</span><strong>${escapeHtml(humanizeKey(position.last_recommendation || "maintain"))}</strong></article>
      <article class="kpi-card"><span>Confidence</span><strong>${formatPct(position.last_recommendation_confidence || 0, 0)}</strong></article>
      <article class="kpi-card"><span>Holding days</span><strong>${escapeHtml(position.holding_days ?? 0)}</strong></article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Original signal</p>
            <h3>Entry, stop, and targets from the study layer</h3>
          </div>
        </div>
        ${originSignal ? `
          <div class="metric-list">
            <div><span>Direction</span><strong>${escapeHtml(originSignal.direction || position.side)}</strong></div>
            <div><span>Entry zone</span><strong>${formatPrice(originSignal.entry_low)} - ${formatPrice(originSignal.entry_high)}</strong></div>
            <div><span>Stop</span><strong>${formatPrice(originSignal.stop_loss)}</strong></div>
            <div><span>Confidence</span><strong>${formatPct(originSignal.confidence_score || 0, 0)}</strong></div>
            <div><span>Rationale</span><strong>${escapeHtml(originSignal.rationale?.summary || "n/a")}</strong></div>
          </div>
        ` : `<div class="empty-state">No origin signal available.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Target comparison</p>
            <h3>Original vs adaptive</h3>
          </div>
        </div>
        <div class="target-grid">
          <article class="target-card">
            <small>Original target 1</small>
            <strong>${formatPrice(originalTargets.find((row) => row.kind === "target_1")?.price)}</strong>
          </article>
          <article class="target-card">
            <small>Adaptive target 1</small>
            <strong>${formatPrice(adaptiveTargets.find((row) => row.kind === "target_1")?.price)}</strong>
          </article>
          <article class="target-card">
            <small>Stop update</small>
            <strong>${formatPrice(position.current_stop)}</strong>
          </article>
        </div>
        <p class="help-text">${escapeHtml(detail.adaptive_targets?.rationale?.summary || detail.original_targets?.rationale?.summary || "Adaptive targets preserve the original signal geometry while re-anchoring to the real position.")}</p>
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Price path</p>
            <h3>Markers across the live position lifecycle</h3>
          </div>
        </div>
        ${chartValuesList.length ? `
          <div class="chart-card">
            <svg viewBox="0 0 640 180" class="chart-svg" role="img" aria-label="Position price chart">
              <path d="${chartPath}" class="sparkline-path"></path>
            </svg>
            <div class="chart-foot">
              <span>Opened ${escapeHtml(formatDateTime(position.opened_at))}</span>
              <span>Last update ${escapeHtml(formatDateTime(position.updated_at))}</span>
            </div>
          </div>
        ` : `<div class="empty-state">No chart history available yet.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Timeline</p>
            <h3>Trade events</h3>
          </div>
          <button class="secondary-button" data-action="open-note" data-item="${escapeHtml(position.position_id || positionId)}" ${canWrite ? "" : "disabled"}>Edit notes</button>
        </div>
        ${events.length ? `
          <div class="factor-list">
            ${events.map((event) => `
              <article class="factor-row">
                <div class="detail-meta">
                  <span class="badge tone-${actionTone(event.event_type === "REDUCE" ? "reduce" : event.event_type === "CLOSE" ? "close" : "maintain")}">${escapeHtml(eventLabel(event))}</span>
                  <span>${escapeHtml(formatDateTime(event.executed_at))}</span>
                </div>
                <strong>${formatPrice(event.price)} - ${formatPrice(event.quantity)}</strong>
                <p>${escapeHtml(event.notes || event.metadata?.summary || compactList(Object.keys(event.metadata || {}), 3))}</p>
              </article>
            `).join("")}
          </div>
        ` : `<div class="empty-state">No events recorded yet.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Recommendations</p>
            <h3>Daily policy output</h3>
          </div>
        </div>
        ${recommendations.length ? `
          <div class="factor-list">
            ${recommendations.slice(0, 6).map((recommendation) => `
              <article class="factor-row">
                <div class="detail-meta">
                  <span class="badge tone-${actionTone(recommendation.action)}">${escapeHtml(humanizeKey(recommendation.action))}</span>
                  <span>${escapeHtml(formatDateTime(recommendation.effective_at))}</span>
                </div>
                <strong>${escapeHtml(formatPct(recommendation.confidence || 0, 0))}</strong>
                <p>${escapeHtml(recommendation.rationale || "No rationale available.")}</p>
                <p class="help-text">${escapeHtml(compactList(recommendation.warning_flags || [], 3))}</p>
              </article>
            `).join("")}
          </div>
        ` : `<div class="empty-state">No recommendation history yet.</div>`}
      </article>
    </section>

    <section class="panel panel-wide">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Risk notes</p>
          <h3>Warnings and context</h3>
        </div>
      </div>
      <div class="metric-list">
        <div><span>Status</span><strong>${escapeHtml(position.status || "open")}</strong></div>
        <div><span>Original stop</span><strong>${formatPrice(position.original_stop)}</strong></div>
        <div><span>Current stop</span><strong>${formatPrice(position.current_stop)}</strong></div>
        <div><span>Last recommendation</span><strong>${escapeHtml(position.last_recommendation_reason || "n/a")}</strong></div>
        <div><span>Warnings</span><strong>${escapeHtml(compactList(position.warning_flags || [], 3))}</strong></div>
      </div>
    </section>
  `;
}
