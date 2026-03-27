# Deploy Free Tier

## Stack

- Frontend: **Netlify**
- Scheduler: **GitHub Actions**
- Storage cloud opzionale: **Firebase Firestore**
- Runtime locale/admin: **FastAPI**

## 1. Netlify

- collega il repository a Netlify
- usa `netlify.toml` gia presente
- publish directory: `.` (root repo)
- entrypoint pubblico: [`index.html`](index.html)

Il frontend deployato legge `static/data/app-state.json`, quindi non dipende da un backend sempre acceso.

## 2. GitHub Actions

Workflow: [`daily-refresh.yml`](.github/workflows/daily-refresh.yml)

Fa tre cose:

1. installa dipendenze Python
2. esegue `python -m swing_trading.jobs.daily_refresh`
3. committa il nuovo `static/data/app-state.json`

Schedule attuale:

- `23:30 UTC`, lunedi-venerdi

Questo orario e stato scelto per stare comodamente dopo la chiusura USA in ogni periodo dell'anno.

## 3. Firebase opzionale

Se vuoi il mirror cloud verso Firestore, aggiungi i secret:

- `FIREBASE_PROJECT_ID`
- `FIREBASE_SERVICE_ACCOUNT_JSON`

Il workflow scrive il JSON della service account in un file temporaneo e usa `GOOGLE_APPLICATION_CREDENTIALS` solo dentro il job.

Le regole Firestore incluse sono volutamente chiuse di default, perche il frontend non legge direttamente Firestore nel refactor corrente.

## 4. Variabili locali

Vedi [`.env.example`](.env.example):

- `DATABASE_PATH`
- `STATIC_EXPORT_PATH`
- `FIREBASE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`

## 5. Deploy locale di verifica

```bash
python -m pip install -r requirements.txt
python -m swing_trading.jobs.daily_refresh --no-firestore-sync
python -m uvicorn app:app --reload
```

## Limiti del free tier

- GitHub Actions: minuti mensili limitati per repository privati
- Netlify: bandwidth/build minutes limitati
- Firestore: quote gratuite limitate su document reads/writes/storage
- Nessun calcolo on-demand pubblico: i dati sono aggiornati al timestamp dell'ultimo job riuscito
- `yfinance` non e una fonte enterprise: possono esistere ritardi, buchi o variazioni storiche

## Consiglio operativo

Per questo progetto specifico il free tier regge bene se:

- l'aggiornamento resta giornaliero
- il frontend legge snapshot statici
- l'universo rimane Top 100 USA + watchlist ragionevole

Se in futuro serviranno scansioni user-triggered a bassa latenza o multiutente reale, questa architettura andrebbe evoluta verso un backend dedicato.
