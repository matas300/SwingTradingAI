# Architecture

## Decisione finale

Stack finale:

- `Netlify` per il frontend statico
- `Firebase Firestore` come persistenza cloud sincronizzata
- `GitHub Actions` per il job giornaliero
- `FastAPI + SQLite` per sviluppo locale e uso amministrativo

La scelta evita un backend always-on a pagamento e mantiene il motore Python nel suo ambiente naturale. Firestore viene sincronizzato dal job giornaliero come store cloud del dataset e delle entita utente, mentre il motore analitico resta Python.

## Principi

- il motore di mercato resta Python
- il frontend legge snapshot e bundle JSON
- il refresh avviene a batch giornaliero
- i dati di studio e le posizioni reali sono entita distinte
- la posizione e event-sourced, non un record statico

## Flusso dati

### Locale

1. `uvicorn app:app --reload`
2. la UI chiama `GET /api/dashboard`
3. il refresh manuale chiama `POST /api/refresh`
4. la pipeline salva SQLite e rigenera `static/data/app-state.json`

### Produzione free-tier

1. GitHub Actions esegue il refresh giornaliero
2. il job aggiorna il dataset locale del workflow
3. il job esporta il bundle statico
4. Netlify serve il frontend
5. Firestore riceve il push delle tabelle principali e puo rialimentare il job con un pull iniziale

## Componenti

- `market_data.py`
  scarica daily OHLCV confermati e costruisce le feature
- `signal_engine.py`
  genera setup long/short spiegabili con entry, stop, target e warning flags
- `calibration.py`
  aggiorna ticker profile e calibra confidence e target
- `target_engine.py`
  mantiene il riferimento all'entry originaria e al prezzo medio reale della posizione
- `position_lifecycle.py`
  ricostruisce lo stato reale da una sequenza di eventi
- `position_policy.py`
  produce la raccomandazione giornaliera per la posizione aperta
- `repository.py`
  espone persistenza, upsert, refresh posizione e bundle dashboard
- `storage.py`
  mantiene compatibilita con gli import precedenti
- `service.py`
  orchestra il batch, il seed della watchlist e l'export JSON

## Modello concettuale

### Study layer

Ticker osservati senza capitale impegnato. Per ogni ticker:

- snapshot giornalieri
- storico segnali
- profilo adattivo
- target originari

### Position layer

Posizioni realmente aperte dall'utente. Per ogni posizione:

- record di sintesi
- eventi `OPEN`, `ADD`, `REDUCE`, `CLOSE`
- snapshot giornalieri
- recommendation history
- target originari e target adattivi

## Dati e relazioni

Le entita principali sono:

- `users`
- `watched_tickers`
- `ticker_daily_snapshots`
- `ticker_profiles`
- `signals`
- `signal_versions`
- `signal_history`
- `open_positions`
- `position_events`
- `position_daily_snapshots`
- `position_recommendations`
- `targets`
- `target_revisions`
- `backtest_runs`
- `ui_preferences`

## Tradeoff del free tier

- `Netlify` e ottimo per frontend statici e cache
- `Firestore` e utile per persistenza, ma con quote da monitorare
- `GitHub Actions` e perfetto per un refresh giornaliero, meno per task frequenti
- `SQLite` e ideale per locale e per il job batch, non per accesso concorrente pesante

## Limiti noti

- il frontend deployato non sostituisce un backend realtime
- il frontend deployato resta snapshot-first e le scritture cloud richiedono ancora un layer di auth/serverless dedicato se si vuole multiutente vero
- il job giornaliero dipende da fonti esterne non garantite al 100 percento
