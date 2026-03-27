# Architecture

## Decisione finale

Scelta implementata: **Netlify + Firebase + GitHub Actions**, con un adattamento pragmatico:

- **Netlify** serve il frontend statico.
- **GitHub Actions** esegue il refresh giornaliero del motore Python.
- **SQLite** e la fonte canonica locale del job.
- **Firestore** e opzionale come mirror cloud, utile per persistenza off-repo.
- **FastAPI** resta per sviluppo locale e admin/debug, non come backend pubblico always-on.

Questa scelta e stata preferita a Cloudflare Workers/D1 per evitare una riscrittura innaturale del runtime Python verso un modello serverless meno adatto a `yfinance`, `pandas` e `ta`.

## Flussi

### Locale

1. `uvicorn app:app --reload`
2. la UI chiama `GET /api/dashboard`
3. un refresh esplicito usa `POST /api/refresh`
4. la pipeline salva SQLite e rigenera `static/data/app-state.json`

### Produzione free-tier

1. GitHub Actions schedulata esegue `python -m swing_trading.jobs.daily_refresh`
2. il job aggiorna `history/swing_trading_ai.sqlite3`
3. il job esporta `static/data/app-state.json`
4. il workflow committa lo snapshot aggiornato
5. Netlify ridistribuisce il frontend
6. opzionalmente il job sincronizza le tabelle verso Firestore

## Componenti

- `market_data.py`
  scarica daily OHLCV confermati, costruisce indicatori e regime di mercato
- `signal_engine.py`
  costruisce fattori direzionali, livelli signed-safe, target multipli e warning flags
- `calibration.py`
  aggrega outcome storici in `ticker_profiles` e adatta confidence/target
- `storage.py`
  gestisce schema, upsert, bundle dashboard e dettaglio ticker
- `service.py`
  orchestra pipeline, seed watchlist, export statico e compatibilita con l'entrypoint legacy
- `api.py`
  espone read APIs e write APIs locali

## Modello dati

### `users`

- PK: `user_id`
- Relazioni: padre di `watched_tickers`, `ui_preferences`
- Timestamp: `created_at`, `updated_at`
- Indici: PK
- Retention: indefinita per il profilo demo locale

### `watched_tickers`

- PK: `watch_id`
- Relazioni: `user_id -> users`
- Timestamp: `created_at`, `updated_at`
- Indici: `(user_id, is_active)`, unique `(user_id, ticker)`
- Retention: indefinita, con `is_active` per archivio logico

### `ticker_daily_snapshots`

- PK: `snapshot_id`
- Relazioni: logiche verso ticker via `ticker`
- Timestamp: `created_at`, `updated_at`
- Indici: unique `(ticker, session_date)`, `(ticker, session_date desc)`
- Retention: indefinita, base di replay e history

### `ticker_profiles`

- PK: `profile_id`
- Relazioni: unique logica su `ticker`
- Timestamp: `created_at`, `updated_at`
- Indici: unique `ticker`, `reliability_score desc`
- Retention: indefinita, stato adattivo corrente

### `model_features`

- PK: `feature_id`
- Relazioni: logiche verso `ticker_daily_snapshots`
- Timestamp: `created_at`, `updated_at`
- Indici: unique `(ticker, session_date, feature_set)`
- Retention: indefinita nel refactor attuale; archiviabile in futuro

### `predictions`

- PK: `prediction_id`
- Relazioni: logiche verso `ticker`, `targets`, `signal_history`
- Timestamp: `created_at`, `updated_at`
- Indici: unique `(ticker, session_date)`, `(ticker, session_date desc)`
- Retention: indefinita nel refactor attuale

### `targets`

- PK: `target_id`
- Relazioni: `prediction_id -> predictions`
- Timestamp: `created_at`, `updated_at`
- Indici: unique `(prediction_id, kind)`
- Retention: indefinita

### `signal_history`

- PK: `signal_id`
- Relazioni: `prediction_id -> predictions`
- Timestamp: `created_at`, `updated_at`
- Indici: `prediction_id unique`, `(ticker, session_date desc)`
- Retention: indefinita

### `backtest_runs`

- PK: `run_id`
- Relazioni: nessuna stretta, ma collega i refresh schedulati
- Timestamp: `started_at`, `completed_at`, `created_at`, `updated_at`
- Indici: PK
- Retention: storica; comprimibile in futuro

### `ui_preferences`

- PK: `preference_id`
- Relazioni: `user_id -> users`
- Timestamp: `created_at`, `updated_at`
- Indici: `user_id unique`
- Retention: finche il profilo esiste

## Limiti noti

- Il mirror Firestore e opzionale e non ancora usato dal frontend.
- Il backend pubblico in produzione e volutamente evitato: il frontend deployato e read-only rispetto ai dati di mercato.
- La persistenza cloud della watchlist richiederebbe un ulteriore layer auth/admin se si volesse modificarla da Netlify senza passare dal job o dal backend locale.
