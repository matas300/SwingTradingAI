import { buildSparklinePath, compactList, escapeHtml, formatDate, formatPct, formatPrice, reliabilityTone, signalTone } from "../formatters.js";

function targetCards(targets) {
  if (!targets?.length) {
    return `<div class="empty-state">No structured targets available for this setup.</div>`;
  }
  return `
    <div class="target-grid">
      ${targets
        .map(
          (target) => `
            <article class="target-card">
              <small>${escapeHtml(target.kind.replaceAll("_", " "))}</small>
              <strong>${formatPrice(target.price)}</strong>
              <span>${formatPct(target.probability || 0, 0)} probability</span>
              <p>${escapeHtml(target.rationale)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

export function renderTickerDetail(state) {
  const ticker = state.route.ticker || state.data?.watchlist?.[0]?.ticker;
  const detail = ticker ? state.data?.tickers?.[ticker] : null;
  if (!detail) {
    return `<div class="empty-state">Choose a ticker from Watchlist or Signals to inspect its adaptive profile.</div>`;
  }

  const prediction = detail.latest_prediction || {};
  const profile = detail.profile || {};
  const closes = (detail.snapshots || []).map((item) => Number(item.close)).filter((value) => Number.isFinite(value));
  const path = buildSparklinePath(closes);

  return `
    <section class="detail-hero panel">
      <div>
        <p class="eyebrow">Ticker detail</p>
        <h2>${escapeHtml(ticker)}</h2>
        <p class="lede">${escapeHtml(prediction?.rationale?.summary || "No active rationale captured yet.")}</p>
      </div>
      <div class="detail-meta">
        <span class="badge tone-${signalTone(prediction.direction)}">${escapeHtml(String(prediction.direction || "neutral"))}</span>
        <span class="badge tone-${reliabilityTone(prediction.reliability_label)}">${escapeHtml(prediction.reliability_label || "Unknown")}</span>
        <button class="ghost-button" data-action="favorite" data-ticker="${escapeHtml(ticker)}">${state.favorites.includes(ticker) ? "Pinned" : "Pin"}</button>
      </div>
    </section>

    <section class="content-grid">
      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Price context</p>
            <h3>Confirmed daily path</h3>
          </div>
          <div class="meta-inline">
            <span>Last close ${formatPrice(detail.summary?.close)}</span>
            <span>Trend ${escapeHtml(detail.summary?.trend || "-")}</span>
          </div>
        </div>
        <div class="chart-card">
          <svg viewBox="0 0 360 120" preserveAspectRatio="none" aria-label="Price sparkline">
            <path d="${escapeHtml(path)}" class="sparkline-path"></path>
          </svg>
          <div class="chart-foot">
            <span>${escapeHtml(formatDate(detail.snapshots?.[0]?.session_date))}</span>
            <span>${escapeHtml(formatDate(detail.snapshots?.at(-1)?.session_date))}</span>
          </div>
        </div>
        ${targetCards(prediction.targets)}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Plan</p>
            <h3>Structured output</h3>
          </div>
        </div>
        <div class="metric-list">
          <div><span>Entry zone</span><strong>${formatPrice(prediction.entry_low)} - ${formatPrice(prediction.entry_high)}</strong></div>
          <div><span>Stop loss</span><strong>${formatPrice(prediction.stop_loss)}</strong></div>
          <div><span>Risk/reward</span><strong>${prediction.risk_reward ? prediction.risk_reward.toFixed(2) : "-"}</strong></div>
          <div><span>Holding horizon</span><strong>${prediction.holding_horizon_days || "-"} days</strong></div>
          <div><span>Confidence</span><strong>${formatPct(prediction.confidence_score, 0)}</strong></div>
          <div><span>Warnings</span><strong>${escapeHtml(compactList(prediction.warning_flags || [], 3))}</strong></div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Adaptive profile</p>
            <h3>Per-ticker calibration</h3>
          </div>
        </div>
        <div class="metric-list">
          <div><span>Sample size</span><strong>${profile.sample_size ?? 0}</strong></div>
          <div><span>Long win rate</span><strong>${formatPct(profile.long_win_rate || 0, 0)}</strong></div>
          <div><span>Short win rate</span><strong>${formatPct(profile.short_win_rate || 0, 0)}</strong></div>
          <div><span>Target shrink</span><strong>${profile.target_shrink_factor?.toFixed?.(2) ?? "-"}</strong></div>
          <div><span>Reliability</span><strong>${profile.reliability_score?.toFixed?.(2) ?? "-"}</strong></div>
          <div><span>Mean target error</span><strong>${formatPct(profile.mean_target_error || 0, 1)}</strong></div>
        </div>
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Explainability</p>
            <h3>Top factors</h3>
          </div>
        </div>
        <div class="factor-list">
          ${(prediction.top_factors || [])
            .map(
              (factor) => `
                <div class="factor-row">
                  <strong>${escapeHtml(factor.name)}</strong>
                  <span>${factor.contribution > 0 ? "+" : ""}${Number(factor.contribution).toFixed(2)}</span>
                  <p>${escapeHtml(factor.detail)}</p>
                </div>
              `,
            )
            .join("")}
        </div>
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">History</p>
            <h3>Recent outcomes</h3>
          </div>
        </div>
        ${
          detail.signal_history?.length
            ? `<div class="signal-table">
                <div class="table-row table-head">
                  <span>Date</span>
                  <span>Direction</span>
                  <span>Status</span>
                  <span>Return</span>
                  <span>Holding</span>
                </div>
                ${detail.signal_history
                  .map(
                    (row) => `
                      <div class="table-row">
                        <span>${escapeHtml(formatDate(row.session_date))}</span>
                        <span>${escapeHtml(row.direction)}</span>
                        <span>${escapeHtml(row.outcome_status)}</span>
                        <span>${formatPct(row.realized_return_pct, 1)}</span>
                        <span>${escapeHtml(`${row.holding_days}d`)}</span>
                      </div>
                    `,
                  )
                  .join("")}
              </div>`
            : `<div class="empty-state">No resolved history captured yet.</div>`
        }
      </article>
    </section>
  `;
}
