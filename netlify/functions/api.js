const crypto = require("crypto");

const { firestore } = require("./_shared/firebase");
const { jsonResponse, parseJsonBody, requireAdmin, routePath } = require("./_shared/http");
const {
  DEFAULT_USER_ID,
  adaptivePositionTargets,
  ensureNonNegativeNumber,
  ensurePositiveNumber,
  entryReferencePrice,
  normalizeTicker,
  nowIso,
  parseTimestamp,
  positionDetail,
  positionDoc,
  rebuildPositionSummary,
  recommendPositionAction,
  snapshotDoc,
  targetLevels,
  updateDashboardPosition,
  updateDashboardSettings,
  updateDashboardWatchlist,
} = require("./_shared/trading");

function makeId(prefix) {
  return `${prefix}:${crypto.randomBytes(6).toString("hex")}`;
}

async function docById(db, collection, id) {
  const snapshot = await db.collection(collection).doc(id).get();
  return snapshot.exists ? snapshot.data() : null;
}

async function setDoc(db, collection, id, payload) {
  await db.collection(collection).doc(id).set(payload, { merge: true });
}

async function allDocs(db, collection) {
  const snapshot = await db.collection(collection).get();
  return snapshot.docs.map((item) => item.data());
}

async function listByField(db, collection, field, value) {
  const snapshot = await db.collection(collection).where(field, "==", value).get();
  return snapshot.docs.map((item) => item.data());
}

async function dashboardBundle(db) {
  const dashboard = await docById(db, "_app", "dashboard");
  return dashboard || {
    generated_at: nowIso(),
    overview: {
      tracked_tickers: 0,
      open_positions: 0,
      total_unrealized_pnl: 0,
      total_realized_pnl: 0,
      positions_requiring_action: 0,
      generated_at: nowIso(),
    },
    study_watchlist: [],
    signals: [],
    open_positions: [],
    tickers: {},
    positions: {},
    history: { signals: [], position_events: [], position_recommendations: [] },
    settings: {},
    architecture: {
      selected: "netlify-firestore-github-actions",
      frontend: "Netlify static SPA",
      batch: "GitHub Actions daily Python job",
      storage: "Firebase cloud sync with local SQLite fallback",
    },
  };
}

function withCapabilities(bundle) {
  return {
    ...bundle,
    capabilities: {
      mode: "netlify-functions",
      write: true,
      refresh: false,
      auth_mode: "admin-token",
    },
  };
}

async function saveDashboard(db, bundle) {
  await db.collection("_app").doc("dashboard").set(bundle, { merge: false });
}

function latestMarketSnapshot(tickerDetail) {
  const snapshots = tickerDetail?.snapshots || [];
  return snapshots.length ? snapshots[snapshots.length - 1] : null;
}

function priceHistorySince(tickerDetail, openedAt) {
  const openedDate = String(openedAt || "").slice(0, 10);
  return (tickerDetail?.snapshots || []).filter((row) => String(row.session_date || "") >= openedDate);
}

async function getTargetDoc(db, subjectType, subjectId, scope) {
  const expectedId = `targets:${subjectType}:${subjectId}${scope === "position_original" ? ":original" : scope === "position_adaptive" ? ":adaptive" : ""}`;
  let target = await docById(db, "targets", expectedId);
  if (target) return target;
  const docs = await allDocs(db, "targets");
  return docs.find((item) => item.subject_type === subjectType && item.subject_id === subjectId && item.scope === scope) || null;
}

async function buildPositionDetailFromStore(db, dashboard, positionId) {
  const position = await docById(db, "open_positions", positionId);
  if (!position) return null;
  const signal = await docById(db, "signals", position.signal_id_origin);
  const originalTargets = await getTargetDoc(db, "position", positionId, "position_original");
  const adaptiveTargets = await getTargetDoc(db, "position", positionId, "position_adaptive");
  const events = await listByField(db, "position_events", "position_id", positionId);
  const recommendations = await listByField(db, "position_recommendations", "position_id", positionId);
  const tickerDetail = dashboard.tickers?.[position.ticker] || null;
  return positionDetail({
    position: {
      ...position,
      position_id: position.id,
      mark_price: position.current_price,
      current_adaptive_targets: targetLevels(adaptiveTargets, "adaptive"),
      targets_from_original_signal: targetLevels(originalTargets, "original"),
      warning_flags: recommendations[0]?.warning_flags_json || [],
    },
    signal,
    originalTargets,
    adaptiveTargets,
    events,
    recommendations,
    tickerDetail,
  });
}

function buildWatchlistResponse(bundle) {
  return {
    tickers: (bundle.study_watchlist || []).map((row) => row.ticker),
    settings: bundle.settings || {},
  };
}

function normalizeTickerList(values) {
  const seen = new Set();
  const tickers = [];
  for (const value of values || []) {
    const ticker = normalizeTicker(value);
    if (!seen.has(ticker)) {
      seen.add(ticker);
      tickers.push(ticker);
    }
  }
  return tickers;
}

function currentContext(dashboard, ticker) {
  const detail = dashboard.tickers?.[ticker] || {};
  return {
    tickerDetail: detail,
    signal: detail.latest_prediction || detail.latest_signal || null,
    profile: detail.profile || null,
    marketSnapshot: latestMarketSnapshot(detail),
  };
}

function targetDocFromSignal(positionId, signal, signalTarget, executionPrice, createdAt, scope) {
  const suffix = scope === "position_original" ? "original" : "adaptive";
  return {
    id: `targets:position:${positionId}:${suffix}`,
    subject_type: "position",
    subject_id: positionId,
    scope,
    ticker: signal.ticker,
    side: signal.direction,
    entry_reference_price: signalTarget?.entry_reference_price ?? entryReferencePrice(signal),
    average_entry_reference: executionPrice,
    stop_loss: signalTarget?.stop_loss ?? signal.stop_loss ?? null,
    target_1: signalTarget?.target_1 ?? null,
    target_2: signalTarget?.target_2 ?? null,
    target_3: signalTarget?.target_3 ?? signalTarget?.optional_target_3 ?? null,
    probabilistic_target: signalTarget?.probabilistic_target ?? null,
    risk_reward: signalTarget?.risk_reward ?? signal.risk_reward ?? null,
    confidence_score: signalTarget?.confidence_score ?? signal.confidence_score ?? 0,
    holding_horizon_estimate: signalTarget?.holding_horizon_estimate ?? signal.holding_horizon_days ?? 0,
    rationale_json:
      scope === "position_adaptive"
        ? { summary: "Adaptive targets inherit the original signal until the next refresh." }
        : signalTarget?.rationale_json ?? signal.rationale ?? {},
    warning_flags_json: signalTarget?.warning_flags_json ?? signal.warning_flags ?? [],
    version_label: "position-open",
    created_at: createdAt,
    updated_at: createdAt,
  };
}

async function persistPositionArtifacts(db, artifacts) {
  await setDoc(db, "open_positions", artifacts.position.id, artifacts.position);
  await setDoc(db, "position_events", artifacts.event.id, artifacts.event);
  await setDoc(db, "targets", artifacts.originalTargets.id, artifacts.originalTargets);
  await setDoc(db, "targets", artifacts.adaptiveTargets.id, artifacts.adaptiveTargets);
  await setDoc(db, "position_recommendations", artifacts.recommendation.id, artifacts.recommendation);
  await setDoc(db, "position_daily_snapshots", artifacts.snapshot.id, artifacts.snapshot);
}

async function createPositionFromSignal(db, dashboard, payload) {
  const signalId = String(payload.signal_id || "").trim();
  const executionPrice = ensurePositiveNumber(payload.execution_price, "execution_price");
  const quantity = ensurePositiveNumber(payload.quantity, "quantity");
  const fees = ensureNonNegativeNumber(payload.fees, "fees");
  const executedAt = (parseTimestamp(payload.executed_at) || new Date()).toISOString();
  const notes = String(payload.notes || "");
  const signal =
    (dashboard.signals || []).find((item) => item.signal_id === signalId) ||
    (await docById(db, "signals", signalId));
  if (!signal) throw new Error(`Signal not found: ${signalId}`);
  if (!["long", "short"].includes(signal.direction)) {
    throw new Error("Only long or short signals can open a real position.");
  }
  const signalTarget =
    dashboard.tickers?.[signal.ticker]?.targets ||
    (await docById(db, "targets", `targets:signal:${signal.signal_id}`));
  if (!signalTarget) throw new Error("Original targets are missing for the selected signal.");

  const { tickerDetail, profile, marketSnapshot } = currentContext(dashboard, signal.ticker);
  const createdAt = nowIso();
  const positionId = makeId("position");
  const eventId = makeId("event");
  const originalTargets = targetDocFromSignal(positionId, signal, signalTarget, executionPrice, createdAt, "position_original");
  const provisionalAdaptive = targetDocFromSignal(positionId, signal, signalTarget, executionPrice, createdAt, "position_adaptive");
  const event = {
    id: eventId,
    position_id: positionId,
    ticker: signal.ticker,
    side: signal.direction,
    event_type: "OPEN",
    quantity,
    price: executionPrice,
    fees,
    executed_at: executedAt,
    source: "user",
    linked_signal_id: signal.signal_id,
    metadata_json: { opened_from_signal: true },
    notes,
    created_at: createdAt,
  };
  let summary = rebuildPositionSummary({
    positionId,
    userId: DEFAULT_USER_ID,
    ticker: signal.ticker,
    strategyId: signal.strategy_id,
    strategyName: signal.strategy_name || signal.setup_name || signal.strategy_id,
    signalIdOrigin: signal.signal_id,
    side: signal.direction,
    openedAt: executedAt,
    events: [event],
    originalTargets: targetLevels(originalTargets, "original"),
    adaptiveTargets: targetLevels(provisionalAdaptive, "adaptive"),
    originalStop: originalTargets.stop_loss,
    currentStop: provisionalAdaptive.stop_loss,
    markPrice: marketSnapshot?.close ?? executionPrice,
    asOf: executedAt,
    priceHistory: priceHistorySince(tickerDetail, executedAt),
    notes,
  });
  const adaptiveTargets = adaptivePositionTargets({
    position: summary,
    signal,
    profile,
    marketSnapshot,
    originalTargets,
  }) || provisionalAdaptive;
  const recommendation = recommendPositionAction({
    position: summary,
    signal,
    profile,
    marketSnapshot,
    originalTargets,
    adaptiveTargets,
    effectiveAt: createdAt,
  });
  summary = rebuildPositionSummary({
    positionId,
    userId: DEFAULT_USER_ID,
    ticker: signal.ticker,
    strategyId: signal.strategy_id,
    strategyName: signal.strategy_name || signal.setup_name || signal.strategy_id,
    signalIdOrigin: signal.signal_id,
    side: signal.direction,
    openedAt: executedAt,
    events: [event],
    originalTargets: targetLevels(originalTargets, "original"),
    adaptiveTargets: targetLevels(adaptiveTargets, "adaptive"),
    originalStop: originalTargets.stop_loss,
    currentStop: adaptiveTargets.stop_loss,
    markPrice: marketSnapshot?.close ?? executionPrice,
    asOf: createdAt,
    priceHistory: priceHistorySince(tickerDetail, executedAt),
    lastRecommendation: recommendation.action,
    lastRecommendationConfidence: recommendation.confidence,
    lastRecommendationReason: recommendation.rationale,
    notes,
  });
  const storedPosition = positionDoc(summary, createdAt, createdAt);
  const snapshot = snapshotDoc(summary, recommendation, marketSnapshot?.market_regime || signal.regime || "MIXED", createdAt);
  await persistPositionArtifacts(db, {
    position: storedPosition,
    event,
    originalTargets,
    adaptiveTargets,
    recommendation,
    snapshot,
  });
  const detail = positionDetail({
    position: {
      ...summary,
      strategy_name: storedPosition.strategy_name,
      created_at: createdAt,
      updated_at: createdAt,
    },
    signal,
    originalTargets,
    adaptiveTargets,
    events: [event],
    recommendations: [recommendation],
    tickerDetail,
  });
  const nextDashboard = updateDashboardPosition(dashboard, detail);
  await saveDashboard(db, nextDashboard);
  return detail;
}

async function createPositionEvent(db, dashboard, positionId, payload) {
  const position = await docById(db, "open_positions", positionId);
  if (!position) throw new Error(`Position not found: ${positionId}`);
  const eventType = String(payload.event_type || "").trim().toUpperCase();
  const createdAt = nowIso();
  const { tickerDetail, signal, profile, marketSnapshot } = currentContext(dashboard, position.ticker);
  const existingEvents = await listByField(db, "position_events", "position_id", positionId);
  let quantity = Number(payload.quantity || 0);
  let price = payload.price == null ? null : Number(payload.price);
  const fees = ensureNonNegativeNumber(payload.fees, "fees");
  const notes = String(payload.notes || "");
  const executedAt = (parseTimestamp(payload.executed_at) || new Date()).toISOString();
  const metadata = payload.metadata || {};
  if (["ADD", "REDUCE", "OPEN"].includes(eventType)) {
    quantity = ensurePositiveNumber(quantity, "quantity");
    price = ensurePositiveNumber(price, "price");
  } else if (eventType === "CLOSE") {
    quantity = quantity > 0 ? quantity : Number(position.current_quantity);
    quantity = ensurePositiveNumber(quantity, "quantity");
    price = price == null ? Number(position.current_price || marketSnapshot?.close || position.average_entry_price) : ensurePositiveNumber(price, "price");
  } else if (eventType === "UPDATE_STOP") {
    price = ensurePositiveNumber(metadata.stop ?? price, "price");
    metadata.stop = price;
  }
  const event = {
    id: makeId("event"),
    position_id: positionId,
    ticker: position.ticker,
    side: position.side,
    event_type: eventType,
    quantity,
    price,
    fees,
    executed_at: executedAt,
    source: "user",
    linked_signal_id: position.signal_id_origin,
    metadata_json: metadata,
    notes,
    created_at: createdAt,
  };
  await setDoc(db, "position_events", event.id, event);

  const originalTargets = await getTargetDoc(db, "position", positionId, "position_original");
  let adaptiveTargets = await getTargetDoc(db, "position", positionId, "position_adaptive");
  const events = [...existingEvents, event];
  let summary = rebuildPositionSummary({
    positionId,
    userId: position.user_id,
    ticker: position.ticker,
    strategyId: position.strategy_id,
    strategyName: position.strategy_name,
    signalIdOrigin: position.signal_id_origin,
    side: position.side,
    openedAt: position.opened_at,
    events,
    originalTargets: targetLevels(originalTargets, "original"),
    adaptiveTargets: targetLevels(adaptiveTargets, "adaptive"),
    originalStop: originalTargets?.stop_loss ?? position.original_stop,
    currentStop: adaptiveTargets?.stop_loss ?? position.current_stop,
    markPrice: marketSnapshot?.close ?? position.current_price ?? position.average_entry_price,
    asOf: createdAt,
    priceHistory: priceHistorySince(tickerDetail, position.opened_at),
    lastRecommendation: position.last_recommendation,
    lastRecommendationConfidence: position.last_recommendation_confidence,
    lastRecommendationReason: position.last_recommendation_reason,
    notes: position.notes,
  });
  if (signal && profile && marketSnapshot && originalTargets) {
    adaptiveTargets = adaptivePositionTargets({
      position: summary,
      signal,
      profile,
      marketSnapshot,
      originalTargets,
    }) || adaptiveTargets;
  }
  const recommendation =
    signal && profile && marketSnapshot && originalTargets
      ? recommendPositionAction({
          position: summary,
          signal,
          profile,
          marketSnapshot,
          originalTargets,
          adaptiveTargets,
          effectiveAt: createdAt,
        })
      : {
          id: `rec:${positionId}:${createdAt.slice(0, 10)}`,
          position_id: positionId,
          effective_at: createdAt,
          action: "no_action",
          confidence: 0.3,
          rationale: "Reason: insufficient data to refresh the position.",
          warning_flags_json: ["insufficient-data"],
          suggested_size_action: "hold",
          created_at: createdAt,
          updated_at: createdAt,
        };
  summary = rebuildPositionSummary({
    positionId,
    userId: position.user_id,
    ticker: position.ticker,
    strategyId: position.strategy_id,
    strategyName: position.strategy_name,
    signalIdOrigin: position.signal_id_origin,
    side: position.side,
    openedAt: position.opened_at,
    events,
    originalTargets: targetLevels(originalTargets, "original"),
    adaptiveTargets: targetLevels(adaptiveTargets, "adaptive"),
    originalStop: originalTargets?.stop_loss ?? position.original_stop,
    currentStop: adaptiveTargets?.stop_loss ?? position.current_stop,
    markPrice: marketSnapshot?.close ?? position.current_price ?? position.average_entry_price,
    asOf: createdAt,
    priceHistory: priceHistorySince(tickerDetail, position.opened_at),
    lastRecommendation: recommendation.action,
    lastRecommendationConfidence: recommendation.confidence,
    lastRecommendationReason: recommendation.rationale,
    notes: position.notes,
  });
  const storedPosition = positionDoc(summary, position.created_at || createdAt, createdAt);
  await setDoc(db, "open_positions", storedPosition.id, storedPosition);
  if (adaptiveTargets) await setDoc(db, "targets", adaptiveTargets.id, adaptiveTargets);
  await setDoc(db, "position_recommendations", recommendation.id, recommendation);
  const snapshot = snapshotDoc(summary, recommendation, marketSnapshot?.market_regime || signal?.regime || "MIXED", createdAt);
  await setDoc(db, "position_daily_snapshots", snapshot.id, snapshot);
  const recommendations = await listByField(db, "position_recommendations", "position_id", positionId);
  const detail = positionDetail({
    position: {
      ...summary,
      strategy_name: storedPosition.strategy_name,
      created_at: storedPosition.created_at,
      updated_at: storedPosition.updated_at,
    },
    signal,
    originalTargets,
    adaptiveTargets,
    events,
    recommendations: [...recommendations.filter((item) => item.id !== recommendation.id), recommendation],
    tickerDetail,
  });
  const nextDashboard = updateDashboardPosition(dashboard, detail);
  await saveDashboard(db, nextDashboard);
  return detail;
}

exports.handler = async function handler(event) {
  const db = firestore();
  const path = routePath(event);
  const method = event.httpMethod.toUpperCase();
  try {
    if (method === "GET" && path === "/dashboard") {
      return jsonResponse(200, withCapabilities(await dashboardBundle(db)));
    }

    if (method === "GET" && path === "/watchlist") {
      return jsonResponse(200, buildWatchlistResponse(await dashboardBundle(db)));
    }

    if (method === "POST" && path === "/watchlist") {
      requireAdmin(event);
      const body = parseJsonBody(event);
      const tickers = normalizeTickerList(body.tickers || []);
      const current = await listByField(db, "watched_tickers", "user_id", DEFAULT_USER_ID);
      for (const item of current) {
        await setDoc(db, "watched_tickers", item.watch_id || item.id || `${DEFAULT_USER_ID}:${item.ticker}`, {
          ...item,
          is_active: 0,
          updated_at: nowIso(),
        });
      }
      for (const ticker of tickers) {
        await setDoc(db, "watched_tickers", `${DEFAULT_USER_ID}:${ticker}`, {
          watch_id: `${DEFAULT_USER_ID}:${ticker}`,
          user_id: DEFAULT_USER_ID,
          ticker,
          label: null,
          notes: "",
          is_active: 1,
          created_at: nowIso(),
          updated_at: nowIso(),
        });
      }
      const nextDashboard = updateDashboardWatchlist(await dashboardBundle(db), tickers);
      await saveDashboard(db, nextDashboard);
      return jsonResponse(200, {
        message: "Watchlist updated. The next scheduled refresh will analyze newly added tickers.",
        tickers,
      });
    }

    if (method === "GET" && path.startsWith("/tickers/")) {
      const ticker = normalizeTicker(path.split("/").pop());
      const dashboard = await dashboardBundle(db);
      const detail = dashboard.tickers?.[ticker];
      if (!detail) {
        return jsonResponse(404, { detail: "Ticker not found in stored history." });
      }
      return jsonResponse(200, detail);
    }

    if (method === "GET" && path === "/positions") {
      const dashboard = await dashboardBundle(db);
      return jsonResponse(200, { items: dashboard.open_positions || [] });
    }

    if (method === "GET" && /^\/positions\/[^/]+$/.test(path)) {
      const dashboard = await dashboardBundle(db);
      const positionId = decodeURIComponent(path.split("/")[2]);
      const detail = dashboard.positions?.[positionId] || (await buildPositionDetailFromStore(db, dashboard, positionId));
      if (!detail) {
        return jsonResponse(404, { detail: "Position not found." });
      }
      return jsonResponse(200, detail);
    }

    if (method === "POST" && path === "/positions/from-signal") {
      requireAdmin(event);
      return jsonResponse(200, await createPositionFromSignal(db, await dashboardBundle(db), parseJsonBody(event)));
    }

    if (method === "POST" && /^\/positions\/[^/]+\/events$/.test(path)) {
      requireAdmin(event);
      const positionId = decodeURIComponent(path.split("/")[2]);
      return jsonResponse(200, await createPositionEvent(db, await dashboardBundle(db), positionId, parseJsonBody(event)));
    }

    if (method === "GET" && path === "/settings") {
      const dashboard = await dashboardBundle(db);
      return jsonResponse(200, dashboard.settings || {});
    }

    if (method === "PUT" && path === "/settings") {
      requireAdmin(event);
      const body = parseJsonBody(event);
      const createdAt = nowIso();
      const settings = {
        preference_id: `prefs:${DEFAULT_USER_ID}`,
        user_id: DEFAULT_USER_ID,
        theme: body.theme || "system",
        density: body.density || "comfortable",
        default_view: body.default_view || "overview",
        favorite_metric: body.favorite_metric || "confidence",
        show_only_actionable: body.show_only_actionable ? 1 : 0,
        risk_budget_pct: Number(body.risk_budget_pct || 0.01),
        max_add_fraction: Number(body.max_add_fraction || 0.25),
        preferences_json: {
          theme: body.theme || "system",
          density: body.density || "comfortable",
          default_view: body.default_view || "overview",
          favorite_metric: body.favorite_metric || "confidence",
          show_only_actionable: Boolean(body.show_only_actionable),
          risk_budget_pct: Number(body.risk_budget_pct || 0.01),
          max_add_fraction: Number(body.max_add_fraction || 0.25),
        },
        created_at: createdAt,
        updated_at: createdAt,
      };
      await setDoc(db, "ui_preferences", settings.preference_id, settings);
      const nextDashboard = updateDashboardSettings(await dashboardBundle(db), settings.preferences_json);
      await saveDashboard(db, nextDashboard);
      return jsonResponse(200, settings.preferences_json);
    }

    if (method === "POST" && path === "/refresh") {
      return jsonResponse(501, {
        detail: "Hosted manual refresh is not wired yet. Use the scheduled GitHub Action or workflow_dispatch.",
      });
    }

    if (method === "GET" && path === "/defaults") {
      return jsonResponse(200, {
        tickers: ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "CRM", "AMD", "NFLX", "DUOL", "SAP", "ENI.MI", "ENEL.MI", "RACE.MI", "RACE"],
        daily_period: "2y",
        architecture: "Netlify + Firebase + GitHub Actions + Netlify Functions",
        firebase_project_id: process.env.FIREBASE_PROJECT_ID || "swingia",
      });
    }

    return jsonResponse(404, { detail: `Unhandled route: ${method} ${path}` });
  } catch (error) {
    return jsonResponse(error.statusCode || 400, {
      detail: error.message || "Unexpected serverless error.",
    });
  }
};
