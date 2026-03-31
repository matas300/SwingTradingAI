const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function createMockFirestore(initialData = {}) {
  const collections = new Map();

  for (const [collectionName, documents] of Object.entries(initialData)) {
    const collection = new Map();
    for (const [documentId, payload] of Object.entries(documents || {})) {
      collection.set(documentId, clone(payload));
    }
    collections.set(collectionName, collection);
  }

  function ensureCollection(name) {
    if (!collections.has(name)) {
      collections.set(name, new Map());
    }
    return collections.get(name);
  }

  const db = {
    _collections: collections,
    collection(name) {
      const collection = ensureCollection(name);
      return {
        doc(id) {
          return {
            async get() {
              return {
                exists: collection.has(id),
                data: () => clone(collection.get(id)),
              };
            },
            async set(payload, options = {}) {
              const nextValue =
                options && options.merge && collection.has(id)
                  ? { ...clone(collection.get(id)), ...clone(payload) }
                  : clone(payload);
              collection.set(id, nextValue);
            },
          };
        },
        where(field, operator, expected) {
          assert.equal(operator, "==");
          return {
            async get() {
              const docs = Array.from(collection.entries())
                .filter(([, payload]) => payload && payload[field] === expected)
                .map(([id, payload]) => ({
                  id,
                  data: () => clone(payload),
                }));
              return { docs };
            },
          };
        },
        async get() {
          const docs = Array.from(collection.entries()).map(([id, payload]) => ({
            id,
            data: () => clone(payload),
          }));
          return { docs };
        },
      };
    },
  };

  return db;
}

function loadHandler(mockDb) {
  const apiPath = path.resolve(__dirname, "../netlify/functions/api.js");
  const firebasePath = path.resolve(__dirname, "../netlify/functions/_shared/firebase.js");

  delete require.cache[apiPath];
  delete require.cache[firebasePath];

  require.cache[firebasePath] = {
    id: firebasePath,
    filename: firebasePath,
    loaded: true,
    exports: {
      firestore: () => mockDb,
    },
  };

  return require(apiPath).handler;
}

function seedDashboard() {
  const signal = {
    prediction_id: "signal-version:TEST:2026-03-31:adaptive-swing-v2",
    signal_id: "signal:TEST:adaptive-swing-v2",
    ticker: "TEST",
    session_date: "2026-03-31",
    direction: "long",
    entry_low: 99.5,
    entry_high: 100.0,
    entry_reference_price: 100.0,
    stop_loss: 96.0,
    confidence_score: 0.74,
    risk_reward: 2.0,
    holding_horizon_days: 8,
    regime: "MIXED",
    reliability_label: "Balanced",
    rationale: { summary: "Test long setup." },
    warning_flags: [],
    top_factors: [],
    strategy_id: "adaptive-swing-v2",
    strategy_name: "trend-pullback",
    setup_name: "trend-pullback",
    generated_at: "2026-03-31T12:00:00Z",
  };

  const targets = {
    id: "targets:signal:signal:TEST:adaptive-swing-v2",
    subject_type: "signal",
    subject_id: signal.signal_id,
    scope: "signal_original",
    ticker: "TEST",
    side: "long",
    entry_reference_price: 100.0,
    average_entry_reference: 100.0,
    stop_loss: 96.0,
    target_1: 108.0,
    target_2: 112.0,
    target_3: null,
    probabilistic_target: 106.0,
    risk_reward: 2.0,
    confidence_score: 0.74,
    holding_horizon_estimate: 8,
    rationale_json: { summary: "Original target geometry." },
    warning_flags_json: [],
    version_label: "signal-open",
    created_at: "2026-03-31T12:00:00Z",
    updated_at: "2026-03-31T12:00:00Z",
  };

  return {
    generated_at: "2026-03-31T12:00:00Z",
    study_watchlist: [
      {
        ticker: "TEST",
        direction: "long",
        confidence_score: 0.74,
        trend: "UP",
        regime: "MIXED",
        warning_flags: [],
        reliability_label: "Balanced",
        strategy_name: "trend-pullback",
      },
    ],
    signals: [signal],
    open_positions: [],
    tickers: {
      TEST: {
        ticker: "TEST",
        summary: {
          ticker: "TEST",
          direction: "long",
          confidence_score: 0.74,
          trend: "UP",
          regime: "MIXED",
          warning_flags: [],
          reliability_label: "Balanced",
          strategy_name: "trend-pullback",
        },
        latest_prediction: signal,
        latest_signal: signal,
        targets,
        profile: {
          ticker: "TEST",
          reliability_score: 0.68,
          target_shrink_factor: 1.0,
          target_aggression: 1.0,
          mean_target_error: 0.08,
          insufficient_data: false,
        },
        snapshots: [
          {
            session_date: "2026-03-31",
            open: 99.0,
            high: 102.0,
            low: 98.0,
            close: 101.0,
            atr: 2.0,
            support: 98.0,
            resistance: 110.0,
            trend: "UP",
            market_regime: "MIXED",
            rsi: 56.0,
            close_vs_ema21_atr: 0.35,
            adx: 24.0,
          },
        ],
        signal_history: [],
      },
    },
    positions: {},
    history: {
      signals: [],
      position_events: [],
      position_recommendations: [],
    },
    settings: {},
    overview: {
      tracked_tickers: 1,
      open_positions: 0,
      total_unrealized_pnl: 0,
      total_realized_pnl: 0,
      positions_requiring_action: 0,
    },
  };
}

test("hosted open position writes the position and updates dashboard collections", async () => {
  process.env.ADMIN_WRITE_TOKEN = "test-admin-token";
  const dashboard = seedDashboard();
  const db = createMockFirestore({
    _app: {
      dashboard,
    },
  });
  const handler = loadHandler(db);

  const response = await handler({
    httpMethod: "POST",
    path: "/api/positions/from-signal",
    headers: {
      "x-admin-token": "test-admin-token",
    },
    body: JSON.stringify({
      signal_id: "signal:TEST:adaptive-swing-v2",
      execution_price: 100.5,
      quantity: 2,
      executed_at: "2026-03-31T14:30",
      fees: 0.5,
      notes: "Open the test position",
    }),
  });

  assert.equal(response.statusCode, 200);
  const payload = JSON.parse(response.body);
  const positionId = payload.position.position_id;

  assert.ok(positionId);
  assert.equal(db._collections.get("open_positions").size, 1);
  assert.equal(db._collections.get("position_events").size, 1);
  assert.equal(db._collections.get("position_recommendations").size, 1);

  const storedDashboard = db._collections.get("_app").get("dashboard");
  assert.equal(storedDashboard.open_positions.length, 1);
  assert.equal(storedDashboard.positions[positionId].position.position_id, positionId);
  assert.equal(storedDashboard.overview.open_positions, 1);
});

test("hosted position events refresh dashboard state after the write", async () => {
  process.env.ADMIN_WRITE_TOKEN = "test-admin-token";
  const dashboard = seedDashboard();
  const db = createMockFirestore({
    _app: {
      dashboard,
    },
  });
  const handler = loadHandler(db);

  const opened = await handler({
    httpMethod: "POST",
    path: "/api/positions/from-signal",
    headers: {
      "x-admin-token": "test-admin-token",
    },
    body: JSON.stringify({
      signal_id: "signal:TEST:adaptive-swing-v2",
      execution_price: 100.5,
      quantity: 2,
      executed_at: "2026-03-31T14:30",
      fees: 0,
      notes: "Open the test position",
    }),
  });
  const openedPayload = JSON.parse(opened.body);
  const positionId = openedPayload.position.position_id;

  const response = await handler({
    httpMethod: "POST",
    path: `/api/positions/${encodeURIComponent(positionId)}/events`,
    headers: {
      "x-admin-token": "test-admin-token",
    },
    body: JSON.stringify({
      event_type: "ADD",
      quantity: 1,
      price: 101.0,
      fees: 0,
      executed_at: "2026-03-31T15:00",
      notes: "Add to the winner",
      metadata: {},
    }),
  });

  assert.equal(response.statusCode, 200);
  const payload = JSON.parse(response.body);
  assert.equal(payload.position.current_quantity, 3);

  const storedDashboard = db._collections.get("_app").get("dashboard");
  assert.equal(storedDashboard.open_positions[0].current_quantity, 3);
  assert.equal(storedDashboard.positions[positionId].position.current_quantity, 3);
});
