const DEFAULT_USER_ID = "local-default-user";

function deepClone(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function normalizeTicker(value) {
  const ticker = String(value || "").trim().toUpperCase();
  if (!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(ticker)) {
    throw new Error(`Invalid ticker: ${value}`);
  }
  return ticker;
}

function ensurePositiveNumber(value, fieldName) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new Error(`${fieldName} must be greater than zero.`);
  }
  return number;
}

function ensureNonNegativeNumber(value, fieldName) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number < 0) {
    throw new Error(`${fieldName} cannot be negative.`);
  }
  return number;
}

function parseTimestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function entryReferencePrice(signal) {
  if (!signal) return null;
  return signal.direction === "long" ? signal.entry_high : signal.entry_low;
}

function targetLevels(targetSet, scope) {
  if (!targetSet) return [];
  const items = [
    ["target_1", targetSet.target_1],
    ["target_2", targetSet.target_2],
    ["target_3", targetSet.target_3 ?? targetSet.optional_target_3],
    ["probabilistic_target", targetSet.probabilistic_target],
  ];
  return items
    .filter(([, price]) => price != null)
    .map(([kind, price]) => ({
      kind,
      price: Number(price),
      probability: null,
      distance_atr: 0,
      rationale: `${kind} ${scope}`,
      scope,
      version: 1,
      reference_price: targetSet.entry_reference_price ?? targetSet.reference_entry_price ?? null,
    }));
}

function extractTarget(targets, kind) {
  return (targets || []).find((target) => target.kind === kind)?.price ?? null;
}

function pnlForClose(side, entryPrice, exitPrice, quantity) {
  return side === "long"
    ? (exitPrice - entryPrice) * quantity
    : (entryPrice - exitPrice) * quantity;
}

function distanceToLevelPct(side, currentPrice, level, intent) {
  if (!Number.isFinite(currentPrice) || !Number.isFinite(level) || currentPrice <= 0) {
    return null;
  }
  if (intent === "stop") {
    return side === "long"
      ? Math.max((currentPrice - level) / currentPrice, 0)
      : Math.max((level - currentPrice) / currentPrice, 0);
  }
  return side === "long"
    ? Math.max((level - currentPrice) / currentPrice, 0)
    : Math.max((currentPrice - level) / currentPrice, 0);
}

function computeExcursions(side, referenceEntry, priceHistory) {
  if (!referenceEntry || !Array.isArray(priceHistory) || !priceHistory.length) {
    return { mfe: 0, mae: 0 };
  }
  let favorable = 0;
  let adverse = 0;
  for (const point of priceHistory) {
    const high = Number(point.high ?? point.close ?? referenceEntry);
    const low = Number(point.low ?? point.close ?? referenceEntry);
    if (side === "long") {
      favorable = Math.max(favorable, (high - referenceEntry) / referenceEntry);
      adverse = Math.max(adverse, (referenceEntry - low) / referenceEntry);
    } else {
      favorable = Math.max(favorable, (referenceEntry - low) / referenceEntry);
      adverse = Math.max(adverse, (high - referenceEntry) / referenceEntry);
    }
  }
  return { mfe: favorable, mae: adverse };
}

function rebuildPositionSummary({
  positionId,
  userId,
  ticker,
  strategyId,
  strategyName,
  signalIdOrigin,
  side,
  openedAt,
  events,
  originalTargets,
  adaptiveTargets,
  originalStop,
  currentStop,
  markPrice,
  asOf,
  priceHistory,
  lastRecommendation = "maintain",
  lastRecommendationConfidence = null,
  lastRecommendationReason = "",
  notes = "",
}) {
  const sortedEvents = [...(events || [])].sort((left, right) => {
    const timeCompare = String(left.executed_at).localeCompare(String(right.executed_at));
    return timeCompare || String(left.id || left.event_id).localeCompare(String(right.id || right.event_id));
  });
  let currentQuantity = 0;
  let costBasis = 0;
  let realizedPnl = 0;
  let initialEntryPrice = 0;
  let averageEntryPrice = 0;
  let initialQuantity = 0;
  let closedAt = null;
  let latestNotes = String(notes || "").trim();
  let liveStop = currentStop ?? originalStop ?? null;
  let liveAdaptiveTargets = [...(adaptiveTargets || [])];

  for (const event of sortedEvents) {
    const quantity = Number(event.quantity || 0);
    const price = event.price == null ? null : Number(event.price);
    const fees = Number(event.fees || 0);
    if (event.event_type === "OPEN" || event.event_type === "ADD") {
      costBasis += Number(price || 0) * quantity;
      currentQuantity += quantity;
      averageEntryPrice = currentQuantity > 0 ? costBasis / currentQuantity : averageEntryPrice;
      if (event.event_type === "OPEN" && initialQuantity === 0) {
        initialQuantity = quantity;
        initialEntryPrice = Number(price || 0);
      }
    } else if (event.event_type === "REDUCE" || event.event_type === "CLOSE") {
      if (currentQuantity <= 0) continue;
      const exitQuantity = event.event_type === "CLOSE" ? currentQuantity : Math.min(quantity, currentQuantity);
      realizedPnl += pnlForClose(side, averageEntryPrice, Number(price || 0), exitQuantity) - fees;
      currentQuantity = Math.max(currentQuantity - exitQuantity, 0);
      costBasis = averageEntryPrice * currentQuantity;
      if (currentQuantity === 0) {
        closedAt = event.executed_at;
      }
    } else if (event.event_type === "UPDATE_STOP") {
      const stopValue = event.metadata?.stop ?? price;
      liveStop = stopValue == null ? liveStop : Number(stopValue);
    } else if (event.event_type === "UPDATE_TARGETS" && Array.isArray(event.metadata?.targets)) {
      liveAdaptiveTargets = [...event.metadata.targets];
    }
    if (event.notes) {
      latestNotes = [latestNotes, String(event.notes).trim()].filter(Boolean).join("\n");
    }
  }

  if (!initialQuantity && sortedEvents[0]) {
    initialQuantity = Number(sortedEvents[0].quantity || 0);
    initialEntryPrice = Number(sortedEvents[0].price || 0);
  }
  if (!averageEntryPrice) {
    averageEntryPrice = initialEntryPrice;
  }

  const currentMark = Number(markPrice ?? averageEntryPrice);
  const unrealizedPnl =
    currentQuantity > 0 ? pnlForClose(side, averageEntryPrice, currentMark, currentQuantity) : 0;
  const totalPnl = realizedPnl + unrealizedPnl;
  const grossExposure = Math.abs(currentQuantity * currentMark);
  const openedDate = parseTimestamp(openedAt) || new Date();
  const asOfDate = parseTimestamp(asOf) || new Date();
  const holdingDays = Math.max(Math.floor((asOfDate - openedDate) / 86400000), 0);
  const excursions = computeExcursions(side, initialEntryPrice || averageEntryPrice, priceHistory);
  const effectiveTargets = liveAdaptiveTargets.length ? liveAdaptiveTargets : [...(originalTargets || [])];

  return {
    position_id: positionId,
    user_id: userId,
    ticker,
    strategy_id: strategyId,
    strategy_name: strategyName,
    signal_id_origin: signalIdOrigin,
    side,
    status: currentQuantity > 0 ? "open" : "closed",
    initial_entry_price: Number((initialEntryPrice || 0).toFixed(4)),
    average_entry_price: Number((averageEntryPrice || 0).toFixed(4)),
    initial_quantity: Number((initialQuantity || 0).toFixed(4)),
    current_quantity: Number((currentQuantity || 0).toFixed(4)),
    opened_at: openedDate.toISOString(),
    closed_at: closedAt || null,
    original_stop: originalStop == null ? null : Number(Number(originalStop).toFixed(4)),
    current_stop: liveStop == null ? null : Number(Number(liveStop).toFixed(4)),
    targets_from_original_signal: [...(originalTargets || [])],
    current_adaptive_targets: effectiveTargets,
    realized_pnl: Number(realizedPnl.toFixed(4)),
    unrealized_pnl: Number(unrealizedPnl.toFixed(4)),
    total_pnl: Number(totalPnl.toFixed(4)),
    gross_exposure: Number(grossExposure.toFixed(4)),
    holding_days: holdingDays,
    max_favorable_excursion: Number(excursions.mfe.toFixed(4)),
    max_adverse_excursion: Number(excursions.mae.toFixed(4)),
    distance_to_stop_pct: distanceToLevelPct(side, currentMark, liveStop, "stop"),
    distance_to_target_1_pct: distanceToLevelPct(side, currentMark, extractTarget(effectiveTargets, "target_1"), "target"),
    distance_to_target_2_pct: distanceToLevelPct(side, currentMark, extractTarget(effectiveTargets, "target_2"), "target"),
    mark_price: Number(currentMark.toFixed(4)),
    current_price: Number(currentMark.toFixed(4)),
    last_recommendation: lastRecommendation,
    last_recommendation_confidence: lastRecommendationConfidence,
    last_recommendation_reason: lastRecommendationReason,
    warning_flags: [],
    notes: latestNotes,
  };
}

function adaptivePositionTargets({ position, signal, profile, marketSnapshot, originalTargets }) {
  if (!signal || !profile || !marketSnapshot || !originalTargets) {
    return originalTargets;
  }
  const originalEntry =
    originalTargets.entry_reference_price ??
    originalTargets.reference_entry_price ??
    entryReferencePrice(signal) ??
    marketSnapshot.close;
  const anchorEntry =
    position.average_entry_price || position.initial_entry_price || originalEntry || marketSnapshot.close;
  const baseT1Distance = Math.abs((originalTargets.target_1 ?? marketSnapshot.close) - (originalEntry ?? marketSnapshot.close));
  const baseT2Distance = Math.abs((originalTargets.target_2 ?? marketSnapshot.close) - (originalEntry ?? marketSnapshot.close));
  const baseProbDistance = Math.abs((originalTargets.probabilistic_target ?? marketSnapshot.close) - (originalEntry ?? marketSnapshot.close));
  const atr = Math.max(Number(marketSnapshot.atr || 0.01), 0.01);
  const calibration = clamp(
    Number(profile.target_shrink_factor || 1) * 0.65 + Number(profile.target_aggression || 1) * 0.35,
    0.74,
    1.18,
  );
  let regimeFactor = 1;
  if (marketSnapshot.market_regime === "RISK_OFF" && position.side === "long") regimeFactor = 0.92;
  if (marketSnapshot.market_regime === "RISK_ON" && position.side === "short") regimeFactor = 0.92;
  if (marketSnapshot.market_regime === "RISK_ON" && position.side === "long") regimeFactor = 1.05;
  if (marketSnapshot.market_regime === "RISK_OFF" && position.side === "short") regimeFactor = 1.05;

  const distance1 = Math.max(baseT1Distance * calibration * regimeFactor, atr * 0.9);
  const distance2 = Math.max(baseT2Distance * calibration * regimeFactor, distance1 * 1.3, atr * 1.6);
  const distanceProb = Math.max(baseProbDistance * calibration, distance1 * 1.1, atr * 0.8);

  let target1;
  let target2;
  let probabilisticTarget;
  let stopLoss;

  if (position.side === "long") {
    target1 = anchorEntry + distance1;
    target2 = anchorEntry + distance2;
    probabilisticTarget = anchorEntry + distanceProb;
    const stopFloor = originalTargets.stop_loss ?? anchorEntry - atr * 1.25;
    const structureStop = marketSnapshot.support ?? anchorEntry - atr * 1.2;
    stopLoss = Math.max(Math.min(stopFloor, anchorEntry - atr * 0.55), structureStop - atr * 0.15);
  } else {
    target1 = anchorEntry - distance1;
    target2 = anchorEntry - distance2;
    probabilisticTarget = anchorEntry - distanceProb;
    const stopCeiling = originalTargets.stop_loss ?? anchorEntry + atr * 1.25;
    const structureStop = marketSnapshot.resistance ?? anchorEntry + atr * 1.2;
    stopLoss = Math.min(Math.max(stopCeiling, anchorEntry + atr * 0.55), structureStop + atr * 0.15);
  }

  const risk = Math.abs(anchorEntry - stopLoss);
  const reward = Math.abs(target1 - anchorEntry);
  const warningFlags = [...new Set([...(originalTargets.warning_flags_json || []), ...(signal.warning_flags || [])])];
  if (Number(profile.target_shrink_factor || 1) < 0.9) warningFlags.push("adaptive-targets-derated");

  return {
    id: `targets:position:${position.position_id}:adaptive`,
    subject_type: "position",
    subject_id: position.position_id,
    scope: "position_adaptive",
    ticker: position.ticker,
    side: position.side,
    entry_reference_price: position.initial_entry_price || originalEntry,
    average_entry_reference: anchorEntry,
    stop_loss: Number(stopLoss.toFixed(4)),
    target_1: Number(target1.toFixed(4)),
    target_2: Number(target2.toFixed(4)),
    target_3: null,
    probabilistic_target: Number(probabilisticTarget.toFixed(4)),
    risk_reward: risk ? Number((reward / risk).toFixed(4)) : null,
    confidence_score: signal.confidence_score,
    holding_horizon_estimate: signal.holding_horizon_days,
    rationale_json: {
      summary: "Adaptive targets preserve the original signal geometry while re-anchoring to the real average entry.",
      original_entry_reference: originalEntry,
      average_entry_reference: anchorEntry,
      calibration_factor: Number(calibration.toFixed(4)),
      regime_factor: Number(regimeFactor.toFixed(4)),
    },
    warning_flags_json: warningFlags,
    version_label: `adaptive:${marketSnapshot.session_date || nowIso().slice(0, 10)}`,
    created_at: originalTargets.created_at || nowIso(),
    updated_at: nowIso(),
  };
}

function recommendPositionAction({ position, signal, profile, marketSnapshot, originalTargets, adaptiveTargets, effectiveAt }) {
  const currentTargets = adaptiveTargets || originalTargets || {};
  const target1 = currentTargets.target_1;
  const target2 = currentTargets.target_2;
  const stopLoss =
    currentTargets.stop_loss ?? originalTargets?.stop_loss ?? signal?.stop_loss ?? position.current_stop;
  const signalAlignment = signal?.direction === position.side;
  const closeToStop = (position.distance_to_stop_pct ?? 1) <= 0.015;
  const nearTarget = (position.distance_to_target_1_pct ?? 1) <= 0.02;
  const extension = Math.abs(Number(marketSnapshot?.close_vs_ema21_atr || 0)) >= 1.35;
  const lowTrendQuality = Number(marketSnapshot?.adx || 0) < 18;
  const riskLoaded = position.current_quantity >= position.initial_quantity * 1.5;
  const profileWeak = Boolean(profile?.insufficient_data) || Number(profile?.reliability_score || 0) < 0.48;
  const pnlPositive = position.total_pnl > 0;
  const rsi = Number(marketSnapshot?.rsi || 50);
  const rsiStretched = (position.side === "long" && rsi >= 70) || (position.side === "short" && rsi <= 30);
  const warningFlags = [...new Set([...(originalTargets?.warning_flags_json || []), ...(adaptiveTargets?.warning_flags_json || []), ...(signal?.warning_flags || [])])];
  let confidence = clamp(
    Number(signal?.confidence_score || 0.5) * 0.55 + Number(profile?.reliability_score || 0.5) * 0.3 + (1 - Math.min(Number(profile?.mean_target_error || 0.2), 0.4)) * 0.15,
    0.2,
    0.92,
  );
  let action = "maintain";
  let addQty = null;
  let reduceQty = null;
  let zoneLow = null;
  let zoneHigh = null;
  const reasons = [];

  if (closeToStop) {
    action = "close";
    reasons.push("price is too close to the active stop");
    warningFlags.push("stop-proximity");
  } else if (signal?.direction === "neutral") {
    action = pnlPositive ? "reduce" : "close";
    reasons.push("latest study signal lost directional edge");
  } else if (!signalAlignment) {
    action = confidence < 0.64 ? "close" : "reduce";
    reasons.push("validated signal flipped against the live position");
    warningFlags.push("signal-flip");
  } else if (nearTarget && (extension || pnlPositive)) {
    action = "reduce";
    reasons.push("target 1 is close and upside extension is fading");
  } else if (lowTrendQuality && extension) {
    action = "reduce";
    reasons.push("trend strength is fading while price remains extended");
  } else if (signalAlignment && Number(signal?.confidence_score || 0) >= 0.7 && !riskLoaded && !profileWeak && !extension && (position.distance_to_stop_pct || 0) >= 0.04) {
    action = "add";
    reasons.push("signal remains aligned with acceptable room to stop");
    reasons.push("total size is still below the defined risk envelope");
  } else if (profileWeak) {
    action = "no_action";
    reasons.push("ticker profile quality is not strong enough for a size change");
    warningFlags.push("data-weak");
  } else {
    reasons.push("trend, targets, and size remain broadly aligned");
  }

  if (rsiStretched && action === "add") {
    action = "maintain";
    reasons.length = 0;
    reasons.push("momentum is too stretched for a disciplined add");
    warningFlags.push("stretched-momentum");
  }

  if (action === "add") {
    addQty = Number(Math.max(position.initial_quantity * 0.25, 1).toFixed(4));
    const anchor = entryReferencePrice(signal) ?? Number(marketSnapshot?.close || position.mark_price || position.average_entry_price);
    zoneLow = Number((anchor - Number(marketSnapshot?.atr || 0) * 0.15).toFixed(4));
    zoneHigh = Number((anchor + Number(marketSnapshot?.atr || 0) * 0.1).toFixed(4));
  } else if (action === "reduce") {
    reduceQty = Number(Math.max(position.current_quantity * 0.25, 1).toFixed(4));
  } else if (action === "close") {
    reduceQty = Number(position.current_quantity.toFixed(4));
  }

  return {
    id: `rec:${position.position_id}:${String(effectiveAt).slice(0, 10)}`,
    position_id: position.position_id,
    effective_at: effectiveAt,
    action,
    confidence: Number(confidence.toFixed(4)),
    suggested_add_qty: addQty,
    suggested_reduce_qty: reduceQty,
    suggested_stop: stopLoss == null ? null : Number(Number(stopLoss).toFixed(4)),
    suggested_target_1: target1 == null ? null : Number(Number(target1).toFixed(4)),
    suggested_target_2: target2 == null ? null : Number(Number(target2).toFixed(4)),
    suggested_target_3: currentTargets.target_3 ?? null,
    rationale: `Reason: ${reasons.join("; ")}`,
    warning_flags_json: [...new Set(warningFlags)],
    suggested_zone_low: zoneLow,
    suggested_zone_high: zoneHigh,
    suggested_size_action:
      addQty != null
        ? `add ${addQty}`
        : action === "reduce" && reduceQty != null
        ? `reduce ${reduceQty}`
        : action === "close"
        ? "close all"
        : "hold",
    created_at: nowIso(),
    updated_at: nowIso(),
  };
}

function positionDoc(summary, createdAt, updatedAt) {
  return {
    id: summary.position_id,
    user_id: summary.user_id,
    ticker: summary.ticker,
    strategy_id: summary.strategy_id,
    strategy_name: summary.strategy_name,
    signal_id_origin: summary.signal_id_origin,
    side: summary.side,
    status: summary.status,
    initial_entry_price: summary.initial_entry_price,
    average_entry_price: summary.average_entry_price,
    initial_quantity: summary.initial_quantity,
    current_quantity: summary.current_quantity,
    opened_at: summary.opened_at,
    closed_at: summary.closed_at,
    last_recommendation: summary.last_recommendation,
    last_recommendation_confidence: summary.last_recommendation_confidence,
    last_recommendation_reason: summary.last_recommendation_reason,
    original_stop: summary.original_stop,
    current_stop: summary.current_stop,
    current_price: summary.mark_price,
    realized_pnl: summary.realized_pnl,
    unrealized_pnl: summary.unrealized_pnl,
    total_pnl: summary.total_pnl,
    gross_exposure: summary.gross_exposure,
    holding_days: summary.holding_days,
    max_favorable_excursion: summary.max_favorable_excursion,
    max_adverse_excursion: summary.max_adverse_excursion,
    distance_to_stop_pct: summary.distance_to_stop_pct,
    distance_to_target_1_pct: summary.distance_to_target_1_pct,
    distance_to_target_2_pct: summary.distance_to_target_2_pct,
    notes: summary.notes,
    created_at: createdAt,
    updated_at: updatedAt,
  };
}

function snapshotDoc(summary, recommendation, regime, generatedAt) {
  return {
    id: `snapshot:${summary.position_id}:${String(generatedAt).slice(0, 10)}`,
    position_id: summary.position_id,
    snapshot_date: String(generatedAt).slice(0, 10),
    close_price: summary.mark_price || summary.average_entry_price,
    current_quantity: summary.current_quantity,
    average_entry_price: summary.average_entry_price,
    market_value: summary.gross_exposure,
    unrealized_pnl: summary.unrealized_pnl,
    realized_pnl_to_date: summary.realized_pnl,
    total_pnl: summary.total_pnl,
    distance_to_stop_pct: summary.distance_to_stop_pct,
    distance_to_target_1_pct: summary.distance_to_target_1_pct,
    distance_to_target_2_pct: summary.distance_to_target_2_pct,
    regime: regime || "MIXED",
    action_recommendation: recommendation.action,
    recommendation_confidence: recommendation.confidence,
    recommendation_reason: recommendation.rationale,
    max_favorable_excursion: summary.max_favorable_excursion,
    max_adverse_excursion: summary.max_adverse_excursion,
    created_at: generatedAt,
    updated_at: generatedAt,
  };
}

function eventResponse(event) {
  return {
    event_id: event.id || event.event_id,
    position_id: event.position_id,
    ticker: event.ticker,
    side: event.side,
    event_type: event.event_type,
    quantity: event.quantity,
    price: event.price,
    fees: event.fees,
    executed_at: event.executed_at,
    source: event.source,
    linked_signal_id: event.linked_signal_id,
    metadata: event.metadata_json || event.metadata || {},
    notes: event.notes || "",
    created_at: event.created_at || "",
  };
}

function recommendationResponse(item) {
  return {
    ...item,
    warning_flags: item.warning_flags_json || [],
  };
}

function positionDetail({ position, signal, originalTargets, adaptiveTargets, events, recommendations, tickerDetail }) {
  const openedAt = String(position.opened_at || "").slice(0, 10);
  const chart = (tickerDetail?.snapshots || [])
    .filter((row) => String(row.session_date || "") >= openedAt)
    .map((row) => ({
      session_date: row.session_date,
      open: row.open,
      high: row.high,
      low: row.low,
      close: row.close,
    }));
  return {
    position,
    origin_signal: signal || null,
    original_targets: originalTargets || null,
    adaptive_targets: adaptiveTargets || null,
    events: (events || []).map(eventResponse),
    recommendations: (recommendations || []).map(recommendationResponse).sort((a, b) => String(b.effective_at).localeCompare(String(a.effective_at))),
    chart,
  };
}

function updateDashboardPosition(bundle, detail) {
  const next = deepClone(bundle || {});
  next.open_positions = Array.isArray(next.open_positions) ? next.open_positions : [];
  next.positions = next.positions || {};
  next.history = next.history || { signals: [], position_events: [], position_recommendations: [] };
  const summary = detail.position;
  const openRow = {
    ...summary,
    strategy_name: summary.strategy_name,
    created_at: summary.created_at,
    updated_at: summary.updated_at,
  };
  next.open_positions = next.open_positions.filter((item) => item.position_id !== summary.position_id);
  if (summary.status === "open") {
    next.open_positions.unshift(openRow);
  }
  next.positions[summary.position_id] = detail;
  if (detail.events?.length) {
    next.history.position_events = [
      detail.events[detail.events.length - 1],
      ...(next.history.position_events || []).filter((item) => item.event_id !== detail.events[detail.events.length - 1].event_id),
    ].slice(0, 150);
  }
  if (detail.recommendations?.length) {
    next.history.position_recommendations = [
      detail.recommendations[0],
      ...(next.history.position_recommendations || []).filter((item) => item.id !== detail.recommendations[0].id),
    ].slice(0, 150);
  }
  next.overview = next.overview || {};
  next.overview.open_positions = next.open_positions.length;
  next.overview.total_unrealized_pnl = Number(next.open_positions.reduce((sum, item) => sum + Number(item.unrealized_pnl || 0), 0).toFixed(4));
  next.overview.total_realized_pnl = Number(next.open_positions.reduce((sum, item) => sum + Number(item.realized_pnl || 0), 0).toFixed(4));
  next.overview.positions_requiring_action = next.open_positions.filter((item) => ["add", "reduce", "close"].includes(item.last_recommendation)).length;
  next.generated_at = nowIso();
  return next;
}

function updateDashboardSettings(bundle, settings) {
  const next = deepClone(bundle || {});
  next.settings = settings;
  next.generated_at = nowIso();
  return next;
}

function updateDashboardWatchlist(bundle, tickers) {
  const next = deepClone(bundle || {});
  const currentByTicker = Object.fromEntries((next.study_watchlist || []).map((row) => [row.ticker, row]));
  next.tickers = next.tickers || {};
  next.study_watchlist = tickers.map((ticker) => currentByTicker[ticker] || {
    ticker,
    direction: "neutral",
    confidence_score: 0,
    trend: "pending",
    regime: "pending",
    warning_flags: ["awaiting-refresh"],
    reliability_label: "pending",
    strategy_name: "awaiting-refresh",
  });
  for (const ticker of tickers) {
    if (!next.tickers[ticker]) {
      next.tickers[ticker] = {
        ticker,
        summary: currentByTicker[ticker] || {
          ticker,
          direction: "neutral",
          confidence_score: 0,
          trend: "pending",
          regime: "pending",
          warning_flags: ["awaiting-refresh"],
          reliability_label: "pending",
          strategy_name: "awaiting-refresh",
        },
        latest_prediction: null,
        latest_signal: null,
        targets: null,
        profile: null,
        snapshots: [],
        signal_history: [],
      };
    }
  }
  next.generated_at = nowIso();
  next.overview = next.overview || {};
  next.overview.tracked_tickers = next.study_watchlist.length;
  return next;
}

module.exports = {
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
};
