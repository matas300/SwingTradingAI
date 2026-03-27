import { escapeHtml } from "../formatters.js";

export function renderSettings(state) {
  const settings = state.settings || {};
  const trackedTickers = (state.data?.watchlist || []).map((row) => row.ticker).join(", ");
  const apiWritable = state.source === "api";

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
            </select>
          </label>
          <label class="toggle-inline">
            <input type="checkbox" name="show_only_actionable" ${settings.show_only_actionable ? "checked" : ""}>
            <span>Show only actionable setups by default</span>
          </label>
          <button type="submit" class="primary-button">Save preferences</button>
        </form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Tracked tickers</p>
            <h3>Daily refresh scope</h3>
          </div>
        </div>
        <form id="watchlist-form" class="form-grid">
          <label>
            <span>Tickers</span>
            <textarea name="tickers" rows="7" ${apiWritable ? "" : "disabled"}>${escapeHtml(trackedTickers)}</textarea>
          </label>
          <p class="help-text">
            ${escapeHtml(
              apiWritable
                ? "Saving here updates the local API watchlist and runs a fresh daily refresh."
                : "Static mode is read-only. Update tracked tickers locally or through the scheduled pipeline config.",
            )}
          </p>
          <button type="submit" class="secondary-button" ${apiWritable ? "" : "disabled"}>Update watchlist</button>
        </form>
      </article>
    </section>
  `;
}
