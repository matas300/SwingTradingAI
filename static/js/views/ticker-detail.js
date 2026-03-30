import { compactList, escapeHtml, formatDate, formatDateTime, formatPct, formatPrice, humanizeKey, reliabilityTone, signalTone, buildSparklinePath } from "../formatters.js";

function chartValues(detail) {
  return (detail?.snapshots || []).map((row) => Number(row.close)).filter((value) => Number.isFinite(value));
}

function signalSummary(signal) {
  if (!signal) return null;
  return signal.latest_prediction || signal.latest_signal || signal;
}

export function renderTickerDetail(state, ticker) {
  const detail = state.data?.tickers?.[ticker];
  const capabilities = state.data?.capabilities || {};
  const canWrite = Boolean(capabilities.write && (capabilities.auth_mode !== "admin-token" || state.adminToken));
  if (!ticker) return `<div class="empty-state">No ticker selected.</div>`;
  if (!detail) return `<div class="empty-state">Ticker ${escapeHtml(ticker)} is not cached yet. Open it from the watchlist or signals first.</div>`;

  const signal = signalSummary(detail);
  const profile = detail.profile || {};
  const snapshots = detail.snapshots || [];
  const values = chartValues(detail);
  const chartPath = buildSparklinePath(values, 640, 180);
  const latestClose = snapshots.at(-1)?.close ?? signal?.entry_reference_price ?? null;

  return `
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Ticker Detail</p>
        <h2>${escapeHtml(ticker)}</h2>
        <p class="lede">Study layer only. This view shows the latest signal, the adaptive profile, and the original target geometry before a real position is opened.</p>
      </div>
      <div class="hero-meta">
        ${signal ? `<span class="pill tone-${signalTone(signal.direction)}">${escapeHtml(signal.direction.toUpperCase())}</span>` : ""}
        ${signal ? `<span class="pill tone-${reliabilityTone(signal.reliability_label)}">${escapeHtml(signal.reliability_label || "unrated")}</span>` : ""}
        ${signal && signal.direction !== "neutral" ? `<button class="primary-button" data-action="open-position-modal" data-item="${escapeHtml(ticker)}" ${canWrite ? "" : "disabled"}>Open position from this signal</button>` : ""}
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi-card"><span>Last close</span><strong>${formatPrice(latestClose)}</strong></article>
      <article class="kpi-card"><span>Confidence</span><strong>${formatPct(signal?.confidence_score ?? 0, 0)}</strong></article>
      <article class="kpi-card"><span>Risk reward</span><strong>${signal?.risk_reward ? signal.risk_reward.toFixed(2) : "-"}</strong></article>
      <article class="kpi-card"><span>Profile reliability</span><strong>${formatPct(profile.reliability_score ?? 0, 0)}</strong></article>
      <article class="kpi-card"><span>Trend</span><strong>${escapeHtml(snapshots.at(-1)?.trend || "n/a")}</strong></article>
      <article class="kpi-card"><span>Regime</span><strong>${escapeHtml(snapshots.at(-1)?.market_regime || "n/a")}</strong></article>
    </section>

    <section class="content-grid">
      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Price context</p>
            <h3>Daily closes</h3>
          </div>
        </div>
        ${values.length ? `
          <div class="chart-card">
            <svg viewBox="0 0 640 180" class="chart-svg" role="img" aria-label="Ticker price sparkline">
              <path d="${chartPath}" class="sparkline-path"></path>
            </svg>
          </div>
        ` : `<div class="empty-state">No price history available.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Signal</p>
            <h3>Latest setup</h3>
          </div>
        </div>
        ${signal ? `
          <div class="metric-list">
            <div><span>Direction</span><strong>${escapeHtml(signal.direction)}</strong></div>
            <div><span>Entry zone</span><strong>${formatPrice(signal.entry_low)} - ${formatPrice(signal.entry_high)}</strong></div>
            <div><span>Stop loss</span><strong>${formatPrice(signal.stop_loss)}</strong></div>
            <div><span>Confidence</span><strong>${formatPct(signal.confidence_score, 0)}</strong></div>
            <div><span>Holding horizon</span><strong>${escapeHtml(signal.holding_horizon_days ? `${signal.holding_horizon_days} days` : "-")}</strong></div>
            <div><span>Warnings</span><strong>${escapeHtml(compactList(signal.warning_flags || [], 3))}</strong></div>
          </div>
          <p class="help-text">${escapeHtml(signal.rationale?.summary || "No rationale available.")}</p>
        ` : `<div class="empty-state">No signal has been stored for this ticker yet.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Profile</p>
            <h3>Adaptive ticker profile</h3>
          </div>
        </div>
        <div class="metric-list">
          <div><span>Sample size</span><strong>${escapeHtml(profile.sample_size ?? 0)}</strong></div>
          <div><span>Long win rate</span><strong>${formatPct(profile.long_win_rate ?? 0, 0)}</strong></div>
          <div><span>Short win rate</span><strong>${formatPct(profile.short_win_rate ?? 0, 0)}</strong></div>
          <div><span>Trend persistence</span><strong>${formatPct(profile.trend_persistence ?? 0, 0)}</strong></div>
          <div><span>Target calibration error</span><strong>${formatPct(profile.confidence_calibration_error ?? 0, 0)}</strong></div>
          <div><span>Warnings</span><strong>${escapeHtml(compactList(profile.warning_flags || [], 2))}</strong></div>
        </div>
      </article>
    </section>

    <section class="panel panel-wide">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Signal history</p>
          <h3>Stored outcomes and snapshots</h3>
        </div>
      </div>
      ${snapshots.length ? `
        <div class="signal-table">
          <div class="table-row table-head ticker-grid">
            <span>Date</span><span>Open</span><span>High</span><span>Low</span><span>Close</span><span>Trend</span><span>Regime</span>
          </div>
          ${snapshots.slice(-8).map((row) => `
            <div class="table-row ticker-grid">
              <span>${escapeHtml(formatDate(row.session_date))}</span>
              <span>${formatPrice(row.open)}</span>
              <span>${formatPrice(row.high)}</span>
              <span>${formatPrice(row.low)}</span>
              <span>${formatPrice(row.close)}</span>
              <span>${escapeHtml(row.trend || "-")}</span>
              <span>${escapeHtml(row.market_regime || "-")}</span>
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty-state">No snapshot history yet.</div>`}
    </section>

    <section class="panel panel-wide">
      <div class="panel-head">
        <div>
          <p class="eyebrow">History</p>
          <h3>Signal tape</h3>
        </div>
      </div>
      ${detail.signal_history?.length ? `
        <div class="signal-table">
          <div class="table-row table-head ticker-grid">
            <span>Date</span><span>Direction</span><span>Status</span><span>Target hit</span><span>Stop hit</span><span>Return</span><span>Holding</span>
          </div>
          ${detail.signal_history.slice(-8).map((row) => `
            <div class="table-row ticker-grid">
              <span>${escapeHtml(formatDate(row.session_date))}</span>
              <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
              <span>${escapeHtml(row.outcome_status || "-")}</span>
              <span>${escapeHtml(row.target_1_hit ? "Yes" : "No")}</span>
              <span>${escapeHtml(row.stop_hit ? "Yes" : "No")}</span>
              <span>${formatPct(row.realized_return_pct || 0, 1)}</span>
              <span>${escapeHtml(row.holding_days != null ? `${row.holding_days}d` : "-")}</span>
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty-state">No signal outcomes have been recorded yet.</div>`}
    </section>
  `;
}
