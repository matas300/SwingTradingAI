import { actionTone, compactList, escapeHtml, formatDateTime, formatPnl, formatPct, formatPrice, reliabilityTone, signalTone, buildSparklinePath } from "../formatters.js";

function signalCard(row) {
  return `
    <button class="signal-spotlight tone-${signalTone(row.direction)}" data-action="open-ticker" data-item="${escapeHtml(row.ticker)}">
      <div>
        <strong>${escapeHtml(row.ticker)}</strong>
        <span>${escapeHtml((row.direction || "neutral").toUpperCase())}</span>
      </div>
      <div>
        <small>Confidence</small>
        <strong>${formatPct(row.confidence_score, 0)}</strong>
      </div>
      <div>
        <small>Warnings</small>
        <span>${escapeHtml(compactList(row.warning_flags || [], 2))}</span>
      </div>
    </button>
  `;
}

function positionCard(row) {
  return `
    <button class="list-row tone-${actionTone(row.last_recommendation)}" data-action="open-position" data-item="${escapeHtml(row.position_id)}">
      <div>
        <strong>${escapeHtml(row.ticker)}</strong>
        <small>${escapeHtml(row.side)} - ${escapeHtml(row.strategy_name || "strategy")}</small>
      </div>
      <div>
        <strong>${formatPnl(row.total_pnl)}</strong>
        <small>Total PnL</small>
      </div>
      <div>
        <strong>${escapeHtml((row.last_recommendation || "no_action").toUpperCase())}</strong>
        <small>${formatPct(row.last_recommendation_confidence || 0, 0)}</small>
      </div>
    </button>
  `;
}

export function renderOverview(state) {
  const data = state.data;
  if (!data) return `<div class="empty-state">No dashboard data loaded yet.</div>`;

  const overview = data.overview || {};
  const signals = data.signals || [];
  const positions = data.open_positions || [];
  const watchlist = data.study_watchlist || [];
  const actionableSignals = signals.filter((row) => row.direction !== "neutral").slice(0, 4);
  const actionQueue = positions.filter((row) => ["add", "reduce", "close"].includes(row.last_recommendation)).slice(0, 4);
  const equityPath = buildSparklinePath(
    positions.map((row) => Number(row.total_pnl || 0)).filter((value) => Number.isFinite(value)),
    640,
    160,
  );

  return `
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Overview</p>
        <h2>Research and execution stay separated, but fully linked.</h2>
        <p class="lede">Latest refresh: ${escapeHtml(formatDateTime(data.generated_at))}. The study watchlist stays capital-free; open positions keep event history, adaptive targets, and a next-action recommendation.</p>
      </div>
      <div class="hero-meta">
        <span class="pill tone-green">${escapeHtml(`${overview.open_positions || 0} open positions`)}</span>
        <span class="pill tone-slate">${escapeHtml(`${overview.tracked_tickers || 0} study tickers`)}</span>
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi-card"><span>Tracked tickers</span><strong>${overview.tracked_tickers ?? 0}</strong></article>
      <article class="kpi-card"><span>Actionable signals</span><strong>${(overview.long_count ?? 0) + (overview.short_count ?? 0)}</strong></article>
      <article class="kpi-card"><span>Open positions</span><strong>${overview.open_positions ?? 0}</strong></article>
      <article class="kpi-card"><span>Unrealized PnL</span><strong>${formatPnl(overview.total_unrealized_pnl ?? 0)}</strong></article>
      <article class="kpi-card"><span>Realized PnL</span><strong>${formatPnl(overview.total_realized_pnl ?? 0)}</strong></article>
      <article class="kpi-card"><span>Avg confidence</span><strong>${formatPct(overview.avg_confidence ?? 0, 0)}</strong></article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Study layer</p>
            <h3>Study watchlist</h3>
          </div>
          <button class="secondary-button" data-action="open-view" data-item="watchlist">Open watchlist</button>
        </div>
        ${watchlist.length ? `<div class="signal-spotlights">${watchlist.slice(0, 4).map(signalCard).join("")}</div>` : `<div class="empty-state">No study tickers available yet.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Execution layer</p>
            <h3>Positions needing attention</h3>
          </div>
          <button class="secondary-button" data-action="open-view" data-item="positions">Open positions</button>
        </div>
        ${actionQueue.length ? `<div class="list-stack">${actionQueue.map(positionCard).join("")}</div>` : `<div class="empty-state">No open position currently requests a stronger action than maintain.</div>`}
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Latest operating queue</p>
            <h3>Open positions</h3>
          </div>
        </div>
        ${positions.length ? `
          <div class="chart-card">
            <svg viewBox="0 0 640 160" class="chart-svg" role="img" aria-label="Open position PnL sparkline">
              <path d="${equityPath}" class="sparkline-path"></path>
            </svg>
          </div>
          <div class="signal-table">
            <div class="table-row table-head overview-grid">
              <span>Ticker</span>
              <span>Side</span>
              <span>Average entry</span>
              <span>Current price</span>
              <span>Total PnL</span>
              <span>Recommendation</span>
              <span>Next target</span>
            </div>
            ${positions.slice(0, 8).map((row) => `
              <button class="table-row table-button overview-grid" data-action="open-position" data-item="${escapeHtml(row.position_id)}">
                <span>${escapeHtml(row.ticker)}</span>
                <span class="badge tone-${signalTone(row.side)}">${escapeHtml(row.side)}</span>
                <span>${formatPrice(row.average_entry_price)}</span>
                <span>${formatPrice(row.mark_price)}</span>
                <span>${formatPnl(row.total_pnl)}</span>
                <span class="badge tone-${actionTone(row.last_recommendation)}">${escapeHtml((row.last_recommendation || "no_action").replaceAll("_", " "))}</span>
                <span>${formatPrice((row.current_adaptive_targets || [])[0]?.price || row.next_target || null)}</span>
              </button>
            `).join("")}
          </div>
        ` : `<div class="empty-state">Open a real position from a signal to start daily position tracking.</div>`}
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Signals</p>
            <h3>High conviction setups</h3>
          </div>
        </div>
        ${actionableSignals.length ? actionableSignals.map(signalCard).join("") : `<div class="empty-state">No actionable study signals in the latest refresh.</div>`}
      </article>
    </section>
  `;
}
