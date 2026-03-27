import { compactList, escapeHtml, formatDate, formatDateTime, formatPct, formatPrice, reliabilityTone, signalTone } from "../formatters.js";

function signalCard(row) {
  return `
    <button class="signal-spotlight tone-${signalTone(row.direction)}" data-action="open-ticker" data-ticker="${escapeHtml(row.ticker)}">
      <div>
        <strong>${escapeHtml(row.ticker)}</strong>
        <span>${escapeHtml(row.direction.toUpperCase())}</span>
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

export function renderOverview(state) {
  const data = state.data;
  if (!data) {
    return `<div class="empty-state">No dashboard data loaded yet.</div>`;
  }

  const overview = data.overview || {};
  const signals = data.signals || [];
  const actionable = signals.filter((row) => row.direction !== "neutral").slice(0, 6);
  const recentHistory = (data.history || []).slice(0, 8);

  return `
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Daily swing intelligence</p>
        <h2>Actionable setup quality, not one more scan dump.</h2>
        <p class="lede">
          Latest refresh: ${escapeHtml(formatDateTime(data.generated_at))}. Source mode: ${escapeHtml(state.source)}.
        </p>
      </div>
      <div class="hero-meta">
        <span class="pill tone-${state.source === "api" ? "green" : "amber"}">${escapeHtml(state.source === "api" ? "Live API" : "Static snapshot")}</span>
        <span class="pill tone-slate">${escapeHtml(formatDate(data.generated_at))}</span>
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi-card"><span>Tracked</span><strong>${overview.tracked_tickers ?? 0}</strong></article>
      <article class="kpi-card"><span>Long</span><strong>${overview.long_count ?? 0}</strong></article>
      <article class="kpi-card"><span>Short</span><strong>${overview.short_count ?? 0}</strong></article>
      <article class="kpi-card"><span>Neutral</span><strong>${overview.neutral_count ?? 0}</strong></article>
      <article class="kpi-card"><span>High confidence</span><strong>${overview.high_confidence_count ?? 0}</strong></article>
      <article class="kpi-card"><span>Avg confidence</span><strong>${formatPct(overview.avg_confidence ?? 0, 0)}</strong></article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Overview</p>
            <h3>Actionable first</h3>
          </div>
        </div>
        ${
          actionable.length
            ? `<div class="signal-spotlights">${actionable.map(signalCard).join("")}</div>`
            : `<div class="empty-state">No actionable signals in the latest daily run.</div>`
        }
      </article>
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Latest outcomes</p>
            <h3>Recent signal history</h3>
          </div>
        </div>
        ${
          recentHistory.length
            ? `<div class="list-stack">
                ${recentHistory
                  .map(
                    (row) => `
                      <div class="list-row">
                        <div>
                          <strong>${escapeHtml(row.ticker)}</strong>
                          <small>${escapeHtml(row.direction)}</small>
                        </div>
                        <div>
                          <strong>${escapeHtml(row.outcome_status)}</strong>
                          <small>${escapeHtml(formatDate(row.session_date))}</small>
                        </div>
                        <div>
                          <strong>${formatPct(row.realized_return_pct, 1)}</strong>
                          <small>${escapeHtml(`${row.holding_days}d`)}</small>
                        </div>
                      </div>
                    `,
                  )
                  .join("")}
              </div>`
            : `<div class="empty-state">Outcome history will populate after daily runs accumulate.</div>`
        }
      </article>
      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Signal snapshot</p>
            <h3>Top live plans</h3>
          </div>
        </div>
        <div class="signal-table">
          <div class="table-row table-head">
            <span>Ticker</span>
            <span>Direction</span>
            <span>Confidence</span>
            <span>RR</span>
            <span>Reliability</span>
            <span>Target 1</span>
          </div>
          ${signals
            .slice(0, 8)
            .map((row) => {
              const target = (row.targets || []).find((item) => item.kind === "target_1");
              return `
                <button class="table-row table-button" data-action="open-ticker" data-ticker="${escapeHtml(row.ticker)}">
                  <span>${escapeHtml(row.ticker)}</span>
                  <span class="badge tone-${signalTone(row.direction)}">${escapeHtml(row.direction)}</span>
                  <span>${formatPct(row.confidence_score, 0)}</span>
                  <span>${row.risk_reward ? row.risk_reward.toFixed(2) : "-"}</span>
                  <span class="badge tone-${reliabilityTone(row.reliability_label)}">${escapeHtml(row.reliability_label)}</span>
                  <span>${target ? formatPrice(target.price) : "-"}</span>
                </button>
              `;
            })
            .join("")}
        </div>
      </article>
    </section>
  `;
}
