# SwingTradingAI

Refactor completo di `SwingTradingAI` in una web app daily-only con:

- frontend a viste separate: `Overview`, `Watchlist`, `Ticker Detail`, `Signals`, `History`, `Settings`
- pipeline Python batchabile e schedulabile
- persistenza canonica su SQLite locale
- export snapshot statico per Netlify
- sync opzionale verso Firebase Firestore da GitHub Actions
- profili adattivi per ticker
- target long/short calibrati e spiegabili
- storico outcome e signal history

## Architettura scelta

Scelta finale: **Opzione B, Netlify + Firebase + GitHub Actions**.

Motivo pratico:

- il motore resta Python (`pandas`, `ta`, `yfinance`)
- GitHub Actions esegue bene un job giornaliero read-heavy
- Netlify ospita gratis il frontend statico
- Firestore puo diventare lo storage cloud di supporto senza esporre segreti nel client
- in locale restano disponibili FastAPI e SQLite per sviluppo e debug

Nel refactor attuale il percorso reale e:

- sviluppo locale: `FastAPI + SQLite + export statico`
- produzione gratuita: `GitHub Actions -> pipeline Python -> SQLite locale del job -> export static/data/app-state.json -> commit -> Netlify deploy`
- opzionale: `GitHub Actions -> sync SQLite -> Firestore`

## Avvio locale

```bash
python -m pip install -r requirements.txt
python -m swing_trading.jobs.daily_refresh --no-firestore-sync
python -m uvicorn app:app --reload
```

Apri poi `http://127.0.0.1:8000`.

## Test

```bash
python -m pytest
```

## File principali

- `swing_trading/market_data.py`: download dati daily confermati e feature engineering
- `swing_trading/signal_engine.py`: direction, entry zone, stop, target, confidence, rationale
- `swing_trading/calibration.py`: ticker profile e correzione target/confidence
- `swing_trading/storage.py`: schema SQLite, persistenza, query dashboard
- `swing_trading/service.py`: pipeline batch, export snapshot, compat layer legacy
- `swing_trading/api.py`: backend FastAPI per uso locale/admin
- `swing_trading/jobs/daily_refresh.py`: job schedulabile
- `static/`: SPA vanilla JS hostabile su Netlify
- `static/data/app-state.json`: ultimo snapshot statico
- `.github/workflows/daily-refresh.yml`: refresh giornaliero

## Endpoint locali

- `GET /api/dashboard`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `GET /api/tickers/{ticker}`
- `GET /api/history`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/refresh`
- `POST /api/scan`

## Note operative

- Il sistema usa solo barre daily confermate.
- Il frontend in modalita statica non lancia scansioni all'avvio: legge l'ultimo snapshot disponibile.
- Le preferenze UI restano salvate anche in `localStorage`; in locale possono anche essere persistite via API.
- La watchlist del job schedulato parte da `config/watchlist.json`.

## Documentazione aggiuntiva

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEPLOY_FREE_TIER.md](DEPLOY_FREE_TIER.md)
- [MODEL_CALIBRATION.md](MODEL_CALIBRATION.md)
- [UI_UX_NOTES.md](UI_UX_NOTES.md)
- [CHANGELOG.md](CHANGELOG.md)
