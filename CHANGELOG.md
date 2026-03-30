# Changelog

## Phase 1. Audit

- File toccati:
  nessuno, audit read-only
- Decisioni prese:
  identificati monolite backend, frontend statico semplice e persistence da consolidare
- Problemi risolti:
  chiarita la necessita di separare study layer e position layer
- Problemi rimasti:
  alcune parti del vecchio stack locale restano come compat layer

## Phase 2. Refactor architetturale

- File toccati:
  `ARCHITECTURE.md`, `DEPLOY_FREE_TIER.md`, `README.md`
- Decisioni prese:
  scelta finale su `Netlify + Firebase + GitHub Actions`
- Problemi risolti:
  evitata una riscrittura verso Cloudflare Workers/D1 non adatta al motore Python
- Problemi rimasti:
  Firestore e sincronizzato dal job e non ancora un backend realtime multiutente completo

## Phase 3. Domain model

- File toccati:
  `swing_trading/models.py`, `swing_trading/position_lifecycle.py`, `swing_trading/position_policy.py`, `swing_trading/target_engine.py`
- Decisioni prese:
  posizioni gestite come eventi e target separati in originari/adattivi
- Problemi risolti:
  ricostruzione di media di carico, realized/unrealized PnL e recommendation giornaliera
- Problemi rimasti:
  la UI deve ancora mostrare tutti i campi avanzati in modo completo

## Phase 4. Signal e calibration

- File toccati:
  `swing_trading/signal_engine.py`, `MODEL_CALIBRATION.md`
- Decisioni prese:
  target derivati da struttura + ATR + correzione ticker-based
- Problemi risolti:
  segnali non piu cosmetici
- Problemi rimasti:
  la calibrazione resta euristica

## Phase 5. Persistence e scheduler

- File toccati:
  `swing_trading/storage.py`, `swing_trading/service.py`, `swing_trading/jobs/daily_refresh.py`
- Decisioni prese:
  SQLite come base locale e export statico per Netlify
- Problemi risolti:
  bundle giornaliero e snapshot persistenti
- Problemi rimasti:
  la sync Firestore richiede configurazione credential completa

## Phase 6. UI notes

- File toccati:
  `UI_UX_NOTES.md`
- Decisioni prese:
  viste separate, no homepage monolitica
- Problemi risolti:
  IA definita per study watchlist, open positions e position detail
- Problemi rimasti:
  alcuni dettagli di rendering finale sono ancora in assestamento

## Phase 7. Documentation completion

- File toccati:
  `SIGNAL_ENGINE.md`, `POSITION_LIFECYCLE.md`
- Decisioni prese:
  documentare chiaramente event sourcing, recommendation e target duali
- Problemi risolti:
  i concetti critici ora hanno una guida autonoma
- Problemi rimasti:
  la migrazione storica dei vecchi artifact non e ancora documentata in modo esaustivo
