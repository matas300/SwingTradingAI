const form = document.getElementById("scan-form");
const tickersField = document.getElementById("tickers");
const periodField = document.getElementById("daily-period");
const accountSizeField = document.getElementById("account-size");
const riskPerTradeField = document.getElementById("risk-per-trade");
const newsLookbackField = document.getElementById("news-lookback-days");
const newsEnabledField = document.getElementById("news-enabled");
const submitButton = document.getElementById("submit-button");
const autoscanButton = document.getElementById("autoscan-button");
const statusLine = document.getElementById("status-line");
const overviewCards = document.getElementById("overview-cards");
const macroContext = document.getElementById("macro-context");
const summaryWrap = document.getElementById("summary-table-wrap");
const tickerCards = document.getElementById("ticker-cards");
const COMPACT_RESULTS_THRESHOLD = 20;
const COMPACT_TICKER_PREVIEW_LIMIT = 18;
const COMPACT_FAILURE_PREVIEW_LIMIT = 8;

function setStatus(message) {
  statusLine.textContent = message;
}

function badgeClass(signal) {
  if (signal === "LONG") return "badge badge-green";
  if (signal === "SHORT") return "badge badge-red";
  if (signal === "NO TRADE") return "badge badge-amber";
  return "badge badge-slate";
}

function riskClass(level) {
  if (level === "LOW") return "badge badge-green";
  if (level === "MODERATE") return "badge badge-amber";
  return "badge badge-red";
}

function formatDateTime(value) {
  if (!value) return "Non disponibile";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("it-IT");
}

function formatDate(value) {
  if (!value) return "Non disponibile";
  const raw = String(value);
  const date = raw.includes("T") ? new Date(raw) : new Date(`${raw}T00:00:00`);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "numeric" });
}

function formatShortDate(value) {
  if (!value) return "";
  const raw = String(value);
  const date = raw.includes("T") ? new Date(raw) : new Date(`${raw}T00:00:00`);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString("it-IT", { day: "2-digit", month: "short" });
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function isBlankLike(value) {
  if (value === null || value === undefined) return true;
  const normalized = String(value).trim().toLowerCase();
  return normalized === "" || normalized === "n/a" || normalized === "n/d" || normalized === "null" || normalized === "none" || normalized === "nan";
}

function formatDisplayValue(value, fallback = "Non disponibile") {
  if (isBlankLike(value)) return fallback;
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? String(value)
      : value.toLocaleString("it-IT", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
  return String(value);
}

function formatDisplayPrice(value, fallback = "Non disponibile") {
  const number = toNumber(value);
  if (number === null) return fallback;
  return number.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatOperationalPrice(signal, value) {
  return formatDisplayPrice(value, signal === "NO TRADE" ? "Non attivo" : "Non disponibile");
}

function normalizeTickers(raw) {
  return raw
    .split(/[\n,;\s]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function renderEmpty(container, message) {
  container.innerHTML = `<div class="empty-state">${message}</div>`;
}

function syncNewsControls() {
  newsLookbackField.disabled = !newsEnabledField.checked;
}

function compactPreviewText(items, limit, formatter = (item) => item) {
  const visibleItems = items.slice(0, limit).map(formatter).filter(Boolean);
  const remaining = Math.max(items.length - visibleItems.length, 0);
  const suffix = remaining > 0 ? ` e altri ${remaining}` : "";
  return `${visibleItems.join(", ")}${suffix}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderOverview(data) {
  const { overview, generated_at, request, analysis_session_date, ui } = data;
  const modeLabel = ui?.scan_mode === "autoscan_top_100_usa"
    ? (ui.universe_name || "Autoscan Top 100 USA")
    : "Scansione manuale";
  const newsLabel = request.news_enabled ? "Attive" : "Spente";

  overviewCards.innerHTML = `
    <div class="overview-card">
      <span class="muted">Ultima scansione</span>
      <strong>${escapeHtml(formatDateTime(generated_at))}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Dati chiusi al</span>
      <strong>${escapeHtml(formatDate(analysis_session_date))}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">LONG</span>
      <strong>${overview.long_count}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">SHORT</span>
      <strong>${overview.short_count}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">NO TRADE</span>
      <strong>${overview.no_trade_count}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Periodo</span>
      <strong>${escapeHtml(request.daily_period)}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Ticker analizzati</span>
      <strong>${request.tickers.length}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Account size</span>
      <strong>${Number(request.account_size).toLocaleString("it-IT")}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Risk per trade</span>
      <strong>${(Number(request.risk_per_trade) * 100).toFixed(1)}%</strong>
    </div>
    <div class="overview-card">
      <span class="muted">Modalita</span>
      <strong>${escapeHtml(modeLabel)}</strong>
    </div>
    <div class="overview-card">
      <span class="muted">News</span>
      <strong>${escapeHtml(newsLabel)}</strong>
    </div>
  `;
}

function renderContext(data) {
  const context = data.context.market;
  const macro = data.context.macro_news;
  const newsEnabled = Boolean(data.request?.news_enabled);

  const warningItems = (context.warnings || []).map((item) => `
    <div class="headline-item">
      <small>Warning</small>
      <p>${escapeHtml(item)}</p>
    </div>
  `).join("");

  const headlineItems = (macro.headlines || []).slice(0, 3).map((item) => `
    <div class="headline-item">
      <small>${escapeHtml(item.headline.source)}</small>
      <p>${escapeHtml(item.headline.title)}</p>
    </div>
  `).join("");

  const hasAlerts = warningItems || headlineItems;
  const macroNewsLabel = newsEnabled
    ? `${escapeHtml(macro.level)} (${Number(macro.net_risk_score).toFixed(1)})`
    : "Spente";
  const themesLabel = newsEnabled
    ? escapeHtml((macro.matched_themes || []).slice(0, 3).map(translatedTheme).join(" | ") || "-")
    : "Filtro news disattivato";
  const headlineCount = newsEnabled ? (macro.headlines?.length ?? 0) : 0;

  macroContext.innerHTML = `
    <div class="context-metrics">
      <div class="mini-card">
        <span class="muted">Regime</span>
        <strong>${escapeHtml(context.risk_mode)}</strong>
      </div>
      <div class="mini-card">
        <span class="muted">SPY / QQQ</span>
        <strong>${escapeHtml(context.benchmark_trend)} / ${escapeHtml(context.growth_trend)}</strong>
      </div>
      <div class="mini-card">
        <span class="muted">VIX</span>
        <strong>${escapeHtml(formatDisplayPrice(context.vix_close))}</strong>
      </div>
      <div class="mini-card">
        <span class="muted">Macro-news</span>
        <strong>${macroNewsLabel}</strong>
      </div>
      <div class="mini-card">
        <span class="muted">Temi dominanti</span>
        <strong>${themesLabel}</strong>
      </div>
      <div class="mini-card">
        <span class="muted">Headline trovate</span>
        <strong>${headlineCount}</strong>
      </div>
    </div>
    ${hasAlerts ? `
      <div class="context-alerts">
        ${warningItems}
        ${headlineItems}
      </div>
    ` : ""}
  `;
}

function confidenceDescriptor(value) {
  const pct = Math.round(Number(value || 0) * 100);
  if (pct >= 80) return { label: `Alta (${pct}%)`, tone: "good" };
  if (pct >= 65) return { label: `Media (${pct}%)`, tone: "warn" };
  if (pct >= 50) return { label: `Base (${pct}%)`, tone: "neutral" };
  return { label: `Debole (${pct}%)`, tone: "neutral" };
}

function toneClass(tone) {
  if (tone === "good") return "tone tone-good";
  if (tone === "warn") return "tone tone-warn";
  if (tone === "bad") return "tone tone-bad";
  return "tone tone-neutral";
}

function humanSignal(signal) {
  if (signal === "LONG") return "Rialzista";
  if (signal === "SHORT") return "Ribassista";
  return "Attesa";
}

function humanTradeAction(signal) {
  if (signal === "LONG") return "Si puo valutare un acquisto";
  if (signal === "SHORT") return "Si puo valutare uno short";
  return "Meglio aspettare";
}

function actionBadgeLabel(signal) {
  if (signal === "LONG") return "Operativo long";
  if (signal === "SHORT") return "Operativo short";
  return "Attesa";
}

function technicalHeadline(signal) {
  if (signal === "LONG") return "Il grafico punta verso l'alto";
  if (signal === "SHORT") return "Il grafico punta verso il basso";
  return "Il grafico non da un messaggio pulito";
}

function marketModeLabel(mode) {
  if (mode === "RISK_ON") return "Mercato favorevole";
  if (mode === "RISK_OFF") return "Mercato fragile";
  return "Mercato incerto";
}

function translatedTheme(theme) {
  return String(theme || "")
    .replace("Rates/inflation", "tassi e inflazione")
    .replace("Energy/oil", "energia e petrolio")
    .replace("War/conflict", "guerra e conflitti")
    .replace("Trump/politics", "Trump e politica")
    .replace("Sanctions/tariffs", "dazi e sanzioni")
    .replace("Earnings", "trimestrali")
    .replace(/\sx\d+$/, "");
}

function relativeStrengthText(value) {
  const number = Number(value || 0);
  if (number >= 0.03) return "piu forte del mercato";
  if (number <= -0.03) return "piu debole del mercato";
  return "in linea col mercato";
}

function adxStrengthText(value) {
  const number = Number(value || 0);
  if (number >= 25) return "con movimento abbastanza forte";
  if (number >= 20) return "con movimento discreto ma non fortissimo";
  return "ma con poca forza";
}

function rsiPressureText(value, signal) {
  const number = Number(value || 0);
  if (signal === "LONG") {
    if (number >= 60) return "e momentum rialzista presente";
    return "ma momentum ancora da confermare";
  }
  if (signal === "SHORT") {
    if (number <= 40) return "e pressione ribassista presente";
    return "ma la pressione in vendita non e ancora piena";
  }
  if (number >= 60) return "con una spinta rialzista";
  if (number <= 40) return "con una pressione ribassista";
  return "con momentum neutro";
}

function technicalNarrative(setup) {
  const { technical, decision } = setup;
  const direction = technical.trend === "UP" ? "impostato al rialzo" : technical.trend === "DOWN" ? "impostato al ribasso" : "laterale";
  const strength = adxStrengthText(technical.adx);
  const momentum = rsiPressureText(technical.rsi, decision.technical_signal);
  const relative = relativeStrengthText(technical.relative_strength_1m);

  if (decision.technical_signal === "LONG") {
    return `Titolo ${direction}, ${strength}, ${momentum} e ${relative} nell'ultimo mese.`;
  }
  if (decision.technical_signal === "SHORT") {
    return `Titolo ${direction}, ${strength}, ${momentum} e ${relative} nell'ultimo mese.`;
  }
  return `Segnali ancora poco allineati: titolo ${direction}, ${strength} e ${relative}.`;
}

function practicalNarrative(setup) {
  const { decision, pricing } = setup;
  const confidence = confidenceDescriptor(decision.operational_confidence);
  const hasLevels = decision.operational_signal !== "NO TRADE" && toNumber(pricing.entry) !== null;
  const hasSize = Number(pricing.position_size || 0) > 0;

  if (decision.operational_signal === "NO TRADE") {
    if (decision.technical_signal !== "NO TRADE") {
      return `Il grafico suggerisce ${humanSignal(decision.technical_signal).toLowerCase()}, ma il filtro rischio consiglia di non entrare adesso. ${confidence.label}.`;
    }
    return `Al momento non ci sono abbastanza conferme per impostare un trade. ${confidence.label}.`;
  }

  if (!hasLevels) {
    return `Setup presente, ma non ancora tradotto in livelli operativi chiari. ${confidence.label}.`;
  }

  if (!hasSize) {
    return `Setup presente, ma con il rischio scelto la size calcolata e troppo piccola o nulla. ${confidence.label}.`;
  }

  return `Trade operativo attivo secondo le regole impostate. ${confidence.label}.`;
}

function macroRiskNarrative(setup) {
  const { macro, company } = setup;
  const themeText = (macro.macro_themes || []).slice(0, 2).map(translatedTheme).join(", ");
  const macroMap = {
    LOW: "Poche turbolenze dalle notizie generali.",
    MODERATE: "Qualche turbolenza dalle notizie generali.",
    HIGH: "Notizie generali pesanti da monitorare.",
    EXTREME: "Notizie generali molto pesanti."
  };
  const companyMap = {
    LOW: "Azienda relativamente tranquilla.",
    MODERATE: "Azienda con qualche notizia da monitorare.",
    HIGH: "Azienda sotto pressione news.",
    EXTREME: "Azienda sotto forte pressione news."
  };

  const parts = [
    `${marketModeLabel(macro.market_mode)}.`,
    macroMap[macro.macro_news_level] || "Contesto generale non chiaro.",
    companyMap[company.news_level] || "Contesto aziendale non chiaro."
  ];

  if (themeText) {
    parts.push(`Temi dominanti: ${themeText}.`);
  }

  return parts.join(" ");
}

function earningsNarrative(earnings) {
  if (!earnings?.next_earnings_date) {
    return {
      main: "Data non disponibile",
      sub: "Nessuna prossima trimestrale trovata."
    };
  }

  const date = new Date(`${earnings.next_earnings_date}T00:00:00`);
  const formattedDate = Number.isNaN(date.getTime())
    ? earnings.next_earnings_date
    : date.toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "numeric" });

  const details = [earnings.label || ""].filter(Boolean);
  if (earnings.warning) {
    details.push(earnings.warning);
  } else if (typeof earnings.days_to_earnings === "number") {
    if (earnings.days_to_earnings <= 7) {
      details.push("Molto vicina: da valutare con prudenza.");
    } else if (earnings.days_to_earnings <= 14) {
      details.push("Abbastanza vicina: meglio tenerla in conto.");
    } else {
      details.push("Non e imminente.");
    }
  }

  return {
    main: formattedDate,
    sub: details.join(" ")
  };
}

function chartColorForSignal(signal) {
  if (signal === "LONG") return "#00c853";
  if (signal === "SHORT") return "#ff3d3d";
  return "#ffab00";
}

function buildLinePath(values, xForIndex, yForValue) {
  let path = "";
  let segmentOpen = false;

  values.forEach((value, index) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      segmentOpen = false;
      return;
    }

    const x = xForIndex(index);
    const y = yForValue(value);
    path += `${segmentOpen ? " L" : " M"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    segmentOpen = true;
  });

  return path.trim();
}

function renderPriceChart(setup) {
  const points = setup.charts?.price || [];
  if (points.length < 2) {
    return `
      <div class="section-card chart-card">
        <div class="chart-head">
          <h4>Grafico prezzo</h4>
          <p>Non ho abbastanza sedute per disegnare un grafico leggibile.</p>
        </div>
      </div>
    `;
  }

  const width = 720;
  const height = 220;
  const padding = { top: 16, right: 52, bottom: 28, left: 18 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xForIndex = (index) => padding.left + (index / Math.max(points.length - 1, 1)) * plotWidth;

  const closeSeries = points.map((point) => toNumber(point.close));
  const shortTrendSeries = points.map((point) => toNumber(point.sma50));
  const longTrendSeries = points.map((point) => toNumber(point.sma200));
  const markerLevels = [
    { label: "Entrata", value: toNumber(setup.pricing.entry), color: "#e1e4e8", dash: "" },
    { label: "Stop", value: toNumber(setup.pricing.stop), color: "#ff3d3d", dash: "6 4" },
    { label: "Target", value: toNumber(setup.pricing.target), color: "#00c853", dash: "4 4" },
  ].filter((item) => item.value !== null);

  const allValues = [
    ...closeSeries,
    ...shortTrendSeries,
    ...longTrendSeries,
    ...markerLevels.map((item) => item.value),
  ].filter((item) => item !== null);

  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = Math.max(max - min, max * 0.02, 1);
  const yMin = min - range * 0.12;
  const yMax = max + range * 0.12;
  const yForValue = (value) => padding.top + ((yMax - value) / (yMax - yMin)) * plotHeight;
  const gridValues = [yMax, yMin + (yMax - yMin) / 2, yMin];

  const closePath = buildLinePath(closeSeries, xForIndex, yForValue);
  const shortTrendPath = buildLinePath(shortTrendSeries, xForIndex, yForValue);
  const longTrendPath = buildLinePath(longTrendSeries, xForIndex, yForValue);
  const firstDate = formatShortDate(points[0]?.date);
  const lastDate = formatShortDate(points[points.length - 1]?.date);

  return `
    <div class="section-card chart-card">
      <div class="chart-head">
        <h4>Grafico prezzo</h4>
        <p>Solo chiusure giornaliere confermate. Serve a vedere direzione, medie e livelli operativi.</p>
      </div>
      <div class="chart-frame">
        <svg viewBox="0 0 ${width} ${height}" class="chart-svg" role="img" aria-label="Grafico daily di ${escapeHtml(setup.ticker)}">
          ${gridValues.map((value) => `
            <g>
              <line x1="${padding.left}" y1="${yForValue(value).toFixed(2)}" x2="${width - padding.right}" y2="${yForValue(value).toFixed(2)}" class="chart-grid-line"></line>
              <text x="${width - padding.right + 6}" y="${(yForValue(value) + 4).toFixed(2)}" class="chart-axis-label">${escapeHtml(value.toFixed(2))}</text>
            </g>
          `).join("")}
          ${markerLevels.map((item) => `
            <g>
              <line x1="${padding.left}" y1="${yForValue(item.value).toFixed(2)}" x2="${width - padding.right}" y2="${yForValue(item.value).toFixed(2)}" stroke="${item.color}" stroke-width="1.4" stroke-dasharray="${item.dash}" opacity="0.85"></line>
              <text x="${padding.left + 6}" y="${(yForValue(item.value) - 6).toFixed(2)}" class="chart-marker-label" fill="${item.color}">${escapeHtml(item.label)}</text>
            </g>
          `).join("")}
          <path d="${closePath}" class="chart-line chart-line-close"></path>
          <path d="${shortTrendPath}" class="chart-line chart-line-short"></path>
          <path d="${longTrendPath}" class="chart-line chart-line-long"></path>
          <circle cx="${xForIndex(points.length - 1).toFixed(2)}" cy="${yForValue(closeSeries[closeSeries.length - 1]).toFixed(2)}" r="4.6" fill="#e1e4e8"></circle>
          <text x="${padding.left}" y="${height - 8}" class="chart-axis-label">${escapeHtml(firstDate)}</text>
          <text x="${width - padding.right - 32}" y="${height - 8}" class="chart-axis-label">${escapeHtml(lastDate)}</text>
        </svg>
      </div>
      <div class="chart-legend">
        <span><i class="legend-dot legend-close"></i> Chiusura</span>
        <span><i class="legend-dot legend-short"></i> Media trend breve</span>
        <span><i class="legend-dot legend-long"></i> Media trend lunga</span>
        ${markerLevels.map((item) => `<span><i class="legend-dot" style="background:${item.color};"></i> ${escapeHtml(item.label)}</span>`).join("")}
      </div>
    </div>
  `;
}

function historySummary(entries) {
  const counts = { LONG: 0, SHORT: 0, "NO TRADE": 0 };
  entries.forEach((entry) => {
    const signal = entry.operational_signal;
    if (signal in counts) counts[signal] += 1;
  });

  return `
    <div class="history-stats">
      <span class="history-pill">Giorni salvati: ${entries.length}</span>
      <span class="history-pill">Long: ${counts.LONG}</span>
      <span class="history-pill">Short: ${counts.SHORT}</span>
      <span class="history-pill">Attesa: ${counts["NO TRADE"]}</span>
    </div>
  `;
}

function renderHistoryChart(setup, entries) {
  if (!entries?.length) {
    return `
      <div class="section-card chart-card">
        <div class="chart-head">
          <h4>Storico salvato</h4>
          <p>Lo storico iniziera a popolarsi man mano che lancerai lo scanner nei prossimi giorni.</p>
        </div>
      </div>
    `;
  }

  const width = 720;
  const height = 220;
  const padding = { top: 16, right: 16, bottom: 28, left: 28 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xForIndex = (index) => padding.left + (index / Math.max(entries.length - 1, 1)) * plotWidth;
  const yForValue = (value) => padding.top + ((100 - value) / 100) * plotHeight;

  const operationalValues = entries.map((item) => Math.round(Number(item.operational_confidence || 0) * 100));
  const technicalValues = entries.map((item) => Math.round(Number(item.technical_confidence || 0) * 100));
  const operationalPath = buildLinePath(operationalValues, xForIndex, yForValue);
  const technicalPath = buildLinePath(technicalValues, xForIndex, yForValue);
  const firstDate = formatShortDate(entries[0]?.session_date);
  const lastDate = formatShortDate(entries[entries.length - 1]?.session_date);
  const latest = entries[entries.length - 1];

  return `
    <div class="section-card chart-card">
      <div class="chart-head">
        <h4>Storico salvato</h4>
        <p>Ogni punto e uno scan giornaliero salvato. La linea piena misura quanto il trade era davvero operabile.</p>
      </div>
      ${historySummary(entries)}
      <div class="chart-frame">
        <svg viewBox="0 0 ${width} ${height}" class="chart-svg" role="img" aria-label="Storico segnali di ${escapeHtml(setup.ticker)}">
          ${[100, 50, 0].map((value) => `
            <g>
              <line x1="${padding.left}" y1="${yForValue(value).toFixed(2)}" x2="${width - padding.right}" y2="${yForValue(value).toFixed(2)}" class="chart-grid-line"></line>
              <text x="2" y="${(yForValue(value) + 4).toFixed(2)}" class="chart-axis-label">${value}%</text>
            </g>
          `).join("")}
          <path d="${technicalPath}" class="chart-line chart-line-history-technical"></path>
          <path d="${operationalPath}" class="chart-line chart-line-history-operational"></path>
          ${entries.map((item, index) => {
            const confidence = Math.round(Number(item.operational_confidence || 0) * 100);
            return `
              <circle cx="${xForIndex(index).toFixed(2)}" cy="${yForValue(confidence).toFixed(2)}" r="4.6" fill="${chartColorForSignal(item.operational_signal)}">
                <title>${escapeHtml(`${item.session_date}: ${item.operational_signal} ${confidence}%`)}</title>
              </circle>
            `;
          }).join("")}
          <text x="${padding.left}" y="${height - 8}" class="chart-axis-label">${escapeHtml(firstDate)}</text>
          <text x="${width - padding.right - 32}" y="${height - 8}" class="chart-axis-label">${escapeHtml(lastDate)}</text>
        </svg>
      </div>
      <div class="chart-legend">
        <span><i class="legend-dot legend-history-operational"></i> Confidenza operativa</span>
        <span><i class="legend-dot legend-history-technical"></i> Confidenza tecnica</span>
        <span><i class="legend-dot legend-long"></i> Punto verde = long</span>
        <span><i class="legend-dot legend-close"></i> Punto nero = attesa</span>
        <span><i class="legend-dot legend-short"></i> Punto rosso = short</span>
      </div>
      <p class="chart-caption">
        Ultimo giorno salvato: ${escapeHtml(formatDate(latest.session_date))}. Ultimo esito operativo: ${escapeHtml(humanTradeAction(latest.operational_signal).toLowerCase())}.
      </p>
    </div>
  `;
}

function renderPlanCell(setup) {
  const { decision, pricing } = setup;
  const hasLevels = decision.operational_signal !== "NO TRADE" && toNumber(pricing.entry) !== null;
  const size = Number(pricing.position_size || 0);

  if (!hasLevels) {
    return `
      <div class="summary-stack">
        <div class="summary-main">Nessun livello operativo</div>
        <div class="summary-sub">Finche il trade non e attivo, ingresso, stop e target restano vuoti.</div>
      </div>
    `;
  }

  const sizeNote = size > 0
    ? `Size indicativa: ${size} azioni.`
    : "Size calcolata nulla con il rischio attuale.";

  return `
    <div class="summary-stack summary-plan">
      <div class="summary-price-line"><span>Entrata</span><strong>${escapeHtml(formatOperationalPrice(decision.operational_signal, pricing.entry))}</strong></div>
      <div class="summary-price-line"><span>Stop</span><strong>${escapeHtml(formatOperationalPrice(decision.operational_signal, pricing.stop))}</strong></div>
      <div class="summary-price-line"><span>Target</span><strong>${escapeHtml(formatOperationalPrice(decision.operational_signal, pricing.target))}</strong></div>
      <div class="summary-sub">${escapeHtml(sizeNote)}</div>
    </div>
  `;
}

function summaryRowClass(signal) {
  if (signal === "LONG") return "summary-row summary-row-long";
  if (signal === "SHORT") return "summary-row summary-row-short";
  return "summary-row summary-row-wait";
}

function sortSetupsForSummary(setups) {
  const score = (setup) => {
    let total = Math.round(Number(setup.decision.operational_confidence || 0) * 100);
    if (setup.decision.operational_signal !== "NO TRADE") total += 100;
    if (Number(setup.pricing.position_size || 0) > 0) total += 20;
    return total;
  };

  return [...setups].sort((left, right) => score(right) - score(left));
}

function buildSetupDisplayState(setups, ui = {}) {
  const sorted = sortSetupsForSummary(setups);
  const actionable = sorted.filter((setup) => setup.decision.operational_signal !== "NO TRADE");
  const waiting = sorted.filter((setup) => setup.decision.operational_signal === "NO TRADE");
  const compactMode = Boolean(ui.only_actionable_view) || sorted.length > COMPACT_RESULTS_THRESHOLD;

  return {
    compactMode,
    sorted,
    actionable,
    waiting,
    visible: compactMode ? actionable : sorted,
    hiddenWaiting: compactMode ? waiting : []
  };
}

function renderCompactWaitingBox(view) {
  if (!view.compactMode || !view.hiddenWaiting.length) return "";

  const preview = compactPreviewText(
    view.hiddenWaiting,
    COMPACT_TICKER_PREVIEW_LIMIT,
    (setup) => setup.ticker
  );
  const intro = view.visible.length
    ? `Mostro solo i ${view.visible.length} titoli operativi per tenere leggibile la pagina.`
    : "In questa scansione non ci sono LONG o SHORT operativi da mostrare.";

  return `
    <details class="compact-box">
      <summary>${escapeHtml(`${view.hiddenWaiting.length} ticker in attesa sono stati compressi`)}</summary>
      <div class="compact-box-body">
        <p>${escapeHtml(intro)}</p>
        <p class="compact-preview">${escapeHtml(preview)}</p>
      </div>
    </details>
  `;
}

function renderFailureBox(failures) {
  if (!failures.length) return "";

  if (failures.length <= COMPACT_FAILURE_PREVIEW_LIMIT) {
    return `<div class="error-box">${failures.map((item) => escapeHtml(item)).join("<br>")}</div>`;
  }

  const preview = failures.slice(0, COMPACT_FAILURE_PREVIEW_LIMIT);
  return `
    <details class="error-box compact-box compact-box--error">
      <summary>${escapeHtml(`${failures.length} ticker non sono stati caricati correttamente`)}</summary>
      <div class="compact-box-body">
        ${preview.map((item) => `<p class="compact-line">${escapeHtml(item)}</p>`).join("")}
        <p class="compact-preview">Apro solo i primi ${COMPACT_FAILURE_PREVIEW_LIMIT}; gli altri restano chiusi qui dentro.</p>
      </div>
    </details>
  `;
}

function summaryCardClass(signal) {
  if (signal === "LONG") return "summary-card summary-card--long";
  if (signal === "SHORT") return "summary-card summary-card--short";
  return "summary-card summary-card--wait";
}

function renderSummaryLevels(setup) {
  const { decision, pricing } = setup;
  const hasLevels = decision.operational_signal !== "NO TRADE" && toNumber(pricing.entry) !== null;
  if (!hasLevels) return "";

  const size = Number(pricing.position_size || 0);
  const sizeText = size > 0 ? `${size} azioni` : "N/D";

  return `
    <div class="summary-card-levels">
      <div class="summary-card-level">
        <span>Entrata</span>
        <strong>${escapeHtml(formatDisplayPrice(pricing.entry))}</strong>
      </div>
      <div class="summary-card-level">
        <span>Stop</span>
        <strong>${escapeHtml(formatDisplayPrice(pricing.stop))}</strong>
      </div>
      <div class="summary-card-level">
        <span>Target</span>
        <strong>${escapeHtml(formatDisplayPrice(pricing.target))}</strong>
      </div>
      <div class="summary-card-level">
        <span>Size</span>
        <strong>${escapeHtml(sizeText)}</strong>
      </div>
    </div>
  `;
}

function renderSummary(setups, ui = {}) {
  if (!setups.length) {
    renderEmpty(summaryWrap, "Nessun risultato disponibile.");
    return;
  }

  const view = buildSetupDisplayState(setups, ui);
  const rows = view.visible;

  const cards = rows.map((setup) => {
    const operationalConfidence = confidenceDescriptor(setup.decision.operational_confidence);
    const earnings = earningsNarrative(setup.earnings);

    return `
      <div class="${summaryCardClass(setup.decision.operational_signal)}">
        <div class="summary-card-header">
          <span class="summary-ticker">${escapeHtml(setup.ticker)}</span>
          <div class="summary-inline">
            <span class="${badgeClass(setup.decision.operational_signal)}">${escapeHtml(actionBadgeLabel(setup.decision.operational_signal))}</span>
            <span class="${toneClass(operationalConfidence.tone)}">${escapeHtml(operationalConfidence.label)}</span>
          </div>
        </div>
        <div class="summary-card-body">
          <div class="summary-card-row">
            <span class="summary-card-row-label">Il grafico dice</span>
            <span class="summary-card-row-text">${escapeHtml(technicalHeadline(setup.decision.technical_signal))}. ${escapeHtml(technicalNarrative(setup))}</span>
          </div>
          <div class="summary-card-row">
            <span class="summary-card-row-label">Cosa fare</span>
            <span class="summary-card-row-text">${escapeHtml(humanTradeAction(setup.decision.operational_signal))}. ${escapeHtml(practicalNarrative(setup))}</span>
          </div>
          <div class="summary-card-row">
            <span class="summary-card-row-label">Contesto</span>
            <span class="summary-card-row-text">${escapeHtml(macroRiskNarrative(setup))}</span>
          </div>
          <div class="summary-card-row">
            <span class="summary-card-row-label">Trimestrale</span>
            <span class="summary-card-row-text">${escapeHtml(earnings.main)} — ${escapeHtml(earnings.sub)}</span>
          </div>
        </div>
        ${renderSummaryLevels(setup)}
      </div>
    `;
  }).join("");

  const cardsHtml = cards
    ? `<div class="summary-cards">${cards}</div>`
    : `<div class="empty-state">Nessun LONG o SHORT operativo da mettere in evidenza. I ticker in attesa sono stati compressi per non allungare inutilmente la pagina.</div>`;
  const bannerText = ui.only_actionable_view
    ? `Vista operativa attiva: mostro solo i setup LONG e SHORT. ${view.hiddenWaiting.length} titoli in attesa restano nascosti.`
    : view.compactMode
    ? `Vista compatta attiva: sopra ${COMPACT_RESULTS_THRESHOLD} risultati mostro solo i setup verdi e rossi. ${view.hiddenWaiting.length} titoli in attesa sono raccolti nel box qui sotto.`
    : "Il bordo colorato indica il segnale (verde = long, rosso = short, ambra = attesa). Entrata, stop e target compaiono solo quando il trade e attivo.";

  summaryWrap.innerHTML = `
    <div class="summary-banner">
      <strong>Come leggere le card:</strong> ${escapeHtml(bannerText)}
    </div>
    ${renderCompactWaitingBox(view)}
    ${cardsHtml}
  `;
}

function renderHeadlineList(title, headlines) {
  if (!headlines?.length) {
    return `<div class="section-card"><h4>${title}</h4><div class="empty-state">Nessuna headline rilevante.</div></div>`;
  }
  return `
    <div class="section-card">
      <h4>${title}</h4>
      <div class="headline-list">
        ${headlines.slice(0, 3).map((item) => `
          <div class="headline-item">
            <small>${escapeHtml(item.headline?.source || "")}</small>
            <p>${escapeHtml(item.headline?.title || "")}</p>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderDetailRows(rows) {
  return `
    <div class="detail-list">
      ${rows.map(([label, value]) => `
        <div class="detail-row">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(formatDisplayValue(value))}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderTickerCards(setups, failures, historyByTicker, ui = {}) {
  if (!setups.length && !failures.length) {
    renderEmpty(tickerCards, "Nessun ticker analizzato.");
    return;
  }

  const view = buildSetupDisplayState(setups, ui);
  const failureHtml = renderFailureBox(failures);

  const cards = view.visible.map((setup) => {
    const technical = setup.technical;
    const macro = setup.macro;
    const company = setup.company;
    const pricing = setup.pricing;
    const earnings = setup.earnings;
    const operational = setup.operational;
    const decision = setup.decision;
    const historyEntries = historyByTicker?.[setup.ticker] || [];

    return `
      <article class="ticker-card">
        <div class="card-top">
          <div>
            <h3>${escapeHtml(setup.ticker)}</h3>
            <p class="card-subline">${escapeHtml(operational.commentary)} Chiusura analizzata: ${escapeHtml(formatDate(setup.analysis_date))}.</p>
          </div>
          <div class="badge-row">
            <span class="${badgeClass(decision.technical_signal)}">Tecnico ${escapeHtml(decision.technical_signal)}</span>
            <span class="${badgeClass(decision.operational_signal)}">Operativo ${escapeHtml(decision.operational_signal)}</span>
            <span class="${riskClass(macro.macro_news_level)}">Macro ${escapeHtml(macro.macro_news_level)}</span>
            <span class="${riskClass(company.news_level)}">Azienda ${escapeHtml(company.news_level)}</span>
          </div>
        </div>

        <div class="chart-grid">
          ${renderPriceChart(setup)}
          ${renderHistoryChart(setup, historyEntries)}
        </div>

        <div class="section-grid">
          <div class="section-card">
            <h4>Analisi Tecnica</h4>
            ${renderDetailRows([
              ["Confidenza tecnica", `${Math.round(decision.technical_confidence * 100)}%`],
              ["Trend", technical.trend],
              ["RSI", technical.rsi],
              ["ADX", technical.adx],
              ["ATR", technical.atr],
              ["RS 1M vs SPY", technical.relative_strength_1m_label],
              ["Supporto", formatDisplayPrice(technical.support)],
              ["Resistenza", formatDisplayPrice(technical.resistance)],
            ])}
            <div class="headline-list">
              <div class="headline-item">
                <small>Conferme</small>
                <p>${escapeHtml((technical.reasons || []).slice(0, 4).join(" | ") || "-")}</p>
              </div>
            </div>
          </div>

          <div class="section-card">
            <h4>Decisione Operativa</h4>
            ${renderDetailRows([
              ["Segnale", decision.operational_signal],
              ["Confidenza operativa", `${Math.round(decision.operational_confidence * 100)}%`],
              ["Grade", decision.grade],
              ["Entry", formatOperationalPrice(decision.operational_signal, pricing.entry)],
              ["Stop", formatOperationalPrice(decision.operational_signal, pricing.stop)],
              ["Target", formatOperationalPrice(decision.operational_signal, pricing.target)],
              ["Size", pricing.position_size ?? (decision.operational_signal === "NO TRADE" ? "Non attiva" : "Non disponibile")],
              ["Size multiplier", `${Number(pricing.size_multiplier).toFixed(2)}x`],
            ])}
            <div class="headline-list">
              <div class="headline-item">
                <small>Motivo operativo</small>
                <p>${escapeHtml((operational.reasons || []).slice(0, 4).join(" | ") || "-")}</p>
              </div>
            </div>
          </div>

          <div class="section-card">
            <h4>Analisi Macro</h4>
            ${renderDetailRows([
              ["Regime", macro.market_mode],
              ["Macro-news", `${macro.macro_news_level} (${macro.macro_news_score})`],
              ["Temi", (macro.macro_themes || []).slice(0, 3).join(" | ") || "Nessuno"],
              ["Warning", (macro.market_warnings || []).slice(0, 2).join(" | ") || "Nessuno"],
            ])}
          </div>

          <div class="section-card">
            <h4>Azienda + Trimestrale</h4>
            ${renderDetailRows([
              ["News azienda", `${company.news_level} (${company.news_score})`],
              ["Temi azienda", (company.themes || []).slice(0, 3).join(" | ") || "Nessuno"],
              ["Data trimestrale", formatDate(earnings.next_earnings_date)],
              ["Distanza", earnings.label],
              ["Warning", earnings.warning || "Nessuno"],
            ])}
          </div>
        </div>

        <div class="section-grid">
          ${renderHeadlineList("Headline macro", macro.macro_headlines)}
          ${renderHeadlineList("Headline azienda", company.headlines)}
        </div>
      </article>
    `;
  }).join("");

  const emptyHtml = view.compactMode && view.hiddenWaiting.length
    ? `<div class="empty-state">Nessun ticker operativo da approfondire nei dettagli. ${view.hiddenWaiting.length} ticker in attesa sono stati compressi nella vista compatta.</div>`
    : "";

  tickerCards.innerHTML = `${failureHtml}${renderCompactWaitingBox(view)}${cards || emptyHtml}`;
}

async function fetchDefaults() {
  const response = await fetch("/api/defaults");
  const data = await response.json();
  tickersField.value = data.tickers.join(", ");
  periodField.value = data.daily_period;
  accountSizeField.value = data.account_size;
  riskPerTradeField.value = data.risk_per_trade;
  newsLookbackField.value = data.news_lookback_days;
  newsEnabledField.checked = Boolean(data.news_enabled);
  syncNewsControls();
}

function setScanButtonsDisabled(disabled) {
  submitButton.disabled = disabled;
  autoscanButton.disabled = disabled;
}

function buildScanPayload(includeTickers = true) {
  return {
    ...(includeTickers ? { tickers: normalizeTickers(tickersField.value) } : {}),
    daily_period: periodField.value,
    account_size: Number(accountSizeField.value),
    risk_per_trade: Number(riskPerTradeField.value),
    news_lookback_days: Number(newsLookbackField.value),
    news_enabled: Boolean(newsEnabledField.checked),
  };
}

async function executeScanRequest({ url, payload, statusMessage }) {
  setScanButtonsDisabled(true);
  setStatus(statusMessage);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Errore API ${response.status}`);
    }

    const data = await response.json();
    renderOverview(data);
    renderContext(data);
    renderSummary(data.setups || [], data.ui || {});
    renderTickerCards(data.setups || [], data.failures || [], data.history || {}, data.ui || {});

    const savedRows = Number(data.storage?.saved_rows || 0);
    const modeLabel = data.ui?.scan_mode === "autoscan_top_100_usa" ? "Autoscan" : "Scan";
    setStatus(`${modeLabel} aggiornato alle ${formatDateTime(data.generated_at)}. Salvate ${savedRows} righe nello storico.`);
  } catch (error) {
    renderEmpty(overviewCards, "Errore nel recupero dei dati.");
    renderEmpty(macroContext, "Errore nel recupero del contesto macro.");
    renderEmpty(summaryWrap, "Errore nella costruzione della tabella.");
    tickerCards.innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
    setStatus("Errore durante la scansione.");
  } finally {
    setScanButtonsDisabled(false);
  }
}

async function runScan() {
  await executeScanRequest({
    url: "/api/scan",
    payload: buildScanPayload(true),
    statusMessage: "Scansione manuale in corso..."
  });
}

async function runAutoScan() {
  await executeScanRequest({
    url: "/api/autoscan",
    payload: buildScanPayload(false),
    statusMessage: "Autoscan Top 100 USA in corso..."
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runScan();
});

autoscanButton.addEventListener("click", async () => {
  await runAutoScan();
});

newsEnabledField.addEventListener("change", () => {
  syncNewsControls();
});

async function bootstrap() {
  renderEmpty(overviewCards, "Caricamento impostazioni...");
  renderEmpty(macroContext, "In attesa della prima scansione.");
  renderEmpty(summaryWrap, "Nessun dato disponibile.");
  renderEmpty(tickerCards, "Lancia la scansione per vedere i dettagli.");
  await fetchDefaults();
  await runScan();
}

bootstrap();
