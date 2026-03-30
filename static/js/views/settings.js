import { escapeHtml } from "../formatters.js";

export function renderSettings(state) {
  const settings = state.settings || {};
  const trackedTickers = (state.data?.study_watchlist || []).map((row) => row.ticker).join(", ");
  const capabilities = state.data?.capabilities || {};
  const canWrite = Boolean(capabilities.write && (capabilities.auth_mode !== "admin-token" || state.adminToken));
  const architecture = state.data?.architecture || {};
  const selectedArchitecture = "Netlify + Firebase + GitHub Actions";

  return `
    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Settings</p>
            <h3>Interface preferences</h3>
          </div>
        </div>
        <form id="settings-form" class="form-grid">
          <label>
            <span>Theme</span>
            <select name="theme">
              <option value="system" ${settings.theme === "system" ? "selected" : ""}>System</option>
              <option value="dark" ${settings.theme === "dark" ? "selected" : ""}>Dark</option>
              <option value="light" ${settings.theme === "light" ? "selected" : ""}>Light</option>
            </select>
          </label>
          <label>
            <span>Density</span>
            <select name="density">
              <option value="comfortable" ${settings.density === "comfortable" ? "selected" : ""}>Comfortable</option>
              <option value="compact" ${settings.density === "compact" ? "selected" : ""}>Compact</option>
            </select>
          </label>
          <label>
            <span>Default view</span>
            <select name="default_view">
              <option value="overview" ${settings.default_view === "overview" ? "selected" : ""}>Overview</option>
              <option value="watchlist" ${settings.default_view === "watchlist" ? "selected" : ""}>Watchlist</option>
              <option value="signals" ${settings.default_view === "signals" ? "selected" : ""}>Signals</option>
              <option value="positions" ${settings.default_view === "positions" ? "selected" : ""}>Open Positions</option>
            </select>
          </label>
          <label>
            <span>Favorite metric</span>
            <select name="favorite_metric">
              <option value="confidence" ${settings.favorite_metric === "confidence" ? "selected" : ""}>Confidence</option>
              <option value="pnl" ${settings.favorite_metric === "pnl" ? "selected" : ""}>PnL</option>
              <option value="risk_reward" ${settings.favorite_metric === "risk_reward" ? "selected" : ""}>Risk reward</option>
            </select>
          </label>
          <label>
            <span>Risk budget %</span>
            <input type="number" min="0" step="0.001" name="risk_budget_pct" value="${escapeHtml(settings.risk_budget_pct ?? 0.01)}">
          </label>
          <label>
            <span>Max add fraction</span>
            <input type="number" min="0" step="0.01" name="max_add_fraction" value="${escapeHtml(settings.max_add_fraction ?? 0.25)}">
          </label>
          <label class="toggle-inline">
            <input type="checkbox" name="show_only_actionable" ${settings.show_only_actionable ? "checked" : ""}>
            <span>Show only actionable setups by default</span>
          </label>
          ${capabilities.auth_mode === "admin-token" ? `
            <label>
              <span>Admin write token</span>
              <input type="password" name="admin_token" value="${escapeHtml(state.adminToken || "")}" placeholder="Required for hosted writes">
            </label>
          ` : `<input type="hidden" name="admin_token" value="">`}
          <button type="submit" class="primary-button">Save preferences</button>
        </form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Watchlist</p>
            <h3>Tracked tickers</h3>
          </div>
        </div>
        <form id="watchlist-form" class="form-grid">
          <label>
            <span>Tickers</span>
            <textarea name="tickers" rows="7" ${canWrite ? "" : "disabled"}>${escapeHtml(trackedTickers)}</textarea>
          </label>
          <p class="help-text">
            ${escapeHtml(
              canWrite
                ? "Saving here updates the writable watchlist source."
                : capabilities.auth_mode === "admin-token"
                ? "Insert the admin token above to unlock hosted watchlist changes."
                : "Static mode is read-only. Update tracked tickers locally or through the scheduled pipeline config.",
            )}
          </p>
          <button type="submit" class="secondary-button" ${canWrite ? "" : "disabled"}>Update watchlist</button>
        </form>
      </article>

      <article class="panel panel-wide">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Deploy</p>
            <h3>Free-tier architecture snapshot</h3>
          </div>
        </div>
        <div class="metric-list">
          <div><span>Selected architecture</span><strong>${escapeHtml(selectedArchitecture)}</strong></div>
          <div><span>Frontend</span><strong>Netlify static SPA</strong></div>
          <div><span>Batch</span><strong>GitHub Actions daily Python job</strong></div>
          <div><span>Storage</span><strong>Firebase cloud sync with local SQLite fallback</strong></div>
        </div>
      </article>
    </section>
  `;
}
