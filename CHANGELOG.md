# Changelog

## Phase 1. Audit

- File toccati:
  nessuno, audit read-only
- Decisioni prese:
  individuati monolite backend, monolite frontend e persistence duplicata
- Problemi risolti:
  chiarita la causa del coupling tra scan live, storage e UI
- Problemi rimasti:
  logica live, backtest e backup file ancora divergenti

## Phase 2. Scelta architettura

- File toccati:
  [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOY_FREE_TIER.md](DEPLOY_FREE_TIER.md)
- Decisioni prese:
  scelta `Netlify + Firebase + GitHub Actions`, con frontend snapshot-first e FastAPI locale/admin
- Problemi risolti:
  evitata la dipendenza da compute always-on e da riscrittura Cloudflare-oriented del motore Python
- Problemi rimasti:
  Firestore e ancora opzionale, non frontend-facing

## Phase 3. Refactor struttura progetto

- File toccati:
  `swing_trading/__init__.py`, `swing_trading/constants.py`, `swing_trading/models.py`, `app.py`, `swing_trading_ai_improved.py`
- Decisioni prese:
  wrapper legacy mantenuti, nuovo package Python separato
- Problemi risolti:
  `app.py` non contiene piu tutta la logica di dominio
- Problemi rimasti:
  i vecchi file di backup non sono ancora rimossi

## Phase 4. DB + persistenza

- File toccati:
  `swing_trading/storage.py`, `.env.example`, `config/watchlist.json`
- Decisioni prese:
  SQLite come source of truth locale del job, JSON statico come export, JSONL/CSV non piu sulla serving path
- Problemi risolti:
  schema normalizzato per users, watchlist, snapshots, features, predictions, targets, signal history, profiles, backtest runs, ui preferences
- Problemi rimasti:
  non esiste ancora una migration automatica dai vecchi artifact storici

## Phase 5. Scheduler giornaliero

- File toccati:
  `swing_trading/jobs/daily_refresh.py`, `.github/workflows/daily-refresh.yml`
- Decisioni prese:
  refresh schedulato via GitHub Actions, non via page load
- Problemi risolti:
  il deploy statico non innesca piu scansioni live a ogni visita
- Problemi rimasti:
  l'orario schedulato e fisso UTC; in futuro si puo rifinire per mercati diversi

## Phase 6. Adaptive ticker profile

- File toccati:
  `swing_trading/calibration.py`, `swing_trading/storage.py`
- Decisioni prese:
  profilo per ticker basato su win rate, target error, MAE/MFE, holding days, regime dominante
- Problemi risolti:
  introdotta una base vera per tarare confidence e target per ticker
- Problemi rimasti:
  shrinkage statistico avanzato non ancora implementato

## Phase 7. Target long/short calibration

- File toccati:
  `swing_trading/signal_engine.py`, `MODEL_CALIBRATION.md`
- Decisioni prese:
  target baseline da ATR + struttura, poi correzione con `target_shrink_factor`
- Problemi risolti:
  livelli signed-safe, output strutturato, confidence piu simmetrica, warning flags esplicite
- Problemi rimasti:
  alcune configurazioni restano conservative e possono produrre RR basso su ticker compressi

## Phase 8. UI redesign

- File toccati:
  `index.html`, `static/index.html`, `static/styles.css`, `static/app.js`, `static/js/*`, `UI_UX_NOTES.md`
- Decisioni prese:
  SPA vanilla JS a viste separate, router hash-based, snapshot-first data loading
- Problemi risolti:
  niente homepage monolitica, ticker detail separato, segnali/tabella/history/settings distinti
- Problemi rimasti:
  il deploy statico resta read-only per watchlist globale e scheduler

## Phase 9. QA finale

- File toccati:
  `tests/test_signal_engine.py`, `tests/test_calibration.py`
- Decisioni prese:
  copertura minima sulle funzioni critiche di generazione segnale e calibrazione
- Problemi risolti:
  esistono ora test deterministici sui punti piu fragili
- Problemi rimasti:
  manca ancora una smoke test frontend piu robusta per la SPA modulare

## Phase 10. Documentazione

- File toccati:
  `README.md`, `ARCHITECTURE.md`, `DEPLOY_FREE_TIER.md`, `MODEL_CALIBRATION.md`, `UI_UX_NOTES.md`, `CHANGELOG.md`
- Decisioni prese:
  documentazione orientata sia a uso locale sia a deploy gratuito
- Problemi risolti:
  flusso di avvio, deploy, limiti free tier e modello di calibrazione ora sono espliciti
- Problemi rimasti:
  una guida di migrazione dai vecchi `history/scan_history.*` al nuovo schema non e ancora stata scritta
