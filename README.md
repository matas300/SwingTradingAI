# SwingTradingAI

SwingTradingAI e stato rifattorizzato come web app daily-oriented per studiare ticker, generare segnali spiegabili e tenere traccia di posizioni reali con storico eventi.

## Cosa fa

- separa chiaramente `Study Watchlist` e `Open Positions`
- consente di aprire una posizione reale da un segnale
- supporta eventi `OPEN`, `ADD`, `REDUCE`, `CLOSE`, `UPDATE_STOP`, `UPDATE_TARGETS`
- ricalcola media di carico, quantity residua, realized/unrealized PnL e raccomandazione operativa
- mantiene target originari e target adattivi
- produce ticker profile adattivi e spiegabilita per segnali e posizioni

## Stack scelto

Architettura finale:

- frontend statico su `Netlify`
- persistenza cloud sincronizzata su `Firebase Firestore`
- scheduler giornaliero e refresh su `GitHub Actions`
- scritture admin online via `Netlify Functions`
- runtime locale/admin in `FastAPI + SQLite`

Questa scelta e stata preferita a Cloudflare Workers/D1 perche il core del progetto resta Python e usa librerie come `pandas`, `ta` e `yfinance`, piu naturali in un job batch Python che in una riscrittura serverless.

## Flussi principali

1. l'utente aggiunge ticker alla watchlist di studio
2. il job giornaliero aggiorna dati, profili, segnali e target
3. il frontend mostra segnali e watchlist in forma separata
4. l'utente puo aprire una posizione reale da un segnale
5. la posizione evolve con eventi parziali e raccomandazioni giornaliere

## Avvio locale

```bash
python -m pip install -r requirements.txt
python -m swing_trading.jobs.daily_refresh --no-firestore-sync
python -m uvicorn app:app --reload
```

Apri poi `http://127.0.0.1:8000`.

## Deploy online

Secret richiesti:

- `GitHub Actions`
  `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`
- `Netlify`
  `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ADMIN_WRITE_TOKEN`

La UI pubblica resta leggibile da tutti. Le scritture online passano da Netlify Functions e richiedono il token admin inserito dalla vista `Settings`.

## Test

```bash
python -m pytest
```

## File chiave

- [`swing_trading/market_data.py`](swing_trading/market_data.py): feature engineering daily e market context
- [`swing_trading/signal_engine.py`](swing_trading/signal_engine.py): segnale long/short, target, confidence e rationale
- [`swing_trading/calibration.py`](swing_trading/calibration.py): ticker profile e calibrazione adattiva
- [`swing_trading/position_lifecycle.py`](swing_trading/position_lifecycle.py): ricostruzione dello stato posizione da eventi
- [`swing_trading/position_policy.py`](swing_trading/position_policy.py): raccomandazione giornaliera sulla posizione
- [`swing_trading/target_engine.py`](swing_trading/target_engine.py): target originari e adattivi
- [`swing_trading/repository.py`](swing_trading/repository.py): schema, query, lifecycle refresh e dashboard bundle
- [`swing_trading/storage.py`](swing_trading/storage.py): layer di compatibilita per gli import legacy
- [`swing_trading/service.py`](swing_trading/service.py): pipeline batch e export snapshot
- [`swing_trading/api.py`](swing_trading/api.py): backend locale per debug e uso manuale
- [`static/`](static/): SPA vanilla JS deployabile su Netlify

## Documenti

- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`DEPLOY_FREE_TIER.md`](DEPLOY_FREE_TIER.md)
- [`SIGNAL_ENGINE.md`](SIGNAL_ENGINE.md)
- [`POSITION_LIFECYCLE.md`](POSITION_LIFECYCLE.md)
- [`MODEL_CALIBRATION.md`](MODEL_CALIBRATION.md)
- [`UI_UX_NOTES.md`](UI_UX_NOTES.md)
- [`CHANGELOG.md`](CHANGELOG.md)
